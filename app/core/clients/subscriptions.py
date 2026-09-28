"""Read subscription terms using the ChatGPT browser transport profile."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from urllib.parse import quote

from curl_cffi.requests import AsyncSession
from pydantic import BaseModel, ConfigDict, StrictBool, StrictStr, TypeAdapter, ValidationError, field_validator

from app.core.clients.codex import require_route_or_direct_egress_opt_in
from app.core.plan_types import normalize_account_plan_type
from app.core.types import JsonValue
from app.core.upstream_proxy import ResolvedUpstreamRoute

_PATH = "/backend-api/subscriptions"
_TIMEOUT_SECONDS = 20


class SubscriptionFetchError(Exception):
    """Closed diagnostics: never retain response bodies, tokens or proxy URLs."""

    def __init__(self, code: str, status_code: int | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


class SubscriptionRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    active_until: datetime | None = None
    is_active: StrictBool | None = None
    active: StrictBool | None = None
    status: StrictStr | None = None
    plan_type: StrictStr | None = None
    account_id: StrictStr | None = None

    @field_validator("active_until", mode="before")
    @classmethod
    def parse_date(cls, value: JsonValue) -> datetime | None:
        if value is None:
            return None
        try:
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                parsed = datetime.fromtimestamp(value, UTC)
            elif isinstance(value, str) and ("T" in value or " " in value):
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            else:
                raise ValueError("invalid subscription date")
            parsed = parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
            if parsed.timestamp() <= 0:
                raise ValueError("invalid subscription date")
            return parsed
        except (ValueError, OverflowError, OSError):
            raise ValueError("invalid subscription date") from None


def parse_subscription_term(payload: JsonValue, *, account_id: str, plan_type: str) -> datetime | None:
    records = payload.get("subscriptions", [payload]) if isinstance(payload, dict) else payload
    try:
        parsed = TypeAdapter(list[SubscriptionRecord]).validate_python(records)
    except ValidationError:
        raise SubscriptionFetchError("invalid_payload") from None
    dates: list[datetime] = []
    inactive = False
    for record in parsed:
        if record.account_id is not None and record.account_id != account_id:
            raise SubscriptionFetchError("identity_mismatch")
        plan = normalize_account_plan_type(record.plan_type) if record.plan_type is not None else plan_type
        if plan not in {plan_type, "free"}:
            raise SubscriptionFetchError("plan_mismatch")
        if (
            plan == "free"
            or record.is_active is False
            or record.active is False
            or record.status in {"inactive", "expired", "canceled", "cancelled", "unpaid", "incomplete_expired"}
        ):
            inactive = True
            continue
        if record.status is not None and record.status not in {"active", "trialing"}:
            raise SubscriptionFetchError("unknown_status")
        if record.active_until is not None:
            dates.append(record.active_until)
    if dates:
        return max(dates)
    if inactive:
        return None
    raise SubscriptionFetchError("missing_term")


async def fetch_subscription_term(
    *,
    access_token: str,
    account_id: str,
    plan_type: str,
    route: ResolvedUpstreamRoute | None,
    allow_direct_egress: bool = False,
) -> datetime | None:
    require_route_or_direct_egress_opt_in(
        route=route, allow_direct_egress=allow_direct_egress, operation="subscription refresh"
    )
    headers = {
        "Accept": "*/*",
        "Authorization": f"Bearer {access_token}",
        "chatgpt-account-id": account_id,
        "x-openai-target-path": _PATH,
        "x-openai-target-route": _PATH,
    }
    # This endpoint needs the browser TLS/HTTP profile, even when the normal
    # Codex transport works on the same account's proxy. Keep it endpoint-local.
    try:
        async with asyncio.timeout(_TIMEOUT_SECONDS):
            async with AsyncSession(
                impersonate="chrome136",
                proxy=route.proxy_url if route else None,
                timeout=_TIMEOUT_SECONDS,
                verify=True,
                allow_redirects=False,
                trust_env=False,
            ) as client:
                response = await client.get(
                    f"https://chatgpt.com{_PATH}?account_id={quote(account_id, safe='')}", headers=headers
                )
                if not 200 <= response.status_code < 300:
                    raise SubscriptionFetchError("http_error", response.status_code)
                return parse_subscription_term(response.json(), account_id=account_id, plan_type=plan_type)
    except SubscriptionFetchError:
        raise
    except Exception:
        raise SubscriptionFetchError("request_failed") from None
