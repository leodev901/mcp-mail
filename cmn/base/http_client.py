
import asyncio
import time
from typing import Optional

import httpx
from httpx import Timeout, Limits
from cmn.base.logger import logger

# httpx.AsyncClient는 내부적으로 커넥션 풀을 관리합니다.
# 외부 API를 호출할 때마다 새 client를 만들면 연결 생성 비용이 커지므로,
# cmn 서버 전체에서 하나의 client를 재사용하도록 전역 변수에 보관합니다.
httpx_client: Optional[httpx.AsyncClient] = None

# 동시에 여러 요청이 들어와 최초 client 생성을 같이 시도할 수 있습니다.
# asyncio.Lock은 "처음 한 번만 생성"되도록 비동기 임계 구역을 보호합니다.
httpx_client_lock = asyncio.Lock()


async def get_httpx_client() -> httpx.AsyncClient:
    # 전역 변수에 저장된 client를 읽고 갱신해야 하므로 global을 선언합니다.
    global httpx_client

    # 이미 생성된 client가 있으면 바로 반환합니다.
    # 대부분의 요청은 이 경로를 타기 때문에 매번 lock을 기다리지 않습니다.
    if httpx_client is None:
        async with httpx_client_lock:
            # lock을 기다리는 동안 다른 coroutine이 먼저 client를 만들 수 있습니다.
            # 그래서 lock 안에서도 한 번 더 None인지 확인하는 double-check 패턴을 사용합니다.
            if httpx_client is None:
                httpx_client = httpx.AsyncClient(
                    # Timeout은 외부 API 호출이 무한정 대기하지 않도록 제한합니다.
                    # 전체 timeout과 단계별 timeout을 함께 두면 장애 상황에서 서버 자원이 묶이는 것을 줄일 수 있습니다.
                    timeout=Timeout(
                        timeout=60.0,  # 전체 요청 타임아웃입니다.
                        connect=10.0,  # TCP 연결을 맺는 데 허용할 최대 시간입니다.
                        read=10.0,     # 응답 데이터를 읽는 데 허용할 최대 시간입니다.
                        write=10.0,    # 요청 데이터를 쓰는 데 허용할 최대 시간입니다.
                        pool=5.0,      # 커넥션 풀에서 빈 연결을 기다리는 최대 시간입니다.
                    ),
                    # Limits는 동시에 열 수 있는 연결 수와 재사용 가능한 keep-alive 연결 수를 제한합니다.
                    # 제한을 두면 외부 API 장애나 트래픽 급증 시 연결이 무한히 늘어나는 것을 막을 수 있습니다.
                    limits=Limits(
                        max_connections=100,
                        max_keepalive_connections=10,
                        keepalive_expiry=30.0,
                    ),
                    # OAuth나 외부 API가 302/307 리다이렉트를 줄 수 있으므로 자동으로 따라가게 합니다.
                    follow_redirects=True,
                    # event_hooks는 httpx 요청/응답 생명주기에 함수들을 끼워 넣는 기능입니다.
                    # 여기서는 모든 외부 HTTP 호출에 공통 로깅을 적용하기 위해 사용합니다.
                    event_hooks={
                        "request": [httpx_log_request],
                        "response": [httpx_log_response],
                    },
                    # 개발/사내망 환경에서 인증서 검증 이슈를 우회하기 위한 설정입니다.
                    # 운영 환경에서는 보안상 verify=True 또는 신뢰할 CA 인증서 지정이 더 안전합니다.
                    verify=False,
                )
    return httpx_client


async def httpx_client_close() -> None:
    # FastAPI lifespan 종료 시점에서 호출해 커넥션 풀을 정리합니다.
    # 닫지 않으면 열린 연결이 남아 리소스 누수나 종료 지연이 생길 수 있습니다.
    global httpx_client
    if httpx_client is not None:
        await httpx_client.aclose()
        httpx_client = None


async def httpx_log_request(request: httpx.Request) -> None:
    # request.extensions는 httpx 요청 객체에 사용자 데이터를 임시로 저장하는 dict입니다.
    # 요청 hook에서 시작 시간을 저장해 두면, 응답 hook에서 총 소요 시간을 계산할 수 있습니다.
    request.extensions["start_time"] = time.perf_counter()
    logger.info(f"[Httpx Request] {request.method} {request.url}")


async def httpx_log_response(response: httpx.Response) -> None:
    # 응답 객체에서 원래 요청 객체를 다시 꺼낼 수 있습니다.
    # 요청 hook에서 저장한 start_time을 읽어 외부 API 호출 시간을 ms 단위로 남깁니다.
    request = response.request
    start = request.extensions["start_time"]
    duration = (time.perf_counter() - start) * 1000 if start else "?"

    # 외부 API 장애 분석에는 method, url, status_code, duration이 기본 단서가 됩니다.
    logger.info(f"[Httpx Response] {request.method} {request.url} -> {response.status_code} {duration:.2f}ms")




