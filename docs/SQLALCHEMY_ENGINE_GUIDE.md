# SQLAlchemy Engine Guide

## 문제 정의
- `sqlalchemy.exit.asyncio`처럼 잘못된 import 경로를 쓰면 `ModuleNotFoundError`가 발생한다.
- FastAPI의 `lifespan`은 시작과 종료 시점의 자원 관리를 담당하므로, 비동기 엔진 생성과 정리를 여기에 두는 것이 자연스럽다.

## 접근 방법
- `AsyncEngine`와 `create_async_engine`은 `sqlalchemy.ext.asyncio`에서 import한다.
- `create_async_engine()`을 쓰면 PostgreSQL도 비동기 드라이버가 필요하므로 `postgresql+asyncpg://...` 형식을 사용한다.
- 앱 시작 시 `create_engine()`으로 엔진을 만들고, 종료 시 `await engine.dispose()`로 정리한다.
- `@asynccontextmanager`를 사용해 `lifespan`을 명시적인 컨텍스트 매니저로 만든다.

## 코드

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from cmn.core.config import settings


# 환경 변수에서 읽은 DB 주소를 엔진 생성에 사용한다.
DATABASE_URL = settings.DATABASE_URL


def create_engine() -> AsyncEngine:
    # 비동기 DB 연결 풀을 생성한다.
    # URL의 `postgresql+asyncpg://` 부분이 async 드라이버 선택을 결정한다.
    return create_async_engine(DATABASE_URL, echo=True, future=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup 구간: 앱이 뜰 때 엔진을 만든다.
    engine = create_engine()
    app.state.engine = engine

    # shutdown 구간은 yield 이후에 실행된다.
    yield

    # 종료 시 연결 풀을 닫아 리소스를 정리한다.
    await engine.dispose()
```

## 검증
- `python -m cmn.main` 또는 `uvicorn cmn.main:app` 실행 시 import 에러가 없어야 한다.
- `DATABASE_URL`은 `postgresql+asyncpg://` 형식이어야 한다.
- 앱 종료 시 `dispose()`가 호출되어야 한다.
- `DATABASE_URL`이 비어 있으면 SQLAlchemy 초기화 오류가 날 수 있으므로 `.env`를 확인한다.

## 한 줄 요약
- 올바른 import 경로는 `sqlalchemy.ext.asyncio`이고, 비동기 엔진은 `lifespan`에서 생성과 정리를 묶는 것이 안전하다.
