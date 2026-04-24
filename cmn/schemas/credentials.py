from typing import List
from pydantic import BaseModel, Field
from cmn.schemas.user import User

class MyAccessToken(BaseModel):
    access_token: str 
    user_info: User | None = None
    yellow_list: List[str] = Field(default_factory=list)