"""Validate project JSON, TOML and non-template YAML without contacting services."""

import json
import tomllib
from pathlib import Path

import yaml


def main():
    root = Path(__file__).resolve().parents[1]
    files = [root / "pyproject.toml", root / ".pre-commit-config.yaml"]
    for directory in (root / "configs", root / "patches", root / ".github"):
        files.extend(p for p in directory.rglob("*") if p.suffix in {".json", ".yaml", ".yml"})
    for path in files:
        text = path.read_text(encoding="utf-8-sig")
        if path.suffix == ".json":
            json.loads(text)
        elif path.suffix == ".toml":
            tomllib.loads(text)
        else:
            list(yaml.safe_load_all(text))
    print(f"Validated {len(files)} configuration files")


if __name__ == "__main__":
    main()
