# Logs API Count Guide

## 대상 코드

- `cmn/api/endpoint/logs_router.py`
- 함수: `get_api_log_count`

## 최근 10분 조건

```python
stmt = select(func.count()).select_from(M365McpApiLog).where(
    M365McpApiLog.provider == user,
    M365McpApiLog.created_at >= func.now() - text("interval '10 minutes'"),
)
```

`where()` 안에 조건을 여러 개 넣으면 SQL의 `AND` 조건으로 연결됩니다.
첫 번째 조건은 특정 사용자의 로그만 조회하고, 두 번째 조건은 생성 시간이 DB 서버 현재 시각 기준 최근 10분 이내인 로그만 남깁니다.

## 왜 DB 시간 기준을 사용하는가

`func.now()`는 애플리케이션 서버 시간이 아니라 DB 서버의 현재 시간을 사용합니다.
로그의 `created_at`도 DB에서 기본값으로 생성되므로, 같은 시간 기준으로 비교하는 편이 더 명시적입니다.

## 대안

Python에서 `datetime.now(timezone.utc) - timedelta(minutes=10)` 값을 만들어 비교할 수도 있습니다.
이 방식은 DB 종류와 무관하게 읽기 쉽지만, 앱 서버와 DB 서버의 시간이 어긋나면 결과가 달라질 수 있습니다.
