#!/usr/bin/env python3
"""Build a deterministic KiCad 10 PCM library package."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

SEMVER = re.compile(r"^(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")
SKIP = {".git", ".github", ".codex", ".agents", "dist", "build", "__pycache__"}
EXTERNAL_MODEL_PREFIXES = (
    "${KICAD6_3RD_PARTY}/",
    "${KICAD10_3RD_PARTY}/3dmodels/com_github_perigoso_keyswitch-kicad-library/",
)


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def copy_tree(source: Path, destination: Path) -> None:
    if not source.is_dir():
        raise ValueError(f"required source directory is missing: {source}")
    shutil.copytree(source, destination, copy_function=shutil.copy2)


def metadata(template: Path, version: str, status: str, package_root: Path) -> dict:
    data = json.loads(template.read_text(encoding="utf-8"))
    data.pop("kicad_version", None)
    data["$schema"] = "https://go.kicad.org/pcm/schemas/v2"
    data["versions"] = [{"version": version, "status": status, "kicad_version": "10.0"}]
    (package_root / "metadata.json").write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return data


def remove_external_model_blocks(text: str) -> str:
    """Remove model blocks that refer to libraries not shipped by this package."""
    output = []
    cursor = 0
    while True:
        start = text.find("(model ", cursor)
        if start < 0:
            output.append(text[cursor:])
            break
        output.append(text[cursor:start])
        depth = 0
        quoted = False
        escaped = False
        end = None
        for index in range(start, len(text)):
            char = text[index]
            if quoted:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    quoted = False
            elif char == '"':
                quoted = True
            elif char == '(':
                depth += 1
            elif char == ')':
                depth -= 1
                if depth == 0:
                    end = index + 1
                    break
        if end is None:
            raise ValueError("unterminated footprint model block")
        block = text[start:end]
        path_start = block.find('"')
        path_end = block.find('"', path_start + 1) if path_start >= 0 else -1
        model_path = block[path_start + 1:path_end] if path_end > path_start else ""
        if model_path.startswith(EXTERNAL_MODEL_PREFIXES):
            cursor = end
            continue
        output.append(block)
        cursor = end
    return "".join(output)


def sanitize_footprints(footprints_root: Path) -> None:
    for footprint in footprints_root.rglob("*.kicad_mod"):
        original = footprint.read_text(encoding="utf-8")
        sanitized = remove_external_model_blocks(original)
        if sanitized != original:
            footprint.write_text(sanitized, encoding="utf-8")


def write_zip(root: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(root.rglob("*")):
            if path.is_file() and not any(part in SKIP for part in path.relative_to(root).parts):
                info = zipfile.ZipInfo(path.relative_to(root).as_posix())
                info.date_time = (2020, 1, 1, 0, 0, 0)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                archive.writestr(info, path.read_bytes())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--metadata", type=Path, default=Path("pcm/metadata.json"))
    parser.add_argument("--version", required=True)
    parser.add_argument("--status", choices=("stable", "testing", "development", "deprecated"), default="stable")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not SEMVER.fullmatch(args.version):
        print(f"invalid semantic version: {args.version}", file=sys.stderr)
        return 2
    repo = args.repo.resolve()
    template = (repo / args.metadata).resolve()
    if not template.is_file():
        print(f"metadata template not found: {template}", file=sys.stderr)
        return 2
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp) / "package"
        root.mkdir()
        copy_tree(repo / "symbols", root / "symbols")
        copy_tree(repo / "footprints", root / "footprints")
        copy_tree(repo / "3dmodels", root / "3dmodels")
        # Project starters are distributable library content. Keep them under
        # their own namespace so installing the PCM package does not mix
        # template files with KiCad's symbol/footprint/model libraries.
        copy_tree(repo / "templates", root / "templates")
        sanitize_footprints(root / "footprints")
        metadata(template, args.version, args.status, root)
        for file in root.rglob("*"):
            if file.is_file() and any(token in file.read_text(encoding="utf-8", errors="ignore") for token in ("C:/Users/", "/home/", "Documents/GitHub/")):
                raise ValueError(f"development path found in package input: {file}")
        write_zip(root, args.output.resolve())
        installed_size = sum(p.stat().st_size for p in root.rglob("*") if p.is_file())
        file_count = sum(1 for p in root.rglob("*") if p.is_file())
    checksum = digest(args.output.resolve())
    checksum_file = args.output.resolve().with_suffix(args.output.suffix + ".sha256")
    checksum_file.write_text(f"{checksum}  {args.output.name}\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output.resolve()), "version": args.version, "sha256": checksum, "download_size": args.output.stat().st_size, "install_size": installed_size, "files": file_count}, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"PCM build failed: {error}", file=sys.stderr)
        raise SystemExit(1)
