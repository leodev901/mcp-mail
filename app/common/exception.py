

# Graph API 관련 에러 정의

class GraphClientError(Exception):
    """
    Graph API 호출 실패를 MCP ToolError 메시지로 바꾸기 위한 기본 예외입니다.
    ToolError 는 구조화 필드를 받지 않으므로, 예외 문자열 자체가 최종 출력 포맷이 되게 만듭니다.
    """

    code = "GRAPH_CLIENT_ERROR"
    message = "Microsoft Graph API 호출에 실패했습니다."

    def __init__(self, detail: str = "") -> None:
        # detail 은 Graph 원본 오류처럼 디버깅에 필요한 상세 문맥을 담는 문자열입니다.
        # super().__init__ 에 최종 메시지를 넣어 ToolError 변환 시 str(exc) 만 사용하게 합니다.
        self.detail = detail
        super().__init__(self.to_tool_message())

    def to_tool_message(self) -> str:
        """
        MCP 클라이언트가 읽을 최종 tool error 메시지를 만듭니다.
        FastMCP ToolError 는 message 하나만 전달하므로 code/detail 을 문자열에 명시합니다.
        """
        return f"[{self.code}] {self.message} detail={self.detail}"


class GraphAccessDeniedError(GraphClientError):
    """MS Graph API 접근이 허용되지 않은 사용자일 때 발생합니다."""

    code = "GRAPH_ACCESS_DENIED"
    message = "해당 사용자는 접근이 허용되지 않습니다."

    def __init__(self, email: str) -> None:
        # email 을 detail 로 넘기면 공통 출력 형식은 유지하면서 원인을 함께 전달할 수 있습니다.
        super().__init__(f"email:{email}")


class GraphBadRequestError(GraphClientError):
    """MS Graph API에 잘못된 요청 파라미터를 보냈을 때 발생합니다."""

    code = "GRAPH_BAD_REQUEST"
    message = "잘못된 요청 파라미터/문법입니다."


class GraphUnauthorizedError(GraphClientError):
    """MS Graph API 인증 실패 시 발생합니다."""

    code = "GRAPH_UNAUTHORIZED"
    message = "인증 실패입니다."


class GraphForbiddenError(GraphClientError):
    """MS Graph API 권한 부족 시 발생합니다."""

    code = "GRAPH_FORBIDDEN"
    message = "접근 권한이 없습니다."


class GraphResourceNotFoundError(GraphClientError):
    """MS Graph API에서 리소스를 찾지 못했을 때 발생합니다."""

    code = "GRAPH_RESOURCE_NOT_FOUND"
    message = "해당 리소스를 찾을 수 없습니다. 사용자 이메일 또는 이벤트 ID를 확인해주세요."


# MCP CMN(공통) 호출 관련 에러 정의

class CmnAuthError(Exception):
    """
    CMN 인증 API 호출 실패를 app 계층에서 다루기 위한 기본 예외입니다.
    code/message/detail 을 명시적으로 들고 있으면 MCP 전역 예외 미들웨어가 일관된 tool 응답을 만들 수 있습니다.
    """

    def __init__(
        self,
        code: str,
        message: str,
        *,
        detail: str = "",
        connect_url: str | None = None,
    ) -> None:
        # super().__init__ 는 파이썬 표준 예외 메시지를 초기화하는 문법입니다.
        # 별도 필드도 함께 저장해 LLM 이 읽기 쉬운 구조화 응답으로 변환합니다.
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail
        self.connect_url = connect_url


class CmnAuthorizationMissingError(CmnAuthError):
    """
    요청에 사용자 토큰이 없어서 CMN 에 사용자 컨텍스트를 물어볼 수 없는 상태입니다.
    app 은 JWT 를 해석하지 않으므로, 토큰 부재를 여기서 명확하게 중단합니다.
    """

    def __init__(self) -> None:
        super().__init__(
            "CMN_AUTHORIZATION_MISSING",
            "사용자 인증 정보가 없어 공통 인증 API를 호출할 수 없습니다.",
        )


class CmnDelegatedTokenRequiredError(CmnAuthError):
    """
    사용자의 Microsoft 365 위임 권한 토큰이 아직 없거나 갱신할 수 없는 상태입니다.
    이 예외는 tool 실패라기보다 사용자에게 동의 절차가 필요하다는 안내 응답으로 바뀝니다.
    """

    def __init__(self, detail: str = "") -> None:
        super().__init__(
            "CMN_DELEGATED_TOKEN_REQUIRED",
            "Microsoft 365 위임 권한 토큰이 없어 먼저 동의가 필요합니다.",
            detail=detail,
        )


class CmnDelegatedTokenResponseError(CmnAuthError):
    """
    CMN 응답이 app 이 기대하는 계약과 다를 때 사용하는 예외입니다.
    응답 파싱 오류를 분리하면 API 계약 깨짐을 빠르게 찾을 수 있습니다.
    """

    def __init__(self, detail: str = "") -> None:
        super().__init__(
            "CMN_DELEGATED_TOKEN_RESPONSE_ERROR",
            "공통 인증 API 응답을 해석하지 못했습니다.",
            detail=detail,
        )
