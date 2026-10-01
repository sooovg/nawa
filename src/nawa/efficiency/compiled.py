"""Compiled inference forward (ROADMAP P4-05, ADR-0007 D2).

``torch.compile`` of the reference forward, on fixed shapes. The compiled module shares weights with the eager one;
the check is the max absolute logit difference against eager, within the tolerance registered in ``p4_05``.
Compilation needs a C++ toolchain; if it fails, the failure is returned (and recorded), not hidden.
"""

from __future__ import annotations

import time
from typing import Any

import torch

from nawa.model.decoder import NawaDecoder


@torch.no_grad()
def compiled_parity(model: NawaDecoder, inputs: list[torch.Tensor]) -> dict[str, Any]:
    model.eval()
    try:
        t0 = time.perf_counter()
        compiled = torch.compile(model.forward, dynamic=False)
        diffs = [float((compiled(x).logits - model(x).logits).abs().max()) for x in inputs]
        return {"available": True, "max_abs_logit_diff": max(diffs), "shapes": [list(x.shape) for x in inputs],
                "seconds_incl_compile": round(time.perf_counter() - t0, 1), "error": None}
    except Exception as exc:  # noqa: BLE001 - any backend failure is a recorded result
        return {"available": False, "max_abs_logit_diff": float("inf"), "shapes": [], "seconds_incl_compile": 0.0,
                "error": f"{type(exc).__name__}: {str(exc)[:300]}"}
