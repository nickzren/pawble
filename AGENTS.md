# AGENTS.md

This is Pawble, a standalone macOS runner for Codex-style pets.

Pawble runs a local pet package:

```text
pet.json
spritesheet.webp
pawble.json        # optional Pawble-only override
```

Authoritative references:

- `docs/PET_PACK_CONTRACT.md` — package contract and validation rules.

Agent rules:

- Local by default.
- On a clean clone, run `make setup-python` before validation or tests if Pillow is missing.
- Do not upload images or call image-generation APIs unless the user explicitly chooses that workflow.
- Do not commit raw pet images or generated personal pet packages.
- `pet-photos/blueberry.jpg` is the tracked sample photo. Other new files in `pet-photos/` are ignored unless the user explicitly wants to track one.
- When helping generate or repair a pet, use `hatch-pet` with Codex/ChatGPT built-in image generation. Do not require `OPENAI_API_KEY` for the normal path.
- Pet creation starts from `pet-photos/<pet-name>.jpg`. If it is missing, ask the user to add one clear pet photo there.
- Default validation checks package structure and loadability only. Do not block a personal pet on visual drift, growth/shrink, or identity consistency.
- Strict visual validation is optional QA for sample pets, screenshots, or user-requested polish.
- Do not reject a generated source row only because its canvas size differs from the final atlas row. The contract applies after extraction: `192x208` frames in a `1536x1872` WebP atlas.
- Imported Codex pets get a default Pawble config when missing, then validate structurally.
- Do not use `make stabilize-pet` as the normal generation path. Use hatch-pet repair/regeneration first. Stabilization is only an explicit fallback for small drift/fringe fixes.
- A pet is not showcase-ready until strict visual validation passes and the contact sheet shows no grow/shrink, center jump, identity drift, or clipped frames.
- Before mutating files, tell the user what you will change.
- Always report the current step, what is present, what is missing, and the next action.

Common workflows:

- Try sample: `make run`
- Import Codex pet to Pawble: `make import-codex-pet PET=<pet-name>`
- Run Pawble pet: `make run PET=<pet-name>`
- Install Pawble pet to Codex: `make install-codex-pet PET=<pet-name>`
- Install Pawble as a Mac app: `make install-app PET=<pet-name>`
- Open installed app: `make open-app`
- Validate: `make validate-pet PET=<pet-name>`
- Validate Codex source package: `make validate-codex-pet PET=<pet-name>`
- Strict visual QA: `make validate-pet-strict PET=<pet-name>`
- Strict Codex visual QA: `make validate-codex-pet-strict PET=<pet-name>`
- Explicit fallback repair: `make stabilize-pet PET=<pet-name>`
- If import warns about existing `pawble.json`, mention that the local Pawble override was preserved.

Create from pet photo:

1. Confirm `pet-photos/<pet-name>.jpg` exists.
2. Use `hatch-pet` with that photo. Use `python3` for hatch-pet helper scripts on this repo.
3. After `prepare_pet_run.py`, run `python3 scripts/harden_hatch_prompts.py <run-dir>` before row generation.
4. Generate and record the first pet-design job before row generation.
5. Generate, record, extract, and validate every row.
6. After hatch-pet writes `${CODEX_HOME:-$HOME/.codex}/pets/<pet-name>/`, run `make validate-codex-pet PET=<pet-name>`.
7. If structural validation fails, repair/regenerate the failing files with hatch-pet before import. Use `python3 scripts/reset_hatch_job.py <run-dir> <row-id>` before replacing a stale row.
8. Run `make import-codex-pet PET=<pet-name> CODEX_PET=<pet-name>`.
9. Run `make validate-pet PET=<pet-name>`.
10. Install and open with `make install-app PET=<pet-name>` and `make open-app`, unless the user asked only to generate the pack.

State check:

- No `pet-photos/<pet-name>.jpg`: ask user to put one clear pet photo there.
- No `pet-packs/<pet-name>/`: ask user to import from Codex or use `hatch-pet` from the pet photo.
- Missing files: name the missing files.
- Old PNG/profile pack in `pet-packs/<pet-name>/`: treat it as obsolete, then import or regenerate the Codex-style pack.
- Invalid pack: run validation, report exact structural issues, then repair or regenerate the failing file or row. Use `make stabilize-pet PET=<pet-name>` only when the user explicitly accepts a fallback cleanup.
- Structurally valid pack: run, install, or open it. Use strict visual QA only for showcase polish or when the user says the pet looks wrong.
