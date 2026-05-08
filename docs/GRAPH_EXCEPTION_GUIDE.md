# Graph Exception Guide

## 목적

`app/common/exception.py` 의 Graph 예외는 MCP tool 호출 중 발생하는 것을 전제로 설계합니다.
FastMCP 의 `ToolError` 는 구조화 필드가 아니라 메시지 문자열 하나를 전달하므로, Graph 예외가 최종 출력 문자열을 직접 만듭니다.

## 흐름

```mermaid
flowchart TD
    A[app/clients/graph_client.py<br/>GraphUnauthorizedError 발생] --> B[FastMCP ToolManager]
    B --> C[ToolError 로 래핑]
    C --> D[app/core/mcp_midleware.py]
    D --> E[exc.__cause__ 확인]
    E --> F[ToolError str(cause)]
```

`GraphClientError` 는 `code`, `message` 를 클래스 속성으로 갖고, 인스턴스 생성 시에는 `detail` 만 받습니다.
이 구조는 하위 예외마다 생성자에서 같은 값을 반복해서 넘기지 않게 합니다.
`super().__init__(self.to_tool_message())` 로 표준 예외 문자열을 초기화하므로 `str(exc)` 가 곧 MCP 출력 메시지가 됩니다.

## 예시

전제조건: Python 3.10 이상, 프로젝트 루트에서 실행합니다.

```python
from app.common.exception import GraphUnauthorizedError

exc = GraphUnauthorizedError("401 Unauthorized")
print(str(exc))
```

기대 결과:

```text
[GRAPH_UNAUTHORIZED] 인증 실패입니다. detail=401 Unauthorized
```

실패 예시:

```python
raise GraphUnauthorizedError(code="GRAPH_UNAUTHORIZED", message="인증 실패")
```

해결 방법:

```python
raise GraphUnauthorizedError("401 Unauthorized")
```

