"""NAWA routing (ROADMAP P6-06; code-only scope, ADR-0008): deterministic lexical query classification, handler
choice, escalation, fallback and trace.

Lexical rules only: the router does not understand meaning or synonyms. Tested on synthetic queries only.
"""

from nawa.routing.router import (HANDLER_ORDER, KIND_ORDER, PLAN_FOR, Flag, Handler, Kind, Route, RouterConfig, Step,
                                 abstention_context, language, route)

__all__ = ["HANDLER_ORDER", "KIND_ORDER", "PLAN_FOR", "Flag", "Handler", "Kind", "Route", "RouterConfig", "Step",
           "abstention_context", "language", "route"]
