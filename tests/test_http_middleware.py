from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from loguru import logger

from app.core.http_middleware import HttpLoggingMiddleware


def test_http_logging_middleware_passes_mcp_request():
    app = FastAPI()
    app.add_middleware(HttpLoggingMiddleware)

    @app.post("/mcp")
    async def mcp_endpoint():
        return {"ok": True}

    client = TestClient(app)
    response = client.post("/mcp", json={"jsonrpc": "2.0", "method": "ping"})

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_http_logging_middleware_replays_body_for_mcp_tool_call():
    app = FastAPI()
    app.add_middleware(HttpLoggingMiddleware)

    @app.post("/mcp")
    async def mcp_endpoint(request: Request):
        return await request.json()

    client = TestClient(app)
    messages: list[str] = []
    sink_id = logger.add(messages.append, format="{message}")

    try:
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "list_calendar_events"},
            },
        )
    finally:
        logger.remove(sink_id)

    assert response.status_code == 200
    assert response.json()["method"] == "tools/call"
    assert any("'method': 'tools/call'" in message for message in messages)


def test_http_logging_middleware_logs_body_for_tools_list():
    app = FastAPI()
    app.add_middleware(HttpLoggingMiddleware)

    @app.post("/mcp")
    async def mcp_endpoint(request: Request):
        return await request.json()

    client = TestClient(app)
    messages: list[str] = []
    sink_id = logger.add(messages.append, format="{message}")

    try:
        response = client.post("/mcp", json={"jsonrpc": "2.0", "method": "tools/list"})
    finally:
        logger.remove(sink_id)

    assert response.status_code == 200
    assert response.json()["method"] == "tools/list"
    assert any("'method': 'tools/list'" in message for message in messages)


def test_http_logging_middleware_does_not_log_body_for_non_http_logging_method():
    app = FastAPI()
    app.add_middleware(HttpLoggingMiddleware)

    @app.post("/mcp")
    async def mcp_endpoint(request: Request):
        return await request.json()

    client = TestClient(app)
    messages: list[str] = []
    sink_id = logger.add(messages.append, format="{message}")

    try:
        response = client.post("/mcp", json={"jsonrpc": "2.0", "method": "ping"})
    finally:
        logger.remove(sink_id)

    assert response.status_code == 200
    assert response.json()["method"] == "ping"
    assert any("body=None" in message for message in messages)
