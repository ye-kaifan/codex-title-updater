"""Exercise the public install commands without touching the user's Codex home."""
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest

import title_updater as updater


class ManageCliTests(unittest.TestCase):
    def test_install_reinstall_controls_and_uninstall_in_isolated_home(self):
        with tempfile.TemporaryDirectory(prefix="title updater test ") as td:
            home = Path(td).resolve() / "codex home"
            home.mkdir()
            target = home / "hooks/codex-title-updater"
            original = {"description": "unrelated", "hooks": {
                "Stop": [{"hooks": [{"type": "command", "command": "other-hook"}]}]}}
            (home / "hooks.json").write_text(json.dumps(original))
            config = b'notify=["keep-this"]\n[features]\nhooks=true\n'
            (home / "config.toml").write_bytes(config)
            env = os.environ | {"CODEX_HOME": str(home),
                                "CODEX_TITLE_UPDATER_PYTHON": sys.executable,
                                "CODEX_TITLE_UPDATER_HOME": str(target / "data"),
                                "CODEX_TITLE_UPDATER_REVIEW": "0"}

            def run(command):
                return subprocess.run(
                    [sys.executable, str(updater.ROOT / "manage.py"), command],
                    env=env, check=True, capture_output=True, text=True).stdout

            first = json.loads(run("install"))
            self.assertEqual(first["installed"], str(target.resolve()))
            self.assertTrue(first["requires_hook_trust_review"])
            self.assertTrue((target / "LICENSE").is_file())
            self.assertFalse((target / "data").exists())
            self.assertEqual((home / "config.toml").read_bytes(), config)
            settings_path = target / "settings.json"
            settings = json.loads(settings_path.read_text()) | {"model": "chosen-model"}
            settings_path.write_text(json.dumps(settings))
            state_path = target / "data/threads/preserved.json"
            state_path.parent.mkdir(parents=True)
            state_path.write_text('{"locked": true}\n')
            run("disable")
            self.assertFalse(json.loads(settings_path.read_text())["enabled"])
            self.assertFalse(json.loads(run("install"))["hooks_changed"])
            self.assertFalse(json.loads(settings_path.read_text())["enabled"])
            self.assertEqual(json.loads(settings_path.read_text())["model"], "chosen-model")
            self.assertTrue(json.loads(state_path.read_text())["locked"])
            run("enable")
            self.assertTrue(json.loads(settings_path.read_text())["enabled"])

            groups = json.loads((home / "hooks.json").read_text())["hooks"]["Stop"]
            self.assertEqual(len(groups), 2)
            argv = shlex.split(groups[-1]["hooks"][0]["command"])
            self.assertEqual(argv[0], sys.executable)
            self.assertEqual(argv[1:], [str(target / "title_updater.py"), "hook"])
            # The installed command must work independently of the checkout/cwd.
            call = subprocess.run(argv, input="{}", text=True, env=env,
                                  cwd=home, capture_output=True, check=True)
            self.assertEqual(call.stdout.strip(), "{}")
            self.assertEqual(call.stderr, "")
            status = subprocess.run(
                ["bash", str(target / "run_manage.sh"), "status"], env=env,
                cwd=home, capture_output=True, text=True, check=True)
            self.assertEqual(json.loads(status.stdout)["install_dir"], str(target))
            result = json.loads(run("uninstall"))
            self.assertTrue(result["removed_hook_registration"])
            self.assertEqual(json.loads((home / "hooks.json").read_text()), original)
            self.assertEqual((home / "config.toml").read_bytes(), config)
            self.assertTrue(json.loads(state_path.read_text())["locked"])
            self.assertFalse(json.loads(settings_path.read_text())["enabled"])
            self.assertFalse(json.loads(run("uninstall"))["removed_hook_registration"])

    def test_uninstall_before_install_does_not_create_hook_configuration(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            subprocess.run([sys.executable, str(updater.ROOT / "manage.py"),
                            "uninstall", "--codex-home", str(home)],
                           check=True, capture_output=True, text=True)
            self.assertEqual(list(home.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
