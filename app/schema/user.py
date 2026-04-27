from typing import Optional, Annotated

from pydantic import AliasChoices, BaseModel, Field


class User(BaseModel):
    user_id: Annotated[str, Field(..., description="사용자 ID", examples=["20075487"])]
    company_code: Annotated[str, Field(..., description="회사 코드", examples=["leodev901"])]
    user_name: Annotated[str, Field(..., description="사용자 이름", examples=["Leo Smith"])]
    user_email: Annotated[str, Field(..., description="사용자 이메일", examples=["admin@leodev901.onmicrosoft.com"])]
    department: Optional[str] = None
    profile: Optional[str] = None
