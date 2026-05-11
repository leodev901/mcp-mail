from urllib.parse import quote

from fastmcp.server.dependencies import get_http_request

from app.clients.graph_client import graph_request
from app.common.exception import GraphAccessDeniedError
from app.service.mail_service import MailRequestContext


class MailWriteService():
    """
    메일 작성/발송 유스케이스를 담당하는 service 계층입니다.
    Tool 은 사용자가 준 값의 계약에 집중하고, 이 계층은 Graph payload 생성과 권한 검사를 담당합니다.
    """

    def _get_request_context(self) -> MailRequestContext:
        """
        요청별 데이터는 request.state 에서 가져옵니다.
        """

        request = get_http_request()
        access_token = getattr(request.state, "graph_access_token", None)
        current_user = getattr(request.state, "current_user", None)
        trace_id = getattr(request.state, "trace_id", "-")
        blacklist = getattr(request.state, "blacklist", []) or []


        return MailRequestContext(
            access_token=access_token,
            current_user=current_user,
            trace_id=trace_id,
            blacklist=[str(item).lower() for item in blacklist],
        )

    def _ensure_user_allowed(self, context: MailRequestContext) -> None:
        """
        메일 쓰기 기능도 읽기 기능과 같은 blacklist 정책을 따릅니다.
        발송은 영향이 크기 때문에 Graph 호출 직전에 service 계층에서 한 번 더 막습니다.
        """

        user_email = (context.current_user.user_email or "").lower()
        user_id = context.current_user.user_id.lower()
        company_code = (context.current_user.company_code or "").lower()
        blocked_keys = {user_email, user_id, company_code}

        if blocked_keys.intersection(context.blacklist):
            raise GraphAccessDeniedError(context.current_user.user_email or context.current_user.user_id)

    def _normalize_recipients(self, recipients: list[str] | None, field_name: str) -> list[str]:
        """
        수신자 목록에서 빈 문자열을 제거합니다.
        Graph 는 잘못된 수신자 형식에서 400 을 반환하므로, 비어 있는 값은 service 입구에서 명확히 차단합니다.
        """

        normalized_recipients = [
            recipient.strip()
            for recipient in (recipients or [])
            if recipient and recipient.strip()
        ]

        if field_name == "to_addresses" and not normalized_recipients:
            raise ValueError("수신자(to_addresses)는 최소 1명 이상 필요합니다.")

        return normalized_recipients

    def _build_recipient_payload(self, recipients: list[str]) -> list[dict]:
        """
        문자열 이메일 목록을 Microsoft Graph 가 요구하는 recipient 객체 배열로 바꿉니다.
        딕셔너리 구조를 한곳에서 만들면 create/send/reply 확장 시 payload 형식을 일관되게 유지할 수 있습니다.
        """

        return [
            {
                "emailAddress": {
                    "address": recipient,
                },
            }
            for recipient in recipients
        ]

    def _build_message_payload(
        self,
        *,
        subject: str,
        body: str,
        to_addresses: list[str],
        cc_addresses: list[str] | None = None,
    ) -> dict:
        """
        Graph message payload 를 생성합니다.
        contentType 은 Text 로 고정해 HTML 삽입 위험을 줄이고, 필요하면 나중에 명시 파라미터로 확장할 수 있게 둡니다.
        """

        normalized_subject = subject.strip()
        normalized_body = body.strip()

        if not normalized_subject:
            raise ValueError("메일 제목(subject)은 비어 있을 수 없습니다.")
        if not normalized_body:
            raise ValueError("메일 본문(body)은 비어 있을 수 없습니다.")

        normalized_to_addresses = self._normalize_recipients(to_addresses, "to_addresses")
        normalized_cc_addresses = self._normalize_recipients(cc_addresses, "cc_addresses")

        message_payload = {
            "subject": normalized_subject,
            "body": {
                "contentType": "Text",
                "content": normalized_body,
            },
            "toRecipients": self._build_recipient_payload(normalized_to_addresses),
        }

        # ccRecipients 는 선택값이므로 실제 값이 있을 때만 Graph payload 에 포함합니다.
        if normalized_cc_addresses:
            message_payload["ccRecipients"] = self._build_recipient_payload(normalized_cc_addresses)

        return message_payload

    async def create_draft(
        self,
        *,
        subject: str,
        body: str,
        to_addresses: list[str],
        cc_addresses: list[str] | None = None,
    ) -> dict:
        """
        메일을 발송하지 않고 Drafts 에 초안으로 저장합니다.
        사용자가 최종 발송 전에 Outlook 에서 검토할 수 있게 하는 안전한 기본 쓰기 동작입니다.
        """

        context = self._get_request_context()
        self._ensure_user_allowed(context)

        message_payload = self._build_message_payload(
            subject=subject,
            body=body,
            to_addresses=to_addresses,
            cc_addresses=cc_addresses,
        )

        result = await graph_request(
            method="POST",
            path="/messages",
            access_token=context.access_token,
            json_body=message_payload,
            trace_id=context.trace_id,
            current_user=context.current_user,
            custom_headers={"Prefer": 'outlook.body-content-type="text"'},
        )

        return {
            "status": "draft_created",
            "id": result.get("id"),
            "subject": result.get("subject"),
            "web_link": result.get("webLink"),
        }

    async def send_email(
        self,
        *,
        subject: str,
        body: str,
        to_addresses: list[str],
        cc_addresses: list[str] | None = None,
    ) -> dict:
        """
        새 메일을 즉시 발송합니다.
        Graph sendMail 은 성공 시 본문 없는 202 를 반환하므로, 호출 성공 여부를 service 응답으로 명시합니다.
        """

        context = self._get_request_context()
        self._ensure_user_allowed(context)

        message_payload = self._build_message_payload(
            subject=subject,
            body=body,
            to_addresses=to_addresses,
            cc_addresses=cc_addresses,
        )

        await graph_request(
            method="POST",
            path="/sendMail",
            access_token=context.access_token,
            json_body={
                "message": message_payload,
                "saveToSentItems": True,
            },
            trace_id=context.trace_id,
            current_user=context.current_user,
        )

        return {
            "status": "sent",
            "subject": message_payload["subject"],
            "to_count": len(message_payload["toRecipients"]),
            "cc_count": len(message_payload.get("ccRecipients", [])),
        }

    async def reply_email(
        self,
        *,
        message_id: str,
        body: str,
        reply_all: bool = False,
    ) -> dict:
        """
        기존 메일에 답장을 발송합니다.
        reply_all 이 True 이면 replyAll 엔드포인트를 사용해 원본의 전체 수신자에게 회신합니다.
        """

        context = self._get_request_context()
        self._ensure_user_allowed(context)

        normalized_message_id = message_id.strip()
        normalized_body = body.strip()

        if not normalized_message_id:
            raise ValueError("답장할 메일 ID(message_id)가 필요합니다.")
        if not normalized_body:
            raise ValueError("답장 본문(body)은 비어 있을 수 없습니다.")

        # 메일 ID 는 URL path segment 로 들어가므로 특수문자를 percent-encoding 합니다.
        encoded_message_id = quote(normalized_message_id, safe="")
        action_name = "replyAll" if reply_all else "reply"

        await graph_request(
            method="POST",
            path=f"/messages/{encoded_message_id}/{action_name}",
            access_token=context.access_token,
            json_body={"comment": normalized_body},
            trace_id=context.trace_id,
            current_user=context.current_user,
        )

        return {
            "status": "reply_sent",
            "message_id": normalized_message_id,
            "reply_all": reply_all,
        }
