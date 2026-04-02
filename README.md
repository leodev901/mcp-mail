# MCP-Mail & CMN (공통 API) 모노레포

Microsoft 365 데이터(메일, 일정, Teams 등) 연동을 제공하는 **FastMCP 서버** (`app`)와,  
**M365 OAuth 인증 및 공통 관리 기능**을 독립적으로 서비스하는 **CMN API 서버** (`cmn`)로 구성된 모노레포 프로젝트입니다.

---

## 🗂 전체 아키텍처 개요

```
mcp-mail/
  app/     ← FastMCP MCP 서버 (MS365 Tools 제공)
  cmn/     ← 공통 API 서버 (M365 OAuth 인증 / 로그 수집)
```

두 앱은 **독립 프로세스로 각각 구동**되며, `app`은 `cmn`의 REST API를 HTTP로 호출하여 토큰 및 설정 정보를 획득합니다.

```mermaid
graph LR
    Client["LLM Agent /\n MCP Client"]
    APP["MCP 서버"]
    CMN["MCP 공통"]
    DB["PostgreSQL\n(회사별 Schema)"]
    GRAPH["MS Graph API"]

    Client -->|MCP Streamable HTTP| APP
    APP -->|GET /api/auth/user/token| CMN
    APP -->|GET /api/auth/app/token| CMN
    CMN -->|Schema 전환 세션| DB
    APP -->|Bearer Token| GRAPH
    CMN -->|OAuth Callback 처리| DB
```

---

## 📦 `cmn` — 공통 API 서버

> **별도 독립 FastAPI 앱**으로 서비스됩니다.  
> M365 OAuth 인증 흐름 관리, 사용자/앱 토큰 발급, MCP Tool 로그 수집이 핵심 역할입니다.

### 실행

```bash
# cmn 서버를 독립 포트(예: 8001)로 기동
uvicorn cmn.main:app --host 0.0.0.0 --port 8001
```

### 디렉터리 구조

```text
cmn/
  main.py                         # FastAPI 앱 생성 및 lifespan(DB 엔진 초기화) 설정

  core/
    config.py                     # 환경변수(.env) 로드 (DATABASE_URL, COMPANY_CODES)

  api/
    routers.py                    # 라우터 일괄 등록 + /health 헬스체크
    dependencies.py               # X-Company-Code 헤더 → 스키마 DB 세션 DI
    endpoint/
      logs.py                     # MCP Tool 실행 로그 수집 API
      m365_oauth.py               # M365 OAuth 콜백, 사용자/앱 토큰 발급 API

  db/
    database.py                   # 비동기 DB 엔진 및 회사별 스키마 세션 관리
    crud/
      m365_oauth_crud.py          # GraphInfo 조회, 사용자 토큰 upsert CRUD
    models/
      base.py                     # DeclarativeBase + AuditMixin (created_at, updated_at)
      m365_mcp_graph_info.py      # M365 앱별 OAuth 설정 테이블 모델
      m365_mcp_tool_log.py        # MCP Tool 실행 로그 테이블 모델
      m365_user_toekn.py          # M365 사용자 위임 토큰 테이블 모델
```

### DB 멀티 스키마 전략

PostgreSQL의 `search_path`를 요청별로 전환하여 회사별 데이터를 격리합니다.

```
요청 헤더: X-Company-Code: leodev901
            ↓
dependencies.py → db.get_session_schema("leodev901")
            ↓
SET LOCAL search_path TO leodev901  (트랜잭션 범위 내에서만 유효)
            ↓
해당 회사 스키마의 테이블에 접근
```

- `COMPANY_CODES` 환경변수에 허용된 코드만 스키마로 접근 가능 (미허가 코드는 오류 반환)
- `SET LOCAL`은 트랜잭션 종료 시 자동 원복 → 커넥션 풀 오염 방지

### API 엔드포인트 목록

#### 인증 (`/api/auth`)

| 메서드 | 경로 | 설명 | 필수 헤더/파라미터 |
| :--: | :-- | :-- | :-- |
| `GET` | `/api/auth/m365/callback` | M365 OAuth 인증 완료 콜백 — `code`, `state` 수신 후 사용자 토큰 저장 | `?code=&state={company_cd}.{user_id}` |
| `GET` | `/api/auth/user/token` | 사용자 위임 토큰 조회 (만료 시 자동 갱신) | `X-Company-Code`, `?app_name=&user_id=` |
| `GET` | `/api/auth/app/token` | 앱 전용 Client Credentials 토큰 발급 | `X-Company-Code`, `?app_name=` |

#### 로그 (`/api/logs`)

| 메서드 | 경로 | 설명 | 필수 헤더 |
| :--: | :-- | :-- | :-- |
| `POST` | `/api/logs/tool` | MCP Tool 실행 로그 저장 | `X-Company-Code` |
| `POST` | `/api/logs/graph` | MS Graph API 호출 로그 저장 (구현 예정) | `X-Company-Code` |

#### 헬스체크

| 메서드 | 경로 | 설명 |
| :--: | :-- | :-- |
| `POST` | `/health` | 서버 상태 확인 |

### 환경 변수 (cmn)

```env
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/dbname
COMPANY_CODES=["leodev901","acme"]
```

| 변수명 | 설명 |
| :-- | :-- |
| `DATABASE_URL` | asyncpg 드라이버 형식의 PostgreSQL URL |
| `COMPANY_CODES` | 허용된 회사 코드 목록 (JSON 배열 형태) |

### DB 테이블 명세

#### `m365_mcp_graph_info` — 회사/앱별 OAuth 설정

| 컬럼 | 타입 | 설명 |
| :-- | :-- | :-- |
| `app_name` (PK) | VARCHAR | 앱 이름 (예: `MAIL`) |
| `key` (PK) | VARCHAR | 설정 키 (예: `tenant_id`, `client_id`, `client_secret`, `redirect_uri`, `scopes`) |
| `value` | TEXT | 설정 값 |
| `created_at` | TIMESTAMPTZ | 생성일시 |
| `updated_at` | TIMESTAMPTZ | 수정일시 |

#### `m365_user_toekn` — 사용자 위임 토큰

| 컬럼 | 타입 | 설명 |
| :-- | :-- | :-- |
| `app_name` (PK) | VARCHAR | 앱 이름 |
| `user_id` (PK) | VARCHAR | 사용자 ID |
| `access_token` | TEXT | OAuth 액세스 토큰 |
| `refresh_token` | TEXT | OAuth 리프레시 토큰 |
| `expires_at` | TIMESTAMPTZ | 액세스 토큰 만료 일시 |
| `created_at` | TIMESTAMPTZ | 생성일시 |
| `updated_at` | TIMESTAMPTZ | 수정일시 |

#### `m365_mcp_tool_log` — MCP Tool 실행 로그

| 컬럼 | 타입 | 설명 |
| :-- | :-- | :-- |
| `id` (PK) | UUID | 로그 고유 ID (`gen_random_uuid()`) |
| `trace_id` | UUID | 요청 추적 ID |
| `tool_name` | VARCHAR | 호출된 Tool 이름 |
| `http_method` | VARCHAR | HTTP 메서드 |
| `http_status` | BIGINT | HTTP 상태 코드 |
| `status` | VARCHAR | 처리 상태 |
| `message` | VARCHAR | 메시지 |
| `request_body` | JSONB | 요청 바디 |
| `response_body` | JSONB | 응답 바디 |
| `created_at` | TIMESTAMPTZ | 생성일시 |
| `updated_at` | TIMESTAMPTZ | 수정일시 |

### M365 OAuth 흐름 (위임 권한)

```mermaid
sequenceDiagram
    participant User as 사용자 브라우저
    participant CMN as cmn API 서버
    participant Entra as Microsoft Entra ID
    participant DB as PostgreSQL

    User->>Entra: 1. OAuth 동의 페이지 직접 접근 (또는 별도 redirect URL 구성)
    Entra-->>CMN: 2. GET /api/auth/m365/callback?code=...&state={company_cd}.{user_id}
    CMN->>DB: 3. m365_mcp_graph_info 에서 앱 설정 조회
    CMN->>Entra: 4. POST /token (authorization_code grant)
    Entra-->>CMN: 5. access_token + refresh_token 반환
    CMN->>DB: 6. m365_user_toekn upsert 저장
    CMN-->>User: 7. 동의 완료 HTML 응답
```

### 토큰 자동 갱신 로직 (`GET /api/auth/user/token`)

```
1. DB에서 (app_name, user_id) 기준 토큰 조회
2. 토큰 없음 → 404 (사용자 동의 필요)
3. expires_at - 5분 > 현재시각(KST) → DB 캐시 그대로 반환
4. 만료 임박 → refresh_token으로 /token 재발급 → DB upsert → 신규 토큰 반환
```

---

## 📦 `app` — FastMCP MCP 서버

> Microsoft 365 데이터를 LLM 에이전트에게 MCP Tool 형태로 제공하는 서버입니다.

### 실행

```bash
# Windows
.\.venv\Scripts\uvicorn.exe app.main:app --host 0.0.0.0 --port 8002

# macOS / Linux
uvicorn app.main:app --host 0.0.0.0 --port 8002
```

### 요청 처리 아키텍처

HTTP 요청은 3개의 미들웨어 계층을 순서대로 거칩니다.

```mermaid
sequenceDiagram
    participant Client
    participant HTTP_MW as HttpMiddleware
    participant ASGI_MW as HttpLoggingASGIMiddleware
    participant MCP_MW as MCPLoggingMiddleware
    participant Tool as MCP Tool
    participant CMN as cmn API 서버
    participant Graph as MS Graph API

    Client->>HTTP_MW: HTTP 요청 (헤더: x-request-id, mcp_user_token)
    note over HTTP_MW: trace_id 추출, 토큰 state 저장
    HTTP_MW->>ASGI_MW: 요청 전달
    note over ASGI_MW: SSE 스트리밍 호환 Req/Res 로깅
    ASGI_MW->>MCP_MW: 요청 전달
    note over MCP_MW: UserInfo 변환 (Lazy), Tool 실행 로깅
    MCP_MW->>Tool: 도구 실행
    Tool->>CMN: GET /api/auth/user/token or /api/auth/app/token
    CMN-->>Tool: access_token 반환
    Tool->>Graph: Graph API 호출 (Bearer)
    Graph-->>Tool: M365 데이터 반환
    Tool-->>Client: 결과 반환 (스트리밍)
```

### 미들웨어 3계층

| 순서 | 미들웨어 | 파일 | 역할 |
| :--: | :-- | :-- | :-- |
| 1 | `HttpMiddleware` | `core/http_middleware.py` | `x-request-id` → `trace_id` 추출, `mcp_user_token` 파싱 후 `request.state` 저장 |
| 2 | `HttpLoggingASGIMiddleware` | `core/http_asgi_middleware.py` | SSE 스트리밍 환경에서 HTTP Req/Res 전체 로깅 (request body 선독 후 재생) |
| 3 | `MCPLoggingMiddleware` | `core/mcp_midleware.py` | JWT로 `UserInfo` 변환(Lazy 1회 파싱, 캐시), Tool 실행 전후 로깅 |

### 🔍 trace_id 전파 경로

```
HTTP 헤더 x-request-id (없으면 uuid4 자동 생성)
  │
  ├─ [http_request]     로그 (HttpLoggingASGIMiddleware)
  ├─ [mcp_tool_call]    로그 (MCPLoggingMiddleware)
  └─ [GraphAPI Request] 로그 (graph_client.py)
        ↓
  응답 헤더 x-request-id 로 클라이언트에 반환
```

### 디렉터리 구조

```text
app/
  main.py                       # FastMCP 앱 생성 및 미들웨어 등록 진입점
  server.py                     # (테스트용) 단일 파일 FastMCP 샘플

  core/
    config.py                   # 환경변수(.env) 및 회사별 MS365 설정
    http_middleware.py           # trace_id / 토큰 파싱 미들웨어
    http_asgi_middleware.py      # ASGI 수준 SSE 스트리밍 로깅 미들웨어
    mcp_midleware.py             # MCP Tool 실행 로깅 미들웨어
    logger_config.py             # 로깅 설정

  clients/
    graph_client.py              # MS Graph API 호출 클라이언트 + [GraphAPI Request] 로그
    http_client.py               # 공통 Async HTTP 클라이언트

  common/
    logger.py                    # OpenTelemetry → Grafana 파이프라인 로거

  models/
    user_info.py                 # JWT 토큰 파싱 결과 UserInfo 모델

  security/
    jwt_auth.py                  # JWT 검증 및 사용자 인가
    key_cache.py                 # 공개키 캐싱

  tools/
    calendar_tools.py            # 일정 조회/생성/수정/삭제
    mail_tools.py                # 메일 조회 (최신, 미읽음, 첨부, 키워드 검색 등)
    sharepoint_tools.py          # SharePoint / OneDrive 파일 조회 및 검색
    teams_tools.py               # Teams 채팅 목록 조회 및 메시지 전송
    to_do_tools.py               # Microsoft To-Do 할 일 관리
```

### Tools 파라미터 우선순위 패턴

모든 Tool 함수는 아래 3단계 우선순위로 `user_email`과 `company_cd`를 결정합니다.

```python
# ① HTTP request.state에서 현재 사용자 정보 읽기
current_user = _get_request_current_user()

# ② 이메일/회사코드 결정 (3단계 우선순위)
if user_email is not None:          # 1순위: 호출 시 파라미터 직접 전달
    query_email = user_email
    query_company_cd = DEFAULT_COMPANY_CD
elif current_user is not None:      # 2순위: JWT 토큰 파싱 사용자 정보
    query_email = current_user.email
    query_company_cd = current_user.company_cd
else:                               # 3순위: .env 파일의 DEFAULT 값 (개발/테스트용)
    query_email = DEFAULT_USER_EMAIL
    query_company_cd = DEFAULT_COMPANY_CD

# ③ Graph API 호출
result = await graph_request(method="GET", path=path, user_email=query_email, ...)
```

### 📊 3계층 로깅 요약

| 계층 | 파일 | 로그 태그 | 로깅 시점 | 레벨 |
| :-- | :-- | :-- | :-- | :--: |
| HTTP 요청/응답 | `http_asgi_middleware.py` | `[http_request]` / `[http_response]` | tools/call, tools/list 요청만 | INFO |
| MCP Tool 실행 | `mcp_midleware.py` | `[mcp_tool_call]` | Tool 함수 실행 전후, 에러 시 | INFO / EXCEPTION |
| Graph API 호출 | `graph_client.py` | `[GraphAPI Request]` | MS Graph API 호출 직후 finally 블록 | INFO / ERROR |

### 선언된 MCP 도구(Tools) 목록

#### 1) 캘린더 도구 (`calendar_tools.py`)

| 도구명 | 상태 | 설명 | 연동 API |
| :-- | :--: | :-- | :-- |
| `list_calendar_events` | ✅ | 시작/종료일 기준 캘린더 일정 조회 | `/calendarView` |
| `get_calendar_event` | ✅ | 단일 일정 상세 조회 | `/events/{id}` |
| `create_calendar_event` | ✅ | 새로운 일정 생성 | `POST /events` |
| `update_calendar_event` | ✅ | 기존 일정 부분 수정 | `PATCH /events/{id}` |
| `delete_calendar_event` | ✅ | 기존 일정 삭제 | `DELETE /events/{id}` |

#### 2) 메일 도구 (`mail_tools.py`)

| 도구명 | 상태 | 설명 | 연동 API |
| :-- | :--: | :-- | :-- |
| `get_recent_emails` | ✅ | 최근 수신 이메일 목록 조회 | `/mailFolders/inbox/messages` |
| `get_unread_emails` | ✅ | 읽지 않은 메일 조회 | `/mailFolders/inbox/messages` |
| `get_important_or_flagged_emails` | ✅ | 중요/깃발 메일 조회 | `/mailFolders/inbox/messages` |
| `search_emails_by_keyword_advanced` | ✅ | 제목/본문 키워드 풀텍스트 검색 | `/messages` |
| `search_emails_by_sender_advanced` | ✅ | 발신자 기준 필터 검색 | `/messages` |
| `search_emails_by_attachment` | ✅ | 첨부파일 유무/파일명 기준 검색 | `/messages` |
| `get_sent_emails` | ✅ | 보낸 편지함 조회 | `/mailFolders/sentitems/messages` |
| `get_email_detail_view` | ✅ | 단일 메일 상세 본문 및 첨부 목록 조회 | `/messages/{id}` |

#### 3) Teams 도구 (`teams_tools.py`)

| 도구명 | 상태 | 설명 | 연동 API |
| :-- | :--: | :-- | :-- |
| `list_my_chats` | ✅ | 참여 중인 채팅방 목록 조회 | `/chats` |
| `get_chat_messages` | ✅ | 특정 채팅방 최근 메시지 조회 | `/chats/{id}/messages` |
| `send_chat_message` | ✅ | 채팅방에 텍스트/HTML 메시지 전송 | `POST /chats/{id}/messages` |

#### 4) SharePoint / OneDrive 도구 (`sharepoint_tools.py`)

| 도구명 | 상태 | 설명 | 연동 API |
| :-- | :--: | :-- | :-- |
| `list_drive_files` | ✅ | 드라이브 파일/폴더 목록 조회 | `/drive/.../children` |
| `search_drive_files` | ✅ | 드라이브 전체 키워드 검색 | `/drive/root/search` |
| `get_drive_file_info` | ✅ | 파일 상세 정보 및 다운로드 링크 조회 | `/drive/items/{id}` |

#### 5) To-Do 도구 (`to_do_tools.py`)

| 도구명 | 상태 | 설명 | 연동 API |
| :-- | :--: | :-- | :-- |
| `todo_list_task_lists` | ✅ | 할 일 목록(카테고리) 조회 | `/todo/lists` |
| `todo_list_tasks` | ✅ | 특정 목록의 할 일 조회 | `/todo/lists/{id}/tasks` |
| `todo_create_task` | ✅ | 새 할 일 생성 | `POST /todo/lists/{id}/tasks` |
| `todo_update_task` | ✅ | 기존 할 일 수정 | `PATCH /todo/lists/{id}/tasks/{id}` |
| `todo_delete_task` | ✅ | 기존 할 일 삭제 | `DELETE /todo/lists/{id}/tasks/{id}` |

### 환경 변수 (app)

```env
LOG_LEVEL=DEBUG
AUTH_JWT_USER_TOKEN=false
MS365_CONFIGS={"leodev901":{"tenant_id":"...","client_id":"...","client_secret":"..."}}
```

| 변수명 | 설명 |
| :-- | :-- |
| `LOG_LEVEL` | 로그 레벨 (DEBUG / INFO / WARNING / ERROR) |
| `AUTH_JWT_USER_TOKEN` | `true` → JWT 실제 검증, `false` → 샘플 사용자 정보 매핑 (개발용) |
| `MS365_CONFIGS` | 회사별 Entra ID 설정 (tenant_id, client_id, client_secret) JSON |

---

## 🚀 실행 방법

### 두 서버 각각 기동

```bash
# 1. CMN 공통 API 서버 (포트 8001)
uvicorn cmn.main:app --host 0.0.0.0 --port 8001

# 2. MCP FastMCP 서버 (포트 8002)
uvicorn app.main:app --host 0.0.0.0 --port 8002
```

### 패키지 설치

```bash
pip install -r requirements.txt
```

### MCP Inspector 테스트

```bash
npx @modelcontextprotocol/inspector
```

- **Transport Type:** `streamable-http`
- **URL:** `http://127.0.0.1:8002/mcp`

---

## 📊 OpenTelemetry → Grafana 로깅 아키텍처

앱에서 `logger.info()` 호출 시, 아래 파이프라인을 통해 Grafana 대시보드로 전달됩니다.

```mermaid
sequenceDiagram
    participant App as 앱 코드 (logger.info)
    participant Handler as LoggingHandler (파이프)
    participant OTLP as OpenTelemetry (배달부)
    participant Grafana as Grafana 서버 (상황실)

    App->>Handler: 1. 로그 발생
    note over Handler: 2. OTLP 국제 규격으로 변환
    Handler->>OTLP: 3. 변환된 로그 전달
    note over OTLP: 4. Batch 프로세서가 모음
    OTLP->>Grafana: 5. gRPC로 일괄 전송
    note over Grafana: 6. 대시보드에서 검색/시각화
```

| Exporter | 비용 | 특징 |
| :-- | :--: | :-- |
| **Grafana (Loki/Tempo)** | 무료/유료 | 강력한 오픈소스 시각화 대시보드 *(기본 설정)* |
| Datadog | 유료 | 연동 쉬움, AI 분석 제공 |
| Dynatrace | 유료 | MSA 자동 구조 파악 |
| Jaeger | 무료 | 분산 트레이싱 특화 |
| Prometheus | 무료 | 메트릭(CPU/메모리) 중심 |
| ELK Stack | 무료/유료 | 대용량 텍스트 로그 검색 |

---

## 한 줄 요약

> **`cmn`은 M365 OAuth 인증과 공통 기능을 전담하는 독립 API 서버이고,  
> `app`은 cmn의 토큰을 활용하여 LLM 에이전트에 MS365 데이터를 제공하는 FastMCP 서버입니다.**