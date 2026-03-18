from types import SimpleNamespace

import pytest
from loguru import logger

from app.core.mcp_midleware import MCPLoggingMiddleware
from app.models.user_info import UserInfo


def _build_request(trace_id: str) -> SimpleNamespace:
    return SimpleNamespace(
        state=SimpleNamespace(
            trace_id=trace_id,
            current_user=UserInfo(
                user_id="20075487",
                email="admin@example.com",
                company_cd="leodev901",
            ),
        )
    )


@pytest.mark.asyncio
async def test_mcp_logging_middleware_logs_trace_id_and_arguments_on_success(monkeypatch):
    middleware = MCPLoggingMiddleware()
    monkeypatch.setattr(
        "app.core.mcp_midleware.get_http_request",
        lambda: _build_request("trace-123"),
    )
    context = SimpleNamespace(
        message=SimpleNamespace(
            name="list_calendar_events",
            arguments={"user_email": "admin@example.com", "top": 10},
        )
    )
    messages: list[str] = []
    sink_id = logger.add(messages.append, format="{message}")

    async def successful_call_next(_context):
        return {"ok": True}

    try:
        result = await middleware.on_call_tool(context, successful_call_next)
    finally:
        logger.remove(sink_id)

    assert result == {"ok": True}
    assert any("trace_id=trace-123" in message for message in messages)
    assert any("tool_name=list_calendar_events" in message for message in messages)
    assert any(
        "arguments={'user_email': 'admin@example.com', 'top': 10}" in message
        for message in messages
    )
    assert any('content={\n  "ok": true\n}' in message for message in messages)
    assert any("email=admin@example.com" in message for message in messages)
    assert any("company_cd=leodev901" in message for message in messages)


@pytest.mark.asyncio
async def test_mcp_logging_middleware_logs_trace_id_and_arguments_on_error(monkeypatch):
    middleware = MCPLoggingMiddleware()
    monkeypatch.setattr(
        "app.core.mcp_midleware.get_http_request",
        lambda: _build_request("trace-456"),
    )
    context = SimpleNamespace(
        message=SimpleNamespace(
            name="list_calendar_events",
            arguments={"start_date": "2026-03-01T00:00:00"},
        )
    )
    messages: list[str] = []
    sink_id = logger.add(messages.append, format="{message}")

    async def failing_call_next(_context):
        raise RuntimeError("tool failed")

    with pytest.raises(RuntimeError, match="tool failed"):
        try:
            await middleware.on_call_tool(context, failing_call_next)
        finally:
            logger.remove(sink_id)

    assert any("trace_id=trace-456" in message for message in messages)
    assert any("status=error" in message for message in messages)
    assert any(
        "arguments={'start_date': '2026-03-01T00:00:00'}" in message
        for message in messages
    )
    assert any("error=RuntimeError: tool failed" in message for message in messages)
    assert any("email=admin@example.com" in message for message in messages)
    assert any("company_cd=leodev901" in message for message in messages)
