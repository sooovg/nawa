"""Reasoning runtime pieces (ROADMAP P6-03, ADR-0008): budget, state, decomposer, planner, generator interface and
self-consistency.

Code-only scope: Track S, CPU, no external model (OD-10), no network, no real data. Generators are deterministic stubs;
a NAWA generator is P6-03a (BLOCKED until G5). Nothing here claims that NAWA reasons or answers better (ADR-0008 D4).
"""

from nawa.reasoning.budget import Budget, BudgetExhausted, Resource, Spend
from nawa.reasoning.consistency import Agreement, agreement
from nawa.reasoning.decomposer import Kind, SubTask, decompose
from nawa.reasoning.generator import (Candidate, FailingStub, Generator, OracleStub, ScriptedStub, WrongStub,
                                      generate_candidates)
from nawa.reasoning.planner import Action, Plan, PlanStep, plan, plan_subtasks
from nawa.reasoning.state import State, StateClosed, StepRecord

__all__ = ["Action", "Agreement", "Budget", "BudgetExhausted", "Candidate", "FailingStub", "Generator", "Kind",
           "OracleStub", "Plan", "PlanStep", "Resource", "ScriptedStub", "Spend", "State", "StateClosed", "StepRecord",
           "SubTask", "WrongStub", "agreement", "decompose", "generate_candidates", "plan", "plan_subtasks"]
