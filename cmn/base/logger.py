import logging 
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from cmn.core.config import settings


def get_logger(
    name: str = "mcp-cmn",
    level: str = "INFO",
    log_file_path: str = "logs/mcp-cmn.log",
) -> logging.Logger:
    # getLogger(name)은 같은 name이면 같은 Logger 인스턴스를 다시 돌려줍니다.
    # 그래서 이 함수는 "앱 전체에서 같은 로거를 재사용"하는 싱글톤 스타일에 가깝게 동작합니다.
    logger = logging.getLogger(name)
    logger.setLevel( getattr(logging, level.upper(), logging.INFO) )

    
    # 이미 handler가 있으면 다시 붙이지 않습니다.
    # 왜냐하면 같은 handler를 중복 추가하면 로그가 한 번 찍힐 때 여러 줄로 중복 출력되기 때문입니다.
    if logger.handlers:
        return logger

    # Formatter
    # %(...)s 문법은 logging이 LogRecord 값을 문자열로 치환할 때 사용하는 포맷 플레이스홀더입니다.
    # 파일명과 라인번호를 함께 남겨야 운영 중 로그만 보고도 원인 위치를 빨리 찾기 쉽습니다.
    formatter = logging.Formatter(
        '[%(levelname)s][%(asctime)s][%(name)s][%(filename)s:%(lineno)d]- %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )

    # StreamHandler
    # StreamHandler는 콘솔(stdout/stderr)로 로그를 보내는 가장 기본적인 handler 입니다.
    # 컨테이너 환경에서는 콘솔 로그를 수집기로 넘기는 경우가 많아서 보통 함께 둡니다.
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel( getattr(logging, level.upper(), logging.INFO) )
    logger.addHandler(stream_handler)

    # FileHandelr
    if log_file_path:
        # mkdir(..., exist_ok=True)는 폴더가 이미 있어도 에러 없이 넘어가는 문법입니다.
        # 로그 파일 디렉터리가 없어서 앱 시작이 실패하지 않도록 먼저 폴더를 보장합니다.
        Path(log_file_path).parent.mkdir(parents=True, exist_ok=True)

        # TimedRotatingFileHandler는 시간 기준으로 로그 파일을 회전합니다.
        # 여기서는 자정 기준으로 10일마다 새 파일로 바꾸고, 백업 로그는 6개까지만 유지합니다.
        file_handler = TimedRotatingFileHandler(
            log_file_path, 
            when="midnight", 
            encoding="utf-8",
            interval=10,
            utc=False,
            backupCount=6,
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel( getattr(logging, level.upper(), logging.INFO) )
        logger.addHandler(file_handler)

    return logger

LOG_LEVEL = getattr(settings, "LOG_LEVEL", "INFO")
LOG_FILE_PATH = getattr(settings, "LOG_FILE_PATH", "logs/mcp-cmn.log")

# 모듈 import 시 한 번만 생성해서 다른 파일에서 같은 로거를 공유합니다.
logger = get_logger(name="mcp-cmn",level=LOG_LEVEL, log_file_path=LOG_FILE_PATH)
# logger.setLevel(...)
# propagate=False는 상위(root) 로거로 로그 이벤트를 다시 전달하지 않겠다는 뜻입니다.
# 상위 로거까지 전파되면 콘솔에 같은 로그가 중복 출력될 수 있어서 여기서 끊습니다.
logger.propagate = False
