from __future__ import annotations

from app.core.clock import Clock
from app.modules.api_keys.service import ApiKeyData
from app.modules.proxy._service.http_bridge.helpers import (
    _http_bridge_session_matches_preferred_account,
    _http_bridge_session_retiring_with_visible_requests,
)
from app.modules.proxy._service.support import _HTTPBridgeSession, _HTTPBridgeSessionKey
from app.modules.proxy.continuity import is_http_bridge_account_neutral_replay, resolve_required_account_id


def _retire_model_excluded_session(session: _HTTPBridgeSession, model_excluded: bool) -> bool:
    if model_excluded:
        # Stop admitting new work to this generation, but keep lifecycle
        # ownership until accepted requests and reserved handoffs drain.
        session.upstream_control.reconnect_requested = True
        session.upstream_control.retire_after_drain = True
    return _http_bridge_session_retiring_with_visible_requests(session)


def _is_required_owner(
    session: _HTTPBridgeSession | None,
    key: _HTTPBridgeSessionKey,
    preferred_account_id: str | None,
    require_preferred_account: bool,
    previous_response_id: str | None,
    force_reselection: bool,
) -> bool:
    return (
        not force_reselection
        and session is not None
        and (require_preferred_account or previous_response_id is not None or key.strength == "hard")
        and _http_bridge_session_matches_preferred_account(
            session=session,
            previous_response_id=previous_response_id,
            preferred_account_id=preferred_account_id,
            require_preferred_account=require_preferred_account,
        )
    )


def _bind_recovery_owner(session: _HTTPBridgeSession, preferred_account_id: str | None) -> str | None:
    if not is_http_bridge_account_neutral_replay(kind=session.key.affinity_kind, key=session.key.affinity_key):
        return preferred_account_id
    return resolve_required_account_id(
        ("requested continuity owner", preferred_account_id),
        ("local account-neutral recovery", session.account.id),
    )


def _touch_reused_session(
    session: _HTTPBridgeSession,
    api_key: ApiKeyData | None,
    model: str | None,
    service_tier: str | None,
    clock: Clock,
) -> None:
    session.api_key = api_key
    session.request_model = model
    session.request_service_tier = service_tier
    session.last_used_at = clock.monotonic()
