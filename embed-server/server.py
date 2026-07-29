#!/usr/bin/env python3
"""
Local OpenAI-compatible embedding server for Qwen3-Embedding-0.6B.

  POST /v1/embeddings  { "input": "..." | ["..."], "model": "..." }
  GET  /health

Env:
  EMBED_HOST=127.0.0.1
  EMBED_PORT=8090
  EMBED_MODEL=Qwen/Qwen3-Embedding-0.6B
  EMBED_DEVICE=cpu   # or cuda
"""

from __future__ import annotations

import json
import os
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

HOST = os.getenv("EMBED_HOST", "127.0.0.1")
PORT = int(os.getenv("EMBED_PORT", "8090"))
MODEL_ID = os.getenv("EMBED_MODEL", "Qwen/Qwen3-Embedding-0.6B")
DEVICE = os.getenv("EMBED_DEVICE", "cpu")

_model = None
_tokenizer = None


def load_model() -> None:
    global _model, _tokenizer
    if _model is not None:
        return
    print(f"Loading {MODEL_ID} on {DEVICE} …", flush=True)
    import torch
    from transformers import AutoModel, AutoTokenizer

    _tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
    _model = AutoModel.from_pretrained(MODEL_ID, trust_remote_code=True)
    _model.eval()
    _model.to(DEVICE)
    print("Model ready.", flush=True)


def embed_texts(texts: list[str]) -> list[list[float]]:
    import torch
    import torch.nn.functional as F

    load_model()
    assert _model is not None and _tokenizer is not None

    # Qwen3-Embedding: mean pool last hidden state, then L2 normalize.
    batch = _tokenizer(
        texts,
        padding=True,
        truncation=True,
        max_length=8192,
        return_tensors="pt",
    )
    batch = {k: v.to(DEVICE) for k, v in batch.items()}
    with torch.no_grad():
        out = _model(**batch)
        hidden = out.last_hidden_state  # [B, T, H]
        mask = batch["attention_mask"].unsqueeze(-1).expand(hidden.size()).float()
        summed = (hidden * mask).sum(dim=1)
        counts = mask.sum(dim=1).clamp(min=1e-9)
        emb = summed / counts
        emb = F.normalize(emb, p=2, dim=1)
    return emb.cpu().tolist()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[embed] {self.address_string()} {fmt % args}", flush=True)

    def _json(self, code: int, payload: dict) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(raw)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        if self.path.split("?")[0] in ("/health", "/v1/health"):
            self._json(200, {"ok": True, "model": MODEL_ID})
            return
        self._json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?")[0]
        if path != "/v1/embeddings":
            self._json(404, {"error": "not found"})
            return
        try:
            n = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
            raw_input = body.get("input", "")
            if isinstance(raw_input, str):
                texts = [raw_input]
            elif isinstance(raw_input, list):
                texts = [str(x) for x in raw_input]
            else:
                self._json(400, {"error": "input must be string or string[]"})
                return
            if not texts:
                self._json(400, {"error": "input is empty"})
                return

            vectors = embed_texts(texts)
            data = [
                {"object": "embedding", "index": i, "embedding": vec}
                for i, vec in enumerate(vectors)
            ]
            self._json(
                200,
                {
                    "object": "list",
                    "model": body.get("model") or MODEL_ID,
                    "data": data,
                    "usage": {"prompt_tokens": 0, "total_tokens": 0},
                },
            )
        except Exception as e:
            traceback.print_exc()
            self._json(500, {"error": str(e)})


def main() -> None:
    load_model()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Embed server http://{HOST}:{PORT}  model={MODEL_ID}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
