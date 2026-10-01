"""Provenance record schema and license check (P2-05; G2: every record carries
source/license/language/domain/quality/date/hash/processing_version)."""

from __future__ import annotations

import hashlib
import re
from typing import Any

G2_FIELDS = ("source", "license", "language", "domain", "quality", "date", "hash", "processing_version")
INPUT_FIELDS = ("id", "text", "source", "license", "domain", "date")


class ProvenanceError(ValueError):
    pass


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def license_status(license_name: str | None, approved: list[str]) -> tuple[bool, str]:
    if not license_name:
        return False, "missing license"
    if license_name not in approved:
        return False, f"license {license_name!r} not approved (OD-03; configs/verification.yaml)"
    return True, ""


def validate_output(rec: dict[str, Any], processing_version: str, languages: list[str]) -> None:
    missing = [k for k in G2_FIELDS + ("id", "text", "steps", "train_eligible") if k not in rec]
    if missing:
        raise ProvenanceError(f"{rec.get('id')}: missing {missing}")
    if rec["hash"] != text_hash(rec["text"]):
        raise ProvenanceError(f"{rec['id']}: hash does not match text")
    if rec["processing_version"] != processing_version:
        raise ProvenanceError(f"{rec['id']}: processing_version {rec['processing_version']!r}")
    if rec["language"] not in languages:
        raise ProvenanceError(f"{rec['id']}: language {rec['language']!r}")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}(T[0-9:.]+Z?)?", str(rec["date"])):
        raise ProvenanceError(f"{rec['id']}: date {rec['date']!r} is not ISO 8601")
    if not 0.0 <= float(rec["quality"]["score"]) <= 1.0:
        raise ProvenanceError(f"{rec['id']}: quality score out of range")
    if rec["train_eligible"]:
        raise ProvenanceError(f"{rec['id']}: the cleaning pipeline never marks data train-eligible (P2-02 decides)")
    for k in ("source", "license", "domain"):
        if not rec[k]:
            raise ProvenanceError(f"{rec['id']}: empty {k}")
