"""NAWA data pipeline tools (ROADMAP P2-05, ADR-0005).

Cleaning (`clean`), PII redaction (`pii`), exact and near de-duplication (`dedup`), decontamination
against evaluation sets (`decontam`), quality score and script-based language tag (`quality`),
provenance and license checks (`provenance`), and the pipeline that chains them (`pipeline`).

Code only at this stage: tested on code-generated fixtures, no external corpus is ingested, the
frozen split is never read, and no output is training data while G2 is open.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from nawa.config import load_yaml

REPO = Path(__file__).resolve().parents[3]
CONFIG_PATH = REPO / "configs" / "data_pipeline.yaml"


def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    cfg = load_yaml(path)
    if cfg.get("schema_version") != 1:
        raise ValueError(f"{path}: unsupported schema_version {cfg.get('schema_version')!r}")
    return cfg
