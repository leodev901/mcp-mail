from typing import Annotated,Optional
from pydantic import BaseModel


class UserInfo(BaseModel):
    user_id: str
    email: Optional[str] = None
    username: Optional[str] = None
    company_cd: Optional[str] = None
    department: Optional[str] = None
    profile: Optional[str] = None
    # cmn_user_id: Optional[str] = None