from __future__ import annotations
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from typing import Optional, List, Annotated, Literal
from urllib.parse import quote
from pydantic import TypeAdapter


from fastmcp.server.dependencies import get_http_request

from app.clients.graph_client import graph_request
from app.common.exception import GraphAccessDeniedError
from app.schema.user import User
from app.schema.mail import MailMessage, MailMessageDetail
from app.utils.date_utils import get_format_to_utc
from app.common.logger import logger
from app.service.mail_guard_service import MailGuardService







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
    def __init__(self):
        self.mail_guard_service = MailGuardService()

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

    async def fetch_emails(
        self,
        *,
        scope: Literal["received", "sent"] = "received",
        top_k: int = 10,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        isRead: Optional[bool] = None,
        isimportant: Optional[bool] = None,
        isflagged: Optional[bool] = None,
        sender: Annotated[Optional[str], "Sender email address filter. Display-name search is also supported."] = None,
        cc: Optional[str] = None,
        has_attachments: Optional[bool] = None,
    ) -> list[MailMessage]:
        """Fetch recent messages through /me/messages.
        This mirrors search_emails by separating received and sent messages with the current user's email address.
        """

        context = self._get_request_context()
        self._ensure_user_allowed(context)
        my_email = self._escape_odata_string(context.current_user.user_email or "")

        await self.mail_guard_service.ensure_api_call_allowed(user_email=my_email)


        # Graph API 에 너무 큰 조회 요청을 보내지 않도록 max 50 설정
        normalized_top_k = max(1, min(top_k, 50))

        # 날짜 정렬 및 필터 기준 설정
        #   - inbox 포함 default -> receivedDateTime 받은시간 기준으로
        #   - sentItem -> sentDateTime 보낸시간 기준으로
        base_datetime = "sentDateTime" if scope == "sent" else "receivedDateTime"

        # from, to 공백일 경우 기본갑 설정 '일주일'
        today = datetime.now(timezone(timedelta(hours=9)))
        if from_date is None:
            from_date = (today - timedelta(days=7)).strftime("%Y-%m-%d")
        if to_date is None:
            to_date = today.strftime("%Y-%m-%d")

        # 필터 리스트 생성
        base_filter: list[str] = [
            f"{base_datetime} ge {get_format_to_utc(from_date)}",
            f"{base_datetime} le {get_format_to_utc(to_date, is_end=True)}",
        ]

        # 받은/참조 메일 또는 보낸메일로 조회 범위 설정
        if not my_email:
            raise ValueError("Current user email is required to filter messages.")
        if scope == "received":
            base_filter.append(
                f"(toRecipients/any(t:t/emailAddress/address eq '{my_email}') "
                f"or ccRecipients/any(c:c/emailAddress/address eq '{my_email}'))"
            )
        elif scope == "sent":
            base_filter.append(f"from/emailAddress/address eq '{my_email}'")

        # bool 필터
        if isRead is not None:
            base_filter.append(f"isRead eq {str(isRead).lower()}")
        if isimportant is not None:
            importance_val = "high" if isimportant else "normal"
            base_filter.append(f"importance eq '{importance_val}'")
        if isflagged:
            base_filter.append("flag/flagStatus eq 'flagged'")
        if has_attachments is not None:
            base_filter.append(f"hasAttachments eq {str(has_attachments).lower()}")

        # 문자열 필터 (Sender/CC)
        if sender:
            s = self._escape_odata_string(sender)
            base_filter.append(f"(from/emailAddress/address eq '{s}' or from/emailAddress/name eq '{s}')")
        if cc:
            c = self._escape_odata_string(cc)
            base_filter.append(f"ccRecipients/any(c:c/emailAddress/address eq '{c}' or c/emailAddress/name eq '{c}')")

        joined_filter = " and ".join(base_filter)

        # 최종 경로 
        path = (
            f"/me/messages"
            f"?$top={normalized_top_k}"
            f"&$select=id,subject,from,sender,receivedDateTime,sentDateTime,toRecipients,bodyPreview,importance,isRead,hasAttachments"
            f"&$orderby={base_datetime} desc"
            f"&$filter={joined_filter}"
        )

        result = await graph_request(
            method="GET",
            path=path,
            access_token=context.access_token,
            trace_id=context.trace_id,
            current_user=context.current_user,
        )

        adapter = TypeAdapter(List[MailMessage])
        return adapter.validate_python(result.get("value", []))


    async def fetch_email_detail(
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
            f"/me/messages/{normalized_mail_id}"
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

        mail_detail = MailMessageDetail.model_validate(result)
        if mail_detail:
            # 메읽 읽음 처리 
            path = f"/me/messages/{normalized_mail_id}"
            payload = {
                "isRead": True
            }
            result = await graph_request(
                method="PATCH",
                path=path,
                access_token=context.access_token,
                trace_id=context.trace_id,
                current_user=context.current_user,
                json_body=payload 
            )
            # print(result) 


        return mail_detail
            
    
    async def search_emails(
        self,
        *,
        scope: Literal["received", "sent"] = "received",
        keywords: str | list[str] | None = None,
        top_k: int = 10,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        isRead: Optional[bool] = None,
        isimportant: Optional[bool] = None,
        isflagged: Optional[bool] = None,
        sender: Optional[str] = None,
        cc: Optional[str] = None,
        has_attachments: Optional[bool] = None,
        category: Optional[str] = None,
    ) -> list[MailMessage]:
        context = self._get_request_context()
        self._ensure_user_allowed(context)
        my_email = self._escape_odata_string(context.current_user.user_email or "")

        await self.mail_guard_service.ensure_api_call_allowed(user_email=my_email)


        search_parts = []

        # 날짜 설정 (기본값 일주일)
        today = datetime.now(timezone(timedelta(hours=9)))
        f_date = from_date or (today - timedelta(days=7)).strftime("%Y-%m-%d")
        t_date = to_date or today.strftime("%Y-%m-%d")

        # scope에 따른 필터 조건 설정
        #   - inboud    = 받은/참조된 메일
        #   - outbound  = 보낸 메일
        if scope == "received":
            search_parts.append(f"(to:{my_email} OR cc:{my_email})")
        elif scope == "sent":
            search_parts.append(f"from:{my_email}")
        date_range = f"{scope}:{get_format_to_utc(f_date)}..{get_format_to_utc(t_date, is_end=True)}"
        search_parts.append(date_range)

        # bool 필터 항목 추가
        if isRead is not None:
            search_parts.append(f"isRead:{str(isRead).lower()}")
        if isimportant is not None:
            importance_val = "high" if isimportant else "normal"
            search_parts.append(f"importance:{importance_val}")
        if isflagged:
            search_parts.append("isflagged:true") # KQL 표준 플래그 검색 양식
        if has_attachments:
            search_parts.append(f"hasattachment:true")
        
        # 문자열 필터 추가 
        if sender:
            search_parts.append(f'from:{sender}')
        if cc:
            search_parts.append(f'cc:{cc}')
        if category:
            search_parts.append(f'category:{category}')


        # 키워드 리스트 추가
        if keywords:
            # build_search_query 결과가 "A B" 라면 search_parts에 추가
            search_parts.append(self._build_search_query(keywords))

        # 검색 파트를 공백으로 합치기 (search에서는 공백이 AND 역할)
        full_search_string = " AND ".join( f"({part})" for part in search_parts )

        # 최종 경로 
        path = (
            f"/me/messages"
            f"?$count=true"
            f"&$top=250"
            f"&$select=id,conversationId,subject,from,sender,receivedDateTime,sentDateTime,bodyPreview,importance,isRead,hasAttachments"
            f"&$search=\"{full_search_string}\"" # 전체를 큰따옴표로 감싸는 것이 안전함
        )

        eamil_list = []
        
        while path:
            # nex_link 존재 하는 만큼 반복해서 수행
            result = await graph_request(
                method="GET",
                path=path,
                access_token=context.access_token,
                trace_id=context.trace_id,
                current_user=context.current_user,
                custom_headers={"ConsistencyLevel": "eventual"},
            )

            emails = result.get("value", [])
            eamil_list.extend(emails)

            # @odata.nextLink 존재 여부 확인 및 경로 갱신
            next_link = result.get("@odata.nextLink")
            if next_link:
                path = next_link.split("https://graph.microsoft.com/v1.0")[-1]
            else:
                path = None


        adapter = TypeAdapter(List[MailMessage])
        search_emails = adapter.validate_python(eamil_list)
        
    
        # 최신순 정렬 + conversaion_id 기준으로 마지막 하나만 남김 
        if search_emails:
            sort_field = "received_date_time" if scope == "received" else "sent_date_time"
            # search_emails.sort(key=lambda x: getattr(x, sort_field) or "", reverse=True)
            # 먼저 과거순으로 정렬 (오래된 메일 -> 최신 메일 순서)
            search_emails.sort(key=lambda x: getattr(x, sort_field) or "")
            unique_threads = {}
            for mail in search_emails:
                conversaion_id = mail.conversation_id

                if conversaion_id:
                    # 딕셔너리의 key를 conversaion_id으로 설정 함으로써, 최근 메일에 같은 conversaion_id가 나온다면 덮어 씌워진다.
                    unique_threads[conversaion_id] = mail
                else:
                    # conversaion_id 가 없으면 id를 Key로 개별 유지
                    unique_threads[mail.id] = mail
            
            # 유니크한 메일만 쌓여 있으므로 다시 최종 최신순 정렬 후 top_k 만큼만 반환 한다.
            final_emails = list(unique_threads.values())
            final_emails.sort(key=lambda x: getattr(x, sort_field) or "", reverse=True)

            logger.debug(f" total email:{len(eamil_list)}, unique email:{len(final_emails)} ")
            return final_emails[:top_k]

        return search_emails
    


    async def find_mail_folders_by_name(
        self,
        *,
        folder_name: str,
    ) -> list[dict]:
        """폴더 표시 이름으로 Outlook 메일 폴더를 찾습니다.
        현재 구현은 최상위 mailFolders 에서 displayName 이 같은 폴더만 찾습니다.
        """

        context = self._get_request_context()
        self._ensure_user_allowed(context)

        normalized_folder_name = folder_name.strip()
        if not normalized_folder_name:
            raise ValueError("조회할 폴더 이름이 누락되었습니다.")

        path = "/me/mailFolders/delta?$select=id,displayName,parentFolderId,totalItemCount,unreadItemCount"

        result = await graph_request(
            method="GET",
            path=path,
            access_token=context.access_token,
            trace_id=context.trace_id,
            current_user=context.current_user,
        )


        return [
            folder for folder in result.get("value", [])
            if (folder.get("displayName") or "").strip() == normalized_folder_name
        ]
    

    # ==================================================================================
    # folder_id 기준으로 '받은편지함' '보낸편지함' 등으로 조회하는 서비스 
    # graph 경로 "/me/mailFolders/{folder_id}/messages/~" 를 사용
    # ==================================================================================

    async def fetch_emails_folder(
        self,
        *,
        folder_id: Annotated[Optional[str],"메일 폴더 id ['inbox', 'sentitems', 'drafts', 'deleteditems', 'outbox', 'junk','archive']"] = "inbox",
        top_k: int = 10,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        isRead: Optional[bool] = None,
        isimportant: Optional[bool] = None,
        isflagged: Optional[bool] = None,
        sender: Annotated[Optional[str],"보낸사람 검색 이메일 주소 (이름검색 안됨)"] = None,
        cc: Optional[str] = None,
        has_attachments: Optional[bool] = None,
    ) -> list[MailMessage]:
        """최근 메일 목록 조회 
        top_k, blacklist, Graph path 구성 비즈니스 로직은 service 계층에서 처리합니다.
        """

        context = self._get_request_context()
        self._ensure_user_allowed(context)

        # Graph API 에 너무 큰 조회 요청을 보내지 않도록 max 50 설정
        normalized_top_k = max(1, min(top_k, 50))

        # 날짜 정렬 및 필터 기준 설정
        #   - inbox 포함 default -> receivedDateTime 받은시간 기준으로
        #   - sentItem -> sentDateTime 보낸시간 기준으로
        base_datetime = "sentDateTime" if folder_id == "sentitems" else "receivedDateTime"

        # from, to 공백일 경우 기본갑 설정 '일주일'
        today = datetime.now(timezone(timedelta(hours=9)))
        if from_date is None:
            from_date = (today - timedelta(days=7)).strftime("%Y-%m-%d")
        if to_date is None:
            to_date = today.strftime("%Y-%m-%d")


        # 필터 리스트 생성
        base_filter:list[str] = [
            f"{base_datetime} ge {get_format_to_utc(from_date)}",
            f"{base_datetime} le {get_format_to_utc(to_date,is_end=True)}",
        ]

        # bool 필터
        if isRead is not None:
            base_filter.append(f"isRead eq {str(isRead).lower()}")
        if isimportant is not None:
            importance_val = "high" if isimportant else "normal"
            base_filter.append(f"importance eq '{importance_val}'")
        if isflagged:
            base_filter.append("flag/flagStatus eq 'flagged'")
        if has_attachments is not None:
            base_filter.append(f"hasAttachments eq {str(has_attachments).lower()}")

        # 문자열 필터 (Sender/CC)
        if sender:
            s = self._escape_odata_string(sender)
            base_filter.append(f"(from/emailAddress/address eq '{s}' or from/emailAddress/name eq '{s}')")
        if cc:
            c = self._escape_odata_string(cc)
            base_filter.append(f"ccRecipients/any(c:c/emailAddress/address eq '{c}' or c/emailAddress/name eq '{c}')")
        
        # 필터 조립
        joined_filter = " and ".join(base_filter)
        
        # 최종 전체 경로 생성
        path = (
            f"/me/mailFolders/{folder_id}/messages"
            f"?$top={normalized_top_k}"
            f"&$select=id,subject,from,sender,{base_datetime},toRecipients,bodyPreview,importance,isRead,hasAttachments"
            f"&$orderby={base_datetime} desc"
            f"&$filter={joined_filter}"
        )
        
        result = await graph_request(
            method="GET",
            path=path,
            access_token=context.access_token,
            trace_id=context.trace_id,
            current_user=context.current_user,
        )

        adapter = TypeAdapter(List[MailMessage])
        return adapter.validate_python(result.get("value", []))
    
    
    async def search_emails_folder(
        self,
        *,
        folder_id: str = "inbox",
        keywords: str | list[str] | None = None,
        top_k: int = 10,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> list[MailMessage]:
        context = self._get_request_context()
        self._ensure_user_allowed(context)

        normalized_top_k = max(1, min(top_k, 50))
        
        
        search_parts = []

        # 날짜 설정 (기본값 일주일)
        today = datetime.now(timezone(timedelta(hours=9)))
        f_date = from_date or (today - timedelta(days=7)).strftime("%Y-%m-%d")
        t_date = to_date or today.strftime("%Y-%m-%d")

        # 날짜 필터 추가 
        base_prefix = "sent" if folder_id == "sentitems" else "received"
        date_range = f"{base_prefix}:{get_format_to_utc(f_date)}..{get_format_to_utc(t_date, is_end=True)}"
        search_parts.append(date_range)

        # 키워드 리스트 추가
        if keywords:
            # build_search_query 결과가 "A B" 라면 search_parts에 추가
            search_parts.append(self._build_search_query(keywords))

        # 검색 파트를 공백으로 합치기 (search에서는 공백이 AND 역할)
        full_search_string = " ".join(search_parts)

        # 정렬 기준 필드명 결정 (select용)
        date_field = f"{base_prefix}DateTime"

        # 최종 경로 
        path = (
            f"/me/mailFolders/{folder_id}/messages"
            f"?$top={normalized_top_k}"
            f"&$select=id,subject,from,sender,{date_field},bodyPreview,importance,isRead,hasAttachments"
            f"&$search=\"{full_search_string}\"" # 전체를 큰따옴표로 감싸는 것이 안전함
        )

        result = await graph_request(
            method="GET",
            path=path,
            access_token=context.access_token,
            trace_id=context.trace_id,
            current_user=context.current_user,
            custom_headers={"ConsistencyLevel": "eventual"},
        )

        adapter = TypeAdapter(List[MailMessage])
        return adapter.validate_python(result.get("value", []))
    

    

   
