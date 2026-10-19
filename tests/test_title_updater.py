import contextlib
import importlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import title_updater as ar
from manage import mutate_hooks


YES = {"rename": True, "topic_changed": True, "old_title_inaccurate": True,
       "confidence": .98, "title": "ToyDB 集群作业排错", "reason": "主要工作已转为集群排错"}
LONG_TITLE = "请把虚构拼图工具中已经修改的按钮和最初发布的版本之间的所有差别都整理出来，包括具体改了哪些文字以及操作步骤…"
REPAIR = {"confidence": .98, "title": "虚构拼图工具版本差异整理", "reason": "压缩超长提问，保留具体对象和任务"}


class FakeBackend:
    def __init__(self, title="TileGame 论文修改"):
        self.value = title
        self.writes = []
        self.fail = False

    def title(self, tid):
        return self.value

    def rename(self, tid, title):
        self.writes.append((tid, title))
        if self.fail:
            raise RuntimeError("offline")
        self.value = title


class HookTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.env = patch.dict(os.environ, {"CODEX_TITLE_UPDATER_HOME": str(self.root / "data")})
        self.env.start()
        self.cfg = dict(ar.DEFAULTS)
        self.backend = FakeBackend()
        self.reviews = []

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def payload(self, n, sid="thread-a", triggers=None, incomplete=None):
        p = self.root / (sid + ".jsonl")
        rows = [{"type": "session_meta", "payload": {"id": sid, "thread_source": "user", "source": "vscode"}}]
        for i in range(1, n + 1):
            tid = f"t{i}"
            trigger = triggers.get(i, "composer") if triggers else "composer"
            rows.append({"type": "event_msg", "payload": {"type": "task_started", "turn_id": tid,
                        "turn_attribution": {"turn_trigger": trigger}}})
            # AGENTS/Page messages have role=user, but must never count as rounds/content.
            for k in ("agents_md.instructions", "additional_content.codex_apps_open_page", "user.text"):
                rows.append({"type": "response_item", "payload": {"type": "message", "role": "user",
                            "internal_chat_message_metadata_passthrough": {"turn_id": tid, "content_item_kinds": [k]},
                            "content": [{"type": "input_text", "text": f"{k}:问题{i}"}]}})
            rows.append({"type": "response_item", "payload": {"type": "function_call", "name": "exec"}})
            if i < n and i not in (incomplete or []):
                rows.append({"type": "event_msg", "payload": {"type": "task_complete", "turn_id": tid,
                            "last_agent_message": "回答"}})
        p.write_text("".join(json.dumps(x) + "\n" for x in rows), encoding="utf-8")
        return {"hook_event_name": "Stop", "session_id": sid, "turn_id": f"t{n}",
                "transcript_path": str(p), "last_assistant_message": "本轮已完成", "stop_hook_active": False}

    def run_hook(self, n, proposal=None, **kw):
        payload = self.payload(n, **kw)
        def review(old, context, config):
            self.reviews.append((n, context))
            return dict(YES if proposal is None else proposal)
        ar.process(payload, self.cfg, self.backend, review)

    def state(self, sid="thread-a"):
        with ar.locked_state(sid) as s:
            return dict(s)

    def events(self):
        p = self.root / "data/audit.jsonl"
        return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines()] if p.exists() else []

    def test_schedule_exactly_1_2_6_8_10(self):
        self.assertEqual([i for i in range(1, 15) if ar.scheduled(i)], [1, 2, 6, 8, 10, 12, 14])

    def test_first_turn_corrects_inaccurate_title_without_requiring_topic_change(self):
        def review(old, context, config):
            self.assertTrue(config["initial_naming"])
            self.assertEqual(len(context), 1)
            return YES | {"topic_changed": False}
        ar.process(self.payload(1), self.cfg, self.backend, review)
        self.assertEqual(len(self.backend.writes), 1)
        self.assertEqual(self.state()["last_rename_round"], 1)
        self.assertNotIn("initial_naming", self.cfg)

    def test_first_turn_does_not_replace_accurate_native_title(self):
        self.run_hook(1, YES | {"topic_changed": False, "old_title_inaccurate": False})
        self.assertEqual(self.backend.writes, [])
        self.assertNotIn("last_rename_round", self.state())

    def test_first_turn_keep_leaves_second_turn_check_without_cooldown(self):
        keep = YES | {"topic_changed": False, "old_title_inaccurate": False}
        self.run_hook(1, keep)
        self.run_hook(2, keep)
        self.assertEqual([x[0] for x in self.reviews], [1, 2])
        self.assertEqual(self.backend.writes, [])
        self.assertNotIn("cooldown", [e["event"] for e in self.events()])

    def test_first_turn_success_cools_down_second_turn(self):
        self.run_hook(1)
        self.run_hook(2)
        self.assertEqual(len(self.backend.writes), 1)
        self.assertEqual([x[0] for x in self.reviews], [1])
        self.assertIn("cooldown", [e["event"] for e in self.events()])
        self.run_hook(6, YES | {"title": "TileEngine 编译排错"})
        self.assertEqual([x[0] for x in self.reviews], [1, 6])

    def test_first_turn_unchanged_title_leaves_second_turn_eligible(self):
        self.run_hook(1, YES | {"title": self.backend.value})
        self.assertNotIn("last_rename_round", self.state())
        self.run_hook(2)
        self.assertEqual(self.state()["last_rename_round"], 2)

    def test_no_cosmetic_change_or_fourth_turn_check(self):
        keep = YES | {"topic_changed": False, "old_title_inaccurate": False}
        for n in range(1, 9):
            self.run_hook(n, keep | {"rename": False} if n == 1 else keep)
        self.assertEqual([x[0] for x in self.reviews], [1, 2, 6, 8])
        self.assertEqual(self.backend.writes, [])

    def test_successful_rename_four_round_cooldown(self):
        for n in range(1, 13):
            self.run_hook(n, YES | {"title": f"ToyDB 第{n}阶段集群排错"})
        self.assertEqual([x[0] for x in self.reviews], [1, 6, 10])
        self.assertEqual(len(self.backend.writes), 3)

    def test_first_turn_failure_does_not_block_second_turn(self):
        self.backend.fail = True
        payload = self.payload(1)
        with self.assertRaises(RuntimeError):
            ar.process(payload, self.cfg, self.backend, lambda *x: YES)
        self.assertNotIn("last_rename_round", self.state())
        ar.process(payload, self.cfg, self.backend, lambda *x: self.fail("duplicate initial naming"))
        self.backend.fail = False
        self.run_hook(2)
        self.assertEqual(self.state()["last_rename_round"], 2)

    def test_first_turn_duplicate_after_reload_does_not_repeat(self):
        payload = self.payload(1)
        ar.process(payload, self.cfg, self.backend, lambda *x: YES)
        importlib.reload(ar)
        ar.process(payload, self.cfg, self.backend, lambda *x: self.fail("duplicate initial naming"))
        self.assertEqual(len(self.backend.writes), 1)

    def test_first_turn_protected_title_stays_locked(self):
        self.cfg["adopt_existing"] = False
        ar.process(self.payload(1), self.cfg, self.backend, lambda *x: self.fail("protected title"))
        self.assertTrue(self.state()["locked"])
        self.assertEqual(self.backend.writes, [])

    def test_first_turn_uses_human_count_not_raw_turn_number(self):
        def review(old, context, config):
            self.assertTrue(config["initial_naming"])
            return YES | {"topic_changed": False}
        ar.process(self.payload(2, triggers={1: "automation"}), self.cfg, self.backend, review)
        self.assertEqual(self.state()["last_rename_round"], 1)

    def test_initial_policy_cannot_leak_into_older_chat(self):
        def review(old, context, config):
            self.assertFalse(config["initial_naming"])
            return YES | {"topic_changed": False, "old_title_inaccurate": False}
        ar.process(self.payload(6), self.cfg | {"initial_naming": True}, self.backend, review)
        self.assertEqual(self.backend.writes, [])

    def test_initial_prompt_does_not_require_changed_topic(self):
        initial = ar.review_prompt("原标题", [{"user": "测试需求"}], initial_naming=True)
        regular = ar.review_prompt("原标题", [{"user": "测试需求"}])
        self.assertIn("不要求话题变化", initial)
        self.assertIn("原标题准确时必须保持", initial)
        self.assertIn("old_title_inaccurate=true", initial)
        self.assertNotIn("只有主要话题/具体对象", initial)
        self.assertIn("只有主要话题/具体对象", regular)

    def test_second_turn_corrects_link_title_without_topic_change(self):
        self.backend.value = "codex://threads/example-thread 请接着处理一…"
        self.run_hook(1, YES | {"rename": False})
        def review(old, context, config):
            self.assertFalse(config["initial_naming"])
            self.assertTrue(config["initial_correction"])
            return YES | {"topic_changed": False, "title": "TileGame 按钮修复说明"}
        payload = self.payload(2)
        ar.process(payload, self.cfg, self.backend, review)
        ar.process(payload, self.cfg, self.backend, lambda *x: self.fail("duplicate correction"))
        self.assertEqual(self.backend.writes, [("thread-a", "TileGame 按钮修复说明")])
        self.assertEqual(self.state()["last_rename_round"], 2)

    def test_initial_correction_does_not_reword_accurate_title(self):
        self.run_hook(2, YES | {"topic_changed": False, "old_title_inaccurate": False})
        self.assertEqual(self.backend.writes, [])
        self.assertNotIn("last_rename_round", self.state())

    def test_initial_correction_remains_available_after_missed_check(self):
        self.run_hook(2, YES | {"rename": False})
        self.run_hook(6, YES | {"topic_changed": False})
        self.assertEqual(self.state()["last_rename_round"], 6)

    def test_after_initial_correction_same_topic_changes_stay_blocked(self):
        self.run_hook(2, YES | {"topic_changed": False})
        self.run_hook(6, YES | {"topic_changed": False, "title": "ToyDB 连接故障排查"})
        self.assertEqual(len(self.backend.writes), 1)
        self.assertEqual(self.state()["last_rename_round"], 2)

    def test_initial_correction_respects_cooldown(self):
        self.run_hook(6, YES | {"topic_changed": False})
        self.run_hook(8, YES | {"title": "TileEngine 编译排错"})
        self.assertEqual([r[0] for r in self.reviews], [6])
        self.assertIn("cooldown", [e["event"] for e in self.events()])

    def test_initial_correction_cannot_leak_from_settings(self):
        self.run_hook(1)
        def review(old, context, config):
            self.assertFalse(config["initial_correction"])
            return YES | {"topic_changed": False, "title": "ToyDB 连接故障排查"}
        ar.process(self.payload(6), self.cfg | {"initial_correction": True}, self.backend, review)
        self.assertEqual(len(self.backend.writes), 1)

    def test_initial_correction_prompt_requires_inaccurate_title(self):
        prompt = ar.review_prompt("codex://threads/example", [], initial_correction=True)
        self.assertIn("不要求话题变化", prompt)
        self.assertIn("原标题准确时保持", prompt)
        self.assertIn("链接本身不是改名理由", prompt)

    def test_unchanged_check_does_not_restart_cooldown(self):
        self.run_hook(2)
        self.run_hook(6, YES | {"rename": False})
        self.run_hook(8, YES | {"title": "TileEngine 编译排错"})
        self.assertEqual(self.state()["last_rename_round"], 8)

    def test_duplicates_and_reload_do_not_repeat(self):
        p = self.payload(2)
        ar.process(p, self.cfg, self.backend, lambda *x: YES)
        importlib.reload(ar)
        ar.process(p, self.cfg, self.backend, lambda *x: self.fail("duplicate review"))
        self.assertEqual(len(self.backend.writes), 1)

    def test_only_composer_rounds_not_auto_goal_or_tool(self):
        self.run_hook(6, triggers={2: "goal_continuation", 3: "hook", 4: "automation", 5: "agent"})
        self.assertEqual(self.state()["completed_human_turns"], 2)
        self.assertEqual(len(self.reviews), 1)
        context = self.reviews[0][1]
        self.assertEqual(len(context), 2)
        self.assertNotIn("agents_md", json.dumps(context))
        self.assertNotIn("codex_apps_open_page", json.dumps(context))

    def test_unknown_trigger_fails_closed(self):
        p = self.payload(2, triggers={2: None})
        ar.process(p, self.cfg, self.backend, lambda *x: self.fail())
        self.assertEqual(self.backend.writes, [])

    def test_incomplete_old_turn_not_counted(self):
        self.run_hook(3, incomplete=[1])
        self.assertEqual(self.state()["completed_human_turns"], 2)

    def test_automatic_stop_and_nested_hook_ignored(self):
        p = self.payload(2)
        p["stop_hook_active"] = True
        ar.process(p, self.cfg, self.backend, lambda *x: self.fail())
        p["stop_hook_active"] = False
        with patch.dict(os.environ, {"CODEX_TITLE_UPDATER_REVIEW": "1"}):
            ar.process(p, self.cfg, self.backend, lambda *x: self.fail())
        self.assertEqual(self.backend.writes, [])

    def test_each_thread_independent(self):
        self.run_hook(2)
        other = FakeBackend()
        ar.process(self.payload(2, sid="thread-b"), self.cfg, other, lambda *x: YES)
        self.assertEqual(len(other.writes), 1)
        self.assertEqual(self.state("thread-b")["last_rename_round"], 2)

    def test_external_rename_locks_even_unscheduled_round(self):
        self.run_hook(2)
        self.backend.value = "用户指定的固定标题"
        self.run_hook(3)
        self.run_hook(6)
        self.assertTrue(self.state()["locked"])
        self.assertEqual(len(self.backend.writes), 1)

    def test_manual_change_during_review_locks(self):
        def review(*x):
            self.backend.value = "用户刚修改的标题"
            return YES
        ar.process(self.payload(2), self.cfg, self.backend, review)
        self.assertTrue(self.state()["locked"])
        self.assertEqual(self.backend.writes, [])

    def test_adopt_existing_selected_policy(self):
        self.run_hook(2)
        self.assertFalse(self.state().get("locked", False))
        self.assertEqual(len(self.backend.writes), 1)

    def test_optional_protect_existing_policy(self):
        self.cfg["adopt_existing"] = False
        self.run_hook(2)
        self.assertTrue(self.state()["locked"])
        self.assertEqual(self.backend.writes, [])

    def test_failed_rename_not_success_or_infinite_retry(self):
        self.backend.fail = True
        p = self.payload(2)
        with self.assertRaises(RuntimeError):
            ar.process(p, self.cfg, self.backend, lambda *x: YES)
        self.assertNotIn("last_rename_round", self.state())
        ar.process(p, self.cfg, self.backend, lambda *x: self.fail())
        self.backend.fail = False
        self.run_hook(6)
        self.assertEqual(self.state()["last_rename_round"], 6)

    def test_crash_after_write_recovers_pending_success(self):
        p = self.payload(2)
        with ar.locked_state("thread-a") as s:
            s.update(handled_turns=["t2"], observed_title=self.backend.value,
                     pending_rename={"old": self.backend.value, "new": YES["title"], "round": 2})
            ar.save(s)
        self.backend.value = YES["title"]
        self.run_hook(3)
        self.assertEqual(self.state()["last_rename_round"], 2)
        self.assertNotIn("pending_rename", self.state())

    def test_lock_contention_skips_duplicate_worker(self):
        with ar.locked_state("thread-a"):
            ar.process(self.payload(2), self.cfg, self.backend, lambda *x: self.fail())
        self.assertEqual(self.backend.writes, [])

    def test_disabled_does_no_work(self):
        self.cfg["enabled"] = False
        ar.process({}, self.cfg, self.backend, lambda *x: self.fail())
        self.assertEqual(self.events(), [])

    def test_disable_while_model_reviewing_prevents_write(self):
        def review(*x):
            return YES
        with patch.object(ar, "settings", return_value=self.cfg | {"enabled": False}):
            ar.process(self.payload(2), self.cfg, self.backend, review)
        self.assertEqual(self.backend.writes, [])
        self.assertIn("disabled_during_review", [e["event"] for e in self.events()])

    def test_complete_corrupted_record_fails_closed(self):
        p = self.payload(2)
        with open(p["transcript_path"], "a") as f:
            f.write("broken record\n")
        with self.assertRaises(ValueError):
            ar.process(p, self.cfg, self.backend, lambda *x: YES)
        self.assertEqual(self.backend.writes, [])

    def test_incomplete_tail_is_tolerated(self):
        p = self.payload(2)
        with open(p["transcript_path"], "a") as f:
            f.write('{"payload":')
        ar.process(p, self.cfg, self.backend, lambda *x: YES)
        self.assertEqual(len(self.backend.writes), 1)

    def test_native_plain_composer_message_context(self):
        p = self.payload(2)
        file = Path(p["transcript_path"])
        records = [json.loads(l) for l in file.read_text(encoding="utf-8").splitlines()]
        for r in records:
            v = r.get("payload", {})
            if r["type"] == "response_item" and v.get("role") == "user":
                kind = v["internal_chat_message_metadata_passthrough"]["content_item_kinds"][0]
                v.pop("internal_chat_message_metadata_passthrough")
                if kind == "agents_md.instructions":
                    v["content"][0]["text"] = "# AGENTS.md instructions\ncontext only"
                if kind == "additional_content.codex_apps_open_page":
                    v["content"][0]["text"] = '<external_codex_apps_open_page>{"page_id":null}</external_codex_apps_open_page>'
        file.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
        parsed = ar.transcript(str(file), "thread-a")
        self.assertIn("问题2", parsed["turns"]["t2"]["user"])
        self.assertNotIn("AGENTS", parsed["turns"]["t2"]["user"])

    def test_reject_other_session_and_subagent(self):
        p = self.payload(2)
        p["session_id"] = "other"
        with self.assertRaises(ValueError):
            ar.process(p, self.cfg, self.backend)
        p = self.payload(2)
        file = Path(p["transcript_path"])
        file.write_text(file.read_text(encoding="utf-8").replace('"thread_source": "user"', '"thread_source": "subagent"'), encoding="utf-8")
        with self.assertRaises(ValueError):
            ar.process(p, self.cfg, self.backend)

    def test_strict_proposal_validation(self):
        for override in [{"confidence": .5}, {"old_title_inaccurate": False}, {"rename": "true"},
                         {"title": "English only"}, {"title": "中文\n标题"}, {"title": " "},
                         {"title": "中" * 41}, {"title": self.backend.value}, {"confidence": float("nan")}]:
            self.assertIsNone(ar.valid_proposal(YES | override, self.backend.value, self.cfg), override)

    def test_initial_naming_keeps_title_and_confidence_validation(self):
        cfg = self.cfg | {"initial_naming": True}
        same_topic = YES | {"topic_changed": False}
        self.assertEqual(ar.valid_proposal(same_topic, self.backend.value, cfg), YES["title"])
        for override in [{"old_title_inaccurate": False}, {"confidence": .5}, {"rename": "true"}, {"rename": False},
                         {"title": "English only"}, {"title": "中文\n标题"}, {"title": self.backend.value}]:
            self.assertIsNone(ar.valid_proposal(same_topic | override, self.backend.value, cfg), override)

    def test_initial_correction_keeps_accuracy_and_confidence_validation(self):
        cfg = self.cfg | {"initial_correction": True}
        result = YES | {"topic_changed": False}
        self.assertEqual(ar.valid_proposal(result, self.backend.value, cfg), YES["title"])
        for override in [{"old_title_inaccurate": False}, {"confidence": .5}, {"rename": False},
                         {"title": self.backend.value}, {"title": "English only"}, {"title": "中文\n标题"}]:
            self.assertIsNone(ar.valid_proposal(result | override, self.backend.value, cfg), override)

    def test_dry_run_has_no_persistent_state_or_rename(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            ar.process(self.payload(2), self.cfg, self.backend, lambda *x: self.fail(), dry_run=True)
        self.assertEqual(json.loads(out.getvalue())["completed_human_turns"], 2)
        self.assertNotIn("handled_turns", self.state())

    def test_overlong_accurate_first_title_is_repaired_without_semantic_veto(self):
        self.backend.value = LONG_TITLE
        self.assertGreater(len(LONG_TITLE), self.cfg["max_title_chars"])
        # Reproduce the old failure: "accurate, same topic, keep" cannot veto a
        # safe replacement after the program establishes the length violation.
        proposal = REPAIR | {"rename": False, "topic_changed": False, "old_title_inaccurate": False}
        self.run_hook(1, proposal)
        self.assertEqual(self.backend.value, REPAIR["title"])
        self.assertTrue(self.events()[-1]["length_repair"])
        self.assertNotIn("keep", [e["event"] for e in self.events()])

    def test_repair_schema_only_requests_replacement_and_uses_configured_limit(self):
        cfg = self.cfg | {"max_title_chars": 18}
        schema = ar.review_schema(LONG_TITLE, cfg)
        self.assertEqual(set(schema["required"]), {"confidence", "title", "reason"})
        self.assertEqual(schema["properties"]["title"]["maxLength"], 18)
        for flags in ({}, {"initial_naming": True}, {"initial_correction": True}):
            prompt = ar.review_prompt(LONG_TITLE, [], max_title_chars=18, **flags)
            self.assertIn("超过 18 字符的硬上限", prompt)
            self.assertNotIn("rename=false", prompt)
            self.assertNotIn("原标题准确时必须保持", prompt)
        self.assertIs(ar.review_schema("正常标题", cfg), ar.SCHEMA)

    def test_length_boundary_and_custom_limit(self):
        for limit in (18, 40, 60):
            with self.subTest(limit=limit):
                cfg = self.cfg | {"max_title_chars": limit}
                exact = "长" * limit
                self.assertIsNone(ar.valid_proposal(REPAIR, exact, cfg))
                self.assertEqual(ar.valid_proposal(REPAIR, exact + "字", cfg), REPAIR["title"])
                self.assertIsNone(ar.valid_proposal(REPAIR | {"title": "新" * (limit + 1)}, exact + "字", cfg))

    def test_overlong_unicode_and_english_use_character_count(self):
        for old in ("长" * 41, "A" * 41, "🙂" * 41, "中 A" * 14):
            with self.subTest(old=old):
                self.assertEqual(ar.valid_proposal(REPAIR, old, self.cfg), REPAIR["title"])

    def test_length_repair_runs_on_unscheduled_round(self):
        self.backend.value = LONG_TITLE
        self.run_hook(3, REPAIR)
        self.assertEqual(self.backend.value, REPAIR["title"])
        self.assertEqual(self.state()["last_rename_round"], 3)

    def test_lowered_limit_repairs_previous_auto_title_during_cooldown(self):
        self.run_hook(1, YES | {"title": "长" * 35})
        self.cfg["max_title_chars"] = 20
        self.run_hook(2, REPAIR)
        self.assertEqual(len(self.backend.writes), 2)
        self.assertEqual(self.backend.value, REPAIR["title"])
        self.assertEqual(self.state()["last_rename_round"], 2)
        self.run_hook(6, YES | {"topic_changed": False})
        self.assertEqual(len(self.backend.writes), 2)

    def test_failed_repair_never_logs_keep_and_next_human_turn_retries(self):
        self.backend.value = LONG_TITLE
        self.run_hook(2, {"rename": False, "title": LONG_TITLE, "confidence": .99, "reason": "含义准确"})
        self.assertEqual(self.events()[-1]["event"], "repair_deferred")
        self.assertEqual(self.events()[-1]["cause"], "invalid_title_length_or_whitespace")
        self.assertNotIn("last_rename_round", self.state())
        ar.process(self.payload(2), self.cfg, self.backend, lambda *x: self.fail("duplicate repair"))
        self.run_hook(3, REPAIR)
        self.assertEqual(self.backend.value, REPAIR["title"])
        self.assertEqual(len(self.backend.writes), 1)

    def test_repair_model_failure_defers_without_truncation_or_same_turn_retry(self):
        self.backend.value = LONG_TITLE
        def review(*args):
            raise TimeoutError("synthetic timeout")
        payload = self.payload(2)
        ar.process(payload, self.cfg, self.backend, review)
        self.assertEqual(self.backend.value, LONG_TITLE)
        self.assertEqual(self.events()[-1]["event"], "repair_deferred")
        self.assertEqual(self.events()[-1]["cause"], "review_error")
        ar.process(payload, self.cfg, self.backend, lambda *x: self.fail("duplicate review"))
        self.run_hook(3, REPAIR)
        self.assertEqual(self.backend.value, REPAIR["title"])

    def test_repair_rejects_unsafe_or_uncertain_replacements(self):
        for result in (None, [], {}, REPAIR | {"confidence": .5}, REPAIR | {"confidence": True},
                       REPAIR | {"confidence": float("nan")}, REPAIR | {"confidence": float("inf")},
                       REPAIR | {"title": "中" * 41}, REPAIR | {"title": "中"},
                       REPAIR | {"title": "English only"}, REPAIR | {"title": " 中文标题"},
                       REPAIR | {"title": "中文\n标题"}, REPAIR | {"title": "中文`标题"},
                       REPAIR | {"title": LONG_TITLE}):
            with self.subTest(result=result):
                self.assertIsNone(ar.valid_proposal(result, LONG_TITLE, self.cfg))

    def test_invalid_repair_result_has_explicit_audit(self):
        self.backend.value = LONG_TITLE
        ar.process(self.payload(1), self.cfg, self.backend, lambda *args: [])
        self.assertEqual(self.events()[-1]["event"], "repair_deferred")
        self.assertEqual(self.events()[-1]["cause"], "invalid_result")
        self.assertEqual(self.backend.writes, [])

    def test_overlong_locked_and_unadopted_titles_are_protected(self):
        self.backend.value = LONG_TITLE
        with ar.locked_state("thread-a") as s:
            s.update(locked=True, lock_reason="user_request")
            ar.save(s)
        ar.process(self.payload(1), self.cfg, self.backend, lambda *args: self.fail("locked"))
        ar.process(self.payload(1, sid="thread-b"), self.cfg | {"adopt_existing": False},
                   self.backend, lambda *args: self.fail("not adopted"))
        self.assertEqual(self.backend.writes, [])

    def test_external_overlong_title_is_not_mistaken_for_repair(self):
        self.run_hook(1)
        self.backend.value = LONG_TITLE
        ar.process(self.payload(3), self.cfg, self.backend, lambda *args: self.fail("manual edit"))
        self.assertTrue(self.state()["locked"])
        self.assertEqual(len(self.backend.writes), 1)

    def test_manual_change_while_repairing_prevents_write(self):
        self.backend.value = LONG_TITLE
        def review(*args):
            self.backend.value = "用户刚修改的标题"
            return REPAIR
        ar.process(self.payload(1), self.cfg, self.backend, review)
        self.assertTrue(self.state()["locked"])
        self.assertEqual(self.backend.writes, [])

    def test_disable_during_repair_prevents_write(self):
        self.backend.value = LONG_TITLE
        with patch.object(ar, "settings", return_value=self.cfg | {"enabled": False}):
            ar.process(self.payload(1), self.cfg, self.backend, lambda *args: REPAIR)
        self.assertEqual(self.backend.writes, [])
        self.assertEqual(self.events()[-1]["event"], "disabled_during_review")

    def completed_payload(self, n=1):
        payload = self.payload(n)
        with open(payload["transcript_path"], "a", encoding="utf-8") as f:
            f.write(json.dumps({"type": "event_msg", "payload": {"type": "task_complete", "turn_id": f"t{n}",
                                                                 "last_agent_message": "回答"}}) + "\n")
        return payload

    def test_explicit_repair_migrates_old_keep_without_rewriting_turn_count(self):
        payload = self.completed_payload()
        self.backend.value = LONG_TITLE
        with ar.locked_state("thread-a") as s:
            s.update(handled_turns=["t1"], completed_human_turns=1, observed_title=LONG_TITLE)
            ar.save(s)
        meta = {"status": {"type": "notLoaded"}, "path": payload["transcript_path"]}
        with patch.object(self.backend, "metadata", return_value=meta, create=True):
            ar.repair_title("thread-a", self.cfg, self.backend, lambda *args: REPAIR)
            ar.repair_title("thread-a", self.cfg, self.backend, lambda *args: self.fail("already repaired"))
        self.assertEqual(self.backend.value, REPAIR["title"])
        self.assertEqual(self.state()["handled_turns"], ["t1"])
        self.assertEqual(self.state()["completed_human_turns"], 1)
        self.assertEqual(self.state()["last_rename_round"], 1)
        self.assertEqual(len(self.backend.writes), 1)
        self.assertTrue(next(e for e in self.events() if e["event"] == "check")["explicit_repair"])

    def test_explicit_repair_preserves_manual_lock(self):
        payload = self.completed_payload()
        self.backend.value = LONG_TITLE
        with ar.locked_state("thread-a") as s:
            s.update(handled_turns=["t1"], observed_title=LONG_TITLE, locked=True, lock_reason="user_request")
            ar.save(s)
        ar.process(payload, self.cfg, self.backend, lambda *args: self.fail("locked"), repair=True)
        self.assertEqual(self.backend.writes, [])
        self.assertTrue(self.state()["locked"])

    def test_explicit_repair_refuses_active_or_incomplete_thread(self):
        payload = self.payload(1)
        for status in ("active", "notLoaded", "unknown"):
            meta = {"status": {"type": status}, "path": payload["transcript_path"]}
            with patch.object(self.backend, "metadata", return_value=meta, create=True):
                with self.assertRaises(ValueError):
                    ar.repair_title("thread-a", self.cfg, self.backend, lambda *args: self.fail("incomplete"))
        self.assertEqual(self.backend.writes, [])

    def test_explicit_repair_dry_run_does_not_change_state_or_title(self):
        payload = self.completed_payload()
        self.backend.value = LONG_TITLE
        meta = {"status": {"type": "idle"}, "path": payload["transcript_path"]}
        with patch.object(self.backend, "metadata", return_value=meta, create=True), contextlib.redirect_stdout(io.StringIO()):
            ar.repair_title("thread-a", self.cfg, self.backend, lambda *args: self.fail("dry run"), dry_run=True)
        self.assertEqual(self.backend.writes, [])
        self.assertNotIn("handled_turns", self.state())


class InstallTests(unittest.TestCase):
    def test_merge_idempotent_uninstall_preserves_everything_else(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            original = {"description": "keep", "hooks": {
                "UserPromptSubmit": [{"hooks": [{"type": "command", "command": "other-user-hook"}]}],
                "Stop": [{"matcher": "*", "hooks": [{"type": "command", "command": "other-stop"},
                           {"type": "mcp_tool", "server": "example", "tool": "noop"},
                           {"type": "prompt", "prompt": "preserve this"}]}]}}
            (root / "hooks.json").write_text(json.dumps(original), encoding="utf-8")
            (root / "config.toml").write_text('notify=["unchanged"]\n', encoding="utf-8")
            target = root / "hooks/codex-title-updater"
            target.mkdir(parents=True)
            python = Path("/example/python3")
            self.assertTrue(mutate_hooks(root, target, python))
            self.assertFalse(mutate_hooks(root, target, python))
            self.assertEqual(len(json.loads((root / "hooks.json").read_text(encoding="utf-8"))["hooks"]["Stop"]), 2)
            self.assertTrue(mutate_hooks(root, target, python, remove=True))
            self.assertEqual(json.loads((root / "hooks.json").read_text(encoding="utf-8")), original)
            self.assertEqual((root / "config.toml").read_text(encoding="utf-8"), 'notify=["unchanged"]\n')
            self.assertEqual(len(list((target / "backups").glob("*.json"))), 2)

    def test_reinstall_with_different_python_does_not_duplicate(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td);target = root / "install";target.mkdir()
            mutate_hooks(root, target, Path("/example/python1"))
            mutate_hooks(root, target, Path("/example/python2"))
            self.assertEqual(len(json.loads((root / "hooks.json").read_text(encoding="utf-8"))["hooks"]["Stop"]), 1)
            mutate_hooks(root, target, Path("/example/python3"), remove=True)
            self.assertNotIn("Stop", json.loads((root / "hooks.json").read_text(encoding="utf-8"))["hooks"])


if __name__ == "__main__":
    unittest.main()
