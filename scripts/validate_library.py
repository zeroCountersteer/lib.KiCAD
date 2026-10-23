#!/usr/bin/env python3
"""Focused structural checks for the maintained KiCad library."""
from __future__ import annotations

import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "com_github_zerocountersteer_lib-kicad"
PACKAGE_MODEL_PREFIX = f"${{KICAD10_3RD_PARTY}}/3dmodels/{PACKAGE_ID}/lib.3dshapes/"


def numbers(text: str, pattern: str) -> list[str]:
    return re.findall(pattern, text, re.M)


def check_equal(label: str, left: set[str], right: set[str]) -> None:
    if left != right:
        raise AssertionError(f"{label}: missing={sorted(left-right)} unexpected={sorted(right-left)}")


def top_level_heads(text: str) -> list[str]:
    """Return the names of direct children of the footprint expression."""
    heads: list[str] = []
    depth = 0
    quoted = False
    escaped = False
    data = False
    index = 0
    while index < len(text):
        char = text[index]
        if data:
            if char == "|":
                data = False
        elif quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char == "|":
            data = True
        elif char == "(":
            if depth == 1:
                match = re.match(r"\(([A-Za-z0-9_]+)", text[index:])
                if match:
                    heads.append(match.group(1))
            depth += 1
        elif char == ")":
            depth -= 1
            if depth < 0:
                raise AssertionError("unbalanced closing parenthesis")
        index += 1
    if depth != 0 or quoted or data:
        raise AssertionError("unterminated footprint expression")
    return heads


def main() -> int:
    a33_sym = (ROOT / "symbols/SoC_Allwinner.kicad_sym").read_text()
    a33_fp = (ROOT / "footprints/Package_SoC.pretty/Allwinner_A33_TFBGA282_14x14mm_P0.8mm.kicad_mod").read_text()
    axp_sym = (ROOT / "symbols/PMIC_XPowers.kicad_sym").read_text()
    axp_fp = (ROOT / "footprints/Package_PMIC.pretty/XPowers_AXP223_QFN-68-1EP_8x8mm_P0.4mm.kicad_mod").read_text()
    fdmc_sym = (ROOT / "symbols/lib.kicad_sym").read_text()
    if '(property "Footprint" "lib:FDMC8321L_Power33"' not in fdmc_sym:
        raise AssertionError("FDMC8321L symbol is not associated with lib:FDMC8321L_Power33")
    if not (ROOT / "footprints/lib.pretty/FDMC8321L_Power33.kicad_mod").is_file():
        raise AssertionError("FDMC8321L Power33 footprint is missing")
    a33_pins = set(numbers(a33_sym, r'^\s*\(number "([A-U](?:1[0-7]|[1-9]))"'))
    a33_pads = set(numbers(a33_fp, r'^\s*\(pad ([A-U](?:1[0-7]|[1-9]))\s'))
    if len(a33_pins) != 282 or len(a33_pads) != 282:
        raise AssertionError(f"A33 count mismatch: symbol={len(a33_pins)} footprint={len(a33_pads)}")
    check_equal("A33 symbol/footprint balls", a33_pins, a33_pads)
    if '(name "PG8"' not in a33_sym or '(number "B16"' not in a33_sym:
        raise AssertionError("A33 PG8 is not mapped to B16")
    if '(name "PG9"' not in a33_sym or '(number "A16"' not in a33_sym:
        raise AssertionError("A33 PG9 is not mapped to A16")
    if not all(token in a33_fp for token in ('-6.4000000000', '0.8000000000', '7.0000000000')):
        raise AssertionError("A33 package geometry markers missing")

    axp_pins = set(numbers(axp_sym, r'^\s*\(number "(\d+)"'))
    axp_pads = set(numbers(axp_fp, r'^\s*\(pad (\d+)\s'))
    expected = {str(i) for i in range(1, 70)}
    check_equal("AXP223 symbol/footprint pads", expected, axp_pins)
    check_equal("AXP223 footprint pads", expected, axp_pads)
    if '(name "EP/GND"' not in axp_sym or '(number "69"' not in axp_sym:
        raise AssertionError("AXP223 exposed pad 69 is not EP/GND")
    if '(pad 69 smd rect (at 0 0) (size 5.59 5.59) (layers "F.Cu" "F.Mask"))' not in axp_fp:
        raise AssertionError("AXP223 pad 69 copper/mask definition is unexpected")
    if axp_fp.count('(layer "F.Paste")') < 3:
        raise AssertionError("AXP223 exposed pad has no windowed paste apertures")
    for file in ROOT.rglob("*"):
        if file.is_file() and file.suffix in {".kicad_mod", ".kicad_sym", ".json", ".yml", ".yaml"}:
            text = file.read_text(encoding="utf-8", errors="ignore")
            if any(bad in text for bad in ("C:/Users/", "Documents/GitHub/", "/home/az/")):
                raise AssertionError(f"development path remains in {file}")
    for footprint in (ROOT / "footprints").rglob("*.kicad_mod"):
        text = footprint.read_text(encoding="utf-8", errors="ignore")
        invalid_heads = set(top_level_heads(text)) & {"scale", "offset", "rotate"}
        if invalid_heads:
            raise AssertionError(f"orphan model transform in {footprint}: {sorted(invalid_heads)}")
        embedded = set(re.findall(r'\(file\s+\(name "([^"]+)"\)\s+\(type model\)', text))
        referenced = set(re.findall(r'\(model\s+"([^"]+)"', text))
        if not embedded <= referenced:
            raise AssertionError(f"unreferenced embedded model in {footprint}: {sorted(embedded-referenced)}")
        for model in referenced:
            if model.startswith(PACKAGE_MODEL_PREFIX):
                filename = model.removeprefix(PACKAGE_MODEL_PREFIX)
                if not (ROOT / "3dmodels/lib.3dshapes" / filename).is_file():
                    raise AssertionError(f"source model reference does not resolve: {footprint}: {model}")
    package = ROOT / "dist/lib.KiCAD-0.1.0.zip"
    if package.is_file():
        with zipfile.ZipFile(package) as archive:
            names = set(archive.namelist())
            for name in names:
                if not name.endswith(".kicad_mod"):
                    continue
                content = archive.read(name).decode("utf-8", errors="ignore")
                for model in re.findall(r'\(model "(\$\{KICAD10_3RD_PARTY\}/3dmodels/lib\.3dshapes/[^"]+)"', content):
                    relative = model.split("/3dmodels/", 1)[1]
                    if f"3dmodels/{relative}" not in names:
                        raise AssertionError(f"package model reference does not resolve: {name}: {model}")
    print("A33: 282/282 balls, PG8=B16, PG9=A16")
    print("AXP223: pads 1..69, EP/GND=69, windowed exposed-pad paste")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, OSError, json.JSONDecodeError, zipfile.BadZipFile) as error:
        print(f"validation failed: {error}", file=sys.stderr)
        raise SystemExit(1)
