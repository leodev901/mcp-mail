from typing import Annotated, Optional, Literal
from pydantic import Field
from fastmcp import FastMCP

from app.service.mail_service import MailService
from app.schema.mail import MailMessage, MailMessageDetail


def register_mail_tools(mcp: FastMCP) -> None:
    """
    메일 관련 MCP Tool을 등록합니다.
    Tool 함수는 파라미터 설명과 반환 계약에 집중하고 실제 로직은 서비스 계층에 위임합니다.
    """

    mail_service = MailService()

    @mcp.tool()
    async def get_recent_emails(
        from_date: Annotated[Optional[str], Field(None, description="조회 시작일 (YYYY-MM-DD 형식). 시작일 기간이 주어지면 입력합니다.",examples=["2026-04-01"])],
        to_date: Annotated[Optional[str], Field(None, description="조회 종료일 (YYYY-MM-DD 형식). 종료일 기간이 주어지면 입력합니다.",examples=["2026-04-30"])],
        top_k: Annotated[int, Field(...,description="가져올 메일의 최대 개수 (1~50 사이 정수, 기본 10)",examples=[10])]=10
    ) -> list[MailMessage]:
        """기간 내 최근 순서로 받은 메일을 조회합니다.
        Microsoft Graph API를 사용하여 메일함에서 최근 수신된 이메일 목록을 읽어옵니다.

        [LLM 에이전트 사용 가이드]
        1. 사용자가 "메일 확인해줘", "오늘 메일 보여줘", "지난주 메일 확인해줘" 처럼 메일 확인을 요청할 때 호출하는 기본 도구 입니다.
        2. 파라미터로 개수(top_k)와 날짜 기간(from_date, to_date)을 선택적으로 적용할 수 있습니다.
        3. 사용자가 특정 기간과 갯수를 명시하지 않으면 최근 30일 기간 내 10개의 메일을 기본 조회합니다.
        """

        # Tool은 입력 파라미터를 서비스로 그대로 넘기고, 비즈니스 조합은 서비스가 담당합니다.
        return await mail_service.fetch_my_mails(
            top_k=top_k,
            from_date=from_date,
            to_date=to_date,
        )


    @mcp.tool()
    async def get_unread_emails(
        from_date: Annotated[Optional[str], Field(None, description="조회 시작일 (YYYY-MM-DD 형식). 시작일 기간이 주어지면 입력합니다.",examples=["2026-04-01"])],
        to_date: Annotated[Optional[str], Field(None, description="조회 종료일 (YYYY-MM-DD 형식). 종료일 기간이 주어지면 입력합니다.",examples=["2026-04-30"])],
        top_k: Annotated[int, Field(...,description="가져올 메일의 최대 개수 (1~50 사이 정수, 기본 10)",examples=[10])]=10
    ) -> list[MailMessage]:
        """아직 읽지 않은 메일(isRead=false)을 조회합니다.
        Microsoft Graph API를 사용하여 메일함 내 사용자가 확인하지 않은 안읽은 메일 목록을 추출합니다.

        [LLM 에이전트 사용 가이드]
        1. 사용자가 "안읽은 메일" 혹은 "미확인 메일" 등 아직 읽지 않은 메일들 만 확인 요청할 때 사용합니다.
        2. 파라미터로 개수(top_k)와 날짜 기간(from_date, to_date)을 선택적으로 적용할 수 있습니다.
        3. 사용자가 특정 기간과 갯수를 명시하지 않으면 최근 30일 기간 내 10개의 메일을 기본 조회합니다.
        """
        return await mail_service.fetch_my_mails(
            top_k=top_k,
            from_date=from_date,
            to_date=to_date,
            isRead=False,
        )


    @mcp.tool()
    async def get_important_emails(
        from_date: Annotated[Optional[str], Field(None, description="조회 시작일 (YYYY-MM-DD 형식). 시작일 기간이 주어지면 입력합니다.",examples=["2026-04-01"])],
        to_date: Annotated[Optional[str], Field(None, description="조회 종료일 (YYYY-MM-DD 형식). 종료일 기간이 주어지면 입력합니다.",examples=["2026-04-30"])],
        top_k: Annotated[int, Field(...,description="가져올 메일의 최대 개수 (1~50 사이 정수, 기본 10)",examples=[10])]=10,
        isimportant: Annotated[bool, "중요(high) 메일 포착 여부. 중요도가 높은 메일을 원하면 True"] = True,
    ) -> list:
        """내 메일 중 중요도가 높은(high) 메일을 필터링해 조회합니다.

        [LLM 에이전트 사용 가이드]
        1. 주된 용도로는 사용자가 "요즘 나한테 온 메일 중에 중요한 메일 있어?" 와 유사한 질문을 했을 때 호출 합니다.
        2. isimportant 파라미터를 통해 각각 중요메일만 가져올 수 있습니다.
        3. 파라미터로 개수(top_k)와 날짜 기간(from_date, to_date)을 선택적으로 적용할 수 있습니다.
        4. 사용자가 특정 기간과 갯수를 명시하지 않으면 최근 30일 기간 내 10개의 메일을 기본 조회합니다.
        """

        return await mail_service.fetch_my_mails(
            top_k=top_k,
            from_date=from_date,
            to_date=to_date,
            isimportant=isimportant,
        )

    @mcp.tool()
    async def get_flagged_emails(
        from_date: Annotated[Optional[str], Field(None, description="조회 시작일 (YYYY-MM-DD 형식). 시작일 기간이 주어지면 입력합니다.",examples=["2026-04-01"])],
        to_date: Annotated[Optional[str], Field(None, description="조회 종료일 (YYYY-MM-DD 형식). 종료일 기간이 주어지면 입력합니다.",examples=["2026-04-30"])],
        top_k: Annotated[int, Field(...,description="가져올 메일의 최대 개수 (1~50 사이 정수, 기본 10)",examples=[10])]=10,
        isflagged: Annotated[bool, "플래그(flagged) 지정 메일 포착 여부. 깃발 표시된 메일을 원하면 True"] = True,
    ) -> list:
        """내 메일 중 중요도가 깃발(플래그)이 꽂힌 메일을 필터링해 조회합니다.

        [LLM 에이전트 사용 가이드]
        1. 주된 용도로는 사용자가 "깃발 찍힌 메일 보여줘" 와 유사한 질문을 했을 때 호출 합니다.
        2. isflagged 파라미터를 통해 플래그 메일만을 볼지 선택할 수 있습니다.
        3. 파라미터로 개수(top_k)와 날짜 기간(from_date, to_date)을 선택적으로 적용할 수 있습니다.
        4. 사용자가 특정 기간과 갯수를 명시하지 않으면 최근 30일 기간 내 10개의 메일을 기본 조회합니다.
        """

        return await mail_service.fetch_my_mails(
            top_k=top_k,
            from_date=from_date,
            to_date=to_date,
            isflagged=isflagged,
        )

        

    @mcp.tool()
    async def  get_emails_sender(
        sender: Annotated[str, Field(..., description="검색할 발신자의 이메일 주소나 표시 이름입니다. 단일 값으로 입력하며 반드시 채워야 합니다.", examples=["john.doe@mail.com", "홍길동", "결제부서"])],
        from_date: Annotated[Optional[str], Field(None, description="검색 결과를 KST 기준으로 후처리 필터링할 시작일 (YYYY-MM-DD 형식). 기간 의도가 있으면 입력합니다.",examples=["2026-04-01"])],
        to_date: Annotated[Optional[str], Field(None, description="검색 결과를 KST 기준으로 후처리 필터링할 종료일 (YYYY-MM-DD 형식). 기간 의도가 있으면 입력합니다.",examples=["2026-04-30"])],
        top_k: Annotated[int, Field(...,description="가져올 메일의 최대 개수 (1~50 사이 정수, 기본 10)",examples=[10])]=10,
    ) -> list[MailMessage]:
        """보낸사람(발신자)로 메일을 검색합니다. 
        이메일 아이디 혹은 표시 이름(display name)으로 필터링이 가능합니다.

        [LLM 에이전트 사용 가이드]
        1. 사용자가 "존(John) 한테 온 메일들 좀 모아줘" "결제부서에서 온 메일 확인해"라고 요구할 때 활용합니다.
        2. sender 파라미터는 필수값이며, 이메일 주소 또는 표시 이름 중 하나를 단일 문자열로 입력합니다.
        3. from_date, to_date는 검색 결과를 Graph 조회 이후 KST 기준으로 후처리 필터링할 때 사용합니다.
        4. 사용자가 특정 기간과 갯수를 명시하지 않으면 최근 30일 기간 내 10개의 메일을 기본 조회합니다.

        """
        return await mail_service.fetch_my_mails(
            top_k=top_k,
            from_date=from_date,
            to_date=to_date,
            sender=sender,
        )
    
    @mcp.tool()
    async def get_emails_cc(
        cc: Annotated[str, Field(..., description="검색할 참조자(CC)의 이메일 주소나 표시 이름입니다. 단일 값으로 입력하며 반드시 채워야 합니다.", examples=["john.doe@mail.com", "홍길동", "결제부서"])],
        from_date: Annotated[Optional[str], Field(None, description="검색 결과를 KST 기준으로 후처리 필터링할 시작일 (YYYY-MM-DD 형식). 기간 의도가 있으면 입력합니다.",examples=["2026-04-01"])],
        to_date: Annotated[Optional[str], Field(None, description="검색 결과를 KST 기준으로 후처리 필터링할 종료일 (YYYY-MM-DD 형식). 기간 의도가 있으면 입력합니다.",examples=["2026-04-30"])],
        top_k: Annotated[int, Field(...,description="가져올 메일의 최대 개수 (1~50 사이 정수, 기본 10)",examples=[10])]=10,
    ) -> list[MailMessage]:
        """참조자(CC)로 메일을 검색합니다.
        이메일 아이디 혹은 표시 이름(display name)으로 필터링이 가능합니다.

        [LLM 에이전트 사용 가이드]
        1. 사용자가 "참조에 존(John)이 들어간 메일 찾아줘" "CC에 결제부서가 있는 메일 확인해"라고 요구할 때 활용합니다.
        2. cc 파라미터는 필수값이며, 이메일 주소 또는 표시 이름 중 하나를 단일 문자열로 입력합니다.
        3. from_date, to_date는 검색 결과를 Graph 조회 이후 KST 기준으로 후처리 필터링할 때 사용합니다.
        4. 사용자가 특정 기간과 갯수를 명시하지 않으면 최근 30일 기간 내 10개의 메일을 기본 조회합니다.

        """
        return await mail_service.fetch_my_mails(
            top_k=top_k,
            from_date=from_date,
            to_date=to_date,
            cc=cc,
        )
    

    @mcp.tool()
    async def get_email_attachment(
        from_date: Annotated[Optional[str], Field(None, description="조회 시작일 (YYYY-MM-DD 형식). 시작일 기간이 주어지면 입력합니다.",examples=["2026-04-01"])],
        to_date: Annotated[Optional[str], Field(None, description="조회 종료일 (YYYY-MM-DD 형식). 종료일 기간이 주어지면 입력합니다.",examples=["2026-04-30"])],
        top_k: Annotated[int, Field(...,description="가져올 메일의 최대 개수 (1~50 사이 정수, 기본 10)",examples=[10])]=10,
    ) -> list[MailMessage]:
        """첨부파일이 있는 메일을 조회합니다.
        일반 메일 목록 조회에서는 첨부파일 이름이나 확장자를 알 수 없으므로 첨부파일 존재 여부만 필터링합니다.

        [LLM 에이전트 사용 가이드]
        1. 사용자가 "첨부파일 있는 메일 찾아줘" "파일 첨부된 메일 보여줘"라고 요구할 때 활용합니다.
        2. 이 도구는 첨부파일 이름이나 확장자를 기준으로 검색하지 않고, 첨부파일이 있는 메일만 조회합니다.
        3. 파라미터로 개수(top_k)와 날짜 기간(from_date, to_date)을 선택적으로 적용할 수 있습니다.
        4. 사용자가 특정 기간과 갯수를 명시하지 않으면 최근 30일 기간 내 10개의 메일을 기본 조회합니다.
        """
        return await mail_service.fetch_my_mails(
            top_k=top_k,
            from_date=from_date,
            to_date=to_date,
            has_attachments=True,
        )
    
    @mcp.tool()
    async def search_emails_title(
        keywords: Annotated[list[str], Field(...,description="검색할 키워드 목록입니다. 각 키워드는 2자 이상이어야 하며, 여러 키워드는 ['회의', '결과']처럼 배열로 나눠 입력합니다.",examples=[["회의", "결과"], ["정산"], ["오류", "로그"]])],
        # scope: Annotated[Literal["title", "content", "all"], Field(...,description="검색 대상 필드입니다. title은 제목, content는 본문, all은 제목/본문 전체 검색에 사용합니다.",examples=["title", "content", "all"])],
        from_date: Annotated[Optional[str], Field(None, description="검색 결과를 KST 기준으로 후처리 필터링할 시작일 (YYYY-MM-DD 형식). 기간 의도가 있으면 입력합니다.",examples=["2026-04-01"])],
        to_date: Annotated[Optional[str], Field(None, description="검색 결과를 KST 기준으로 후처리 필터링할 종료일 (YYYY-MM-DD 형식). 기간 의도가 있으면 입력합니다.",examples=["2026-04-30"])],
        top_k: Annotated[int, Field(...,description="가져올 메일의 최대 개수 (1~50 사이 정수, 기본 10)",examples=[10])]=10,
        
    ) -> list[MailMessage]:
        """키워드로 메일 검색 하기 
        메일 제목에서 키워드가 포함된 메일을 찾아서 보여줍니다.

        [LLM 에이전트 사용 가이드]
        1. 사용자가 "최근 '회의' 관련된 메일 찾아줘", "제목에 '주간업무'가 들어간 메일 보여줘" 등의 요청을 할 때 사용합니다.
        2. 검색어는 keywords 배열에 넣으며, 각 키워드는 2자 이상이어야 합니다.
        3. 여러 키워드는 ["회의", "결과"]처럼 나눠 보내고, 서비스에서는 모든 키워드가 함께 걸리도록 검색 범위를 좁힙니다.
        4. 사용자가 특정 기간과 갯수를 명시하지 않으면 최근 30일 기간 내 10개의 메일을 기본 조회합니다.
        """

        # 키워드 검색은 Graph $search 제약이 있어 일반 목록 조회와 분리된 service 메서드로 구현
        return await mail_service.search_my_mails(
            top_k=top_k,
            from_date=from_date,
            to_date=to_date,
            keywords=keywords,
            scope="title",
        )
    
    @mcp.tool()
    async def search_emails_content(
        keywords: Annotated[list[str], Field(...,description="검색할 키워드 목록입니다. 각 키워드는 2자 이상이어야 하며, 여러 키워드는 ['회의', '결과']처럼 배열로 나눠 입력합니다.",examples=[["회의", "결과"], ["정산"], ["오류", "로그"]])],
        # scope: Annotated[Literal["title", "content", "all"], Field(...,description="검색 대상 필드입니다. title은 제목, content는 본문, all은 제목/본문 전체 검색에 사용합니다.",examples=["title", "content", "all"])],
        from_date: Annotated[Optional[str], Field(None, description="검색 결과를 KST 기준으로 후처리 필터링할 시작일 (YYYY-MM-DD 형식). 기간 의도가 있으면 입력합니다.",examples=["2026-04-01"])],
        to_date: Annotated[Optional[str], Field(None, description="검색 결과를 KST 기준으로 후처리 필터링할 종료일 (YYYY-MM-DD 형식). 기간 의도가 있으면 입력합니다.",examples=["2026-04-30"])],
        top_k: Annotated[int, Field(...,description="가져올 메일의 최대 개수 (1~50 사이 정수, 기본 10)",examples=[10])]=10,
        
    ) -> list[MailMessage]:
        """키워드로 메일 검색 하기 
        메일 제목에서 키워드가 포함된 메일을 찾아서 보여줍니다.

        [LLM 에이전트 사용 가이드]
        1. 사용자가 "최근 '회의' 관련된 메일 찾아줘", "내용에 '주간업무'가 들어간 메일 보여줘" 등의 요청을 할 때 사용합니다.
        2. 검색어는 keywords 배열에 넣으며, 각 키워드는 2자 이상이어야 합니다.
        3. 여러 키워드는 ["회의", "결과"]처럼 나눠 보내고, 서비스에서는 모든 키워드가 함께 걸리도록 검색 범위를 좁힙니다.
        4. 사용자가 특정 기간과 갯수를 명시하지 않으면 최근 30일 기간 내 10개의 메일을 기본 조회합니다.
        """

        # 키워드 검색은 Graph $search 제약이 있어 일반 목록 조회와 분리된 service 메서드로 구현
        return await mail_service.search_my_mails(
            top_k=top_k,
            from_date=from_date,
            to_date=to_date,
            keywords=keywords,
            scope="content",
        )


    @mcp.tool()
    async def get_sent_emails(
        from_date: Annotated[Optional[str], Field(None, description="조회 시작일 (YYYY-MM-DD 형식). 시작일 기간이 주어지면 입력합니다.",examples=["2026-04-01"])],
        to_date: Annotated[Optional[str], Field(None, description="조회 종료일 (YYYY-MM-DD 형식). 종료일 기간이 주어지면 입력합니다.",examples=["2026-04-30"])],
        top_k: Annotated[int, Field(...,description="가져올 보낸 메일의 최대 개수 (1~50 사이 정수, 기본 10)",examples=[10])]=10,
    ) -> list[MailMessage]:
        """보낸편지함(Sent Items)의 메일을 최근 순서로 조회합니다.
        Microsoft Graph API를 사용하여 내가 보낸 이메일 목록을 읽어옵니다.

        [LLM 에이전트 사용 가이드]
        1. 사용자가 "내가 보낸 메일 보여줘", "어제 발송한 메일 확인해줘" 처럼 보낸편지함 확인을 요청할 때 호출합니다.
        2. 파라미터로 개수(top_k)와 날짜 기간(from_date, to_date)을 선택적으로 적용할 수 있습니다.
        3. 보낸편지함은 수신 시간이 아니라 발신 시간(sentDateTime)을 기준으로 최신순 조회합니다.
        4. 사용자가 특정 기간과 갯수를 명시하지 않으면 최근 30일 기간 내 10개의 메일을 기본 조회합니다.
        """
        return await mail_service.fetch_my_sent_mails(
            top_k=top_k,
            from_date=from_date,
            to_date=to_date,
        )


    @mcp.tool()
    async def get_email_detail(
        id: Annotated[str, Field(..., description="상세 조회할 메일의 고유 ID입니다. 반드시 get_recent_emails, get_unread_emails, get_sent_emails 같은 목록 조회 도구 결과에서 받은 id 값을 그대로 입력해야 합니다.", examples=["AAMkAGVmMDEz..."])],
    ) -> MailMessageDetail:
        """메일 고유 ID로 단일 메일의 상세 정보를 조회합니다.
        본문(body)과 첨부파일 메타데이터(attachments)를 포함한 상세 정보를 가져옵니다.

        [LLM 에이전트 사용 가이드]
        1. 사용자가 메일 목록 결과를 보고 "첫번째 메일 자세히 읽어줘" "이 메일 본문 보여줘"처럼 상세 내용을 요청할 때 호출합니다.
        2. 이 도구는 사용자의 자연어만으로 바로 호출하지 말고, 먼저 목록 조회 도구를 호출해 대상 메일의 id를 확보한 뒤 호출합니다.
        3. id 파라미터에는 목록 조회 결과의 id 값을 수정하지 말고 그대로 넣어야 합니다.
        4. 응답에는 제목, 발신자, 수신/발신 시각, 본문, 첨부파일 메타데이터가 포함됩니다.
        """
        return await mail_service.fetch_my_mail_detail(mail_id=id)
    

    @mcp.tool()
    async def get_emails_folder(
        folder_name: Annotated[str, Field(..., description="조회할 Outlook 메일 폴더 이름입니다. 사용자가 만든 폴더명과 정확히 일치해야 합니다.",examples=["청구서", "내 폴더"])],
        from_date: Annotated[Optional[str], Field(None, description="조회 시작일 (YYYY-MM-DD 형식). 시작일 기간이 주어지면 입력합니다.",examples=["2026-04-01"])],
        to_date: Annotated[Optional[str], Field(None, description="조회 종료일 (YYYY-MM-DD 형식). 종료일 기간이 주어지면 입력합니다.",examples=["2026-04-30"])],
        top_k: Annotated[int, Field(...,description="가져올 메일의 최대 개수 (1~50 사이 정수, 기본 10)",examples=[10])]=10,
    ) -> list[MailMessage]:
        """특정 Outlook 메일 폴더의 메일을 조회합니다.
        폴더 이름으로 folder id를 먼저 찾고, 찾은 folder id를 사용해 해당 폴더의 메일을 조회합니다.

        [LLM 에이전트 사용 가이드]
        1. 사용자가 "청구서 폴더의 메일 보여줘"처럼 특정 메일 폴더를 명시할 때 호출합니다.
        2. folder_name은 Outlook 왼쪽 폴더 목록에 보이는 이름과 정확히 일치해야 합니다.
        3. 같은 이름의 폴더가 여러 개 있으면 안전한 조회를 위해 에러를 반환합니다.
        4. 사용자가 특정 기간과 갯수를 명시하지 않으면 최근 30일 기간 내 10개의 메일을 기본 조회합니다.
        """

        # folder_name 이름으로 folder_id 가져오는 서비스 구현 
        folders = await mail_service.find_mail_folders_by_name(folder_name=folder_name)

        if len(folders) == 0:
            raise ValueError(f"사서함에 {folder_name}이름의 폴더가 없습니다.")
        elif len(folders) > 1:
            raise ValueError(f"사서함에 {folder_name}이름의 폴더가 여러개이므로 조회 할 수 없습니다.")
        else:
            folder_id = folders[0]["id"]

        
        return await mail_service.fetch_my_mails(
            top_k=top_k,
            from_date=from_date,
            to_date=to_date,
            folder_id=folder_id,
        )


        
