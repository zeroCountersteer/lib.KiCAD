#!/usr/bin/env python3
"""Generate static KiCad PCM v2 repository.json and packages.json."""
from __future__ import annotations

import argparse
import json
import time
import zipfile
from pathlib import Path


def release_versions(releases: list[dict], identifier: str) -> list[dict]:
    versions = []
    for release in releases:
        tag = release.get("tag_name", "")
        if not tag.startswith("v") or release.get("draft"):
            continue
        version = tag[1:]
        for asset in release.get("assets", []):
            if asset.get("name") == f"lib.KiCAD-{version}.zip":
                digest = asset.get("digest", "")
                versions.append({"version": version, "status": "stable", "kicad_version": "10.0", "download_url": asset.get("browser_download_url"), "download_size": asset.get("size"), **({"download_sha256": digest.split(":", 1)[1]} if digest.startswith("sha256:") else {})})
    return versions


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metadata", type=Path, default=Path("pcm/metadata.json"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--status", choices=("stable", "testing", "development", "deprecated"), default="stable")
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--asset-url", required=True)
    parser.add_argument("--releases-json", type=Path)
    parser.add_argument("--pages-url", default="https://zerocountersteer.github.io/lib.KiCAD")
    args = parser.parse_args()
    package = json.loads(args.metadata.read_text(encoding="utf-8"))
    package.pop("$schema", None)
    repository_web = "https://github.com/zeroCountersteer/lib.KiCAD"
    for role in ("author", "maintainer"):
        if role in package and "contact" not in package[role]:
            package[role]["contact"] = {"web": repository_web}
    package["versions"] = []
    if args.releases_json and args.releases_json.is_file():
        releases = json.loads(args.releases_json.read_text(encoding="utf-8"))
        if releases and isinstance(releases[0], list):
            releases = [release for page in releases for release in page]
        package["versions"] = release_versions(releases, package["identifier"])
    checksum = __import__("hashlib").sha256(args.zip.read_bytes()).hexdigest()
    with zipfile.ZipFile(args.zip) as archive:
        install_size = sum(entry.file_size for entry in archive.infolist())
    current = {"version": args.version, "status": args.status, "kicad_version": "10.0", "download_url": args.asset_url, "download_sha256": checksum, "download_size": args.zip.stat().st_size, "install_size": install_size}
    if not any(v.get("version") == args.version for v in package["versions"]):
        package["versions"].append(current)
    else:
        package["versions"] = [current if v.get("version") == args.version else v for v in package["versions"]]
    package["versions"].sort(key=lambda item: item["version"], reverse=True)
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    (out / "packages.json").write_text(json.dumps({"$schema": "https://go.kicad.org/pcm/schemas/v2#/definitions/PackageArray", "packages": [package]}, indent=2) + "\n", encoding="utf-8")
    now = int(time.time())
    (out / "repository.json").write_text(json.dumps({"$schema": "https://go.kicad.org/pcm/schemas/v2#/definitions/Repository", "schema_version": 2, "name": "zeroCountersteer lib.KiCAD", "maintainer": {"name": "zeroCountersteer", "contact": {"web": "https://github.com/zeroCountersteer/lib.KiCAD"}}, "packages": {"url": f"{args.pages_url.rstrip('/')}/packages.json", "update_time_utc": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()), "update_timestamp": now}}, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
