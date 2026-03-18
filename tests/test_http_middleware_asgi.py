import asyncio

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient

from app.core.http_ASGI_middware import HttpLoggingASGIMiddleware


def test_http_logging_asgi_keeps_trace_id_until_stream_end():
    app = FastAPI()
    app.add_middleware(HttpLoggingASGIMiddleware)

    captured_trace_ids: list[str] = []

    @app.post("/mcp/")
    async def mcp_endpoint(request: Request):
        await request.body()

        async def body_stream():
            captured_trace_ids.append(getattr(request.state, "trace_id", "-"))
            yield b'{"chunk": 1}'
            await asyncio.sleep(0)
            captured_trace_ids.append(getattr(request.state, "trace_id", "-"))
            yield b'{"chunk": 2}'

        return StreamingResponse(body_stream(), media_type="text/event-stream")

    client = TestClient(app)
    response = client.post("/mcp/", json={"jsonrpc": "2.0", "method": "tools/list"})

    assert response.status_code == 200
    assert "x-request-id" in response.headers
    assert len(captured_trace_ids) == 2
    assert captured_trace_ids[0] != "-"
    assert captured_trace_ids[0] == captured_trace_ids[1]
