import logging
import os
import platform
from typing import Optional

from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.resources import Resource

from cmn.base.logger import logger
from cmn.core.config import settings


_open_telemetry_provider: Optional[LoggerProvider] = None
_open_telemetry_handler: Optional[logging.Handler] = None


def setup_opentelemetry() -> None:
    """
    Direct OTLP 로그 전송을 1회만 초기화합니다.

    현재 템플릿의 역할:
    - cmn logger에 OpenTelemetry LoggingHandler를 붙인다.
    - Python 로그를 OTLP HTTP endpoint로 직접 전송한다.
    """
    global _open_telemetry_provider, _open_telemetry_handler

    if not settings.ENABLE_OTEL_DIRECT:
        logger.info("OpenTelemetry direct export is disabled.")
        return

    # 왜 이렇게 했는지:
    # - OpenTelemetry global logger provider는 프로세스 안에서 보통 1회만 설정합니다.
    # - 같은 프로세스에 다시 중복 초기화하면 handler 중복, exporter 중복 전송이 날 수 있습니다.
    if _open_telemetry_provider is not None:
        logger.info("OpenTelemetry provider is already initialized.")
        return

    # .env에 이미 쓰고 있는 GRAFANA_* 설정을 그대로 사용합니다.
    # 변수명을 이중으로 두면 운영/개발 중 어떤 값을 써야 하는지 혼란이 커져서 단일 설정으로 맞춥니다.
    endpoint = settings.GRAFANA_ENDPOINT.strip()
    if not endpoint:
        logger.info("OpenTelemetry endpoint is empty. Skip initialization.")
        return

    token = settings.GRAFANA_API_TOKEN.strip()
    headers = None
    if token:
        # 현재 direct 템플릿은 Bearer 토큰 방식으로 Grafana OTLP endpoint에 붙는 것을 기준으로 합니다.
        headers = {"Authorization": f"Bearer {token}"}

    service_name = settings.OTEL_SERVICE_NAME.strip() or settings.APP_NAME.strip() or "mcp-cmn"
    resource = Resource.create(
        {
            "service.name": service_name,
            "service.version": settings.OTEL_SERVICE_VERSION.strip() or "1.0.0",
            "service.instance.id": os.getenv("POD_NAME", platform.node()),
            "deployment.environment": settings.ENV,
        }
    )

    # Resource.create(...)는 이 프로세스가 어떤 서비스인지 식별하는 메타데이터를 만듭니다.
    # 나중에 Grafana나 Collector에서 어떤 서비스 로그인지 구분할 때 핵심 정보가 됩니다.
    provider = LoggerProvider(resource=resource)
    exporter = OTLPLogExporter(
        endpoint=endpoint,
        headers=headers,
    )
    provider.add_log_record_processor(BatchLogRecordProcessor(exporter))

    # set_logger_provider(...)는 OpenTelemetry 전역 provider를 설정하는 문법입니다.
    # 이후 LoggingHandler가 이 provider를 통해 로그를 export 합니다.
    set_logger_provider(provider)

    otel_handler = LoggingHandler(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        logger_provider=provider,
    )

    # 같은 LoggingHandler가 중복으로 붙으면 로그 1건이 여러 번 export 될 수 있습니다.
    # 그래서 현재 logger.handlers 안에 같은 타입 handler가 있는지 먼저 검사합니다.
    if not any(isinstance(handler, LoggingHandler) for handler in logger.handlers):
        logger.addHandler(otel_handler)
        _open_telemetry_handler = otel_handler
    else:
        # 이미 같은 handler가 있으면 새 handler는 연결하지 않고 닫아 자원을 줄입니다.
        otel_handler.close()

    _open_telemetry_provider = provider

    logger.info(
        "OpenTelemetry direct exporter initialized. "
        f"service={service_name} endpoint={endpoint}"
    )


def shutdown_opentelemetry() -> None:
    """
    Direct OTLP 로그 전송 자원을 정리합니다.

    주의:
    - 이 함수는 주로 프로세스 종료 시점 정리를 위한 용도입니다.
    - Python OTel global provider는 프로세스 중간에 반복 재초기화하는 패턴보다
      시작/종료 수명주기로 다루는 것이 일반적입니다.
    """
    global _open_telemetry_provider, _open_telemetry_handler

    if _open_telemetry_handler is not None:
        logger.removeHandler(_open_telemetry_handler)
        _open_telemetry_handler.close()
        _open_telemetry_handler = None

    if _open_telemetry_provider is None:
        return

    # force_flush()는 배치 버퍼에 남아 있는 로그를 최대한 먼저 내보내려는 문법입니다.
    # shutdown()은 exporter / processor 자원을 정리해 종료 시 로그 유실을 줄입니다.
    _open_telemetry_provider.force_flush()
    _open_telemetry_provider.shutdown()
    _open_telemetry_provider = None
