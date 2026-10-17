#!/usr/bin/env python3
"""No-login native App Server/install checks in a disposable, synthetic CODEX_HOME.

No model turns, real conversations, credentials or global settings are accessed.
This does NOT verify trusted Stop execution in a signed-in client.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

import title_updater as ar
from platform_support import configure_stdio


def main():
    configure_stdio()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    args.work_dir.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    cli = ar.executable()
    report = {"kind": "native_offline_integration", "model_calls": 0,
              "signed_in_stop_hook_e2e": False, "platform": sys.platform, "checks": []}
    with tempfile.TemporaryDirectory(prefix="native 中文 & %PATH% ! ' ", dir=args.work_dir.resolve()) as td:
        home = Path(td)
        target = home / "hooks/codex-title-updater"
        original = {"hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "echo unrelated"}]}]}}
        ar.atomic_json(home / "hooks.json", original)
        config = b"[features]\nhooks=true\n"
        (home / "config.toml").write_bytes(config)
        env = os.environ | {"CODEX_HOME": str(home), "CODEX_TITLE_UPDATER_CLI": cli,
                            "CODEX_TITLE_UPDATER_HOME": str(target / "data"),
                            "CODEX_TITLE_UPDATER_REVIEW": "0"}

        def manage(command):
            result = subprocess.run([sys.executable, "-X", "utf8", str(ar.ROOT / "manage.py"), command],
                                    env=env, check=True, capture_output=True, text=True,
                                    encoding="utf-8", timeout=60)
            return result.stdout

        with patch.dict(os.environ, env):
            version = subprocess.run([cli, "--version"], env=env, check=True, capture_output=True,
                                     text=True, encoding="utf-8", timeout=15).stdout.strip()
            report["codex_version"] = version
            manage("install")
            assert json.loads(manage("status"))["registered_hooks"] == 1
            assert not json.loads(manage("install"))["hooks_changed"]
            diagnostic = json.loads(manage("doctor"))
            # Direct installed commands must also retain their selected home
            # when launched from an ordinary shell without CODEX_HOME.
            direct = subprocess.run([sys.executable, "-X", "utf8", str(target / "title_updater.py"), "doctor"],
                                    env={k: v for k, v in env.items() if k != "CODEX_HOME"},
                                    check=True, capture_output=True, text=True, encoding="utf-8", timeout=60)
            assert json.loads(direct.stdout)["hooks"] == diagnostic["hooks"]
            registered = json.loads((target / "registration.json").read_text(encoding="utf-8"))["command"]
            items = [item for group in diagnostic["hooks"]["data"] for item in group["hooks"]
                     if item.get("command") == registered]
            assert len(items) == 1 and items[0]["enabled"] and items[0]["eventName"] == "stop"
            assert items[0]["trustStatus"] == "untrusted", items
            assert not any(group["errors"] for group in diagnostic["hooks"]["data"])
            # Preserve the native hooks/list output, including trust/enable status,
            # so CI evidence does not imply that installation granted trust.
            report["hooks"] = diagnostic["hooks"]
            report["checks"].append("install_reinstall_status_doctor")
            # Verify actual native argument parsing (not a fake Python peer):
            # quotes/TOML, Unicode and shell metacharacters remain single values.
            # This model name is a fixture for config/read; no turn is started.
            model = "fixture 中文 model & % ! ' ` $"
            argv = [cli, "app-server", "--stdio", "--disable", "hooks", "-c",
                    "model=" + json.dumps(model, ensure_ascii=False),
                    "-c", 'model_reasoning_effort="low"']
            with ar.Rpc(argv, env=env) as rpc:
                rpc.call("initialize", {"clientInfo": {"name": "offline_argv_probe", "version": "0.1.0"}})
                rpc.send({"method": "initialized"})
                cfg = rpc.call("config/read", {"includeLayers": False})["config"]
                assert cfg["model"] == model and cfg["model_reasoning_effort"] == "low"
            report["checks"].append("native_argv_toml_unicode_metacharacters")
            with ar.Backend(ar.DEFAULTS).server() as rpc:
                thread = rpc.call("thread/start", {"cwd": str(home), "ephemeral": False,
                                                   "approvalPolicy": "never", "sandbox": "read-only"})["thread"]
                tid = thread["id"]
                for title in ("虚构测试初始标题", "虚构测试改名结果"):
                    rpc.call("thread/name/set", {"threadId": tid, "name": title})
                    actual = rpc.call("thread/read", {"threadId": tid})["thread"].get("name")
                    assert actual == title, (actual, title)
                report["checks"].append("synthetic_thread_start_name_set_read")
            manage("disable")
            assert not json.loads(manage("status"))["settings"]["enabled"]
            manage("enable")
            assert json.loads(manage("status"))["settings"]["enabled"]
            manage("uninstall")
            assert json.loads((home / "hooks.json").read_text(encoding="utf-8")) == original
            assert (home / "config.toml").read_bytes() == config
            report["checks"].append("disable_enable_uninstall_preserve_unrelated_configuration")
    report["pass"] = True
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
