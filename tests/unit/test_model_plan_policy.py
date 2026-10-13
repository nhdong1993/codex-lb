import pytest

from app.core.model_plan_policy import model_plan_allowed, parse_model_plan_policies

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("model", "plan", "expected"),
    [
        ("gpt-6-luna", "pro", True),
        ("gpt-6-luna", " PRO ", True),
        ("gpt-6-luna", "prolite", False),
        ("gpt-6-luna", None, False),
        ("gpt-6-luna", "unknown", False),
        ("gpt-6-luna-latest", "free", True),
        ("GPT-6-LUNA", "free", True),
        (None, "free", True),
    ],
)
def test_model_plan_membership_is_exact_without_entitlement_equivalence(model, plan, expected):
    assert model_plan_allowed({"gpt-6-luna": ["pro"]}, model, plan) is expected


@pytest.mark.parametrize("raw", ["null", "[]", '{"gpt-6-luna":[]}', '{"gpt-6-luna":["guest"]}', "not-json"])
def test_model_plan_persisted_invalid_restriction_never_becomes_empty(raw):
    with pytest.raises(ValueError):
        parse_model_plan_policies(raw)
