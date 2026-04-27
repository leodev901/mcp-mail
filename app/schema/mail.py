
from datetime import datetime, timedelta

from typing import Annotated, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel




class GraphBaseModl(BaseModel):
    model_config=ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )


# ===============================================================
# 서브 모델
# ===============================================================
class EmailAddress(BaseModel):
    name: Annotated[Optional[str], Field(None, description="이름(display name)",alias="name")]
    address: Annotated[str, Field(..., description="이메일 주소",alias="address")]

class Sender(BaseModel):
    email_address: Annotated[Optional[EmailAddress], Field(None, description="발신자 정보",alias="emailAddress")]


# class Recipient(BaseModel):
#     email_address: EmailAddress = Field(..., alias="emailAddress")

class MessageBody(BaseModel):
    content_type: Annotated[Optional[str], Field(None, description="본문 형식", alias="contentType")]
    content: Annotated[Optional[str], Field(None, description="본문 내용", alias="content")]

class Attachment(BaseModel):
    id: Annotated[Optional[str], Field(None, description="첨부파일 고유 ID")]
    name: Annotated[Optional[str], Field(None, description="첨부파일 이름")]
    content_type: Annotated[Optional[str], Field(None, description="첨부파일 MIME 타입", alias="contentType")]
    size: Annotated[Optional[int], Field(None, description="첨부파일 크기")]

# ===============================================================
# Grap API Message(메일) 조회 결과 모델
# ===============================================================
class MailMessage(GraphBaseModl):
    id: Annotated[str, Field(..., description="메세지(메일) 고유 ID")]

    subject: Annotated[Optional[str], Field(None, description= "메일 제목")]
    sender: Annotated[Optional[Sender], Field(None, description= "발신자 정보",alias="from")]
    received_date_time: Annotated[Optional[str], Field(None, description= "수신 일시")]
    sent_date_time: Annotated[Optional[str], Field(None, description= "발신 일시")]

    body_preview: Annotated[Optional[str], Field(None, description= "메일 본문 미리보기")]
    
    importance: Annotated[Optional[str], Field(None,description="중요도")] 
    is_read: Annotated[bool, Field(None, description="읽음 여부")]
    has_attachments: Annotated[bool, Field(None, description="첨부 파일 여부")]
    to_recipients: Annotated[list[Sender], Field(default_factory=list, description="수신자 목록")]
    
    
    # 
    # to_recipients: Annotated[list[dict], "수신자 목록"] = []
    # cc_recipients: Annotated[list[dict], "참조자 목록"] = []
    # bcc_recipients: Annotated[list[dict], "숨은 참조자 목록"] = []

    @field_validator("received_date_time", "sent_date_time",mode="before")
    @classmethod
    def convert_to_kst(cls, v: str) -> str:
        if v and v.endswith('Z'):
            utc_dt = datetime.fromisoformat(v.replace('Z', '+00:00'))
            return format(utc_dt + timedelta(hours=9), "%Y-%m-%dT%H:%M:%S+09:00")
        return v


class MailMessageDetail(MailMessage):
    body: Annotated[Optional[MessageBody], Field(None, description="메일 본문")]
    attachments: Annotated[list[Attachment], Field(default_factory=list, description="첨부파일 목록")]
