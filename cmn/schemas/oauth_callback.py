from typing import Annotated, Optional
from pydantic import BaseModel, Field


class OAuthCallbackParams(BaseModel):
    code: Annotated[Optional[str], Field(None, description="OAuth 위임 코드")] 
    state: Annotated[Optional[str], Field(None, description="지정된 state 값 '회사코드.사번' 형식 e.g. 'leodev901.20075487")] 
    error: Annotated[Optional[str], Field(None, description="오류 코드")] 
    error_description: Annotated[Optional[str], Field(None, description="오류 상세 정보")] 

