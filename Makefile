# NAWA — standard commands (AGENTS.md §12).
# Only bootstrap targets are implemented. Others fail on purpose until their
# ROADMAP task is DONE, so nobody mistakes a stub for a working pipeline.

PYTHON ?= python3

.PHONY: help setup test secrets ci data train eval report gate repro sanity push-model push-data

help:
	@echo "Implemented: setup test secrets ci eval report repro sanity"
	@echo "Not yet implemented (see ROADMAP.md): data train gate push-model push-data"

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
MODEL ?= oracle
SPLIT ?= dev
SUITE ?= all
eval:  ## make eval MODEL=hf:<dir> SPLIT=dev SUITE=all
	python eval/run_eval.py --model $(MODEL) --split $(SPLIT) --suites $(SUITE)
report:  ## make report RUN=eval/runs/<run_id>
	python eval/report.py $(RUN) --markdown
gate:
	$(call not_implemented,gate,P1-07 records gate evidence; automated gate checks: P10-05)
repro:  ## rebuild dev/calib, check the pipeline end-to-end with the oracle backend, run tests
	python -m nawa.evaluation.build --split dev --out eval/build
	python -m nawa.evaluation.build --split calib --out eval/build
	python eval/run_eval.py --model oracle --split dev
	python -m pytest -q
sanity:  ## P3-05: XOR + tiny char LM on the reference decoder, local CPU (about 3 min)
	python -m nawa.training.sanity
push-model:
	$(call not_implemented,push-model,P4-08 / P5-09 (requires manifest + gate))
push-data:
	$(call not_implemented,push-data,P2-08 (requires license approval))
