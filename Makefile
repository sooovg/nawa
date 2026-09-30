# NAWA — standard commands (AGENTS.md §12).
# Only bootstrap targets are implemented. Others fail on purpose until their
# ROADMAP task is DONE, so nobody mistakes a stub for a working pipeline.

PYTHON ?= python3

.PHONY: help setup test secrets ci data train eval gate repro push-model push-data

help:
	@echo "Implemented: setup test secrets ci"
	@echo "Not yet implemented (see ROADMAP.md): data train eval gate repro push-model push-data"

setup:
	$(PYTHON) -m pip install -e ".[dev]"
	pre-commit install || echo "pre-commit not available; skipped hook install"

test:
	$(PYTHON) -m pytest

secrets:
	git ls-files -z | xargs -0 detect-secrets-hook --baseline .secrets.baseline

ci: test secrets

define not_implemented
	@echo "make $(1): not implemented yet — owned by ROADMAP task $(2). Refusing to run."; exit 1
endef

data:
	$(call not_implemented,data,P2-05..P2-08)
train:
	$(call not_implemented,train,P3-06 / P5)
eval:
	$(call not_implemented,eval,P1-07)
gate:
	$(call not_implemented,gate,P1-07)
repro:
	$(call not_implemented,repro,P1-07 / P10-05)
push-model:
	$(call not_implemented,push-model,P4-08 / P5-09 (requires manifest + gate))
push-data:
	$(call not_implemented,push-data,P2-08 (requires license approval))
