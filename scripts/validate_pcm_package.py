#!/usr/bin/env python3
"""Validate a built KiCad PCM content-library archive."""
from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path

ALLOWED_ROOTS = {"symbols", "footprints", "3dmodels", "templates", "resources", "metadata.json"}
MODEL_RE = re.compile(r'\(model\s+"([^"]+)"')


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    with zipfile.ZipFile(args.archive) as archive:
        names = archive.namelist()
        if not names:
            raise ValueError("archive is empty")
        roots = {name.split("/", 1)[0] for name in names}
        unexpected = roots - ALLOWED_ROOTS
        if unexpected:
            raise ValueError(f"unexpected archive root(s): {', '.join(sorted(unexpected))}")
        if "metadata.json" not in names:
            raise ValueError("metadata.json is missing")
        metadata = json.loads(archive.read("metadata.json"))
        if metadata.get("type") != "library":
            raise ValueError("package metadata type is not library")
        if not any(name.startswith(("symbols/", "footprints/", "3dmodels/")) for name in names):
            raise ValueError("package contains no library content")

        model_paths = []
        for name in names:
            if not name.startswith("footprints/") or not name.endswith(".kicad_mod"):
                continue
            model_paths.extend(MODEL_RE.findall(archive.read(name).decode("utf-8")))
        for model in model_paths:
            if model.startswith("${KICAD6_3RD_PARTY}/"):
                raise ValueError(f"legacy KICAD6 model reference remains: {model}")
            if model.startswith("${KICAD10_3RD_PARTY}/"):
                relative = model.split("}/", 1)[1]
                if relative not in names:
                    raise ValueError(f"shipped model is missing: {relative}")
        print(f"PCM package validation OK: {args.archive} ({len(names)} entries)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError, zipfile.BadZipFile) as error:
        print(f"PCM package validation failed: {error}", file=sys.stderr)
        raise SystemExit(1)
