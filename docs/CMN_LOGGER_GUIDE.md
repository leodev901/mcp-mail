# CMN_LOGGER_GUIDE

## 개요

`cmn/base/logger.py`는 `logging` 표준 라이브러리 기반 공통 로거를 생성합니다.

- 콘솔 로그: `StreamHandler`
- 파일 로그: `TimedRotatingFileHandler`
- 공유 방식: 모듈 import 시 싱글톤처럼 1회 생성

관련 코드 경로:
- `cmn/base/logger.py`
- `cmn/core/config.py`

## 현재 정책

- `LOG_LEVEL`, `LOG_FILE_PATH`는 `Settings`에서 읽습니다.
- 파일 로그는 자정 기준 `interval=10`으로 회전합니다.
- 백업 로그는 `backupCount=6`개까지만 유지합니다.
- `logger.propagate = False`로 상위 로거 중복 전파를 막습니다.

## 왜 이렇게 구성했는가

- 표준 `logging`은 FastAPI, uvicorn, OTLP 연동과 궁합이 좋습니다.
- 지금 서비스는 실행 중 로거를 재초기화할 일이 거의 없어서 import 시점 싱글톤 구성이 단순합니다.
- 콘솔과 파일을 함께 남기면 로컬 디버깅과 운영 수집을 둘 다 대응하기 쉽습니다.
