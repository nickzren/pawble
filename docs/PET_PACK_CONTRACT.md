# Pet Pack Contract

Pawble runs Codex-compatible pet packages.

## Required Shape

```text
pet-packs/<pet-name>/
  pet.json
  spritesheet.webp
  pawble.json        # optional Pawble-only behavior override
```

The tracked sample lives at:

```text
sample-pets/blueberry/
  pet.json
  spritesheet.webp
  pawble.json
```

## pet.json

Required fields:

```json
{
  "id": "blueberry",
  "displayName": "Blueberry",
  "description": "Nick's Blueberry pet.",
  "spritesheetPath": "spritesheet.webp"
}
```

Rules:

- `id` must be a non-empty string.
- `displayName` must be a non-empty string.
- `spritesheetPath` must be exactly `spritesheet.webp`.
- `spritesheetPath` must be relative and must not contain `..`.

## spritesheet.webp

Rules:

- Format: transparent-capable WebP.
- Size: `1536x1872`.
- Atlas layout: `8` columns by `9` rows.
- Cell size: `192x208`.
- Used cells must contain visible pet pixels.
- Unused cells must be transparent.

Generated source row images are not the pack contract. They may be larger than
the final row, or use a different canvas size, as long as the hatch workflow can
extract the requested frames cleanly. The hard requirements apply to the
extracted `192x208` frames and final `1536x1872` WebP atlas.

Row layout:

```text
row 0: idle           6 frames
row 1: running-right  8 frames
row 2: running-left   8 frames
row 3: waving         4 frames
row 4: jumping        5 frames
row 5: failed         8 frames
row 6: waiting        6 frames
row 7: running        6 frames
row 8: review         6 frames
```

## pawble.json

`pawble.json` is optional and Pawble-only.

Example:

```json
{
  "schemaVersion": 1,
  "idleFrameSequence": [1, 1, 1, 1, 1, 3, 1],
  "movementFrameSource": "running",
  "mirrorMovementFrameSourceForLeft": true
}
```

Rules:

- `schemaVersion` must be `1`.
- `idleFrameSequence`, when present, must be a non-empty array of idle frame indexes from `0` through `5`.
- `movementFrameSource`, when present, must be one of `idle`, `running-right`, `running-left`, `waving`, `jumping`, `failed`, `waiting`, `running`, or `review`.
- `mirrorMovementFrameSourceForLeft`, when present, must be a boolean.

## Validator

- `make validate-pet` validates `sample-pets/blueberry/` for package structure and loadability.
- `make validate-pet PET=<pet-name>` validates `pet-packs/<pet-name>/` when it has `pet.json`.
- If `pet-packs/<pet-name>/pet.json` is missing and `sample-pets/<pet-name>/pet.json` exists, `make validate-pet PET=<pet-name>` validates that sample pack instead.
- Valid packs exit `0` and print `pack ready`.
- Invalid packs exit non-zero and list every issue.
- On a clean clone, run `make setup-python` once before validation or tests.
- `make validate-codex-pet PET=<pet-name>` validates `${CODEX_HOME:-~/.codex}/pets/<pet-name>/` before import.
- Default validation does not fail personal pets for visual drift, growth/shrink, or identity consistency.
- `make validate-pet-strict PET=<pet-name>` and `make validate-codex-pet-strict PET=<pet-name>` add visual QA checks for row centering and frame bounds stability.
- Do not promote a pet into `sample-pets/` until strict visual validation passes and the contact sheet looks consistent.
- `make stabilize-pet PET=<pet-name>` is an explicit fallback for small drift/fringe fixes. Do not use it to hide a visibly inconsistent sample.

## Strict Visual QA

Strict visual QA is optional for personal pets and expected for public sample pets.

Rules checked in strict mode:

- All rows keep the pet visually centered within `2px`.
- Stationary and movement rows (`idle`, `running-right`, `running-left`, `waiting`, `running`, `review`) keep visible bounds stable within `2px`.
- Selected `idleFrameSequence` frames keep visible bounds stable within `2px` total spread.
- The configured `movementFrameSource` row keeps visible bounds stable within `2px`.

## Codex Import/Install

- `make import-codex-pet PET=<pet-name>` copies `${CODEX_HOME:-~/.codex}/pets/<pet-name>/` to `pet-packs/<pet-name>/`.
- `make install-codex-pet` installs `sample-pets/blueberry/` into `${CODEX_HOME:-~/.codex}/pets/blueberry/`.
- `make install-codex-pet PET=<pet-name>` installs `pet-packs/<pet-name>/` into `${CODEX_HOME:-~/.codex}/pets/<pet-name>/`.
- Import/install copies only `pet.json` and `spritesheet.webp`.
- Import creates a default `pawble.json` when missing.
- Import validates package structure and loadability after copying.
- Import preserves an existing `pawble.json` override and prints a warning.
- Install validates before copying.

## Mac App Install

- `make install-app` installs `sample-pets/blueberry/` as `~/Applications/Pawble.app`.
- `make install-app PET=<pet-name>` installs `pet-packs/<pet-name>/` as `~/Applications/Pawble.app`.
- The app bundle includes the selected pet and optional `pawble.json`.
- The installed app shows in the Dock when running.
