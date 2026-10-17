"""Offline process fixture: JSON-RPC fragments, stuck stdin and inherited pipes."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

mode = sys.argv[1]
if mode.startswith("judge"):
    if mode == "judge_silent":
        time.sleep(60)
        raise SystemExit
    if mode == "judge_fail":
        raise SystemExit(7)
    prompt = sys.stdin.buffer.read().decode("utf-8")
    Path(os.environ["TEST_REVIEW_CAPTURE"]).write_text(json.dumps({
        "argv": sys.argv[2:], "prompt": prompt,
        "recursion_guard": os.environ.get("CODEX_TITLE_UPDATER_REVIEW")}, ensure_ascii=False), encoding="utf-8")
    result = Path(sys.argv[sys.argv.index("--output-last-message") + 1])
    result.write_text(json.dumps({"rename": False, "reason": "保持中文标题"}, ensure_ascii=False), encoding="utf-8")
    raise SystemExit
if mode == "silent":
    time.sleep(60)
    raise SystemExit
if mode == "eof":
    raise SystemExit

for line in sys.stdin.buffer:
    item = json.loads(line)
    if "method" not in item:
        continue
    if mode == "tree":
        marker = sys.argv[2]
        subprocess.Popen([sys.executable, "-c",
                          "import time,pathlib;time.sleep(1);pathlib.Path(" + repr(marker) +
                          ").write_text('leaked',encoding='utf-8')"])
    sys.stdout.buffer.write(b'\n\r\n')
    sys.stdout.buffer.write((json.dumps({"method": "notice", "params": "中文通知"}, ensure_ascii=False) + "\n").encode())
    sys.stdout.buffer.write(b'{"id":"approval","method":"tool/call"}\n')
    if mode == "malformed":
        sys.stdout.buffer.write(b'not-json\n')
    else:
        data = (json.dumps({"id": item["id"], "result": item["params"]}, ensure_ascii=False) + "\r\n").encode()
        # Fragment a multibyte UTF-8 character across pipe writes.
        split = data.find("中".encode()) + 1
        sys.stdout.buffer.write(data[:split])
        sys.stdout.buffer.flush()
        time.sleep(.01)
        sys.stdout.buffer.write(data[split:])
    sys.stdout.buffer.flush()
    if mode == "tree":
        break
