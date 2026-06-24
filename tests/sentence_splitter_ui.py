"""Serve a browser UI for watching stream2sentence split pasted text."""

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib
import json
from pathlib import Path
import socket
import sys
import time
import traceback


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>stream2sentence Live Splitter</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #080b09;
      --panel: #111713;
      --panel-raised: #171f1a;
      --panel-soft: #0d120f;
      --ink: #f6f8f3;
      --muted: #8a948d;
      --dim: #465048;
      --line: rgba(227, 235, 220, 0.12);
      --gold: #f0bc5e;
      --green: #64d48b;
      --coral: #ff806b;
      --focus: rgba(100, 212, 139, 0.32);
      --shadow: 0 18px 70px rgba(0, 0, 0, 0.42);
    }

    * {
      box-sizing: border-box;
    }

    html,
    body {
      min-height: 100%;
    }

    body {
      margin: 0;
      background:
        linear-gradient(135deg, rgba(240, 188, 94, 0.08), transparent 34%),
        linear-gradient(315deg, rgba(100, 212, 139, 0.07), transparent 38%),
        var(--bg);
      color: var(--ink);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      letter-spacing: 0;
    }

    button,
    select,
    textarea {
      font: inherit;
      letter-spacing: 0;
    }

    .shell {
      min-height: 100vh;
      display: grid;
      grid-template-rows: auto 1fr;
    }

    .topbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 18px 22px;
      border-bottom: 1px solid var(--line);
      background: rgba(8, 11, 9, 0.78);
      backdrop-filter: blur(18px);
      position: sticky;
      top: 0;
      z-index: 10;
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
      min-width: 0;
    }

    .brand-mark {
      width: 36px;
      height: 36px;
      border-radius: 8px;
      display: grid;
      place-items: center;
      color: #10140f;
      font-weight: 900;
      background:
        linear-gradient(135deg, var(--green), var(--gold));
      box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.22) inset;
      flex: 0 0 auto;
    }

    .brand-title {
      display: grid;
      gap: 2px;
      min-width: 0;
    }

    .brand-title strong {
      font-size: 15px;
      line-height: 1.1;
      white-space: nowrap;
    }

    .brand-title span {
      color: var(--muted);
      font-size: 12px;
      line-height: 1.2;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .controls {
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }

    .field {
      display: grid;
      gap: 5px;
    }

    .field label {
      color: var(--muted);
      font-size: 11px;
      line-height: 1;
    }

    select {
      height: 38px;
      padding: 0 34px 0 12px;
      border: 1px solid var(--line);
      border-radius: 8px;
      color: var(--ink);
      background: var(--panel-raised);
      outline: none;
    }

    .check-field {
      height: 38px;
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 0 12px;
      border: 1px solid var(--line);
      border-radius: 8px;
      color: var(--ink);
      background: var(--panel-raised);
      font-size: 12px;
      cursor: pointer;
      user-select: none;
    }

    .check-field input {
      width: 16px;
      height: 16px;
      margin: 0;
      accent-color: var(--green);
    }

    .check-field:focus-within {
      border-color: rgba(100, 212, 139, 0.65);
      box-shadow: 0 0 0 4px var(--focus);
    }

    select:focus,
    textarea:focus {
      border-color: rgba(100, 212, 139, 0.65);
      box-shadow: 0 0 0 4px var(--focus);
    }

    .primary {
      min-width: 104px;
      height: 42px;
      border: 0;
      border-radius: 8px;
      color: #0d110d;
      cursor: pointer;
      font-weight: 800;
      background: linear-gradient(135deg, var(--green), var(--gold));
      box-shadow: 0 10px 30px rgba(100, 212, 139, 0.18);
    }

    .primary:hover {
      filter: brightness(1.06);
    }

    .primary.stop {
      background: linear-gradient(135deg, var(--coral), var(--gold));
      box-shadow: 0 10px 30px rgba(255, 128, 107, 0.16);
    }

    .status {
      min-width: 112px;
      color: var(--muted);
      font-size: 12px;
      text-align: right;
    }

    .workspace {
      display: grid;
      grid-template-columns: minmax(0, 1.18fr) minmax(320px, 0.82fr);
      gap: 18px;
      padding: 18px;
      min-height: 0;
    }

    .pane {
      min-height: 0;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: linear-gradient(180deg, rgba(255, 255, 255, 0.035), rgba(255, 255, 255, 0.015)), var(--panel);
      box-shadow: var(--shadow);
      overflow: hidden;
      display: grid;
      grid-template-rows: auto 1fr;
    }

    .pane-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 14px;
      padding: 14px 16px;
      border-bottom: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.025);
    }

    .pane-head h1,
    .pane-head h2 {
      margin: 0;
      font-size: 14px;
      line-height: 1.2;
    }

    .meter {
      min-width: 138px;
      height: 8px;
      border-radius: 999px;
      overflow: hidden;
      background: rgba(255, 255, 255, 0.08);
    }

    .meter span {
      display: block;
      width: 0%;
      height: 100%;
      background: linear-gradient(90deg, var(--green), var(--gold));
      transition: width 90ms linear;
    }

    .editor-wrap {
      position: relative;
      min-height: 0;
      background:
        linear-gradient(rgba(255, 255, 255, 0.035) 1px, transparent 1px),
        var(--panel-soft);
      background-size: 100% 34px;
    }

    textarea,
    .stream-view {
      width: 100%;
      height: 100%;
      min-height: 520px;
      padding: 20px;
      border: 0;
      outline: 0;
      resize: none;
      overflow: auto;
      background: transparent;
      color: var(--ink);
      font-family: "Cascadia Mono", "SFMono-Regular", Consolas, "Liberation Mono", monospace;
      font-size: 15px;
      line-height: 1.62;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
    }

    textarea::placeholder {
      color: #566159;
    }

    .stream-view {
      display: none;
    }

    .processed {
      color: var(--ink);
    }

    .pending {
      color: var(--dim);
    }

    .caret {
      display: inline-block;
      width: 2px;
      height: 1.16em;
      margin: 0 1px -0.19em;
      background: var(--gold);
      animation: blink 0.86s steps(2, start) infinite;
    }

    @keyframes blink {
      50% {
        opacity: 0.2;
      }
    }

    .sentence-list {
      min-height: 0;
      overflow-y: auto;
      padding: 14px;
      display: grid;
      align-content: start;
      gap: 10px;
      background:
        linear-gradient(90deg, rgba(100, 212, 139, 0.05), transparent 32%),
        var(--panel-soft);
    }

    .empty {
      height: 100%;
      display: grid;
      place-items: center;
      color: var(--dim);
      text-align: center;
      padding: 24px;
      font-size: 14px;
    }

    .sentence {
      display: grid;
      grid-template-columns: 34px minmax(0, 1fr);
      gap: 10px;
      padding: 13px;
      border: 1px solid rgba(255, 255, 255, 0.095);
      border-radius: 8px;
      background: rgba(255, 255, 255, 0.045);
      animation: land 170ms ease-out;
    }

    @keyframes land {
      from {
        transform: translateY(5px);
        opacity: 0;
      }
      to {
        transform: translateY(0);
        opacity: 1;
      }
    }

    .number {
      width: 34px;
      height: 26px;
      border-radius: 7px;
      display: grid;
      place-items: center;
      color: #10140f;
      background: var(--gold);
      font-size: 12px;
      font-weight: 900;
    }

    .sentence p {
      margin: 0;
      color: var(--ink);
      font-size: 14px;
      line-height: 1.48;
      overflow-wrap: anywhere;
    }

    .stats {
      color: var(--muted);
      font-size: 12px;
    }

    @media (max-width: 920px) {
      .workspace {
        grid-template-columns: 1fr;
      }

      .topbar {
        align-items: flex-start;
      }

      .controls {
        justify-content: flex-start;
      }
    }

    @media (max-width: 620px) {
      .topbar {
        display: grid;
      }

      .controls {
        width: 100%;
      }

      .status {
        text-align: left;
        width: 100%;
      }

      textarea,
      .stream-view {
        min-height: 390px;
      }
    }
  </style>
</head>
<body>
  <main class="shell">
    <header class="topbar">
      <div class="brand">
        <div class="brand-mark">S2</div>
        <div class="brand-title">
          <strong>stream2sentence live lab</strong>
          <span>Consensus tokenizer, character-by-character</span>
        </div>
      </div>
      <div class="controls">
        <div class="field">
          <label for="delay">Delay</label>
          <select id="delay">
            <option value="0">0 ms</option>
            <option value="10">10 ms</option>
            <option value="20">20 ms</option>
            <option value="50" selected>50 ms</option>
            <option value="100">100 ms</option>
            <option value="200">200 ms</option>
          </select>
        </div>
        <label class="check-field" for="autoContext">
          <input id="autoContext" type="checkbox">
          <span>Auto context</span>
        </label>
        <label class="check-field" for="neverSplitNumbers">
          <input id="neverSplitNumbers" type="checkbox">
          <span>Never split numbers</span>
        </label>
        <button id="startStop" class="primary" type="button">Start</button>
        <div id="status" class="status">Idle</div>
      </div>
    </header>

    <section class="workspace">
      <section class="pane">
        <div class="pane-head">
          <h1>Input stream</h1>
          <div class="meter" aria-hidden="true"><span id="meter"></span></div>
        </div>
        <div class="editor-wrap">
          <textarea id="input" spellcheck="false" placeholder="Paste text here."></textarea>
          <div id="streamView" class="stream-view" aria-live="polite">
            <span id="processed" class="processed"></span><span id="cursor" class="caret"></span><span id="pending" class="pending"></span>
          </div>
        </div>
      </section>

      <section class="pane">
        <div class="pane-head">
          <h2>Extracted sentences</h2>
          <div id="stats" class="stats">0 sentences</div>
        </div>
        <div id="sentences" class="sentence-list">
          <div id="empty" class="empty">Sentences appear here as soon as the splitter yields them.</div>
        </div>
      </section>
    </section>
  </main>

  <script>
    const input = document.querySelector("#input");
    const streamView = document.querySelector("#streamView");
    const processed = document.querySelector("#processed");
    const pending = document.querySelector("#pending");
    const cursor = document.querySelector("#cursor");
    const sentences = document.querySelector("#sentences");
    const empty = document.querySelector("#empty");
    const startStop = document.querySelector("#startStop");
    const delay = document.querySelector("#delay");
    const autoContext = document.querySelector("#autoContext");
    const neverSplitNumbers = document.querySelector("#neverSplitNumbers");
    const statusText = document.querySelector("#status");
    const stats = document.querySelector("#stats");
    const meter = document.querySelector("#meter");

    let controller = null;
    let running = false;
    let activeText = "";
    let count = 0;

    function setRunning(next) {
      running = next;
      startStop.textContent = next ? "Stop" : "Start";
      startStop.classList.toggle("stop", next);
      delay.disabled = next;
      autoContext.disabled = next;
      neverSplitNumbers.disabled = next;
    }

    function showInputMode() {
      input.style.display = "block";
      streamView.style.display = "none";
    }

    function showStreamMode(text) {
      activeText = text;
      input.style.display = "none";
      streamView.style.display = "block";
      updateProgress(0);
      streamView.scrollTop = 0;
    }

    function updateProgress(index) {
      const safeIndex = Math.max(0, Math.min(index, activeText.length));
      processed.textContent = activeText.slice(0, safeIndex);
      pending.textContent = activeText.slice(safeIndex);
      meter.style.width = activeText.length ? `${(safeIndex / activeText.length) * 100}%` : "0%";
      streamView.scrollTop = streamView.scrollHeight;
    }

    function resetSentences() {
      count = 0;
      sentences.innerHTML = "";
      sentences.appendChild(empty);
      empty.style.display = "grid";
      stats.textContent = "0 sentences";
    }

    function addSentence(text) {
      count += 1;
      empty.style.display = "none";
      const item = document.createElement("article");
      item.className = "sentence";

      const number = document.createElement("div");
      number.className = "number";
      number.textContent = count;

      const body = document.createElement("p");
      body.textContent = text;

      item.append(number, body);
      sentences.appendChild(item);
      stats.textContent = `${count} ${count === 1 ? "sentence" : "sentences"}`;
      sentences.scrollTop = sentences.scrollHeight;
    }

    async function start() {
      const text = input.value;
      if (!text.trim()) {
        statusText.textContent = "Paste text";
        input.focus();
        return;
      }

      controller = new AbortController();
      resetSentences();
      showStreamMode(text);
      setRunning(true);
      statusText.textContent = "Streaming";

      try {
        const response = await fetch("/api/stream", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({
            text,
            delay_ms: Number(delay.value),
            auto_context: autoContext.checked,
            never_split_numbers: neverSplitNumbers.checked
          }),
          signal: controller.signal
        });

        if (!response.ok || !response.body) {
          throw new Error(`HTTP ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { value, done } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            if (!line) continue;
            const event = JSON.parse(line);
            if (event.type === "progress") {
              updateProgress(event.index);
            } else if (event.type === "sentence") {
              addSentence(event.sentence);
            } else if (event.type === "done") {
              updateProgress(text.length);
              statusText.textContent = "Complete";
            } else if (event.type === "error") {
              throw new Error(event.message);
            }
          }
        }

        statusText.textContent = "Complete";
      } catch (error) {
        if (error.name === "AbortError") {
          statusText.textContent = "Stopped";
        } else {
          statusText.textContent = "Error";
          console.error(error);
        }
      } finally {
        setRunning(false);
        controller = null;
      }
    }

    function stop() {
      if (controller) {
        controller.abort();
      }
    }

    startStop.addEventListener("click", () => {
      if (running) {
        stop();
      } else {
        start();
      }
    });

    input.addEventListener("input", () => {
      if (!running) {
        statusText.textContent = input.value ? "Ready" : "Idle";
      }
    });

    showInputMode();
  </script>
</body>
</html>
"""


class SentenceSplitterUiHandler(BaseHTTPRequestHandler):
    sentence_splitter_cls = None

    def log_message(self, fmt, *args):
        return

    def do_GET(self):
        if self.path not in {"/", "/index.html"}:
            self.send_error(404)
            return

        body = HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("content-type", "text/html; charset=utf-8")
        self.send_header("content-length", str(len(body)))
        self.send_header("cache-control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != "/api/stream":
            self.send_error(404)
            return

        try:
            length = int(self.headers.get("content-length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            text = str(payload.get("text", ""))
            delay_ms = int(payload.get("delay_ms", 50))
            auto_context = payload.get("auto_context") is True
            never_split_numbers = payload.get("never_split_numbers") is True
        except Exception:
            self.send_error(400, "Invalid JSON payload")
            return

        delay_seconds = max(delay_ms, 0) / 1000
        self.send_response(200)
        self.send_header("content-type", "application/x-ndjson; charset=utf-8")
        self.send_header("cache-control", "no-store")
        self.send_header("x-accel-buffering", "no")
        self.end_headers()

        try:
            splitter = self.sentence_splitter_cls(
                tokenizer="nltk+rule-based",
                language="en",
                minimum_sentence_length=1,
                context_size=12,
                context_size_look_overhead=64,
                auto_context=auto_context,
                never_split_numbers=never_split_numbers,
            )

            for index, char in enumerate(text, start=1):
                if delay_seconds:
                    time.sleep(delay_seconds)

                splitter.add(char)
                self.write_event({"type": "progress", "index": index})
                for sentence in splitter.stream():
                    self.write_event({"type": "sentence", "sentence": sentence})

            for sentence in splitter.flush():
                self.write_event({"type": "sentence", "sentence": sentence})

            self.write_event({"type": "done"})
        except (BrokenPipeError, ConnectionResetError):
            return
        except Exception as exc:
            self.write_event({"type": "error", "message": str(exc)})

    def write_event(self, event):
        line = json.dumps(event, ensure_ascii=False) + "\n"
        self.wfile.write(line.encode("utf-8"))
        self.wfile.flush()


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--log-file")
    return parser


def load_sentence_splitter():
    import nltk

    nltk.download = lambda *args, **kwargs: True
    from stream2sentence import SentenceSplitter

    stream2sentence_module = importlib.import_module("stream2sentence.stream2sentence")
    stream2sentence_module.nltk_initialized = True
    stream2sentence_module.initialize_nltk = lambda *args, **kwargs: None
    return SentenceSplitter


def reserve_port(host, preferred_port):
    for port in range(preferred_port, preferred_port + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((host, port))
            except OSError:
                continue
            return port

    raise RuntimeError(f"No free port found from {preferred_port} to {preferred_port + 49}")


def main():
    args = build_parser().parse_args()
    SentenceSplitterUiHandler.sentence_splitter_cls = load_sentence_splitter()
    port = reserve_port(args.host, args.port)
    server = ThreadingHTTPServer((args.host, port), SentenceSplitterUiHandler)
    url = f"http://{args.host}:{port}/"
    if args.log_file:
        Path(args.log_file).write_text(f"stream2sentence UI: {url}\n", encoding="utf-8")
    if sys.stdout is not None:
        try:
            print(f"stream2sentence UI: {url}", flush=True)
        except Exception:
            pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        log_file = None
        for index, arg in enumerate(sys.argv):
            if arg == "--log-file" and index + 1 < len(sys.argv):
                log_file = sys.argv[index + 1]
                break
            if arg.startswith("--log-file="):
                log_file = arg.split("=", 1)[1]
                break

        if log_file:
            Path(log_file).write_text(traceback.format_exc(), encoding="utf-8")
        raise
