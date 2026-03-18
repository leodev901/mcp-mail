from typing import Optional
import os
import platform

from loguru import logger
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.resources import Resource

import base64
import logging


from app.core.config import settings
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
# from opentelemetry.exporter.otlp.proto.grpc.log_exporter import OTLPLogExporter

_open_telemetry_provider: Optional[LoggerProvider] = None


def _init_open_telemetry_provider() -> None:
    """
    OpenTelemetry(OPTL) 초기화 함수
    오픈텔레메트리(OpenTelemetry)는 다양한 환경에서 발생하는 로그, 메트릭, 추적(Trace) 데이터를
    표준화된 방식으로 수집하는 도구입니다.
    """
    global _open_telemetry_provider

    if _open_telemetry_provider is None:
        # 1. Resource 설정: '누가' 로그를 생성했는지 신분증을 만듭니다.
        # 서비스의 이름, 버전, 그리고 실행 중인 컨테이너/서버 아이디를 기록합니다.
        _open_telemetry_provider = LoggerProvider(
            resource=Resource.create(
                {
                    "service.name": "mcp-sample",
                    "service.version": "1.0.0",
                    "service.instance.id": os.getenv("POD_NAME", platform.node()),
                }
            )
        )

        # Grafana Cloud용 인증 토큰(Basic Auth) 만들기
        username = settings.GRAFANA_INSTANCE_ID.strip()
        password = settings.GRAFANA_API_TOKEN.strip()
        auth_string = base64.b64encode(f"{username}:{password}".encode()).decode()

        # 2. Exporter 설정: 수집된 로그를 '어디로' 보낼지 결정합니다.
        # 여기서는 Grafana(그라파나) 엔드포인트로 설정하여 로그를 전송합니다.
        exporter = OTLPLogExporter(
            # endpoint=settings.GRAFANA_ENDPOINT,
            # insecure=True # HTTPS가 아닌 HTTP 통신을 허용합니다 (보안이 확실한 내부망에서 주로 사용)

            # leodev901 grafana 연결하기
            endpoint=settings.GRAFANA_ENDPOINT,
            # insecure 매개변수 삭제 (URL의 https://를 보고 자동 판단함)
            headers={"Authorization": f"Basic {auth_string}"} # 헤더 키를 대문자로 변경
        )

        # 3. Processor 설정: 로그를 건건이 보내서 성능이 떨어지는 것을 막고자,
        # 상자에 '모아서(Batch)' 한 번에 효율적으로 전송(Export)하도록 설정합니다.
        _open_telemetry_provider.add_log_record_processor(
            BatchLogRecordProcessor(exporter)
        )

        # 4. 전역 Provider로 등록: 
        # OpenTelemetry 시스템이 이제부터 위에서 만든 설정을 사용하도록 적용합니다.
        set_logger_provider(_open_telemetry_provider)
        
        print(f"✅ OpenTelemetry(OTLP) Exporter initialized. [Service: mcp-sample]")
        print(f"   - Endpoint: {settings.GRAFANA_ENDPOINT}")



def init_logger() -> None:
    """
    애플리케이션 전역 로거를 초기화하는 함수
    로컬 환경이 아닐 때만 OpenTelemetry를 연결하여 그라파나로 로그를 보냅니다.
    """
    global _open_telemetry_provider

    # Grafana 설정이 있는 경우 강제로 활성화하거나, 'local'이 아닐 때 작동
    is_grafana_configured = bool(settings.GRAFANA_ENDPOINT and settings.GRAFANA_API_TOKEN)
    
    if _open_telemetry_provider is None and (is_grafana_configured or getattr(settings, "ENV", "local") != "local"):
        _init_open_telemetry_provider() # 위에서 만든 OPTL 초기화 로직 실행

        # 5. Handler 설정: 기존 파이썬/Loguru 로깅 시스템과 OpenTelemetry를 연결해주는 다리(Handler)를 만듭니다.
        handler = LoggingHandler(
            level=logging.DEBUG, # DEBUG 레벨 이상의 모든 로그를 가져오겠다는 뜻입니다.
            logger_provider=_open_telemetry_provider
        )

        # 6. Loguru에 추가: 이렇게 하면 앞으로 애플리케이션 안에서 `logger.info("...")`를 쓸 때마다 
        # 콘솔 화면에도 출력되고, 동시에 핸들러 다리를 타고 그라파나로도 안전하게 전송됩니다.
        logger.add(handler)