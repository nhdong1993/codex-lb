"""Collect a source Responses stream into the standalone compact contract."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import cast

from pydantic import ValidationError

from app.core.clients.proxy import _proxy_response_error_from_compact_sse_terminal
from app.core.errors import openai_error
from app.core.openai.models import (
    CompactResponsePayload,
    ResponseUsage,
    ResponseUsageDetails,
    normalize_compaction_item_id,
)
from app.core.openai.requests import ResponsesCompactRequest, ResponsesRequest
from app.core.types import JsonValue
from app.core.utils.sse import parse_sse_data_json
from app.modules.model_sources.forwarding import ModelSourceForwardingError, SourceUsage, _usage_from_responses_event


def source_compact_request(payload: ResponsesCompactRequest) -> ResponsesRequest:
    # Keep source history before subscription-specific trimming/cleanup. V1's
    # compact contract collapses duplicate triggers; native ingress validates
    # their original placement before reaching here.
    data = payload.model_dump(mode="json", exclude_none=True)
    assert isinstance(payload.input, list)  # Request validation normalizes text into message items.
    data["input"] = [
        item for item in payload.input if not (isinstance(item, dict) and item.get("type") == "compaction_trigger")
    ] + [{"type": "compaction_trigger"}]
    data["stream"] = True
    data["store"] = False
    result = ResponsesRequest.model_validate(data)
    result._codex_lb_client_reasoning_effort = payload._codex_lb_client_reasoning_effort
    result._codex_lb_provider_reasoning_effort_materialized = payload._codex_lb_provider_reasoning_effort_materialized
    return result


def invalid_source_compaction(message: str) -> ModelSourceForwardingError:
    return ModelSourceForwardingError(
        status_code=502,
        upstream_status_code=200,
        payload=cast(dict[str, JsonValue], openai_error("invalid_upstream_response", message)),
    )


def _compaction_item(item: JsonValue) -> dict[str, JsonValue] | None:
    if not isinstance(item, dict) or item.get("type") not in ("compaction", "compaction_summary"):
        return None
    encrypted = item.get("encrypted_content")
    if not isinstance(encrypted, str) or not encrypted:
        return None
    normalized: dict[str, JsonValue] = {"type": "compaction", "encrypted_content": encrypted}
    item_id = normalize_compaction_item_id(item.get("id"))
    if item_id is not None:
        normalized["id"] = item_id
    if isinstance(status := item.get("status"), str) and status.strip():
        normalized["status"] = status
    return normalized


def _validated_terminal_usage(value: JsonValue) -> ResponseUsage | None:
    try:
        usage = ResponseUsage.model_validate(value)
    except ValidationError:
        return None
    if usage.input_tokens is None or usage.output_tokens is None:
        return None
    counters = [usage.input_tokens, usage.output_tokens, usage.total_tokens]
    for details in (usage.input_tokens_details, usage.output_tokens_details):
        if details is not None:
            counters.extend((details.cached_tokens, details.reasoning_tokens))
    if any(counter is not None and counter < 0 for counter in counters):
        return None
    return usage


async def collect_source_compaction(events: AsyncIterator[str], *, model: str) -> dict[str, JsonValue]:
    # Retain only the compact item and scalar usage, never buffer history/deltas.
    streamed_item: dict[str, JsonValue] | None = None
    observed_usage: SourceUsage | None = None
    async for block in events:
        event = parse_sse_data_json(block)
        if event is None:
            continue
        event_type = event.get("type")
        if event_type in ("response.failed", "response.incomplete", "error") or (
            event_type is None and isinstance(event.get("error"), dict)
        ):
            try:
                error = _proxy_response_error_from_compact_sse_terminal(event, str(event_type or "error"))
            except ValidationError:
                raise invalid_source_compaction("Invalid compact error envelope from model source") from None
            raise ModelSourceForwardingError(
                status_code=error.status_code,
                payload=cast(dict[str, JsonValue], error.payload),
                upstream_status_code=200,
            )
        # Parse complete events here as well: the lower-level stream observer
        # cannot capture usage in a terminal larger than its own buffer cap.
        observed_usage = _usage_from_responses_event(event) or observed_usage
        if event_type == "response.output_item.done":
            streamed_item = _compaction_item(event.get("item")) or streamed_item
        if event_type != "response.completed":
            continue
        response = event.get("response")
        if not isinstance(response, dict) or response.get("status") not in (None, "completed"):
            raise invalid_source_compaction("Invalid compact completion from model source")
        output = response.get("output")
        item = (
            next((parsed for raw in output if (parsed := _compaction_item(raw)) is not None), None)
            if isinstance(output, list)
            else None
        )
        item = item or streamed_item
        if item is None:
            raise invalid_source_compaction("Model source did not return encrypted compaction output")
        result: dict[str, JsonValue] = {
            "object": "response.compaction",
            "model": model,
            "status": "completed",
            "output": [item],
        }
        terminal_usage = response.get("usage")
        if terminal_usage is None:
            terminal_usage = event.get("usage")
        for key in ("id", "service_tier"):
            if key in response:
                result[key] = response[key]
        try:
            if terminal_usage is not None:
                # An invalid terminal leaves usage absent so limited-key settlement
                # fails closed; it must never resurrect valid earlier counters.
                if (usage := _validated_terminal_usage(terminal_usage)) is not None:
                    result["usage"] = usage.model_dump(mode="json", exclude_none=True)
            elif observed_usage is not None:
                result["usage"] = ResponseUsage(
                    input_tokens=observed_usage.input_tokens,
                    output_tokens=observed_usage.output_tokens,
                    total_tokens=observed_usage.input_tokens + observed_usage.output_tokens,
                    input_tokens_details=ResponseUsageDetails(cached_tokens=observed_usage.cached_input_tokens),
                    output_tokens_details=(
                        ResponseUsageDetails(reasoning_tokens=observed_usage.reasoning_tokens)
                        if observed_usage.reasoning_tokens is not None
                        else None
                    ),
                ).model_dump(mode="json", exclude_none=True)
            return CompactResponsePayload.model_validate(result).model_dump(mode="json", exclude_none=True)
        except ValidationError:
            raise invalid_source_compaction("Invalid compact response envelope from model source") from None
    raise invalid_source_compaction("Model source stream ended before compact completion")
