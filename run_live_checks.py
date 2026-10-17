#!/usr/bin/env python3
"""Live integration checks using ONLY the committed, invented synthetic cases.

Never reads a user's conversation or submits project files as model input.
Isolated test threads and hooks live in a fresh CODEX_HOME under the chosen work directory.
"""
import argparse
import json
import os
from pathlib import Path
import tempfile

import title_updater as ar


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--work-dir", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    ap.add_argument("--api-only", action="store_true")
    args = ap.parse_args()
    args.work_dir.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    report = json.loads(args.report.read_text(encoding="utf-8")) if args.api_only and args.report.exists() else {
        "input_provenance": "Only tests/synthetic_cases.json; invented test data", "checks": []}
    # Live judgments inherit the already configured provider. Only hardcoded synthetic
    # texts enter the prompt; no real session is opened by this test.
    os.environ["CODEX_TITLE_UPDATER_HOME"] = str(args.work_dir.resolve() / "review-data")
    ar.data_home().mkdir(parents=True, exist_ok=True)
    config = ar.settings()
    cases = json.loads((ar.ROOT / "tests/synthetic_cases.json").read_text(encoding="utf-8"))
    for case in ([] if args.api_only else cases):
        review_config = config | {"initial_naming": case.get("initial_naming", False),
                                  "initial_correction": case.get("initial_correction", False)}
        result = ar.judge(case["old_title"], case["context"], review_config)
        accepted = ar.valid_proposal(result, case["old_title"], review_config) is not None
        entry = {"case": case["case"], "result": result, "accepted": accepted,
                 "pass": accepted == case["expect_rename"]}
        report["checks"].append(entry)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(entry, ensure_ascii=False), flush=True)
    # thread/start + name/set/name/read use an empty, isolated Codex home. No user
    # conversation is renamed and no model turn is started for this API check.
    with tempfile.TemporaryDirectory(prefix="native-api-", dir=args.work_dir) as td:
        os.environ["CODEX_HOME"] = td
        with ar.Backend(config).server() as rpc:
            thread = rpc.call("thread/start", {"cwd": td, "ephemeral": False,
                                               "approvalPolicy": "never", "sandbox": "read-only"})["thread"]
            tid = thread["id"]
            rpc.call("thread/name/set", {"threadId": tid, "name": "虚构测试初始标题"})
            first = rpc.call("thread/read", {"threadId": tid})["thread"].get("name")
            rpc.call("thread/name/set", {"threadId": tid, "name": "虚构测试改名结果"})
            second = rpc.call("thread/read", {"threadId": tid})["thread"].get("name")
            entry = {"case": "native_name_api", "first": first, "second": second,
                     "pass": first == "虚构测试初始标题" and second == "虚构测试改名结果"}
            report["checks"].append(entry)
            print(json.dumps(entry, ensure_ascii=False), flush=True)
    report["pass"] = all(c["pass"] for c in report["checks"])
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not report["pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
