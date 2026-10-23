#!/usr/bin/env python3
"""Make custom model references portable without touching stock KiCad paths."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL_ROOT = ROOT / "3dmodels" / "lib.3dshapes"
PACKAGE_ID = "com_github_zerocountersteer_lib-kicad"
MODEL_PREFIX = f"${{KICAD10_3RD_PARTY}}/3dmodels/{PACKAGE_ID}/lib.3dshapes/"
EXTERNAL_MODEL_PREFIXES = (
    "${KICAD6_3RD_PARTY}/",
    "${KICAD10_3RD_PARTY}/3dmodels/com_github_perigoso_keyswitch-kicad-library/",
)


def model_blocks(text: str):
    """Yield complete model-expression spans without truncating nested transforms."""
    cursor = 0
    while True:
        model_start = text.find("(model ", cursor)
        if model_start < 0:
            return
        start = text.rfind("\n", cursor, model_start) + 1
        depth = 0
        quoted = False
        escaped = False
        for index in range(model_start, len(text)):
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
            elif char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    block = text[model_start:index + 1]
                    first_quote = block.find('"')
                    second_quote = block.find('"', first_quote + 1)
                    yield start, index + 1, block[first_quote + 1:second_quote]
                    cursor = index + 1
                    break
        else:
            raise ValueError(f"unterminated model block at offset {start}")


def rewrite(path: Path) -> None:
    text = path.read_text(encoding="utf-8", errors="replace")
    text = text.replace(
        "${KICAD10_3RD_PARTY}/3dmodels/lib.3dshapes/",
        MODEL_PREFIX,
    )
    output = []
    cursor = 0
    for start, end, model in model_blocks(text):
        output.append(text[cursor:start])
        block = text[start:end]
        if model.startswith(EXTERNAL_MODEL_PREFIXES):
            cursor = end
            continue
        if model.startswith(("${", "http:", "https:")) or not Path(model).is_absolute():
            output.append(block)
            cursor = end
            continue
        filename = Path(model.replace("\\", "/")).name
        if (MODEL_ROOT / filename).is_file():
            output.append(block.replace(model, f"{MODEL_PREFIX}{filename}"))
        # Drop absolute references to models outside this repository.
        cursor = end
    output.append(text[cursor:])
    path.write_text("".join(output), encoding="utf-8")


for footprint in sorted((ROOT / "footprints").rglob("*.kicad_mod")):
    rewrite(footprint)
