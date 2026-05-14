from typing import Optional
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from pydantic import TypeAdapter
from fastmcp.server.dependencies import get_http_request


from app.clients.graph_client import graph_request
from app.schema.mail import MailMessage
from app.schema.mail_hit_containers import MailHitsContainers
from app.schema.user import User
from app.common.exception import GraphAccessDeniedError
from app.common.logger import logger
from app.utils.date_utils import get_format_to_utc




@dataclass
class MailRequestContext:
    """메일 service 가 tool 실행 중 필요로 하는 요청 단위 값입니다.
    """
    access_token: str
    current_user: User
    trace_id: str
    blacklist: list[str]



class MailSearchAPIService:
    def __init__(self):
        pass

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
        사용자가 yellow_list 에 포함되어 있는지 검사합니다.
        이 검사는 Graph 호출 여부를 결정하는 비즈니스 규칙이므로 graph_client 가 아니라 service 계층에 둡니다.
        """

        user_email = (context.current_user.user_email or "").lower()
        user_id = context.current_user.user_id.lower()
        company_code = (context.current_user.company_code or "").lower()
        blocked_keys = {user_email, user_id, company_code}

        if blocked_keys.intersection(context.blacklist):
            raise GraphAccessDeniedError(context.current_user.user_email or context.current_user.user_id)

    
    async def search_my_mails(
        self,
        *,
        top_k: int = 50,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        isRead: Optional[bool] = None,
        isimportant: Optional[bool] = None,
        isflagged: Optional[bool] = None,
        sender: Optional[str] = None,
        cc: Optional[str] = None,
        has_attachments: Optional[bool] = None,
        keywords: list[str] | None = None,
    )->list[MailMessage]:
        
        context = self._get_request_context()
        self._ensure_user_allowed(context)

        # from, to 없을 경우 일주일 기본 세팅
        today = datetime.now(timezone(timedelta(hours=9)))
        if from_date is None:
            from_date = (today - timedelta(days=7)).strftime("%Y-%m-%d")
        if to_date is None:
            to_date = today.strftime("%Y-%m-%d")
            
        # 기존 조건 from~to
        query_parts:list[str] =[ f'received:{get_format_to_utc(from_date)}..{get_format_to_utc(to_date,is_end=True)}' ]
        
        # 조건에 따른 query 조합하기
        if isRead is not None: 
            query_parts.append(f"isRead:{isRead}")
        
        if isimportant is True:
            query_parts.append("importance:high")
        
        if isflagged is not None:
            query_parts.append(f"isflagged:{str(isflagged).lower()}")

        if sender:
            query_parts.append(f'from:"{sender}"')

        if cc:
            query_parts.append(f'cc:"{cc}"')

        if has_attachments is not None:
            query_parts.append(f"hasattachments:{str(has_attachments).lower()}")
        
        if keywords is not None:
            kw_query = " AND ".join(f'"{k}"' for k in keywords)
            query_parts.append(f"({kw_query})")

        # 최종 쿼리 조합
        full_query = "AND ".join( f"({query})" for query in query_parts )

        logger.debug(f"full_query: {full_query}")

        path = f"/search/query"
        payload = {
            "requests": [
                {
                    "entityTypes": ["message"],
                    "query": {
                        "queryString": full_query
                    },
                    "from": 0,
                    "size": top_k,
                    "fields": [
                        "id", 
                        "subject", 
                        "toRecipients",
                        "sentDateTime",
                        "from", 
                        "receivedDateTime", 
                        "importance", 
                        "isRead", 
                        "hasAttachments", 
                        "bodyPreview",
                    ]
                }
            ]
        }

        result = await graph_request(
            method="POST",
            path=path,
            access_token=context.access_token,
            trace_id=context.trace_id,
            current_user=context.current_user,
            json_body=payload
        )

        containers = result.get("value", [{}])[0].get("hitsContainers", [])
        if not containers:
            return []

        adapter = TypeAdapter(MailHitsContainers)
        search_result = adapter.validate_python(containers[0])
        return search_result.convert_mail_message()
        