from typing import Annotated, Optional
from pydantic import BaseModel, Field, field_validator


class OAuthCallbackParams(BaseModel):
    code: Annotated[Optional[str], Field(None, description="OAuth 위임 코드")] 
    state: Annotated[Optional[str], Field(None, description="지정된 state 값 '회사코드.사번' 형식 e.g. 'leodev901.20075487")] 
    error: Annotated[Optional[str], Field(None, description="오류 코드")] 
    error_description: Annotated[Optional[str], Field(None, description="오류 상세 정보")]

    # Microsoft로 부터 콜백으로 받는 파라미터들 정규화
    @field_validator("code", "state", "error", "error_description", mode="before")
    @classmethod
    def normatlize_str(cls, value):
        if value is None:
            return None
        return str(value).strip() or None
    
class CallbackState(BaseModel):
    """OAuth callback의 state 문자열을 파싱한 내부 값 객체"""
    company_code: Annotated[str, Field(...,description="회사 코드",examples=["leodev901"])]
    user_id: Annotated[str, Field(...,description="사번",examples=["20075487"])]


    



