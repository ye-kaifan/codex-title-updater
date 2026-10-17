#!/usr/bin/env python3
"""Install/disable/remove only this hook; preserve all unrelated configuration."""
import argparse
import contextlib
import datetime as dt
import json
import math
import os
from pathlib import Path
import shutil
import sys
import subprocess

from title_updater import ROOT, DEFAULTS, atomic_json, codex_home
from platform_support import configure_stdio, file_lock, hook_command


def mutate_hooks(home, install_root, python, remove=False, timeout=240):
    path = home / "hooks.json"
    before = path.read_bytes() if path.exists() else None
    obj = json.loads(before) if before is not None else {}
    hooks = obj.setdefault("hooks", {})
    command = hook_command(python, install_root / "title_updater.py")
    manifest = install_root / "registration.json"
    previous = json.loads(manifest.read_text(encoding="utf-8")).get("command") if manifest.exists() else None
    registration = {"command": command, "codex_home": str(home)}
    own_commands = {command}
    if previous:
        own_commands.add(previous)
    groups = hooks.get("Stop", [])
    kept = []
    for group in groups:
        handlers = [h for h in group.get("hooks", [])
                    if not (h.get("type") == "command" and h.get("command") in own_commands)]
        if handlers:
            kept.append(group | {"hooks": handlers})
        elif not group.get("hooks"):
            kept.append(group)
    if not remove:
        kept.append({"hooks": [{"type": "command", "command": command,
                                "async": False, "timeout": timeout,
                                "env": {"CODEX_HOME": str(home)},
                                "statusMessage": "检查会话标题"}]})
    if kept:
        hooks["Stop"] = kept
    else:
        hooks.pop("Stop", None)
    if before is not None and json.loads(before) == obj:
        if not remove:
            atomic_json(manifest, registration)
        return False
    if before is None and remove:
        return False
    if before is not None:
        backup = install_root / "backups" / ("hooks-" + dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ".json")
        backup.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        backup.write_bytes(before)
        backup.chmod(0o600)
    if (path.read_bytes() if path.exists() else None) != before:
        raise RuntimeError("hooks.json 在操作期间被其他进程修改，已取消写入；请重试")
    atomic_json(path, obj)
    if not remove:
        atomic_json(manifest, registration)
    return True


def main():
    configure_stdio()
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=["install", "enable", "disable", "uninstall", "status", "doctor"])
    p.add_argument("--codex-home", type=Path)
    p.add_argument("--install-dir", type=Path)
    args = p.parse_args()
    manifest = ROOT / "registration.json"
    installed = json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else {}
    # Installed entry points remember their home/custom install directory, even
    # when the calling shell no longer has CODEX_HOME set.
    home = (args.codex_home or codex_home()).expanduser().resolve()
    default_target = (ROOT if installed.get("codex_home") == str(home) and args.codex_home is None
                      else home / "hooks/codex-title-updater")
    target = (args.install_dir or default_target).expanduser().resolve()
    with contextlib.ExitStack() as stack:
        if args.command == "install":
            target.mkdir(parents=True, exist_ok=True, mode=0o700)
        if args.command in ("install", "enable", "disable", "uninstall") and target.exists():
            try:
                stack.enter_context(file_lock(target / ".manage.lock"))
            except BlockingIOError:
                p.error("另一个安装或管理操作正在运行，请稍后重试")
        execute(args.command, home, target, p)


def execute(command, home, target, parser):
    cfgpath = target / "settings.json"
    if command == "install":
        for name in ("title_updater.py", "platform_support.py", "manage.py", "README.md", "LICENSE",
                     "run_manage.sh", "run_manage.ps1"):
            src, dst = ROOT / name, target / name
            if src.resolve() != dst.resolve():
                shutil.copy2(src, dst)
        cfg = DEFAULTS | (json.loads(cfgpath.read_text(encoding="utf-8")) if cfgpath.exists() else {})
        atomic_json(cfgpath, cfg)
        # Four metadata/name operations, each with initialize + RPC, plus review
        # and cleanup. Leave enough time for our own deadlines to clean children
        # before Codex's outer hook timeout can terminate the Python process.
        timeout = max(180, math.ceil(cfg["review_timeout"] + 8 * cfg["rpc_timeout"] + 30))
        changed = mutate_hooks(home, target, Path(sys.executable), timeout=timeout)
        print(json.dumps({"installed": str(target), "hooks_changed": changed,
                          "requires_hook_trust_review": True}, ensure_ascii=False, indent=2))
    elif command in ("enable", "disable"):
        if not cfgpath.exists():
            parser.error("请先 install")
        cfg = json.loads(cfgpath.read_text(encoding="utf-8"))
        cfg["enabled"] = command == "enable"
        atomic_json(cfgpath, cfg)
        print("已启用检查开关；仍需 Codex 信任该 Hook" if cfg["enabled"] else "已停用；下一次 Hook 调用起立即跳过")
    elif command == "uninstall":
        changed = mutate_hooks(home, target, Path(sys.executable), remove=True)
        if cfgpath.exists():
            cfg = json.loads(cfgpath.read_text(encoding="utf-8"))
            atomic_json(cfgpath, cfg | {"enabled": False})
        print(json.dumps({"removed_hook_registration": changed, "state_and_backups_preserved": True}))
    elif command == "doctor":
        if not (target / "title_updater.py").is_file():
            parser.error("请先 install")
        env = os.environ | {"CODEX_HOME": str(home)}
        result = subprocess.run([sys.executable, "-X", "utf8", str(target / "title_updater.py"), "doctor"], env=env)
        if result.returncode:
            raise SystemExit(result.returncode)
    else:
        manifest = target / "registration.json"
        registered = json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else {}
        hooks_file = home / "hooks.json"
        hooks = json.loads(hooks_file.read_text(encoding="utf-8")) if hooks_file.exists() else {}
        matches = [h for g in hooks.get("hooks", {}).get("Stop", []) for h in g.get("hooks", [])
                   if h.get("type") == "command" and h.get("command") == registered.get("command")]
        print(json.dumps({"install_dir": str(target), "hooks_file": str(home / "hooks.json"),
                          "settings": json.loads(cfgpath.read_text(encoding="utf-8")) if cfgpath.exists() else None,
                          "registered_hooks": len(matches), "codex_home": str(home),
                          "state_dir": str(Path(os.environ.get("CODEX_TITLE_UPDATER_HOME") or target / "data").expanduser().resolve())},
                         ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
