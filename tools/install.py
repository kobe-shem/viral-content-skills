#!/usr/bin/env python3
"""Install this suite without touching unrelated skill folders."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile

PACKAGE = "viral-content-skills"
NAMES = ("viral-content", "viral-research", "viral-ideate", "viral-script", "viral-direct", "viral-learn")
MARKER = ".viral-content-install.json"


def tree_hash(path):
    result = hashlib.sha256()
    for file in sorted(path.rglob("*")):
        if file.is_file() and file.name != MARKER and "__pycache__" not in file.parts:
            result.update(file.relative_to(path).as_posix().encode())
            result.update(b"\0")
            result.update(file.read_bytes())
    return result.hexdigest()


def install(source, target, replace=False):
    source, target = Path(source).resolve(), Path(target).expanduser().resolve()
    for name in NAMES:
        if not (source / name / "SKILL.md").is_file():
            raise ValueError("Missing source skill: " + name)
        dest = target / name
        if dest.exists() or dest.is_symlink():
            if dest.is_symlink():
                raise ValueError("Refusing to replace a symlink: " + str(dest))
            try:
                marker = json.loads((dest / MARKER).read_text())
            except (OSError, ValueError):
                marker = {}
            if marker.get("package") != PACKAGE:
                raise ValueError("Unrelated existing skill; preserve it: " + str(dest))
            if not replace:
                raise ValueError("Already installed; use --replace to update with backup: " + name)
    target.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup = target.parent / "skill-backups" / PACKAGE / stamp
    changed, saved = [], []
    with tempfile.TemporaryDirectory(prefix=".viral-stage-", dir=str(target.parent)) as temporary:
        stage = Path(temporary)
        for name in NAMES:
            shutil.copytree(source / name, stage / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            digest = tree_hash(stage / name)
            (stage / name / MARKER).write_text(json.dumps({"package": PACKAGE, "installed_at": stamp, "source_sha256": digest}, indent=2) + "\n")
        try:
            for name in NAMES:
                dest = target / name
                if dest.exists():
                    backup.mkdir(parents=True, exist_ok=True)
                    dest.rename(backup / name)
                    saved.append(name)
                (stage / name).rename(dest)
                changed.append(name)
        except Exception:
            for name in reversed(changed):
                shutil.rmtree(target / name)
            for name in reversed(saved):
                (backup / name).rename(target / name)
            raise
    return {"package": PACKAGE, "target": str(target), "skills": list(NAMES), "backup": str(backup) if saved else None,
            "hashes": {name: tree_hash(target / name) for name in NAMES}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, default=Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "skills")
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()
    try:
        result = install(Path(__file__).resolve().parents[1] / "skills", args.target, args.replace)
    except (OSError, ValueError) as exc:
        parser.exit(1, str(exc) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
