from typing import Annotated, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel
from app.schema.mail import MailMessage



class MailSearchHit(BaseModel):
    model_config=ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )
    """
    Search API의 hits 배열 안에 들어있는 단일 검색 결과입니다.
    """

    hit_id: Annotated[Optional[str], Field(None, alias="hitId", description="Search API 검색 결과 ID")]
    rank: Annotated[Optional[int], Field(None, description="검색 결과 순위")]
    summary: Annotated[Optional[str], Field(None, description="검색 결과 요약")]
    resource: Annotated[MailMessage, Field(..., description="실제 메일 메시지")]

    @model_validator(mode="before")
    @classmethod
    def fill_resource_id_from_hit_id(cls, data: dict) -> dict:
        """
        Search API는 message id를 resource.id가 아니라 hitId로 리턴 해주므로
        hitId를 MailMessage의 id로 복사합니다.
        """

        if not isinstance(data, dict):
            return data

        resource = data.get("resource")
        hit_id = data.get("hitId")

        if isinstance(resource, dict) and hit_id and not resource.get("id"):
            resource["id"] = hit_id

        return data


class MailHitsContainers(BaseModel):
    model_config=ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )

    hits: Annotated[list[MailSearchHit], Field(default_factory=list, description="검색 결과 목록")]
    total: int = Field(..., description="검색된 총 메일 수")
    more_results_available: Annotated[
        bool,
        Field(False, description="추가 검색 결과 존재 여부"),
    ]

    def convert_mail_message(self) -> list[MailMessage]:
        return [hit.resource for hit in self.hits]
