import asyncio
import httpx    
from typing import Optional
from loguru import logger
import time


# httpx.AsyncClient는 내부적으로 커넥션 풀을 가집니다.
# 요청마다 새로 만들면 TCP/TLS 연결을 계속 새로 열게 되므로, 앱 전체에서 하나를 재사용합니다.
http_client: Optional[httpx.AsyncClient] = None

# 여러 비동기 요청이 동시에 최초 client 생성을 시도할 수 있습니다.
# Lock은 "처음 한 번만 생성"되도록 임계 구역을 보호합니다.
httpx_client_lock = asyncio.Lock()

async def get_httpx_client() -> httpx.AsyncClient:
    # 전역 변수에 저장된 client를 읽고/갱신해야 하므로 global을 선언합니다.
    global http_client

    # 이미 생성된 client가 있으면 락 없이 바로 반환합니다.
    # 대부분의 요청은 이 경로를 타기 때문에 불필요한 lock 대기를 줄일 수 있습니다.
    if http_client is None:
        async with httpx_client_lock:
            # lock을 기다리는 동안 다른 coroutine이 먼저 만들었을 수 있습니다.
            # 그래서 lock 안에서도 한 번 더 None인지 확인합니다.
            if http_client is None:
                http_client = httpx.AsyncClient()
    return http_client

async def close_httpx_client() -> None:
    # FastAPI lifespan이나 앱 종료 시점에서 호출해 커넥션 풀을 정리합니다.
    # 닫지 않으면 열린 커넥션이 남아 리소스 누수가 생길 수 있습니다.
    global http_client
    if http_client is not None:
        await http_client.aclose()
        http_client = None

async def httpx_log_request(request: httpx.Request) -> None:
    # event hook에서 요청 시작 시간을 request.extensions에 저장합니다.
    # extensions는 httpx가 요청/응답 사이에 사용자 데이터를 전달할 때 쓰는 dict입니다.
    request.extensions["start_time"] = time.perf_counter()
    logger.info(f"[HTTP Request] {request.method} {request.url}")

async def httpx_log_response(response: httpx.Response) -> None:
    # 응답 hook에서는 response.request로 원래 요청 객체에 접근할 수 있습니다.
    # 요청 hook에서 저장한 start_time을 읽어 외부 API 호출 시간을 계산합니다.
    request = response.request
    start = request.extensions.get("start_time")
    elapsed = (time.perf_counter() - start ) if start else "?"

    # 외부 HTTP 호출은 장애 추적에 중요하므로 method, url, status, elapsed를 함께 남깁니다.
    logger.info(
        f"[HTTP Response] {request.method} {request.url}"
        f" - status_code: {response.status_code}, elapsed: {elapsed:.2f}s"
    )
