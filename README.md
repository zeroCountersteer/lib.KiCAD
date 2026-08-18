# lib.KiCAD

`lib.KiCAD` is a personal KiCad 10+ content library distributed both as a normal git checkout and as a static KiCad Plugin and Content Manager (PCM) v2 repository. It contains the existing grouped `lib` library plus audited Allwinner A33 and X-Powers AXP223 symbols and footprints.

## Source layout

* `symbols/` — grouped `lib.kicad_sym`, `SoC_Allwinner.kicad_sym`, and `PMIC_XPowers.kicad_sym`.
* `footprints/` — `lib.pretty`, `Package_SoC.pretty`, and `Package_PMIC.pretty`.
* `3dmodels/` — the existing custom `lib.3dshapes` collection.
* `pcm/` — v2 package metadata template.
* `scripts/` — importer, portability normalizer, validator, package builder, and repository-index generator.

## Direct git use

Add `symbols/*.kicad_sym` in Symbol Editor → Manage Symbol Libraries and add the three `footprints/*.pretty` directories in Footprint Libraries. For custom 3D models, set `KICAD10_3RD_PARTY` to this repository root, or use the PCM installation. Custom references use `${KICAD10_3RD_PARTY}/3dmodels/lib.3dshapes/...`; stock `${KICAD10_3DMODEL_DIR}` references are unchanged. The PCM build removes references to legacy external model libraries that are not shipped by this package, so a clean PCM installation never points at an unavailable KiCad 6 or third-party model tree.

## Validate and build locally

```sh
python3 scripts/validate_library.py
mkdir -p dist
python3 scripts/build_pcm_package.py --version 0.1.0 \
  --output dist/lib.KiCAD-0.1.0.zip
unzip -l dist/lib.KiCAD-0.1.0.zip
```

The archive contains `symbols/`, `footprints/`, `3dmodels/`, `templates/`, and `metadata.json`. It is deterministic and emits a `.sha256` sidecar. Run `python3 scripts/validate_pcm_package.py dist/lib.KiCAD-0.1.0.zip` to verify the archive layout and all packaged 3D model references.

## Releases and PCM repository

Create an immutable semantic-version release:

```sh
git tag v0.1.0
git push origin v0.1.0
```

The tag workflow validates the library, builds `lib.KiCAD-0.1.0.zip`, creates the GitHub Release asset, derives prior tagged releases from the GitHub API, generates `repository.json` and `packages.json`, and deploys those files to GitHub Pages. The expected repository URL is:

`https://zerocountersteer.github.io/lib.KiCAD/repository.json`

In KiCad 10, open Preferences → Manage Plugin and Content Manager → Manage Repositories, add that URL, and refresh. The update flow is: push to `main` → GitHub rebuilds the moving `rolling` release → Pages index updates → KiCad sees the new development version. Stable immutable releases still use the tag flow above. The rolling package is versioned as `0.99.<GitHub run number>` so every push is a real PCM update and sorts above the current `0.x` stable releases. The ZIP is always uploaded as the single mutable `lib.KiCAD-rolling.zip` asset in the `rolling` release, so the release does not accumulate one asset per update.

Enable Settings → Pages once in the GitHub repository, choose **GitHub Actions** as the source, and keep the `github-pages` environment available. No package ZIP is copied to Pages; it remains a GitHub Release asset, while the rolling asset is intentionally replaced on each successful `main` build.

## Component audits and provenance

The A33 conversion contains all 282 sparse TFBGA balls on the MiniDev 17×17 grid, with the confirmed correction `PG8=B16` and `PG9=A16`. The AXP223 conversion contains pads 1–69, names pad 69 `EP/GND`, and uses three smaller F.Paste apertures rather than one solid exposed-pad aperture. Thermal vias are left to the board designer.

Both components are derived from the MIT-licensed A33-MiniDev project; see `THIRD_PARTY_NOTICES.md`. No MiniDev 3D model is shipped because redistributable provenance was not independently established. Existing CAD content has mixed provenance and is not falsely declared uniformly MIT; see `LICENSE`.
