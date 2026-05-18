# MAIL_FETCH_GUIDE

## Purpose

`app/service/mail_service.py`의 `fetch_emails`는 Microsoft Graph `/me/messages` 경로를 사용해 메일함 전체에서 메일을 조회합니다.
폴더 경로를 직접 선택하지 않고 현재 로그인한 사용자의 메일 주소를 `$filter` 조건에 넣어 받은 메일과 보낸 메일을 구분합니다.

## Flow

```mermaid
flowchart TD
    A[Mail Tool] --> B[MailService.fetch_emails]
    B --> C{foldscope}
    C -->|received| D[toRecipients or ccRecipients contains my email]
    C -->|sent| E[from address equals my email]
    D --> F[/me/messages + $filter]
    E --> F
    F --> G[MailMessage list]
```

실제 코드는 `app/service/mail_service.py`에 있습니다.
`foldscope="received"`는 내가 받는 사람 또는 참조에 포함된 메일을 조회합니다.
`foldscope="sent"`는 보낸 사람이 현재 사용자 메일 주소인 메일을 조회합니다.
폴더를 직접 지정해야 하는 경우에는 `fetch_emails_folder`가 `/me/mailFolders/{folder_id}/messages` 경로를 계속 사용합니다.

## Example

Prerequisite: FastMCP request context has `graph_access_token`, `current_user`, and `trace_id`.

```python
messages = await mail_service.fetch_emails(
    foldscope="sent",
    top_k=10,
    from_date="2026-05-01",
    to_date="2026-05-15",
)
```

Expected result: `/me/messages`에서 현재 사용자가 보낸 메일만 최신순으로 최대 10개 반환합니다.

Failure example:

```python
messages = await mail_service.fetch_emails(folder_id="sentItems")
```

Fix: `/me/messages` 기반 조회에서는 `folder_id`가 아니라 `foldscope="sent"`를 사용합니다.
폴더 ID 기반 조회가 필요하면 `fetch_emails_folder(folder_id="sentItems")`를 사용합니다.

## Design Note

추가 헬퍼 함수는 만들지 않고 기존 `_get_request_context`, `_ensure_user_allowed`, `_escape_odata_string`만 사용했습니다.
이렇게 한 이유는 검색 함수와 같은 책임 범위를 유지하면서도 기존 서비스 구조를 크게 흔들지 않기 위해서입니다.
대안으로는 받은/보낸 메일 필터 조립을 별도 헬퍼로 분리할 수 있지만, 지금 범위에서는 추상화가 늘어나는 트레이드오프가 있습니다.
