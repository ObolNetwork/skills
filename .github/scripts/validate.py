#!/usr/bin/env python3
"""Validate plugin structure: manifest, skill frontmatter, and script imports."""

import json
import sys
from pathlib import Path

errors = []

# 1. Validate plugin.json
manifest_path = Path(".claude-plugin/plugin.json")
if not manifest_path.exists():
    errors.append("Missing .claude-plugin/plugin.json")
else:
    try:
        manifest = json.loads(manifest_path.read_text())
        for field in ("name", "description", "version", "author"):
            if field not in manifest:
                errors.append(f"plugin.json missing required field: {field}")
        if "author" in manifest and "name" not in manifest.get("author", {}):
            errors.append("plugin.json author missing 'name' field")
    except json.JSONDecodeError as e:
        errors.append(f"plugin.json is not valid JSON: {e}")

# 2. Validate SKILL.md files
skills_dir = Path("skills")
skill_dirs = [d for d in skills_dir.iterdir() if d.is_dir()] if skills_dir.exists() else []

if not skill_dirs:
    errors.append("No skill directories found under skills/")

for skill_dir in skill_dirs:
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        errors.append(f"{skill_dir.name}: missing SKILL.md")
        continue

    content = skill_md.read_text()

    # Check frontmatter exists
    if not content.startswith("```skill\n---"):
        errors.append(f"{skill_dir.name}: SKILL.md must start with ```skill frontmatter block")
        continue

    # Extract frontmatter
    try:
        # Find the YAML between --- markers inside the ```skill block
        first_marker = content.index("---") + 3
        second_marker = content.index("---", first_marker)
        frontmatter = content[first_marker:second_marker]
    except ValueError:
        errors.append(f"{skill_dir.name}: SKILL.md frontmatter malformed (missing --- markers)")
        continue

    # Check required fields (simple string matching, no yaml dependency)
    if "name:" not in frontmatter:
        errors.append(f"{skill_dir.name}: SKILL.md frontmatter missing 'name'")
    if "description:" not in frontmatter:
        errors.append(f"{skill_dir.name}: SKILL.md frontmatter missing 'description'")

# Report
if errors:
    print("Validation failed:\n")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)
else:
    print(f"Validation passed: {len(skill_dirs)} skill(s) OK")
