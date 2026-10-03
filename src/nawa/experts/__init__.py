"""NAWA expert specifications and registry (ROADMAP P7-02; code-only scope, ADR-0009).

P7-01 defines seven expert domains: Arabic, programming, math, documents/OCR, search, planning, and safety.
P7-02 gives each expert a goal, a data contract, test cases, limits, and a routing decision — as data, not
as a running model. The experts are stubs: deterministic, synthetic-only, no network, no external model
(ADR-0009, OD-10). They are consumed later by P7-03 (router chooses core or expert(s)) and P7-04 (adding an
expert does not break isolation).

This module reuses the existing ``nawa.routing`` (P6-06) types — ``Kind``, ``Handler`` — to express each
expert's routing decision. It does not build a second router.
"""

from nawa.experts.spec import (DataContract, DataPolicy, EXPERT_SPECS, ExpertDomain, ExpertLimits,
                                ExpertSpec, ExpertTestCase, FailureMode, get_expert_spec,
                                validate_expert_specs)
from nawa.experts.registry import (EXPERT_REGISTRY, ExpertRegistry, ExpertStatus, deregister_expert,
                                   get_expert, list_experts, register_expert, registry_snapshot)
from nawa.experts.router import ExpertRoute, route_with_experts

__all__ = ["DataContract", "DataPolicy", "EXPERT_REGISTRY", "EXPERT_SPECS", "ExpertDomain",
           "ExpertLimits", "ExpertRegistry", "ExpertRoute", "ExpertSpec", "ExpertStatus",
           "ExpertTestCase", "FailureMode", "deregister_expert", "get_expert", "get_expert_spec",
           "list_experts", "register_expert", "registry_snapshot", "route_with_experts",
           "validate_expert_specs"]
