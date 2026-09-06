#!/usr/bin/env python3
"""Validate portable skill structure, local links, and accidental local coupling."""
from __future__ import annotations

import json
from pathlib import Path
import re
import sys

NAMES = ("viral-content", "viral-research", "viral-ideate", "viral-script", "viral-direct", "viral-learn")


def validate(root):
    root = Path(root).resolve()
    errors = []
    for name in NAMES:
        skill = root / "skills" / name / "SKILL.md"
        if not skill.is_file():
            errors.append("Missing " + str(skill.relative_to(root)))
            continue
        text = skill.read_text()
        front = re.match(r"\A---\s*\n(.*?)\n---(?:\s*\n|$)", text, re.S)
        if not front or not re.search(r"(?m)^name:\s*" + re.escape(name) + r"\s*$", front.group(1)):
            errors.append("Invalid name/frontmatter: " + name)
        if not front or not re.search(r"(?m)^description:\s*\S", front.group(1)):
            errors.append("Missing description: " + name)
        elif front:
            scalar = re.search(r"(?m)^description:\s*(.*)$", front.group(1)).group(1)
            if (": " in scalar or " #" in scalar) and not scalar.startswith(('"', "'")):
                errors.append("Quote YAML description containing colon/comment syntax: " + name)
            if scalar.startswith('"'):
                try:
                    if not isinstance(json.loads(scalar), str):
                        raise ValueError("description must be a string")
                except ValueError:
                    errors.append("Invalid quoted description: " + name)
        if len(text.splitlines()) > 150:
            errors.append("Entrypoint exceeds 150 lines; move conditional detail: " + name)
        if not (skill.parent / "agents" / "openai.yaml").is_file():
            errors.append("Missing UI metadata: " + name)
    for file in root.rglob("*"):
        if not file.is_file() or ".git" in file.parts or "__pycache__" in file.parts:
            continue
        if file.suffix not in (".md", ".json", ".yaml", ".yml", ".py", ".toml"):
            continue
        text = file.read_text()
        relative = file.relative_to(root)
        if re.search(r"/(?:Users|home)/[A-Za-z0-9_.-]+/", text):
            errors.append("Machine-specific absolute path: " + str(relative))
        if file.suffix == ".md":
            for link in re.findall(r"\]\(([^)]+)\)", text):
                if "://" in link or link.startswith("#") or link.startswith("mailto:"):
                    continue
                dest = link.split("#")[0]
                if dest and not (file.parent / dest).exists():
                    errors.append("Broken local link in " + str(relative) + ": " + dest)
        if file.suffix == ".json":
            try:
                json.loads(text)
            except ValueError as exc:
                errors.append("Invalid JSON " + str(relative) + ": " + str(exc))
    return errors


if __name__ == "__main__":
    failures = validate(Path(__file__).resolve().parents[1])
    print(json.dumps({"ok": not failures, "errors": failures}, indent=2))
    sys.exit(bool(failures))
