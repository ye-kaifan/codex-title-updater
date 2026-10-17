#!/usr/bin/env python3
"""Install/disable/remove only this hook; preserve all unrelated configuration."""
import argparse
import datetime as dt
import json
from pathlib import Path
import shlex
import shutil
import sys

from title_updater import ROOT, DEFAULTS, atomic_json, codex_home


def mutate_hooks(home, install_root, python, remove=False):
    path = home / "hooks.json"
    before = path.read_bytes() if path.exists() else None
    obj = json.loads(before) if before is not None else {}
    hooks = obj.setdefault("hooks", {})
    command = shlex.join([str(python), str(install_root / "title_updater.py"), "hook"])
    manifest = install_root / "registration.json"
    previous = json.loads(manifest.read_text()).get("command") if manifest.exists() else None
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
                                "async": False, "timeout": 180,
                                "statusMessage": "检查会话标题"}]})
    if kept:
        hooks["Stop"] = kept
    else:
        hooks.pop("Stop", None)
    if before is not None and json.loads(before) == obj:
        if not remove:
            atomic_json(manifest, {"command": command})
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
        atomic_json(manifest, {"command": command})
    return True


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=["install", "enable", "disable", "uninstall", "status"])
    p.add_argument("--codex-home", type=Path, default=codex_home())
    p.add_argument("--install-dir", type=Path)
    args = p.parse_args()
    home = args.codex_home.resolve()
    target = (args.install_dir or home / "hooks/codex-title-updater").resolve()
    cfgpath = target / "settings.json"
    if args.command == "install":
        target.mkdir(parents=True, exist_ok=True, mode=0o700)
        for name in ("title_updater.py", "manage.py", "README.md", "LICENSE", "run_manage.sh"):
            src, dst = ROOT / name, target / name
            if src.resolve() != dst.resolve():
                shutil.copy2(src, dst)
        cfg = DEFAULTS | (json.loads(cfgpath.read_text()) if cfgpath.exists() else {})
        atomic_json(cfgpath, cfg)
        changed = mutate_hooks(home, target, Path(sys.executable))
        print(json.dumps({"installed": str(target), "hooks_changed": changed,
                          "requires_hook_trust_review": True}, ensure_ascii=False, indent=2))
    elif args.command in ("enable", "disable"):
        if not cfgpath.exists():
            p.error("请先 install")
        cfg = json.loads(cfgpath.read_text())
        cfg["enabled"] = args.command == "enable"
        atomic_json(cfgpath, cfg)
        print("已启用检查开关；仍需 Codex 信任该 Hook" if cfg["enabled"] else "已停用；下一次 Hook 调用起立即跳过")
    elif args.command == "uninstall":
        changed = mutate_hooks(home, target, Path(sys.executable), remove=True)
        if cfgpath.exists():
            cfg = json.loads(cfgpath.read_text())
            atomic_json(cfgpath, cfg | {"enabled": False})
        print(json.dumps({"removed_hook_registration": changed, "state_and_backups_preserved": True}))
    else:
        print(json.dumps({"install_dir": str(target), "hooks_file": str(home / "hooks.json"),
                          "settings": json.loads(cfgpath.read_text()) if cfgpath.exists() else None,
                          "state_dir": str(target / "data")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
