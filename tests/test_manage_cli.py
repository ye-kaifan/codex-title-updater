"""Exercise the public install commands without touching the user's Codex home."""
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
import venv

import title_updater as updater


class ManageCliTests(unittest.TestCase):
    def test_install_reinstall_controls_and_uninstall_in_isolated_home(self):
        with tempfile.TemporaryDirectory(prefix="title updater test ") as td:
            home = Path(td).resolve() / "codex 中文 home & %PATH% ! ' $`"
            home.mkdir()
            venv_root = Path(td).resolve() / "Python 中文 & %PATH% ! '"
            venv.EnvBuilder(with_pip=False).create(venv_root)
            python = venv_root / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            target = home / "hooks/codex-title-updater"
            original = {"description": "unrelated", "hooks": {
                "Stop": [{"hooks": [{"type": "command", "command": "other-hook"}]}]}}
            (home / "hooks.json").write_text(json.dumps(original), encoding="utf-8")
            config = b'notify=["keep-this"]\n[features]\nhooks=true\n'
            (home / "config.toml").write_bytes(config)
            env = os.environ | {"CODEX_HOME": str(home),
                                "CODEX_TITLE_UPDATER_PYTHON": str(python),
                                "CODEX_TITLE_UPDATER_HOME": str(target / "data"),
                                "CODEX_TITLE_UPDATER_REVIEW": "0"}

            def run(command):
                return subprocess.run(
                    [str(python), str(updater.ROOT / "manage.py"), command],
                    env=env, check=True, capture_output=True, text=True, encoding="utf-8").stdout

            first = json.loads(run("install"))
            self.assertEqual(first["installed"], str(target.resolve()))
            self.assertTrue(first["requires_hook_trust_review"])
            self.assertTrue((target / "LICENSE").is_file())
            self.assertFalse((target / "data").exists())
            self.assertEqual((home / "config.toml").read_bytes(), config)
            settings_path = target / "settings.json"
            settings = json.loads(settings_path.read_text(encoding="utf-8")) | {"model": "chosen-model"}
            settings_path.write_text(json.dumps(settings), encoding="utf-8")
            state_path = target / "data/threads/preserved.json"
            state_path.parent.mkdir(parents=True)
            state_path.write_text('{"locked": true}\n', encoding="utf-8")
            run("disable")
            self.assertFalse(json.loads(settings_path.read_text(encoding="utf-8"))["enabled"])
            self.assertFalse(json.loads(run("install"))["hooks_changed"])
            self.assertFalse(json.loads(settings_path.read_text(encoding="utf-8"))["enabled"])
            self.assertEqual(json.loads(settings_path.read_text(encoding="utf-8"))["model"], "chosen-model")
            self.assertTrue(json.loads(state_path.read_text(encoding="utf-8"))["locked"])
            run("enable")
            self.assertTrue(json.loads(settings_path.read_text(encoding="utf-8"))["enabled"])

            groups = json.loads((home / "hooks.json").read_text(encoding="utf-8"))["hooks"]["Stop"]
            self.assertEqual(len(groups), 2)
            handler = groups[-1]["hooks"][0]
            command = handler["command"]
            if os.name == "nt":
                argv = [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/s", "/c", command]
            else:
                self.assertEqual(shlex.split(command), [str(python), "-X", "utf8",
                                                       str(target / "title_updater.py"), "hook"])
                argv = ["/bin/sh", "-c", command]
            # The installed command must work independently of the checkout/cwd.
            payload = {"hook_event_name": "Stop", "session_id": "synthetic", "turn_id": "t1",
                       "transcript_path": str(home / "不存在的中文会话.jsonl")}
            call = subprocess.run(argv, input=json.dumps(payload, ensure_ascii=False), text=True,
                                  encoding="utf-8", env=env | handler["env"],
                                  cwd=home, capture_output=True, check=True)
            self.assertEqual(call.stdout.strip(), "{}")
            self.assertEqual(call.stderr, "")
            event = json.loads((target / "data/audit.jsonl").read_text(encoding="utf-8"))
            self.assertIn("不存在的中文会话.jsonl", event["error"])
            wrapper = (["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                        str(target / "run_manage.ps1")] if os.name == "nt" else
                       ["bash", str(target / "run_manage.sh")])
            status = subprocess.run(wrapper + ["status"], env=env,
                cwd=home, capture_output=True, text=True, encoding="utf-8", check=True)
            self.assertEqual(json.loads(status.stdout)["install_dir"], str(target))
            result = json.loads(run("uninstall"))
            self.assertTrue(result["removed_hook_registration"])
            self.assertEqual(json.loads((home / "hooks.json").read_text(encoding="utf-8")), original)
            self.assertEqual((home / "config.toml").read_bytes(), config)
            self.assertTrue(json.loads(state_path.read_text(encoding="utf-8"))["locked"])
            self.assertFalse(json.loads(settings_path.read_text(encoding="utf-8"))["enabled"])
            self.assertFalse(json.loads(run("uninstall"))["removed_hook_registration"])

    def test_uninstall_before_install_does_not_create_hook_configuration(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            subprocess.run([sys.executable, str(updater.ROOT / "manage.py"),
                            "uninstall", "--codex-home", str(home)],
                           check=True, capture_output=True, text=True)
            self.assertEqual(list(home.iterdir()), [])

    def test_explicit_home_custom_install_and_installed_entry_without_environment(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td).resolve() / "中文 Codex home"
            target = Path(td).resolve() / "custom 安装 & '"
            env = dict(os.environ)
            env.pop("CODEX_HOME", None)
            env.pop("CODEX_TITLE_UPDATER_HOME", None)
            env["CODEX_TITLE_UPDATER_PYTHON"] = sys.executable
            wrapper = (["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                        str(updater.ROOT / "run_manage.ps1")] if os.name == "nt" else
                       ["bash", str(updater.ROOT / "run_manage.sh")])
            subprocess.run(wrapper + ["install", "--codex-home", str(home), "--install-dir", str(target)],
                           check=True, env=env, capture_output=True)
            handler = json.loads((home / "hooks.json").read_text(encoding="utf-8"))["hooks"]["Stop"][0]["hooks"][0]
            self.assertEqual(handler["env"]["CODEX_HOME"], str(home))
            status = subprocess.run([sys.executable, str(target / "manage.py"), "status"],
                                    env=env, capture_output=True, check=True, text=True, encoding="utf-8")
            self.assertEqual(json.loads(status.stdout)["install_dir"], str(target))
            self.assertEqual(json.loads(status.stdout)["codex_home"], str(home))
            subprocess.run([sys.executable, str(target / "manage.py"), "uninstall"],
                           env=env, capture_output=True, check=True)
            self.assertNotIn("Stop", json.loads((home / "hooks.json").read_text(encoding="utf-8"))["hooks"])


if __name__ == "__main__":
    unittest.main()
