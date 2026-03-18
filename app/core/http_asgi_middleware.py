import asyncio
import json
import time
import uuid

from loguru import logger
from starlette.types import ASGIApp, Message, Receive, Scope, Send


HTTP_LOGGING_METHODS = {"tools/call", "tools/list"}

class HttpLoggingASGIMiddleware:
    """
    가장 기본적인 ASGI HTTP 미들웨어.

    1. 요청마다 trace_id, user_token, current_user를 기록하여 요청 시작부터 응답 스트림 종료까지 유지한다.
    2. request body / response body 로깅 위치를 잡아둔다.
    """


    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def _read_request_messages(
        self,
        receive: Receive,
    ) -> tuple[list[Message], bytes]:
        """
        요청 body를 끝까지 읽어서
        1. 원본 request message 목록
        2. 이어 붙인 body bytes를 같이 반환한다.
        """
        request_messages: list[Message] = []
        request_body_chunks: list[bytes] = []

        while True:
            message = await receive()
            request_messages.append(message)

            if message["type"] == "http.request":
                request_body_chunks.append(message.get("body", b""))
                if not message.get("more_body", False):
                    break
            else:
                break

        return request_messages, b"".join(request_body_chunks)
    

    def _build_body_for_log(self, body_bytes: bytes) -> dict | str | None:
        """
        body bytes를 로그에 남기기 쉬운 형태로 바꾼다.

        반환 우선순위:
        1. JSON dict면 dict
        2. JSON이지만 dict가 아니면 문자열
        3. 일반 텍스트면 문자열
        4. 디코드할 수 없으면 None
        """
        if not body_bytes:
            return None

        try:
            parsed_body = json.loads(body_bytes.decode("utf-8"))
            if isinstance(parsed_body, dict):
                return parsed_body
            return str(parsed_body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            try:
                return body_bytes.decode("utf-8")
            except UnicodeDecodeError:
                return None
    
    
    def _get_method_name(self, request_body: dict | str | None) -> str | None:
        if request_body is None:
            return None
        if isinstance(request_body, str):
            return None
        return request_body.get("method")
    

    def _is_http_logging_target(self, method_name: str | None) -> bool:
        return method_name in HTTP_LOGGING_METHODS
    

    def _log_http_message(self,
                    title,
                    scope,
                    trace_id,
                    client_ip,
                    status_code: int = None,
                    elapsed_ms: float = None,
                    headers: dict = None ,
                    body: dict | str = None,
                    error_message: str = None,
    ):
        log_meesage=f"{title} >>> trace_id={trace_id}"
        log_meesage+=f" method={scope['method']} path={scope['path']} ip={client_ip}"
        log_meesage+=f" status={status_code}" if status_code is not None else ""
        log_meesage+=f" elapsed_ms={elapsed_ms:.1f}" if elapsed_ms is not None else ""
        log_meesage+=f"\n - headers={headers}" if headers is not None else ""
        log_meesage+=f"\n - body={body}" if body is not None else ""
        log_meesage+=f"\n - error={error_message}" if error_message else ""
        logger.info(log_meesage)



    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """
        ASGI 미들웨어의 진입점.

        문법 설명:
        - scope: 이번 요청의 메타 정보다. method, path, headers 등이 들어 있다.
        - receive: 요청 body를 읽는 비동기 함수다.
        - send: 응답을 바깥으로 보내는 비동기 함수다.
        """
        # http가 아닌 요청은 PASS 해야 함 -> websocket, lifespan 등
        # FastAPI 전용이 아니라 ASGI 프로토콜 전체 위에서 동작하기 때문에 liefespan 등 패싱 해야 함
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # health check 에서는 미들웨어 로깅을 하지 않고 PASS
        if scope["path"] == "/api/health":
            await self.app(scope, receive, send)
            return
        

        started = time.perf_counter()
        client = scope.get("client")
        client_ip = client[0] if client else "unknown"

        # 헤더 bytes -> docode 사용
        headers: dict[str, str] = {}
        for key, value in scope.get("headers", []):
            headers[key.decode("latin-1")] = value.decode("latin-1")

        # request.state 에서 저장한 값 읽어오기
        state = scope.setdefault("state", {})
        trace_id = state.get("trace_id") or headers.get("x-request-id") or str(uuid.uuid4())

        # request body는 ASGI에서 한 번 읽으면 끝이므로,
        # 먼저 모두 읽어서 저장한 다음 downstream app에 다시 재생해야 한다.
        request_messages, request_body_bytes = await self._read_request_messages(receive)
        request_body_log = self._build_body_for_log(request_body_bytes)

        is_logging = self._is_http_logging_target(self._get_method_name(request_body_log))

        header_json = json.dumps(headers, ensure_ascii=False, indent=2)

        request_body_log_json = json.dumps(request_body_log, ensure_ascii=False, indent=2)

        # TO-DO logging: Rquest '요청' 로그를 저장 한다. 
        # /mcp 는 실제 처리 전 리다이렉트 전용 경로라 로그에서 제외한다.
        if is_logging:
            self._log_http_message(
                title="[http_request]",
                scope=scope,
                trace_id=trace_id,
                client_ip=client_ip,
                headers=header_json,
                body=request_body_log_json,
            )

        # 먼저 읽은 request 메시지를 앱이 다시 읽을 수 있게 재생한다.
        replay_index = 0
        response_done = asyncio.Event()

        async def replay_receive() -> Message:
            nonlocal replay_index

            if replay_index < len(request_messages):
                message = request_messages[replay_index]
                replay_index += 1
                return message

            # request body를 이미 모두 넘긴 뒤 receive()가 다시 불리면 보통 disconnect 감시
            # 응답이 끝날 때까지 기다렸다가 disconnect를 내려준다.
            await response_done.wait()
            return {"type": "http.disconnect"}

        response_status_code = 500
        response_headers: dict[str, str] = {}
        response_body_chunks: list[bytes] = []

        async def send_wrapper(message: Message) -> None:
            """
            - 상태코드 확인
            - 응답 헤더 확인
            - 응답 body 수집
            - 마지막 body 청크에서 cleanup 실행
            """
            nonlocal response_status_code, response_headers

            if message["type"] == "http.response.start":
                response_status_code = message["status"]

                raw_headers = list(message.get("headers", []))
                updated_headers: list[tuple[bytes, bytes]] = []
                request_id_header_found = False

                for key, value in raw_headers:
                    if key.lower() == b"x-request-id":
                        updated_headers.append((b"x-request-id", trace_id.encode("utf-8")))
                        request_id_header_found = True
                    else:
                        updated_headers.append((key, value))

                if not request_id_header_found:
                    updated_headers.append((b"x-request-id", trace_id.encode("utf-8")))

                message["headers"] = updated_headers

                for key, value in updated_headers:
                    response_headers[key.decode("latin-1")] = value.decode("latin-1")

            if message["type"] == "http.response.body":
                response_body_chunks.append(message.get("body", b""))

                # 스트리밍 종료
                if not message.get("more_body", False):

                    elapsed_ms = (time.perf_counter() - started) * 1000.0
                    response_body_bytes = b"".join(response_body_chunks)
                    response_body_log = self._build_body_for_log(response_body_bytes)

                    # if isinstance(response_body_log,dict):
                    #     response_body_log_json = json.dumps(response_body_log.get("data"), ensure_ascii=False, indent=2)
                    # else:
                    #     response_body_log_json = response_body_log

                    

                    # TO-DO logging:
                    # 여기서 response body / headers / status / elapsed_ms를 2차 로깅한다.
                    if is_logging:
                        self._log_http_message(
                            title="[http_response]",
                            scope=scope,
                            trace_id=trace_id,
                            client_ip=client_ip,
                            status_code=response_status_code,
                            elapsed_ms=elapsed_ms,
                            headers=response_headers,
                            body=response_body_log,
                        )

                    response_done.set()

            await send(message)

        try:
            # custom된 replay_receive, send_wrapper 으로 다음 호출을 넘긴다. 
            await self.app(scope, replay_receive, send_wrapper)

        except Exception:
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            if is_logging :
                self._log_http_message(
                    title="[http_request_failed]",
                    scope=scope,
                    trace_id=trace_id,
                    client_ip=client_ip,
                    elapsed_ms=elapsed_ms,
                    headers=headers,
                    body=request_body_log,
                    error_message="exception raised in downstream app",
                )
            logger.exception("downstream app raised an exception")
            response_done.set()
            raise
