
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
    conversation_id: Annotated[Optional[str], Field(None, description="대화 ID")]

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


# ===============================================================
# Report 모델
# ===============================================================
class MailSenderSummary(BaseModel):
    """보고서에서 자주 등장한 발신자를 표현하는 작은 요약 모델입니다."""

    sender: Annotated[str, Field(..., description="발신자 이름 또는 이메일")]
    count: Annotated[int, Field(..., description="해당 발신자의 메일 수")]


class MailPeriodSummary(BaseModel):
    """한 기간의 메일 목록을 사람이 읽기 좋은 집계 정보로 압축한 모델입니다."""

    period_label: Annotated[str, Field(..., description="기간 이름 (예: 지난주, 이번주, 지난달, 이번달)")]
    from_date: Annotated[str, Field(..., description="조회 시작일 (YYYY-MM-DD)")]
    to_date: Annotated[str, Field(..., description="조회 종료일 (YYYY-MM-DD)")]
    listed_count: Annotated[int, Field(..., description="응답에 포함된 메일 수")]
    unread_count: Annotated[int, Field(..., description="응답 메일 중 안 읽은 메일 수")]
    important_count: Annotated[int, Field(..., description="응답 메일 중 중요도가 high 인 메일 수")]
    attachment_count: Annotated[int, Field(..., description="응답 메일 중 첨부파일이 있는 메일 수")]
    top_senders: Annotated[list[MailSenderSummary], Field(default_factory=list, description="메일 수 기준 주요 발신자 목록")]
    important_mails: Annotated[list[MailMessage], Field(default_factory=list, description="중요 메일 목록")]
    recent_mails: Annotated[list[MailMessage], Field(default_factory=list, description="기간 내 최근 메일 목록")]
    summary_text: Annotated[str, Field(..., description="기간별 요약 문장")]


class MailWeeklyReport(BaseModel):
    """지난주와 이번주 메일 목록 및 요약 정보를 함께 반환하는 주간 리포트 모델입니다."""

    last_week: Annotated[MailPeriodSummary, Field(..., description="지난주 메일 요약")]
    this_week: Annotated[MailPeriodSummary, Field(..., description="이번주 메일 요약")]
    report_content: Annotated[str, Field(..., description="주간 메일 비교 요약")]


class MailMonthlyReport(BaseModel):
    """지난달과 이번달 메일 목록 및 요약 정보를 함께 반환하는 월간 리포트 모델입니다."""

    last_month: Annotated[MailPeriodSummary, Field(..., description="지난달 메일 요약")]
    this_month: Annotated[MailPeriodSummary, Field(..., description="이번달 메일 요약")]
    report_content: Annotated[str, Field(..., description="월간 메일 비교 요약")]
