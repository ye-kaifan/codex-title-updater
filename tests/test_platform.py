"""Real OS processes and pipes; no login, models, user config or real titles."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import title_updater as ar
from platform_support import communicate, file_lock, spawn, stop_process

PEER = Path(__file__).with_name("rpc_peer.py")


class ProcessTests(unittest.TestCase):
    def rpc(self, mode, *args, timeout=2):
        return ar.Rpc([sys.executable, "-X", "utf8", str(PEER), mode, *args], timeout)

    def test_fragmented_unicode_large_reply_notifications_and_requests(self):
        with self.rpc("echo") as rpc:
            value = {"text": "中文路径 & ' % ! $ `" * 10000}
            self.assertEqual(rpc.call("echo", value), value)
            self.assertEqual(rpc.wait_notification("notice")["params"], "中文通知")
            self.assertEqual(rpc.call("again", {"a": "中文"}), {"a": "中文"})
        self.assertFalse(rpc.reader.is_alive())
        self.assertFalse(rpc.writer.is_alive())
        rpc.close()

    def test_rpc_eof_and_malformed_json_clean_up(self):
        for mode, error in (("eof", (RuntimeError, BrokenPipeError)), ("malformed", json.JSONDecodeError)):
            with self.subTest(mode=mode):
                with self.assertRaises(error):
                    with self.rpc(mode) as rpc:
                        rpc.call("test", {})
                self.assertIsNotNone(rpc.proc.poll())
                self.assertFalse(rpc.reader.is_alive())

    def test_rpc_read_timeout_and_blocked_write_are_bounded(self):
        for value in ({}, {"huge": "中" * 1000000}):
            start = time.monotonic()
            with self.assertRaises(TimeoutError):
                with self.rpc("silent", timeout=.2) as rpc:
                    rpc.call("never", value)
            self.assertLess(time.monotonic() - start, 5)
            self.assertIsNotNone(rpc.proc.poll())
            self.assertFalse(rpc.writer.is_alive())

    def test_notification_timeout_is_bounded(self):
        with self.rpc("silent") as rpc:
            with self.assertRaises(TimeoutError):
                rpc.wait_notification("never", timeout=.1)

    def test_close_cleans_descendant_after_parent_already_exited(self):
        with tempfile.TemporaryDirectory() as td:
            marker = Path(td) / "leaked.txt"
            with self.rpc("tree", str(marker)) as rpc:
                self.assertEqual(rpc.call("test", {}), {})
                rpc.proc.wait(timeout=3)
            self.assertFalse(rpc.reader.is_alive(), "descendant kept the pipe open")
            time.sleep(1.1)
            self.assertFalse(marker.exists(), "grandchild survived cleanup")

    def test_review_timeout_includes_stdin_and_reaps_process(self):
        proc = spawn([sys.executable, str(PEER), "silent"], stdin=subprocess.PIPE,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        start = time.monotonic()
        with self.assertRaises(subprocess.TimeoutExpired):
            communicate(proc, b"x" * 2000000, .2)
        self.assertLess(time.monotonic() - start, 5)
        self.assertIsNotNone(proc.poll())
        stop_process(proc)


class LockTests(unittest.TestCase):
    def test_cross_process_exclusion_and_release_after_crash(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "中文 lock"
            code = ("from pathlib import Path;from platform_support import file_lock;import sys,time;"
                    "lock=file_lock(Path(sys.argv[1]));lock.__enter__();print('ready',flush=True);time.sleep(60)")
            proc = spawn([sys.executable, "-c", code, str(path)], cwd=ar.ROOT,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                self.assertEqual(proc.stdout.readline().strip(), b"ready")
                with self.assertRaises(BlockingIOError):
                    with file_lock(path):
                        self.fail("second process acquired an occupied lock")
            finally:
                stop_process(proc)
                proc.stdout.close()
                proc.stderr.close()
            with file_lock(path):
                pass

    def test_utf8_atomic_state_and_transcript_with_unicode(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "含空格 中文.json"
            ar.atomic_json(path, {"title": "中文标题"})
            self.assertIn("中文标题", path.read_text(encoding="utf-8"))
            self.assertEqual(list(path.parent.glob(".write-*")), [])


class DiscoveryTests(unittest.TestCase):
    def test_explicit_missing_cli_never_falls_back(self):
        with patch.dict(os.environ, {"CODEX_TITLE_UPDATER_CLI": "/no-such-cli"}):
            with self.assertRaises(RuntimeError):
                ar.executable()

    @unittest.skipUnless(os.name == "nt", "native Windows npm layout")
    def test_npm_shim_resolves_native_exe_without_shell(self):
        import platform
        arch = "aarch64" if platform.machine().lower() in ("arm64", "aarch64") else "x86_64"
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            shim = root / "codex.cmd"
            shim.write_text("do not execute this", encoding="utf-8")
            binary = root / ("node_modules/@openai/codex-win32-test/vendor/" + arch + "-pc-windows-msvc/codex/codex.exe")
            binary.parent.mkdir(parents=True)
            binary.touch()
            with patch.dict(os.environ, {"CODEX_TITLE_UPDATER_CLI": str(shim)}):
                self.assertEqual(ar.executable(), str(binary.resolve()))


class ReviewProcessTests(unittest.TestCase):
    def test_judge_argv_unicode_input_and_cleanup_on_success_failure_and_timeout(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "中文 review & % ! '"
            root.mkdir()
            (root / "config.toml").write_text('[mcp_servers.test-server]\ncommand="unused"\n', encoding="utf-8")
            capture = root / "capture.json"
            env = {"CODEX_HOME": str(root), "CODEX_TITLE_UPDATER_HOME": str(root / "data"),
                   "TEST_REVIEW_CAPTURE": str(capture)}
            for mode in ("judge", "judge_fail", "judge_silent"):
                def fake_spawn(argv, **kwargs):
                    return spawn([sys.executable, "-X", "utf8", str(PEER), mode] + argv[1:], **kwargs)
                with patch.dict(os.environ, env), patch.object(ar, "executable", return_value=sys.executable), \
                     patch.object(ar, "spawn", side_effect=fake_spawn):
                    cfg = ar.DEFAULTS | {"model": "model & ' % !", "review_timeout": .3}
                    if mode == "judge":
                        result = ar.judge("原标题", [{"user": "中文输入 $` & % !"}], cfg)
                        self.assertEqual(result["reason"], "保持中文标题")
                        sent = json.loads(capture.read_text(encoding="utf-8"))
                        self.assertIn("中文输入 $` & % !", sent["prompt"])
                        self.assertIn("mcp_servers.test-server.enabled=false", sent["argv"])
                        self.assertIn("model & ' % !", sent["argv"])
                        self.assertIn("hooks", sent["argv"])
                        self.assertEqual(sent["recursion_guard"], "1")
                    else:
                        with self.assertRaises((RuntimeError, subprocess.TimeoutExpired)):
                            ar.judge("原标题", [], cfg)
                    self.assertEqual(list((root / "data").glob("review-*")), [])
