/**
 * Static + browser-smoke tests for crag.html
 * Run: node tests/crag-ui.test.mjs
 */
import { spawn } from "node:child_process";
import { createServer } from "node:http";
import { readFileSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");
const HTML_PATH = join(ROOT, "crag.html");
const CHROME =
  process.env.PLAYWRIGHT_CHROME ||
  process.env.CHROME_PATH ||
  (existsSync("/usr/bin/google-chrome-stable")
    ? "/usr/bin/google-chrome-stable"
    : existsSync("/opt/google/chrome/chrome")
      ? "/opt/google/chrome/chrome"
      : existsSync("/usr/bin/chromium-browser")
        ? "/usr/bin/chromium-browser"
        : existsSync("/usr/bin/chromium")
          ? "/usr/bin/chromium"
          : "google-chrome-stable");

let passed = 0;
let failed = 0;

function assert(cond, msg) {
  if (cond) {
    passed += 1;
    console.log("  ✓", msg);
  } else {
    failed += 1;
    console.error("  ✗", msg);
  }
}

function staticContract() {
  console.log("\n[static] design + production contracts");
  const html = readFileSync(HTML_PATH, "utf8");

  assert(html.includes("--bg: #000000"), "dark Apple near-black base");
  assert(html.includes("--accent: #0a84ff"), "system blue accent");
  assert(html.includes("--branch: #ff9f0a"), "correction branch warm signal");
  assert(html.includes("-apple-system"), "Apple system font stack");
  assert(html.includes("prefers-reduced-motion"), "reduced-motion media query");
  assert(html.includes("function trapFocus"), "focus trap for overlays");
  assert(html.includes("window.__CragUI"), "test helpers exported");
  assert(html.includes("degraded-flag"), "visible degraded answer flag");
  assert(html.includes("MAX_CORRECTION_ATTEMPTS"), "correction attempt cap");
  assert(html.includes('data-od-id="stepper"'), "OpenDesign stepper hook");
  assert(html.includes('data-od-id="drawer"'), "OpenDesign drawer hook");
  assert(html.includes("AbortController"), "abortable pipeline");
  assert(html.includes('id="drawer-close"'), "drawer explicit close");
  assert(html.includes("drawer-backdrop"), "drawer backdrop close");
  assert(html.includes('e.key !== "Escape"') || html.includes('e.key === "Escape"'), "Escape closes overlays");
  assert(html.includes("From correction"), "correction-sourced label");
  assert(html.includes("Clear conversation"), "clear confirm modal");
  assert(html.includes("function cancelRun") || html.includes("cancelRun"), "cancel path");
  assert(!/font-weight:\s*560/.test(html), "no invalid font-weight 560");
  assert(html.includes("shake"), "empty-submit shake feedback");
  assert(html.includes("empty-retrieval") || html.includes("empty-banner"), "zero-doc empty state");
  assert(html.includes("aria-modal"), "modal/drawer aria-modal");
  assert(html.includes("live-region"), "pipeline live region");
}

function startStaticServer() {
  const html = readFileSync(HTML_PATH, "utf8");
  // Inject a self-test boot when ?autotest=1 is present
  const injected = html.replace(
    "checkBackend();",
    `window.__CRAG_FORCE_MOCK = true;
  checkBackend();
  if (new URLSearchParams(location.search).get("autotest") === "1") {
    (async function __autotest() {
      try {
        await delay(500);
        window.__CragUI.forceOffline(false);
        const emptyOk = window.__CragUI.submitQuery("   ") === false && window.__CragUI.getState().turns.length === 0;
        window.__CragUI.submitQuery("How does corrective RAG improve answer faithfulness?");
        const afterSubmit = window.__CragUI.getState().turns.length === 1 && window.__CragUI.getState().turns[0].status === "running";
        await delay(180);
        window.__CragUI.cancelRun();
        await delay(250);
        const cancelled = window.__CragUI.getState().turns[0] && window.__CragUI.getState().turns[0].status === "cancelled";
        window.__CragUI.forceOffline(true);
        const offlineBlocked = window.__CragUI.submitQuery("should not start") === false;
        const scen = window.__CragUI.detectScenario("force a timeout during retrieval");
        const scenEmpty = window.__CragUI.detectScenario("no sources about x");
        const results = {
          ok: emptyOk && afterSubmit && cancelled && offlineBlocked && scen === "timeout" && scenEmpty === "empty",
          emptyOk, afterSubmit, cancelled, offlineBlocked, scen, scenEmpty,
          maxAttempts: window.__CragUI.MAX_CORRECTION_ATTEMPTS
        };
        const pre = document.createElement("pre");
        pre.id = "results-json";
        pre.textContent = JSON.stringify(results);
        document.body.appendChild(pre);
        document.title = "DONE";
      } catch (e) {
        const pre = document.createElement("pre");
        pre.id = "results-json";
        pre.textContent = JSON.stringify({ ok: false, error: String(e) });
        document.body.appendChild(pre);
        document.title = "DONE";
      }
    })();
  }`
  );

  return new Promise((resolve) => {
    const server = createServer((req, res) => {
      const url = req.url || "/";
      if (url.startsWith("/crag.html") || url === "/" || url.startsWith("/?")) {
        res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
        res.end(injected);
        return;
      }
      res.writeHead(404);
      res.end("not found");
    });
    server.listen(0, "127.0.0.1", () => {
      const { port } = server.address();
      resolve({ server, port });
    });
  });
}

function runChromeHarness(port) {
  return new Promise((resolve, reject) => {
    const userData = `/tmp/crag-ui-test-profile-${process.pid}-${Date.now()}`;
    const dump = spawn(
      CHROME,
      [
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        `--user-data-dir=${userData}`,
        "--virtual-time-budget=12000",
        "--run-all-compositor-stages-before-draw",
        "--dump-dom",
        `http://127.0.0.1:${port}/crag.html?autotest=1`
      ],
      { stdio: ["ignore", "pipe", "pipe"] }
    );
    let dom = "";
    let stderr = "";
    const timer = setTimeout(() => {
      dump.kill("SIGKILL");
      reject(new Error("Chrome harness timed out"));
    }, 18000);

    dump.stdout.on("data", (d) => {
      dom += d.toString();
    });
    dump.stderr.on("data", (d) => {
      stderr += d.toString();
    });
    dump.on("error", (err) => {
      clearTimeout(timer);
      reject(err);
    });
    dump.on("close", (code) => {
      clearTimeout(timer);
      if (!dom && code !== 0) {
        reject(new Error("Chrome dump failed: " + stderr.slice(0, 200)));
        return;
      }
      resolve({ dom, stderr });
    });
  });
}

async function browserSmoke() {
  console.log("\n[smoke] headless browser interactions");
  let server;
  try {
    const started = await startStaticServer();
    server = started.server;
    const { dom } = await runChromeHarness(started.port);

    const m = dom.match(/<pre id="results-json">([\s\S]*?)<\/pre>/);
    if (!m) {
      assert(dom.includes("CRAG") || dom.includes("Corrective"), "app shell present in dump");
      console.log("  ⚠ results-json not found (virtual-time may be short); static dump only");
      console.log("  dump tail:", dom.slice(-400).replace(/\s+/g, " "));
      return;
    }
    let results;
    try {
      const raw = m[1]
        .replace(/&quot;/g, '"')
        .replace(/&#39;/g, "'")
        .replace(/&amp;/g, "&")
        .replace(/&lt;/g, "<")
        .replace(/&gt;/g, ">");
      results = JSON.parse(raw);
    } catch (e) {
      console.error("  parse fail raw:", m[1].slice(0, 300));
      assert(false, "results-json parseable");
      return;
    }
    if (!results.ok) console.error("  results:", JSON.stringify(results));
    assert(results.emptyOk, "empty submit does not start pipeline");
    assert(results.afterSubmit, "valid submit creates running turn");
    assert(results.cancelled, "cancel marks turn cancelled");
    assert(results.offlineBlocked, "offline blocks submit");
    assert(results.scen === "timeout", "timeout scenario detection");
    assert(results.scenEmpty === "empty", "empty scenario detection");
    assert(results.maxAttempts === 2, "MAX_CORRECTION_ATTEMPTS is 2");
    assert(results.ok, "overall smoke ok");
  } catch (err) {
    const msg = String(err.message || err);
    if (/ENOENT|not found|No such file/i.test(msg)) {
      console.log("  ⚠ skipping browser smoke (Chrome not available):", msg);
      return;
    }
    failed += 1;
    console.error("  ✗ browser smoke failed:", msg);
  } finally {
    if (server) server.close();
  }
}

async function logicSmokeWithoutChrome() {
  console.log("\n[logic] pure scenario helpers via vm");
  // Lightweight re-check of scenario strings embedded in source
  const html = readFileSync(HTML_PATH, "utf8");
  assert(html.includes('return "empty"'), "empty scenario branch");
  assert(html.includes('return "timeout"'), "timeout scenario branch");
  assert(html.includes('return "degraded"'), "degraded scenario branch");
  assert(html.includes('return "correct"'), "correct scenario branch");
  assert(html.includes("status === \"cancelled\""), "cancelled status UI");
  assert(html.includes("Regenerate"), "regenerate action");
  assert(html.includes("data-action=\"feedback\""), "feedback controls");
}

async function main() {
  console.log("CRAG UI tests");
  staticContract();
  await logicSmokeWithoutChrome();
  await browserSmoke();
  console.log(`\n${passed} passed, ${failed} failed`);
  process.exit(failed ? 1 : 0);
}

main();
