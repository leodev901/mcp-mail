import asyncio
import httpx    
from typing import Optional
from loguru import logger
import time



http_client: Optional[httpx.AsyncClient] = None
httpx_client_lock = asyncio.Lock()

async def get_httpx_client() -> httpx.AsyncClient:
    global http_client
    if http_client is None:
        async with httpx_client_lock:
            if http_client is None:
                http_client = httpx.AsyncClient()
    return http_client

async def close_httpx_client() -> None:
    global http_client
    if http_client is not None:
        await http_client.aclose()
        http_client = None

async def httpx_log_request(request: httpx.Request) -> None:
    request.extensions["start_time"] = time.perf_counter()
    logger.info(f"[HTTP Request] {request.method} {request.url}")

async def httpx_log_response(response: httpx.Response) -> None:
    request = response.request
    start = request.extensions.get("start_time")
    elapsed = (time.perf_counter() - start ) if start else "?"

    logger.info(
        f"[HTTP Response] {request.method} {request.url}"
        f" - status_code: {response.status_code}, elapsed: {elapsed:.2f}s"
    )