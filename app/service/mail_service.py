from __future__ import annotations
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from typing import Optional, List
from urllib.parse import quote
from pydantic import TypeAdapter


from fastmcp.server.dependencies import get_http_request

from app.clients.graph_client import graph_request
from app.common.exception import GraphAccessDeniedError
from app.schema.user import User
from app.schema.mail import MailMessage, MailMessageDetail




@dataclass
class MailRequestContext:
    """
    메일 service 가 tool 실행 중 필요로 하는 요청 단위 값입니다.
    dataclass 는 여러 값을 하나의 객체로 묶는 문법이며, 함수 인자가 길어지는 것을 막기 위해 사용합니다.
    """

    access_token: str
    current_user: User
    trace_id: str
    blacklist: list[str]


class MailService:
    """
    메일 관련 유스케이스를 모아 두는 service 계층입니다.
    Tool 은 입출력 계약에 집중하고, 이 계층은 사용자 컨텍스트 확인과 Graph 조회 조건 조합을 담당합니다.
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
        사용자가 blacklist 에 포함되어 있는지 검사합니다.
        이 검사는 Graph 호출 여부를 결정하는 비즈니스 규칙이므로 graph_client 가 아니라 service 계층에 둡니다.
        """

        user_email = (context.current_user.user_email or "").lower()
        user_id = context.current_user.user_id.lower()
        company_code = (context.current_user.company_code or "").lower()
        blocked_keys = {user_email, user_id, company_code}

        if blocked_keys.intersection(context.blacklist):
            raise GraphAccessDeniedError(context.current_user.user_email or context.current_user.user_id)


    def _build_base_filter(
        self,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        date_field: str = "receivedDateTime",
    ) -> list[str]:
        """
        날짜 조건을 Graph OData filter 문자열로 조합합니다.
        Microsoft Outlook에서는 날짜가 UTC로 저장, 응답하므로 사용자로부터 받은 KST 날짜를 UTC 기준으로 변환합니다.
        """

        filters: list[str] = []

        KST = timedelta(hours=9)

        # 날짜가 없으면 KST 기준 오늘 날짜 00:00:00을 기준으로 
        today_kst = datetime.now(timezone(KST)).replace(hour=0, minute=0, second=0, microsecond=0)
        
        if from_date: # 사용자가 준 YYYY-MM-DD 날짜 
            from_date_time=datetime.strptime(from_date, "%Y-%m-%d")
        else: # 기본 조회는 KST 기준 최근 30일로 제한한다.
            from_date_time=today_kst - timedelta(days=30)
           

        # 종료일을 각 날짜의 자정으로 계산
        if to_date: 
            to_date_time = datetime.strptime(to_date, "%Y-%m-%d") + timedelta(days=1) - timedelta(seconds=1)
        else: 
            to_date_time = today_kst + timedelta(days=1) - timedelta(seconds=1)

            
        # Graph 필터는 UTC로 계산 되므로 다시 KST에서 -9 시간 씩 차감해야 함.
        filters.append(f"{date_field} ge {(from_date_time - KST).strftime('%Y-%m-%dT%H:%M:%SZ')}")
        filters.append(f"{date_field} le {(to_date_time - KST).strftime('%Y-%m-%dT%H:%M:%SZ')}")
        
        return filters

    def _is_mail_in_kst_date_range(
        self,
        mail: MailMessage,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> bool:
        """
        Graph $search 는 $filter/$orderby 와 함께 쓰기 까다로우므로 날짜 범위는 응답 모델 변환 후 검사합니다.
        MailMessage 의 received_date_time 은 schema validator 에서 KST 문자열로 변환되어 있습니다.
        """

        if not mail.received_date_time:
            return False

        received_date = datetime.fromisoformat(mail.received_date_time).date()
        today_kst = datetime.now(timezone(timedelta(hours=9))).date()
        start_date = datetime.strptime(from_date, "%Y-%m-%d").date() if from_date else today_kst - timedelta(days=30)
        end_date = datetime.strptime(to_date, "%Y-%m-%d").date() if to_date else today_kst

        if received_date < start_date:
            return False
        if received_date > end_date:
            return False

        return True

    def _normalize_search_keywords(self, keywords: str | list[str]) -> list[str]:
        """
        Tool 에서는 여러 검색어를 list[str] 로 받을 수 있으므로 Graph 검색 전 문자열 목록으로 정리합니다.
        검색어가 너무 짧으면 결과 후보가 과도하게 넓어지기 때문에 2자 이상만 허용합니다.
        """

        raw_keywords = [keywords] if isinstance(keywords, str) else keywords
        normalized_keywords = [keyword.strip() for keyword in raw_keywords if keyword and keyword.strip()]

        if not normalized_keywords:
            raise ValueError("검색어는 최소 1개 이상 필요합니다.")
        if any(len(keyword) < 2 for keyword in normalized_keywords):
            raise ValueError("각 검색어는 2자 이상이어야 합니다.")

        return normalized_keywords

    def _build_search_query(self, keywords: str | list[str], scope: Optional[str] = None) -> str:
        """
        Microsoft Graph 의 $search 값은 텍스트 검색 전용 표현식으로 따로 구성합니다.
        여러 검색어는 AND 로 묶어 모든 키워드가 함께 걸리도록 범위를 좁힙니다.
        """

        normalized_keywords = [
            keyword.replace('"', '\\"')
            for keyword in self._normalize_search_keywords(keywords)
        ]

        if scope == "title":
            return " AND ".join(f"subject:{keyword}" for keyword in normalized_keywords)
        if scope == "content":
            return " AND ".join(f"body:{keyword}" for keyword in normalized_keywords)

        return " AND ".join(normalized_keywords)

    def _escape_odata_string(self, value: str) -> str:
        """
        OData 문자열 값 안의 작은따옴표는 두 번 써야 문법 오류가 나지 않습니다.
        예: O'Neil -> O''Neil
        """

        return value.strip().replace("'", "''")

    async def fetch_my_mails(
        self,
        *,
        top_k: int = 10,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        isRead: Optional[bool] = None,
        isimportant: Optional[bool] = None,
        isflagged: Optional[bool] = None,
        sender: Optional[str] = None,
        cc: Optional[str] = None,
        has_attachments: Optional[bool] = None,
    ) -> list[MailMessage]:
        """최근 메일 목록 조회 
        top_k, blacklist, Graph path 구성 비즈니스 로직은 service 계층에서 처리합니다.
        """

        context = self._get_request_context()
        self._ensure_user_allowed(context)

        # Graph API 에 너무 큰 조회 요청을 보내지 않도록 한 번 더 방어합니다.
        normalized_top_k = max(1, min(top_k, 50))

        path = (
            f"/mailFolders/inbox/messages"
            f"?$top={normalized_top_k}"
            f"&$select=id,subject,from,sender,receivedDateTime,bodyPreview,importance,isRead,hasAttachments"
            f"&$orderby=receivedDateTime desc"
        )
        
        # 기본 필터는 날짜 미지정 시 최근 30일 ~ 오늘입니다.
        base_filter = self._build_base_filter(from_date, to_date)

        # 추가 필터 조합 로직
        if isRead is not None: 
            base_filter.append(f"isRead eq {str(isRead).lower()}")
        if isimportant:
                base_filter.append("importance eq 'high'")
        if isflagged:
            base_filter.append("flag/flagStatus eq 'flagged'")
        if has_attachments is not None:
            base_filter.append(f"hasAttachments eq {str(has_attachments).lower()}")
        
        if sender:
            escaped_sender = self._escape_odata_string(sender)
            base_filter.append(
                f"(from/emailAddress/address eq '{escaped_sender}' or from/emailAddress/name eq '{escaped_sender}')"
            )
        if cc:
            escaped_cc = self._escape_odata_string(cc)
            base_filter.append(
                f"ccRecipients/any(c:c/emailAddress/address eq '{escaped_cc}' or c/emailAddress/name eq '{escaped_cc}')"
            )
        

        # 필터 쿼리 path 추가
        joined_filter = " and ".join(base_filter)
        path += f"&$filter={joined_filter}"

        result = await graph_request(
            method="GET",
            path=path,
            access_token=context.access_token,
            trace_id=context.trace_id,
            current_user=context.current_user,
        )

        adapter = TypeAdapter(List[MailMessage])
        return adapter.validate_python(result.get("value", []))

    async def fetch_my_sent_mails(
        self,
        *,
        top_k: int = 10,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> list[MailMessage]:
        """보낸편지함 메일 목록 조회
        보낸편지함은 수신 시간이 아니라 sentDateTime 을 기준으로 기간 필터와 정렬을 적용합니다.
        """

        context = self._get_request_context()
        self._ensure_user_allowed(context)

        # Graph API 에 너무 큰 조회 요청을 보내지 않도록 한 번 더 방어합니다.
        normalized_top_k = max(1, min(top_k, 50))

        path = (
            f"/mailFolders/sentitems/messages"
            f"?$top={normalized_top_k}"
            f"&$select=id,subject,toRecipients,sentDateTime,bodyPreview,importance,isRead,hasAttachments"
            f"&$orderby=sentDateTime desc"
        )

        # 보낸편지함은 sentDateTime 기준으로 KST 날짜 조건을 UTC 필터로 변환합니다.
        base_filter = self._build_base_filter(from_date, to_date, date_field="sentDateTime")
        joined_filter = " and ".join(base_filter)
        path += f"&$filter={joined_filter}"

        result = await graph_request(
            method="GET",
            path=path,
            access_token=context.access_token,
            trace_id=context.trace_id,
            current_user=context.current_user,
        )

        adapter = TypeAdapter(List[MailMessage])
        return adapter.validate_python(result.get("value", []))

    async def fetch_my_mail_detail(
        self,
        *,
        mail_id: str,
    ) -> MailMessageDetail:
        """메일 고유 ID 로 단일 메일 상세 정보를 조회합니다.
        목록 조회에서 받은 id 를 사용하며, 본문과 첨부파일 메타데이터를 함께 가져옵니다.
        """

        context = self._get_request_context()
        self._ensure_user_allowed(context)

        normalized_mail_id = mail_id.strip()
        if not normalized_mail_id:
            raise ValueError("메일 ID가 누락되었습니다.")

        path = (
            f"/messages/{normalized_mail_id}"
            f"?$select=id,subject,from,sender,receivedDateTime,sentDateTime,bodyPreview,body,importance,isRead,hasAttachments,toRecipients"
            f"&$expand=attachments($select=id,name,contentType,size)"
        )

        result = await graph_request(
            method="GET",
            path=path,
            access_token=context.access_token,
            trace_id=context.trace_id,
            current_user=context.current_user,
            custom_headers={"Prefer": 'outlook.body-content-type="text"'},
        )

        return MailMessageDetail.model_validate(result)
    

    async def search_my_mails(
        self,
        *,
        keywords: str | list[str] | None = None,
        scope: Optional[str] = None,
        top_k: int = 10,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> list[MailMessage]:
        """
        키워드 기반 메일 검색을 수행합니다.
        Graph $search 는 검색 인덱스용 쿼리이므로 일반 목록 조회의 $filter/$orderby 와 분리합니다.
        """

        context = self._get_request_context()
        self._ensure_user_allowed(context)

        # Graph 검색 결과는 최대 250개 제한이 있으므로, 날짜 후처리를 고려해 요청량을 조금 여유 있게 잡습니다.
        normalized_top_k = max(1, min(top_k, 50))
        search_top_k = max(normalized_top_k, 50)

        
        path = (
            f"/mailFolders/inbox/messages"
            f"?$top={search_top_k}"
            f"&$select=id,subject,from,sender,receivedDateTime,bodyPreview,importance,isRead,hasAttachments"
            # f"&$search={search_query}"
        )

        if keywords and scope:
            # Graph 메일 $search 는 전체 검색식을 큰따옴표로 감싸야 합니다. 예: $search="subject:광고"
            search_query = quote(f'"{self._build_search_query(keywords, scope)}"')
            path += f"&$search={search_query}"

        result = await graph_request(
            method="GET",
            path=path,
            access_token=context.access_token,
            trace_id=context.trace_id,
            current_user=context.current_user,
            custom_headers={"ConsistencyLevel": "eventual"},
        )

        adapter = TypeAdapter(List[MailMessage])
        searched_mails = adapter.validate_python(result.get("value", []))
        filtered_mails = [
            mail for mail in searched_mails
            if self._is_mail_in_kst_date_range(mail, from_date, to_date)
        ]
        sorted_mails = sorted(
            filtered_mails,
            key=lambda mail: mail.received_date_time or "",
            reverse=True,
        )

        return sorted_mails[:normalized_top_k]

   
