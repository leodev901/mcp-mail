from types import SimpleNamespace

import pytest
from loguru import logger
from mcp.types import CallToolRequestParams

from app.core.mcp_midleware import MCPLoggingMiddleware
from app.models.user_info import UserInfo


@pytest.mark.asyncio
async def test_mcp_logging_middleware_reads_trace_id_and_user_from_request_state(monkeypatch):
    middleware = MCPLoggingMiddleware()
    request = SimpleNamespace(
        state=SimpleNamespace(
            trace_id="trace-123",
            current_user=UserInfo(
                user_id="20075487",
                email="admin@leodev901.onmicrosoft.com",
                company_cd="leodev901",
            ),
        )
    )
    monkeypatch.setattr("app.core.mcp_midleware.get_http_request", lambda: request)

    context = SimpleNamespace(
        message=CallToolRequestParams(name="list_my_calendar_events", arguments={})
    )
    messages: list[str] = []
    sink_id = logger.add(messages.append, format="{message}")

    async def call_next(_context):
        return {"ok": True}

    try:
        result = await middleware.on_call_tool(context, call_next)
    finally:
        logger.remove(sink_id)

    assert result == {"ok": True}
    assert any("trace_id=trace-123" in message for message in messages)
    assert any('content={\n  "ok": true\n}' in message for message in messages)
    assert any("admin@leodev901.onmicrosoft.com" in message for message in messages)
    assert any("company_cd=leodev901" in message for message in messages)
