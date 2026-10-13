"""Operator restrictions, independent of catalog entitlements and source routing."""

from __future__ import annotations

from typing import Annotated

from pydantic import AfterValidator, Field, StringConstraints, TypeAdapter

from app.core.plan_types import normalize_account_plan_type


def _plan(value: str) -> str:
    normalized = normalize_account_plan_type(value)
    if normalized is None:
        raise ValueError("Unrecognized account plan")
    return normalized


def _model(value: str) -> str:
    if not value or value != value.strip() or any(char.isspace() for char in value):
        raise ValueError("Model IDs must be exact nonblank identifiers without whitespace")
    return value


Plan = Annotated[str, StringConstraints(strict=True), AfterValidator(_plan)]
ModelId = Annotated[str, StringConstraints(strict=True), AfterValidator(_model)]
PlanList = Annotated[list[Plan], Field(min_length=1), AfterValidator(lambda plans: sorted(set(plans)))]
ModelPlanPolicies = dict[ModelId, PlanList]
_POLICY_ADAPTER = TypeAdapter(ModelPlanPolicies)


def parse_model_plan_policies(raw: str) -> ModelPlanPolicies:
    # Never silently drop an invalid hard restriction.
    return _POLICY_ADAPTER.validate_json(raw)


def model_plan_allowed(policies: ModelPlanPolicies, model: str | None, plan: str | None) -> bool:
    allowed = policies.get(model) if model is not None else None
    return allowed is None or normalize_account_plan_type(plan) in allowed
