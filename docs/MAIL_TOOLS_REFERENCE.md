# MAIL_TOOLS_REFERENCE

## 목적

`app/tools/mail_tools.py`에 등록된 메일 MCP 도구를 한눈에 확인하기 위한 참조 문서입니다.
이 문서는 도구 함수명, 한글 이름, 입력 조건, 출력, 실제 서비스 구현 위치를 함께 정리합니다.

## 공통 전제

- 모든 도구는 `register_mail_tools(mcp)`에서 FastMCP Tool로 등록됩니다.
- MCP 요청에는 사용자 컨텍스트 조회를 위한 `biz-user-token` 헤더가 필요합니다.
- 메일 조회/검색 도구는 Microsoft Graph delegated `Mail.Read` 권한이 필요합니다.
- 초안 생성은 `Mail.ReadWrite`, 발송/답장/전달은 `Mail.Send` 권한이 필요합니다.
- 날짜 입력은 `YYYY-MM-DD` 형식이며, 서비스 계층에서 KST 기준 날짜를 Graph UTC 필터로 변환합니다.
- `top_k`는 일반 조회 도구에서 1~50 범위로 제한됩니다.

## 도구 목록

| 분류 | 도구 함수명 | 도구 한글이름 | description | 기능 설명 | input 조건 | 결과 output | 구현 서비스 | Graph API / 처리 방식 | 비고 |
| :-- | :-- | :-- | :-- | :-- | :-- | :-- | :-- | :-- | :-- |
| 조회 | `get_recent_emails` | 최근 메일 조회 | 기간 내 최근 순서로 받은 메일을 조회합니다. | 받은편지함 기준 최근 수신 메일 목록을 가져옵니다. | `from_date`, `to_date` 선택<br>`top_k` 기본 10, 최대 50 | `list[MailMessage]` | `MailService.fetch_my_mails()` | `GET /me/mailFolders/inbox/messages` | 기간 미지정 시 최근 30일 |
| 조회 | `get_unread_emails` | 안 읽은 메일 조회 | 아직 읽지 않은 메일을 조회합니다. | `isRead=false` 조건으로 미확인 메일만 가져옵니다. | `from_date`, `to_date` 선택<br>`top_k` 기본 10, 최대 50 | `list[MailMessage]` | `MailService.fetch_my_mails(isRead=False)` | `GET /me/mailFolders/inbox/messages` + `$filter=isRead eq false` | 단순 unread 확인용 |
| 조회 | `get_important_emails` | 중요 메일 조회 | 중요도가 높은 메일을 조회합니다. | `importance=high` 조건으로 중요 메일을 필터링합니다. | `from_date`, `to_date` 선택<br>`top_k` 기본 10, 최대 50<br>`isimportant` 기본 `True` | `list[MailMessage]` | `MailService.fetch_my_mails(isimportant=True)` | `GET /me/mailFolders/inbox/messages` + `$filter=importance eq 'high'` | 중요 메일 중심 보고 전처리에 유용 |
| 조회 | `get_flagged_emails` | 플래그 메일 조회 | 깃발 표시된 메일을 조회합니다. | Outlook 플래그가 지정된 메일만 가져옵니다. | `from_date`, `to_date` 선택<br>`top_k` 기본 10, 최대 50<br>`isflagged` 기본 `True` | `list[MailMessage]` | `MailService.fetch_my_mails(isflagged=True)` | `GET /me/mailFolders/inbox/messages` + `$filter=flag/flagStatus eq 'flagged'` | 후속 조치 메일 확인용 |
| 조회 | `get_emails_sender` | 발신자 기준 메일 검색 | 보낸사람으로 메일을 검색합니다. | 발신자 이메일 주소 또는 표시 이름이 일치하는 메일을 조회합니다. | `sender` 필수<br>`from_date`, `to_date` 선택<br>`top_k` 기본 10, 최대 50 | `list[MailMessage]` | `MailService.fetch_my_mails(sender=...)` | `GET /me/mailFolders/inbox/messages` + 발신자 `$filter` | `sender`는 단일 문자열 |
| 조회 | `get_emails_cc` | 참조자 기준 메일 검색 | 참조자(CC)로 메일을 검색합니다. | CC 수신자 이메일 주소 또는 표시 이름이 일치하는 메일을 조회합니다. | `cc` 필수<br>`from_date`, `to_date` 선택<br>`top_k` 기본 10, 최대 50 | `list[MailMessage]` | `MailService.fetch_my_mails(cc=...)` | `GET /me/mailFolders/inbox/messages` + `ccRecipients/any(...)` | `cc`는 단일 문자열 |
| 조회 | `get_email_attachment` | 첨부 메일 조회 | 첨부파일이 있는 메일을 조회합니다. | 첨부파일 존재 여부가 `true`인 메일만 조회합니다. | `from_date`, `to_date` 선택<br>`top_k` 기본 10, 최대 50 | `list[MailMessage]` | `MailService.fetch_my_mails(has_attachments=True)` | `GET /me/mailFolders/inbox/messages` + `$filter=hasAttachments eq true` | 첨부파일 이름 검색은 아님 |
| 검색 | `search_emails_title` | 제목 키워드 검색 | 제목에서 키워드가 포함된 메일을 검색합니다. | Graph `$search`를 사용해 제목 기준 키워드 검색을 수행합니다. | `keywords` 필수, `list[str]`<br>각 키워드 2자 이상<br>`from_date`, `to_date` 선택<br>`top_k` 기본 10, 최대 50 | `list[MailMessage]` | `MailService.search_my_mails(scope="title")` | `GET /me/mailFolders/inbox/messages` + `$search=subject:...` | 날짜 범위는 응답 후 KST 기준 후처리 |
| 검색 | `search_emails_content` | 본문 키워드 검색 | 본문에서 키워드가 포함된 메일을 검색합니다. | Graph `$search`를 사용해 본문 기준 키워드 검색을 수행합니다. | `keywords` 필수, `list[str]`<br>각 키워드 2자 이상<br>`from_date`, `to_date` 선택<br>`top_k` 기본 10, 최대 50 | `list[MailMessage]` | `MailService.search_my_mails(scope="content")` | `GET /me/mailFolders/inbox/messages` + `$search=body:...` | 날짜 범위는 응답 후 KST 기준 후처리 |
| 조회 | `get_sent_emails` | 보낸 메일 조회 | 보낸편지함의 메일을 최근 순서로 조회합니다. | Sent Items 기준 발송 메일 목록을 가져옵니다. | `from_date`, `to_date` 선택<br>`top_k` 기본 10, 최대 50 | `list[MailMessage]` | `MailService.fetch_my_sent_mails()` | `GET /me/mailFolders/sentitems/messages` | 날짜 기준은 `sentDateTime` |
| 조회 | `get_email_detail` | 메일 상세 조회 | 메일 고유 ID로 단일 메일의 상세 정보를 조회합니다. | 목록 조회에서 받은 `id`로 본문과 첨부파일 메타데이터를 가져옵니다. | `id` 필수<br>목록/검색 결과의 메일 ID 그대로 사용 | `MailMessageDetail` | `MailService.fetch_my_mail_detail()` | `GET /me/messages/{id}` + `$expand=attachments` | 자연어만으로 바로 호출하지 않고 먼저 목록 조회 권장 |
| 조회 | `get_emails_folder` | 폴더별 메일 조회 | 특정 Outlook 메일 폴더의 메일을 조회합니다. | 폴더 이름으로 folder id를 찾은 뒤 해당 폴더의 메일을 조회합니다. | `folder_name` 필수<br>`from_date`, `to_date` 선택<br>`top_k` 기본 10, 최대 50 | `list[MailMessage]` | `MailService.find_mail_folders_by_name()` + `fetch_my_mails(folder_id=...)` | `GET /me/mailFolders` 후 `GET /me/mailFolders/{id}/messages` | 같은 이름 폴더가 여러 개면 오류 |
| 작성 | `create_draft` | 메일 초안 생성 | 이메일을 발송하지 않고 임시 보관함에 저장합니다. | 새 메일 메시지를 Drafts에 초안으로 생성합니다. | `subject` 필수<br>`body` 필수<br>`to_addresses` 필수, 1명 이상<br>`cc_addresses` 선택 | `dict`<br>`status=draft_created`<br>`id`, `subject`, `web_link` | `MailWriteService.create_draft()` | `POST /me/messages` | 안전한 기본 작성 흐름 |
| 작성 | `send_email` | 메일 즉시 발송 | 이메일을 즉시 발송합니다. | 새 메일을 발송하고 보낸 편지함에 저장합니다. | `subject` 필수<br>`body` 필수<br>`to_addresses` 필수, 1명 이상<br>`cc_addresses` 선택 | `dict`<br>`status=sent`<br>`subject`, `to_count`, `cc_count` | `MailWriteService.send_email()` | `POST /me/sendMail` | 사용자 명시 발송 요청이 있을 때 사용 |
| 작성 | `reply_email` | 메일 답장 | 기존 이메일에 답장을 발송합니다. | 원본 메일 ID 기준으로 답장 또는 전체 답장을 발송합니다. | `message_id` 필수<br>`body` 필수<br>`reply_all` 선택, 기본 `False` | `dict`<br>`status=reply_sent`<br>`message_id`, `reply_all` | `MailWriteService.reply_email()` | `POST /me/messages/{id}/reply` 또는 `replyAll` | `message_id`는 조회 결과 ID 그대로 사용 |
| 작성 | `forward_email` | 메일 전달 | 기존 이메일을 다른 수신자에게 전달합니다. | 원본 메일 ID 기준으로 지정 수신자에게 메일을 전달합니다. | `message_id` 필수<br>`to_addresses` 필수, 1명 이상<br>`comment` 선택 | `dict`<br>`status=forwarded`<br>`message_id`, `to_count` | `MailWriteService.forward_email()` | `POST /me/messages/{id}/forward` | 전달 코멘트는 원본 메일 위에 함께 전송 |
| 리포트 | `mail_weekly_report` | 주간 메일 리포트 | 지난주와 이번주 메일 목록 및 요약 정보를 조회합니다. | 지난주 월~일요일, 이번주 월~일요일 메일을 비교 가능한 구조로 반환합니다. | `top_k` 기본 50 | `MailWeeklyReport`<br>`last_week`, `this_week`, `report_content` | `MailReportService.fetch_weekly_report()` | 내부적으로 기간별 `MailService.fetch_my_mails()` 재사용 | 현재 구현은 기간별 최대 50건 기준 |
| 리포트 | `mail_monthly_report` | 월간 메일 리포트 | 지난달과 이번달 메일 목록 및 요약 정보를 조회합니다. | 지난달 1일~말일, 이번달 1일~말일 메일을 비교 가능한 구조로 반환합니다. | `top_k` 기본 50 | `MailMonthlyReport`<br>`last_month`, `this_month`, `report_content` | `MailReportService.fetch_monthly_report()` | 내부적으로 기간별 `MailService.fetch_my_mails()` 재사용 | 현재 구현은 기간별 최대 50건 기준 |

## 출력 스키마 요약

| 스키마 | 사용 도구 | 주요 필드 |
| :-- | :-- | :-- |
| `MailMessage` | 목록/검색 계열 도구 | `id`, `subject`, `sender`, `received_date_time`, `sent_date_time`, `body_preview`, `importance`, `is_read`, `has_attachments` |
| `MailMessageDetail` | `get_email_detail` | `MailMessage` 필드 + `body`, `attachments` |
| `MailPeriodSummary` | 리포트 내부 기간 요약 | `period_label`, `from_date`, `to_date`, `listed_count`, `unread_count`, `important_count`, `attachment_count`, `top_senders`, `important_mails`, `recent_mails`, `summary_text` |
| `MailWeeklyReport` | `mail_weekly_report` | `last_week`, `this_week`, `report_content` |
| `MailMonthlyReport` | `mail_monthly_report` | `last_month`, `this_month`, `report_content` |

## 사용 기준

- 단순 메일 확인은 `get_recent_emails`를 우선 사용합니다.
- 기간/발신자/참조자/첨부/중요도 같은 조건이 명확하면 전용 조회 도구를 사용합니다.
- 메일 본문 전체가 필요하면 목록 조회 후 `get_email_detail`을 호출합니다.
- 사용자가 "작성해줘"라고만 말한 경우에는 `create_draft`를 우선 사용합니다.
- 사용자가 "바로 보내줘", "발송해줘"라고 명시하면 `send_email`을 사용할 수 있습니다.
- 답장/전체답장/전달은 반드시 기존 메일의 `message_id`가 필요합니다.
- 주간보고/월간보고 작성 목적이면 `mail_weekly_report`, `mail_monthly_report`를 사용합니다.

## 개선 후보

- `mail_weekly_report`, `mail_monthly_report`는 현재 `top_k=50` 기준이므로, 실제 보고서 정확도를 높이려면 Graph 페이지네이션 기반 `max_items` 방식으로 확장하는 것이 좋습니다.
- `get_email_attachment`는 첨부파일 존재 여부만 확인하므로, 첨부파일 이름/확장자 검색이 필요하면 상세 조회 또는 첨부 전용 검색 도구를 추가할 수 있습니다.
- 작성 계열 도구는 조직 정책에 따라 관리자 동의가 필요할 수 있으므로, 운영 전 Microsoft Graph 권한 정책 확인이 필요합니다.
