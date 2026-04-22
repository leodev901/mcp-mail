# DATABASE_SESSION_GUIDE.md

## 목적
- `cmn/core/database.py` 의 `Database.session()` 함수가 왜 필요한지 빠르게 이해하기 위한 가이드입니다.

## 문제 정의
- 멀티 테넌트 환경에서는 회사별 schema 를 바꿔가며 조회해야 합니다.
- 동시에 외부 API 호출 전까지 DB 세션을 짧게 쓰고 바로 반환해야 커넥션 점유를 줄일 수 있습니다.

## 접근 방법
- `Database.session(schema)` 는 `async with` 문법으로 짧게 세션을 열고 닫게 합니다.
- `schema` 가 있으면 `search_path` 를 바꿔 해당 schema 를 기본 schema 처럼 조회합니다.

## 코드 예시
```python
async with db.session("company_a") as session:
    repo = AuthRepository(session)
    graph_infos = await repo.get_graph_infos("MAIL")
```

## SET LOCAL 과 SET 차이
- `SET LOCAL search_path TO company_a`
- 현재 트랜잭션 안에서만 유효합니다.
- 트랜잭션 종료 후 원래 상태로 돌아갑니다.
- 요청 단위 schema 전환에서는 이쪽이 더 안전합니다.

- `SET search_path TO company_a`
- 현재 DB 연결에 설정이 남습니다.
- 같은 연결을 pool 이 재사용하면 다음 요청도 이전 schema 를 볼 수 있습니다.

## 왜 이렇게 했는지
- DB 조회가 끝나면 세션을 닫고 커넥션을 빨리 반환하기 위해서입니다.
- 멀티 테넌트 환경에서 schema 설정이 다른 요청으로 새어나가는 위험을 줄이기 위해서입니다.

## 검증
- `async with` 블록 종료 후 세션이 닫히는지 확인합니다.
- 외부 API 호출 전에 DB 세션 구간이 끝나는지 로그로 확인합니다.
- schema 값은 허용 목록으로 검증하는 것이 안전합니다.

## 한 줄 요약
- `Database.session()` 은 짧은 DB 사용 구간을 만들기 위한 도우미이고, 요청 단위 schema 전환에는 보통 `SET LOCAL` 이 더 안전합니다.
