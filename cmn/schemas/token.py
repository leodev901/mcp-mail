from pydantic import BaseModel, Field
from typing import Annotated, Optional

class TokenData(BaseModel):
    token_type: Annotated[str, Field(...,description="토큰 타입")]
    scope: Annotated[Optional[str], Field(None,description="허용 권한 범위")]
    expires_in: Annotated[int, Field(...,description="토큰 만료 시간 (second)")]
    ext_expires_in: Annotated[Optional[int], Field(None,description="확장 유효 기간 (MS 전용 필드)")]
    access_token: Annotated[str, Field(...,description="실제 API 접근용 토큰")]
    refresh_token: Annotated[Optional[str], Field(None,description="토큰 갱신하기 위한 refresh 토큰")]
    id_token: Annotated[Optional[str], Field(None,description="사용자 신원 정보(Identity)")]



