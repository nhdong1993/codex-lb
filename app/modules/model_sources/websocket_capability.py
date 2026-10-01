"""Conservative catalog and installer policy over the complete permitted pool."""

from __future__ import annotations

from app.core.config.settings_cache import get_settings_cache
from app.db.models import ModelSource
from app.db.session import get_background_session
from app.modules.api_keys.service import ApiKeyData
from app.modules.model_sources.catalog import source_websocket_models
from app.modules.model_sources.repository import ModelSourcesRepository
from app.modules.model_sources.selection import (
    allowed_source_ids_for_api_key,
    effective_model_for_api_key,
    responses_source_model_candidates,
)
from app.modules.proxy._service.support import configured_upstream_stream_transport
from app.modules.proxy.request_policy import model_alias_requests_fast_mode, resolve_model_alias


def source_websocket_capabilities(
    sources: list[ModelSource], api_key: ApiKeyData | None, *, prohibit_fast_mode: bool
) -> dict[str, bool]:
    """Evaluate advertised names against the pool their requests actually select."""
    allowed = allowed_source_ids_for_api_key(api_key)
    sources = [source for source in sources if source.is_enabled and (allowed is None or source.id in allowed)]
    models = source_websocket_models(sources)
    names = set(models)
    if api_key is not None:
        names.update(api_key.allowed_models or ())
        if api_key.enforced_model:
            names.add(api_key.enforced_model)
    capabilities: dict[str, bool] = {}
    for name in names:
        raw_model = effective_model_for_api_key(api_key, name) or name
        model = resolve_model_alias(raw_model) or raw_model
        if prohibit_fast_mode and model_alias_requests_fast_mode(raw_model):
            raw_model = model
        candidates = responses_source_model_candidates(model, api_key, raw_model=raw_model)
        for candidate in candidates:
            if candidate in models:
                capabilities[name] = models[candidate]
                break
    return capabilities


async def source_only_key_supports_websockets(api_key: ApiKeyData) -> bool:
    if not (api_key.assigned_source_ids and not api_key.assigned_account_ids):
        return True
    settings = await get_settings_cache().get()
    if configured_upstream_stream_transport(settings) == "http":
        return False
    async with get_background_session() as session:
        sources = await ModelSourcesRepository(session).list_enabled_sources()
        models = source_websocket_capabilities(sources, api_key, prohibit_fast_mode=settings.prohibit_fast_mode)
    if api_key.enforced_model:
        models = {name: flag for name, flag in models.items() if name == api_key.enforced_model}
    elif api_key.allowed_models:
        models = {name: flag for name, flag in models.items() if name in api_key.allowed_models}
    return bool(models) and all(models.values())
