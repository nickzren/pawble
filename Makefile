PET ?=
PET_PACK = pet-packs/$(PET)
SAMPLE_PACK = sample-pets/$(PET)
PACK ?= $(if $(PET),$(if $(wildcard $(PET_PACK)/pet.json),$(PET_PACK),$(if $(wildcard $(SAMPLE_PACK)/pet.json),$(SAMPLE_PACK),$(PET_PACK))),sample-pets/blueberry)
CODEX_HOME ?= $(HOME)/.codex
CODEX_PET ?= $(if $(PET),$(PET),blueberry)
CODEX_PACK = $(CODEX_HOME)/pets/$(CODEX_PET)
APP_NAME ?= Pawble
APP_BUNDLE ?= .build/$(APP_NAME).app
APP_INSTALL_DIR ?= $(HOME)/Applications
APP_INSTALL_PATH ?= $(APP_INSTALL_DIR)/$(APP_NAME).app
APP_PACK = $(APP_BUNDLE)/Contents/Resources/pets/default
PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
SWIFT ?= swift
SWIFT_ENV = CLANG_MODULE_CACHE_PATH="$(CURDIR)/.build/clang-module-cache"
SWIFT_FLAGS = --disable-sandbox --scratch-path .build --cache-path .build/swiftpm-cache --config-path .build/swiftpm-config --security-path .build/swiftpm-security --manifest-cache local

.PHONY: setup-python run validate-pet validate-pet-strict validate-codex-pet validate-codex-pet-strict stabilize-pet import-codex-pet install-codex-pet build-app install-app open-app test

setup-python:
	python3 -m venv .venv
	.venv/bin/python -m pip install -r requirements.txt

run: validate-pet
	$(SWIFT_ENV) $(SWIFT) run $(SWIFT_FLAGS) Pawble --pack "$(PACK)"

validate-pet:
	$(PYTHON) scripts/validate_pet.py "$(PACK)"

validate-pet-strict:
	$(PYTHON) scripts/validate_pet.py --strict-visual "$(PACK)"

validate-codex-pet:
	$(PYTHON) scripts/validate_pet.py "$(CODEX_PACK)"

validate-codex-pet-strict:
	$(PYTHON) scripts/validate_pet.py --strict-visual "$(CODEX_PACK)"

stabilize-pet:
	$(PYTHON) scripts/stabilize_spritesheet.py "$(PACK)"

import-codex-pet:
	@test -n "$(PET)" || (echo "PET is required: make import-codex-pet PET=<pet-name>" >&2; exit 2)
	@test -f "$(CODEX_PACK)/pet.json" || (echo "Missing $(CODEX_PACK)/pet.json" >&2; exit 1)
	@test -f "$(CODEX_PACK)/spritesheet.webp" || (echo "Missing $(CODEX_PACK)/spritesheet.webp" >&2; exit 1)
	install -d "pet-packs/$(PET)"
	cp "$(CODEX_PACK)/pet.json" "pet-packs/$(PET)/pet.json"
	cp "$(CODEX_PACK)/spritesheet.webp" "pet-packs/$(PET)/spritesheet.webp"
	@echo "Imported $(CODEX_PET) from $(CODEX_PACK) to pet-packs/$(PET)"
	@if test -f "pet-packs/$(PET)/pawble.json"; then echo "Preserved pet-packs/$(PET)/pawble.json (Pawble-only override). Remove it if it no longer matches this pet."; fi
	$(PYTHON) scripts/ensure_pawble_config.py "pet-packs/$(PET)"
	$(PYTHON) scripts/validate_pet.py "pet-packs/$(PET)"

install-codex-pet: validate-pet
	install -d "$(CODEX_PACK)"
	cp "$(PACK)/pet.json" "$(CODEX_PACK)/pet.json"
	cp "$(PACK)/spritesheet.webp" "$(CODEX_PACK)/spritesheet.webp"
	@echo "Installed $(CODEX_PET) to $(CODEX_PACK)"
	@echo "In Codex, refresh custom pets from Settings > Appearance > Pets."

build-app: validate-pet
	$(SWIFT_ENV) $(SWIFT) build $(SWIFT_FLAGS)
	$(PYTHON) scripts/safe_delete_app.py --base ".build" --target "$(APP_BUNDLE)"
	install -d "$(APP_BUNDLE)/Contents/MacOS" "$(APP_BUNDLE)/Contents/Resources" "$(APP_PACK)"
	cp Resources/Info.plist "$(APP_BUNDLE)/Contents/Info.plist"
	install -m 755 ".build/debug/Pawble" "$(APP_BUNDLE)/Contents/MacOS/Pawble"
	cp "$(PACK)/pet.json" "$(APP_PACK)/pet.json"
	cp "$(PACK)/spritesheet.webp" "$(APP_PACK)/spritesheet.webp"
	@if test -f "$(PACK)/pawble.json"; then cp "$(PACK)/pawble.json" "$(APP_PACK)/pawble.json"; fi
	$(PYTHON) scripts/make_app_icon.py "$(PACK)/spritesheet.webp" "$(APP_BUNDLE)/Contents/Resources/AppIcon.icns"
	@codesign --force --deep --sign - "$(APP_BUNDLE)" >/dev/null 2>&1 || true
	@echo "Built $(APP_BUNDLE)"

install-app: build-app
	install -d "$(APP_INSTALL_DIR)"
	$(PYTHON) scripts/safe_delete_app.py --base "$(APP_INSTALL_DIR)" --target "$(APP_INSTALL_PATH)"
	cp -R "$(APP_BUNDLE)" "$(APP_INSTALL_PATH)"
	@echo "Installed $(APP_INSTALL_PATH)"
	@echo "Open it from Finder, or run: make open-app"

open-app:
	open "$(APP_INSTALL_PATH)"

test: validate-pet
	$(PYTHON) scripts/test_source_contract.py
	$(PYTHON) scripts/test_app_icon.py
	$(PYTHON) scripts/test_validate_pet.py
	$(SWIFT_ENV) $(SWIFT) build $(SWIFT_FLAGS)
	PAWBLE_SKIP_SWIFT_BUILD=1 $(PYTHON) scripts/test_runtime_contract.py
