from fastmcp import FastMCP
from loguru import logger
from typing import Annotated,Optional,Literal
from datetime import datetime
import httpx
from app.clients.graph_client import graph_request  
from fastmcp.server.dependencies import get_http_request
from app.models.user_info import UserInfo


def register_mail_tools(mcp: FastMCP):

    def _get_request_current_user() -> UserInfo | None:
        # Tool 이 HTTP 요청 바깥에서도 호출될 수 있어, 요청이 없으면 None 으로 둔다.
        try:
            request = get_http_request()
        except RuntimeError:
            logger.error(f"현재 사용자 정보를 가져오는 중 오류 발생: {str(e)}")
            return None

        return getattr(request.state, "current_user", None)


    def _build_base_filter(from_date: Optional[str] = None, to_date: Optional[str] = None) -> str:
        filters = []
        if from_date:
            filters.append(f"receivedDateTime ge {from_date}T00:00:00Z")
        if to_date:
            filters.append(f"receivedDateTime le {to_date}T23:59:59Z")
        return " and ".join(filters)

    @mcp.tool()
    async def get_recent_emails(
        tok_k: Annotated[int, "가져올 메일의 최대 개수 (1에서 50 사이의 정수, 기본 10)"] = 10,
        from_date: Annotated[Optional[str], "조회 시작일 (YYYY-MM-DD 형식). 조회시작일 기간이 주어지면 입력합니다."] = None,
        to_date: Annotated[Optional[str], "조회 종료일 (YYYY-MM-DD 형식). 조회종료일 기간이 주어지면 입력합니다."] = None,
        # email: Annotated[Optional[str], "메일을 조회할 사용자의 이메일 주소 (예: user@company.com). 특정인 지정이 없으면 비워둡니다."] = None
    ) -> list:
        """
        기간 내 최근 순서로 받은 메일을 조회합니다.
        Microsoft Graph API를 사용하여 메일함에서 최근 수신된 이메일 목록을 읽어옵니다.

        [LLM 에이전트 사용 가이드]
        1. 사용자가 "메일 확인해줘" 혹은 "오늘 메일 보여줘 보여줘", "지난주 메일 확인해줘" 등 기간을 명시하거나 또는 기간을 명시하지 않아도 메일을 확인 할 때 호출하세요. 사용자 요청으로 메일 확인 시 가장 기본적으로 호출하는 도구입니다. 
        2. 파라미터로 개수(tok_k)와 날짜 기간(from_date, to_date)을 필터를 선택적으로 적용 할 수 있습니다.
        3. 만약 사용자가 특정 기간을 명시하지 않으면, 기본적으로 최근 10개의 메일을 조회합니다.
        4. 반환값은 딕셔너리(dict) 요소들로 구성된 형태의 리스트(list)입니다. 필요한 항목(제목, 보낸사람, 받은 시간 등)을 가공하여 사용자에게 응답하세요.

        Args:
            - tok_k (int): 가져올 메일의 최대 개수 (기본값: 10, 최대: 50)
            - from_date (str, optional): 조회 시작일 (YYYY-MM-DD 형식)
            - to_date (str, optional): 조회 종료일 (YYYY-MM-DD 형식)

        Returns:
            list: 조건에 맞는 메일 정보들을 담고 있는 딕셔너리의 리스트입니다.
                예시: [{"id": "...", "subject": "...", "sender_address": "...", "sender_name": "...", "received_time": "..."}]
                에러가 발생할 경우, 리스트에 단일 딕셔너리 형태로 에러 메시지가 반환될 수 있습니다 (예: [{"error": "..."}]).
        """
        try:
            
            current_user = _get_request_current_user()
            # 1순위: current_user
            # 2순위: 기본값
            if current_user:
                query_email = current_user.email
                query_company_cd = current_user.company_cd
            else:
                # raise ValueError("현재 사용자 정보를 찾을 수 없습니다.")
                query_email = "admin@leodev901.onmicrosoft.com" #DEFAULT_USER_EMAIL
                query_company_cd = "leodev901" #DEFAULT_COMPANY_CD
            

            path = (
                f"/mailFolders/inbox/messages"
                f"?$top={tok_k}"
                f"&$select=id,subject,sender,receivedDateTime"
                f"&$orderby=receivedDateTime desc"
            )
            base_filter = _build_base_filter(from_date, to_date)
            if base_filter:
                path+="&$filter="+base_filter
            
            result = await graph_request(
                method="GET",
                path=path,
                user_email=query_email,
                company_cd=query_company_cd
            )

            emails = result.get("value", [])
            if not emails:
                return []
            
            parsed_emails = []
            for msg in emails:
                parsed_emails.append({
                    "id": msg.get("id"),
                    "subject": msg.get("subject", "(제목 없음)"),
                    "sender_address": msg.get("sender", {}).get("emailAddress", {}).get("address", "알 수 없음"),
                    "sender_name": msg.get("sender", {}).get("emailAddress", {}).get("name", "알 수 없음"),
                    "received_time": msg.get("receivedDateTime")
                })

            return parsed_emails
        except Exception as e:
            raise RuntimeError(f"최근 메일 조회 도중 오류 발생: {str(e)}")


    @mcp.tool()
    async def get_unread_emails(
        tok_k: Annotated[int, "가져올 안읽은 메일의 최대 개수 (1에서 50 사이의 정수)"] = 10,
        from_date: Annotated[Optional[str], "조회 시작일 (YYYY-MM-DD 형식). 특정 기간이 주어지면 입력합니다."] = None,
        to_date: Annotated[Optional[str], "조회 종료일 (YYYY-MM-DD 형식). 특정 기간이 주어지면 입력합니다."] = None,
        # email: Annotated[Optional[str], "메일을 조회할 사용자의 이메일 주소 (예: user@company.com). 특정인 지정이 없으면 비워둡니다."] = None
    ) -> list:
        """
        아직 읽지 않은 메일(isRead=false)을 조회합니다.
        Microsoft Graph API를 사용하여 메일함 내 사용자가 확인하지 않은 안읽은 메일 목록을 추출합니다.

        [LLM 에이전트 사용 가이드]
        1. 사용자가 "안읽은 메일 확인해줘"라고 요청할 때 사용합니다.
        2. 'from_date'와 'to_date'를 통해 특정 기간 내 안읽고 남아 있는 메일을 추려볼 수 있습니다.
        3. 반환 결과를 가공하여, "사용자가 읽지 않은 메일 n건 중 주요 내역은 다음과 같습니다..." 등의 형태로 응답할 때 용이합니다.

        Args:
            - tok_k (int): 가져올 메일의 최대 개수 (기본값: 10, 최대: 50)
            - from_date (str, optional): 조회 시작일 (YYYY-MM-DD 형식)
            - to_date (str, optional): 조회 종료일 (YYYY-MM-DD 형식)

        Returns:
            list: 조건에 맞는 안읽은 메일 정보가 담긴 구조화된 리스트 객체.
                에러나 실패 시엔 [{"error": "..."}] 포맷의 단일 항목 리스트가 떨어집니다.
        """
        try:
            current_user = _get_request_current_user()
            # 1순위: current_user
            # 2순위: 기본값
            if current_user:
                query_email = current_user.email
                query_company_cd = current_user.company_cd
            else:
                # raise ValueError("현재 사용자 정보를 찾을 수 없습니다.")
                query_email = "admin@leodev901.onmicrosoft.com" #DEFAULT_USER_EMAIL
                query_company_cd = "leodev901" #DEFAULT_COMPANY_CD
            

            path = (
                f"/mailFolders/inbox/messages"
                f"?$top={tok_k}"
                f"&$select=id,subject,sender,receivedDateTime,isRead"
                f"&$orderby=receivedDateTime desc"
            )

            filters = ["isRead eq false"]
            base_filter = _build_base_filter(from_date, to_date)
            if base_filter:
                filters.append(base_filter)

            if filters:
                path += f"&$filter={' and '.join(filters)}"

            result = await graph_request(
                method="GET",
                path=path,
                user_email=query_email,
                company_cd=query_company_cd
            )

            emails = result.get("value", [])

            parsed_emails = []
            for msg in emails:
                parsed_emails.append({
                    "id": msg.get("id"),
                    "subject": msg.get("subject", "(제목 없음)"),
                    "sender_address": msg.get("sender", {}).get("emailAddress", {}).get("address", "알 수 없음"),
                    "sender_name": msg.get("sender", {}).get("emailAddress", {}).get("name", "알 수 없음"),
                    "received_time": msg.get("receivedDateTime"),
                    "is_read": msg.get("isRead")
                })

            return parsed_emails
        except Exception as e:
            raise RuntimeError(f"안읽은 메일 조회 중 발생한 오류: {str(e)}")


    @mcp.tool()
    async def get_important_or_flagged_emails(
        tok_k: Annotated[int, "가져올 메일의 최대 개수 (1에서 50 사이의 정수)"] = 10,
        from_date: Annotated[Optional[str], "조회 시작일 (YYYY-MM-DD 형식). 특정 기간이 주어지면 입력합니다."] = None,
        to_date: Annotated[Optional[str], "조회 종료일 (YYYY-MM-DD 형식). 특정 기간이 주어지면 입력합니다."] = None,
        isimportant: Annotated[bool, "중요(high) 메일 포착 여부. 중요도가 높은 메일을 원하면 True"] = True,
        isflagged: Annotated[bool, "플래그(flagged) 지정 메일 포착 여부. 깃발 표시된 메일을 원하면 True"] = True,
        # email: Annotated[Optional[str], "메일을 조회할 사용자의 이메일 주소. 특정인 지정이 없으면 비워둡니다."] = None
    ) -> list:
        """
        중요도가 높거나(high) 깃발(플래그)이 꽂힌 메일들을 필터링해 조회합니다.

        [LLM 에이전트 사용 가이드]
        1. 주된 용도로는 사용자가 "요즘 나한테 온 메일 중에 중요한 거나 깃발 찍힌 거 있어?" 라고 물었을 때 호출합니다.
        2. isimportant 와 isflagged 파라미터를 통해 각각 중요메일만을 볼지, 플래그 메일만을 볼지 선택할 수 있습니다.
        3. 반환값은 딕셔너리 리스트이며, 각 항목에서 중요도(importance) 상태와 플래그(flag_status) 상태를 직접 확인할 수 있습니다.

        Args:
            - tok_k (int): 조회할 개수 (기본 10)
            - from_date (str, optional): 일정 시작
            - to_date (str, optional): 일정 끝
            - isimportant (bool): 중요도 높음(high) 조회 활성화 (기본 True)
            - isflagged (bool): 깃발 표시 조건 활용 여부 (기본 True)

        Returns:
            list: 조건에 맞는 중요/플래그 지정된 메일 목록
        """
        try:
            current_user = _get_request_current_user()
            # 1순위: current_user
            # 2순위: 기본값
            if current_user:
                query_email = current_user.email
                query_company_cd = current_user.company_cd
            else:
                # raise ValueError("현재 사용자 정보를 찾을 수 없습니다.")
                query_email = "admin@leodev901.onmicrosoft.com" #DEFAULT_USER_EMAIL
                query_company_cd = "leodev901" #DEFAULT_COMPANY_CD

            path = (
                f"/mailFolders/inbox/messages"
                f"?$top={tok_k}"
                f"&$select=id,subject,sender,receivedDateTime,importance,flag"
                f"&$orderby=receivedDateTime desc"
            )

            filter_conditions = []
            if isimportant:
                filter_conditions.append("importance eq 'high'")
            if isflagged:
                filter_conditions.append("flag/flagStatus eq 'flagged'")

            if not filter_conditions:
                return [{"error": "isimportant 또는 isflagged 속성 중 하나는 최소한 True여야 합니다."}]

            importance_flag_filter = "(" + " or ".join(filter_conditions) + ")"

            all_filters = [importance_flag_filter]
            base_filter = _build_base_filter(from_date, to_date)
            if base_filter:
                all_filters.append(base_filter)

            path += f"&$filter={' and '.join(all_filters)}"

            result = await graph_request(
                method="GET",
                path=path,
                user_email=query_email,
                company_cd=query_company_cd
            )

            emails = result.get("value", [])

            parsed_emails = []
            for msg in emails:
                parsed_emails.append({
                    "id": msg.get("id"),
                    "subject": msg.get("subject", "(제목 없음)"),
                    "sender_address": msg.get("sender", {}).get("emailAddress", {}).get("address", "알 수 없음"),
                    "sender_name": msg.get("sender", {}).get("emailAddress", {}).get("name", "알 수 없음"),
                    "received_time": msg.get("receivedDateTime"),
                    "importance": msg.get("importance", ""),
                    "flag_status": msg.get("flag", {}).get("flagStatus", "")
                })

            return parsed_emails
        except Exception as e:
            raise RuntimeError(f"동작 중 오류가 발생했습니다: {str(e)}")


    @mcp.tool()
    async def search_emails_by_keyword_advanced(
        keyword: Annotated[str, "검색할 키워드 (예: 회의결과, 정산, 오류). 반드시 채워져야 하는 **필수값**입니다."],
        tok_k: Annotated[int, "최대 조회 가능 메일 건수 (기본 10)"] = 10,
        from_date: Annotated[Optional[str], "조회 일자 제한 (시작일 YYYY-MM-DD 형식)"] = None,
        to_date: Annotated[Optional[str], "조회 일자 제한 (종료일 YYYY-MM-DD 형식)"] = None,
        scope: Annotated[Literal["제목", "본문", "all"], "검색 대상 필드 (제목, 본문, all 중 택 1). 기본값: all"] = "all",
        # email: Annotated[Optional[str], "대상 이메일"] = None
    ) -> list:
        """
        특정 키워드가 메일 제목 또는 본문에 포함되는지 검사하여 검색합니다. Graph API의 광범위한 풀텍스트 Search를 활용합니다.

        [LLM 에이전트 사용 가이드]
        1. 사용자가 "최근 회의 관련된 메일 찾아줘", "제목에 주간업무가 들어간 메일 보여줘" 등의 요청을 할 때 사용합니다.
        2. 'keyword'는 반드시 채워야 하며, 'scope'를 통해 세밀하게 제목에서만 찾을 것인지 범위 조정이 가능합니다.

        Args:
            - keyword (str): 대상 메일에서 반드시 추출할 주요 문자열. 이 필드는 **필수값**입니다.
            - tok_k (int): 가져올 최대 메일 개수
            - from_date (str, optional): 필터링할 시작 일시 범위.
            - to_date (str, optional): 필터링할 마지막 일시 범위.
            - scope (Literal["제목", "본문", "all"]): 검색 키워드 타겟 범위입니다.

        Returns:
            list: 검색된 메일 데이터가 파싱된 명시적 JSON 호환 딕셔너리 리스트입니다.
        """
        try:
            if not keyword.strip():
                return [{"error": "keyword 파라미터는 비어있을 수 없습니다."}]

            current_user = _get_request_current_user()
            # 1순위: current_user
            # 2순위: 기본값
            if current_user:
                query_email = current_user.email
                query_company_cd = current_user.company_cd
            else:
                # raise ValueError("현재 사용자 정보를 찾을 수 없습니다.")
                query_email = "admin@leodev901.onmicrosoft.com" #DEFAULT_USER_EMAIL
                query_company_cd = "leodev901" #DEFAULT_COMPANY_CD

            path = (
                f"/messages"
                f"?$top={tok_k}"
                f"&$select=id,subject,sender,receivedDateTime"
            )

            search_query = keyword
            if scope == "제목":
                search_query = f"subject:\"{keyword}\""
            else:
                search_query = f"\"{keyword}\""

            if from_date or to_date:
                if from_date:
                    search_query += f" AND received>={from_date}"
                if to_date:
                    search_query += f" AND received<={to_date}"

            path += f"&$search={search_query}"

            result = await graph_request(
                method="GET",
                path=path,
                user_email=query_email,
                company_cd=query_company_cd,
                custom_headers={"ConsistencyLevel": "eventual"}
            )

            emails = result.get("value", [])

            # Sort by latest since $search overrides default ordering
            emails = sorted(emails, key=lambda x: x.get("receivedDateTime", ""), reverse=True)

            parsed_emails = []
            for msg in emails:
                parsed_emails.append({
                    "id": msg.get("id"),
                    "subject": msg.get("subject", "(제목 없음)"),
                    "sender_address": msg.get("sender", {}).get("emailAddress", {}).get("address", "알 수 없음"),
                    "sender_name": msg.get("sender", {}).get("emailAddress", {}).get("name", "알 수 없음"),
                    "received_time": msg.get("receivedDateTime")
                })

            return parsed_emails
        except Exception as e:
            raise RuntimeError(f"키워드 검색 처리 중 예기치 못한 에러: {str(e)}")


    @mcp.tool()
    async def search_emails_by_sender_advanced(
        sender: Annotated[str, "검색할 발신자의 이메일 주소나 발신자 이름 (예: john.doe@mail.com). **필수값**입니다."],
        tok_k: Annotated[int, "최대 조회 건수"] = 10,
        from_date: Annotated[Optional[str], "조회 시작일 (YYYY-MM-DD 형식)"] = None,
        to_date: Annotated[Optional[str], "조회 종료일 (YYYY-MM-DD 형식)"] = None,
        # email: Annotated[Optional[str], "대상 이메일"] = None
    ) -> list:
        """
        특정 사람(발신자)으로부터 받은 메일을 모아서 조회합니다. 이메일 아이디 혹은 표시 이름으로 필터링이 가능합니다.

        [LLM 에이전트 사용 가이드]
        1. 사용자가 "존(John) 한테 온 메일들 좀 모아줘" "결제부서에서 온 메일 확인해"라고 요구할 때 활용합니다.
        2. 'sender' 파라미터는 필수적입니다. 이메일 주소 포맷이나 단순한 발신자명 기반 모두 탐지하려 시도합니다.

        Args:
            - sender (str): 발신자의 텍스트(이름 혹은 주소). 이 필드는 반드시 채워야 하는 **필수값**입니다.
            - tok_k (int): 로드할 메일 개수 하한과 상한
            - from_date (str, optional): 구체적 날짜 조건 지정
            - to_date (str, optional): 구체적 날짜 조건 지정

        Returns:
            list: 발송자 필터링이 통과된 정제된 딕셔너리 리스트.
        """
        try:
            if not sender.strip():
                return [{"error": "sender 값이 제공되어야 합니다."}]

            current_user = _get_request_current_user()
            # 1순위: current_user
            # 2순위: 기본값
            if current_user:
                query_email = current_user.email
                query_company_cd = current_user.company_cd
            else:
                # raise ValueError("현재 사용자 정보를 찾을 수 없습니다.")
                query_email = "admin@leodev901.onmicrosoft.com" #DEFAULT_USER_EMAIL
                query_company_cd = "leodev901" #DEFAULT_COMPANY_CD

            path = (
                f"/messages"
                f"?$top={tok_k}"
                f"&$select=id,subject,sender,receivedDateTime"
                f"&$orderby=receivedDateTime desc"
            )

            filters = [f"(from/emailAddress/address eq '{sender}' or from/emailAddress/name eq '{sender}')"]
            base_filter = _build_base_filter(from_date, to_date)
            if base_filter:
                filters.append(base_filter)

            path += f"&$filter={' and '.join(filters)}"

            try:
                result = await graph_request(
                    method="GET",
                    path=path,
                    user_email=query_email,
                    company_cd=query_company_cd
                )
                emails = result.get("value", [])
                is_search = False
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 400:
                    search_query = f"from:\"{sender}\""
                    if from_date: search_query += f" AND received>={from_date}"
                    if to_date: search_query += f" AND received<={to_date}"
                    
                    fallback_path = (
                        f"/messages"
                        f"?$top={tok_k}"
                        f"&$select=id,subject,sender,receivedDateTime"
                        f"&$search={search_query}"
                    )
                    
                    result = await graph_request(
                        method="GET",
                        path=fallback_path,
                        user_email=query_email,
                        company_cd=query_company_cd,
                        custom_headers={"ConsistencyLevel": "eventual"}
                    )
                    emails = result.get("value", [])
                    is_search = True
                else:
                    return [{"error": f"발신자 기반 검색 통신 실패(HTTP {e.response.status_code}): {e.response.text}"}]

            if locals().get("is_search"):
                emails = sorted(emails, key=lambda x: x.get("receivedDateTime", ""), reverse=True)

            parsed_emails = []
            for msg in emails:
                parsed_emails.append({
                    "id": msg.get("id"),
                    "subject": msg.get("subject", "(제목 없음)"),
                    "sender_address": msg.get("sender", {}).get("emailAddress", {}).get("address", "알 수 없음"),
                    "sender_name": msg.get("sender", {}).get("emailAddress", {}).get("name", "알 수 없음"),
                    "received_time": msg.get("receivedDateTime")
                })

            return parsed_emails
        except Exception as e:
            raise RuntimeError(f"발신자별 조회 실패: {str(e)}")


    @mcp.tool()
    async def search_emails_by_attachment(
        tok_k: Annotated[int, "최대 조회 건수"] = 10,
        from_date: Annotated[Optional[str], "조회 시작일 (YYYY-MM-DD 형식)"] = None,
        to_date: Annotated[Optional[str], "조회 종료일 (YYYY-MM-DD 형식)"] = None,
        filename: Annotated[Optional[str], "검색할 첨부파일명 (일부분만 맞아도 필터링 됨)"] = None,
        fileext: Annotated[Optional[str], "검색할 첨부파일의 확장자명. (예: pdf, jpg, docx)"] = None,
        # email: Annotated[Optional[str], "대상 이메일"] = None
    ) -> list:
        """
        첨부파일이 포함된 메일이거나, 혹은 특정한 첨부파일명이나 파일 확장자를 가진 메일만을 검색해냅니다.

        [LLM 에이전트 사용 가이드]
        1. 사용자가 "pdf가 첨부된 이메일", "결산 보고서 파일이 있는 메일" 등을 찾을 때 진입되는 라우팅 도구입니다.
        2. 'filename'이나 'fileext' 조건이 들어온다면, 첨부된 메일 중 조건과 일치하는 메일만을 필터링해 반환합니다.
        3. 조건 없이 요청하면 단순히 첨부파일이 존재하는 모든 최신 이메일을 탐색합니다.

        Args:
            - tok_k (int): 탐색할 메일 총량 설정 지표.
            - from_date (str, optional): 시간 탐색 지정 범위 한계선(시작)
            - to_date (str, optional): 시간 탐색 범위 한계선(끝)
            - filename (str, optional): 첨부파일명에 포함된 키워드. (빈 값이면 제한 무효)
            - fileext (str, optional): 확장자명 형식. (빈 값이면 제한 무효)

        Returns:
            list: 해당 첨부파일 조건에 부합하는 메일 및 메일의 첨부파일 이름 목록이 매핑된 Array Dictionary
        """
        try:
            current_user = _get_request_current_user()
            # 1순위: current_user
            # 2순위: 기본값
            if current_user:
                query_email = current_user.email
                query_company_cd = current_user.company_cd
            else:
                # raise ValueError("현재 사용자 정보를 찾을 수 없습니다.")
                query_email = "admin@leodev901.onmicrosoft.com" #DEFAULT_USER_EMAIL
                query_company_cd = "leodev901" #DEFAULT_COMPANY_CD

            path = (
                f"/messages"
                f"?$top={tok_k}"
                f"&$select=id,subject,sender,receivedDateTime,hasAttachments"
                f"&$expand=attachments($select=name,contentType,size)"
            )

            filters = ["hasAttachments eq true"]
            base_filter = _build_base_filter(from_date, to_date)
            if base_filter:
                filters.append(base_filter)

            path += f"&$filter={' and '.join(filters)}"

            result = await graph_request(
                method="GET",
                path=path,
                user_email=query_email,
                company_cd=query_company_cd
            )

            emails = result.get("value", [])
            matched_emails = []

            for msg in emails:
                attachments = msg.get("attachments", [])
                is_match = False

                if not filename and not fileext:
                    is_match = True
                else:
                    for att in attachments:
                        att_name = (att.get("name") or "").lower()

                        if fileext and att_name.endswith(fileext.lower()):
                            is_match = True
                        if filename and filename.lower() in att_name:
                            is_match = True

                        if is_match:
                            break

                if is_match:
                    # Store the exact names so the AI can relay them
                    exact_attachments = [a.get("name") for a in attachments if a.get("name")]

                    matched_emails.append({
                        "id": msg.get("id"),
                        "subject": msg.get("subject", "(제목 없음)"),
                        "sender_address": msg.get("sender", {}).get("emailAddress", {}).get("address", "알 수 없음"),
                        "sender_name": msg.get("sender", {}).get("emailAddress", {}).get("name", "알 수 없음"),
                        "received_time": msg.get("receivedDateTime"),
                        "attachments": exact_attachments
                    })

            return matched_emails
        except Exception as e:
            raise RuntimeError(f"첨부파일 식별 연산자에서 에러가 일어났습니다: {str(e)}")


    @mcp.tool()
    async def get_sent_emails(
        tok_k: Annotated[int, "가져올 보낸 메일의 최대 수"] = 10,
        from_date: Annotated[Optional[str], "조회 시작일 (YYYY-MM-DD 형식)"] = None,
        to_date: Annotated[Optional[str], "조회 종료일 (YYYY-MM-DD 형식)"] = None,
        # email: Annotated[Optional[str], "대상 이메일"] = None
    ) -> list:
        """
        내가 상대방에게 보냈었던 보낸편지함(Sent Items) 항목들을 검색합니다.

        [LLM 에이전트 사용 가이드]
        1. 사용자가 "내가 보낸 편지들", "발송에 성공한 메일들" 등에 대한 질의를 할 때 사용됩니다.
        2. 일반 메일 수신함과는 다르게 'receivedDateTime' 대신 'sentDateTime' 속성이 중점이 됩니다.
        3. to_addresses 필드를 통해 이메일을 누구에게 발송했는지를 확인할 수 있습니다.

        Args:
            - tok_k (int): 메일 추출 리미트 (기본값 10)
            - from_date (str, optional): 제한할 범위의 좌측 시작 일람
            - to_date (str, optional): 제한할 기간 범위의 우측 파라미터

        Returns:
            list: 발송을 완료한 이메일 목록 정보들에 대한 딕셔너리 구조.
        """
        try:
            current_user = _get_request_current_user()
            # 1순위: current_user
            # 2순위: 기본값
            if current_user:
                query_email = current_user.email
                query_company_cd = current_user.company_cd
            else:
                # raise ValueError("현재 사용자 정보를 찾을 수 없습니다.")
                query_email = "admin@leodev901.onmicrosoft.com" #DEFAULT_USER_EMAIL
                query_company_cd = "leodev901" #DEFAULT_COMPANY_CD

            path = (
                f"/mailFolders/sentitems/messages"
                f"?$top={tok_k}"
                f"&$select=id,subject,toRecipients,receivedDateTime,sentDateTime"
                f"&$orderby=sentDateTime desc"
            )

            base_filter = _build_base_filter(from_date, to_date)
            if base_filter:
                path += f"&$filter={base_filter.replace('receivedDateTime', 'sentDateTime')}"

            result = await graph_request(
                method="GET",
                path=path,
                user_email=query_email,
                company_cd=query_company_cd
            )

            emails = result.get("value", [])

            parsed_emails = []
            for msg in emails:
                # Recipients generally form an array
                to_recs = msg.get("toRecipients", [])
                to_addresses = [r.get("emailAddress", {}).get("address", "알 수 없음") for r in to_recs]
                to_names = [r.get("emailAddress", {}).get("name", "알 수 없음") for r in to_recs]

                parsed_emails.append({
                    "id": msg.get("id"),
                    "subject": msg.get("subject", "(제목 없음)"),
                    "to_addresses": to_addresses,
                    "to_names": to_names,
                    "sent_time": msg.get("sentDateTime")
                })

            return parsed_emails
        except Exception as e:
            raise RuntimeError(f"보낸 편지함 로드 스페이스에서 에러가 일어났습니다: {str(e)}")


    @mcp.tool()
    async def get_email_detail_view(
        id: Annotated[str, "조회할 원본 메일의 고유 ID 스트링입니다. 다른 조회 파이프라인에서 추출한 고유 id여야 합니다. 이 값은 반드시 채워져야 하는 **필수값**입니다."],
        # email: Annotated[Optional[str], "대상 이메일"] = None
    ) -> dict:
        """
        한 개의 지정된 메일에 대한 심층 내용. 메일 본문 내용 및 전체 첨부파일 데이터를 종합 조회합니다.

        [LLM 에이전트 사용 가이드]
        1. 사용자가 메일 목록 결과를 보고 "첫번째 메일 자세히 읽어줘" 등 메일 상세 조회 액션을 요구할 경우 호출합니다.
        2. 이전 Tool 도구 결괏값에서 가져온 특정 메일의 'id' 값을 필수로 파라미터에 집어넣어 이용합니다.
        3. 응답은 '하나의 dict' 노드로 떨어지며, 이 내부에 메일 본문과 파일 내용까지 담기므로 응답 시 깔끔하게 정리해 사용자에게 보여주세요.

        Args:
            - id (str): 열람하고자 하는 Microsoft Graph 메일 아이디. **필수값**입니다.

        Returns:
            dict: 찾으려고 한 단일 메일에 대한 모든 컴포넌트 데이터들의 오브젝트 모음입니다.
                예시로 본문을 의미하는 'body_content'나 첨부들의 'attachments'가 안에 내포되어 있습니다.
        """
        try:
            if not id or not str(id).strip():
                return {"error": "메일 ID가 누락되었습니다."}

            current_user = _get_request_current_user()
            # 1순위: current_user
            # 2순위: 기본값
            if current_user:
                query_email = current_user.email
                query_company_cd = current_user.company_cd
            else:
                # raise ValueError("현재 사용자 정보를 찾을 수 없습니다.")
                query_email = "admin@leodev901.onmicrosoft.com" #DEFAULT_USER_EMAIL
                query_company_cd = "leodev901" #DEFAULT_COMPANY_CD


            path = (
                f"/messages/{id}"
                f"?$expand=attachments($select=name,size)"
            )

            try:
                msg = await graph_request(
                    method="GET",
                    path=path,
                    user_email=query_email,
                    company_cd=query_company_cd,
                    custom_headers={"Prefer": 'outlook.body-content-type="text"'}
                )
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    return {"error": f"요청한 고유 아이디({id})의 원천 메일 데이터를 찾지 못했습니다."}
                return {"error": f"단일 메일 상세조회 연결 실패(HTTP {e.response.status_code}): {e.response.text}"}

            subject = msg.get("subject", "(제목 없음)")
            sender_address = msg.get("sender", {}).get("emailAddress", {}).get("address", "알 수 없음")
            sender_name = msg.get("sender", {}).get("emailAddress", {}).get("name", "알 수 없음")
            received = msg.get("receivedDateTime", "")
            body_content = msg.get("body", {}).get("content", "")

            attachments_info = []
            if msg.get("hasAttachments", False):
                attachments = msg.get("attachments", [])
                for att in attachments:
                    name = att.get("name", "Unknown")
                    size = att.get("size", 0)
                    attachments_info.append({
                        "name": name,
                        "size_bytes": size
                    })

            return {
                "id": id,
                "subject": subject,
                "sender_address": sender_address,
                "sender_name": sender_name,
                "received_time": received,
                "body_content": body_content,
                "attachments": attachments_info
            }
        except Exception as e:
            raise RuntimeError(f"특정 메일의 메타데이터 및 본문을 디코딩하지 못했습니다: {str(e)}")
