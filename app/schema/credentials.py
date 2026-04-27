from typing import List

from pydantic import BaseModel, Field, field_validator

from app.common.exception import CmnAuthError
from app.schema.user import User


class MyAccessToken(BaseModel):
    access_token: str
    user_info: User
    yellow_list: List[str] = Field(default_factory=list)

    @field_validator("access_token")
    @classmethod
    def validate_access_token(cls, value: str) -> str:
        # access_token 은 Graph 호출의 필수 전제라 schema 단계에서 먼저 막습니다.
        # validator 는 검증 후 반드시 값을 return 해야 Pydantic 이 필드를 유지합니다.
        if not value:
            raise CmnAuthError("ACCEES_TOKEN_NOT_IDENTIFIED", "사용자의 access_token을 발급/찾을 수 없습니다.")
        return value

    @field_validator("user_info")
    @classmethod
    def validate_user(cls, value: User) -> User:
        # user 안의 필수 사용자 식별값도 CMN 응답 계약에 속하므로 schema 가 검증합니다.
        # 이렇게 두면 middleware 는 이미 검증된 모델만 request.state 에 저장하면 됩니다.
        if not value:
            raise CmnAuthError("USER_NOT_IDENTIFIED", "사용자 정보(user)가 응답에 포함되어 있지 않습니다.")

        if not value.company_code:
            raise CmnAuthError("COMPANY_CODE_NOT_IDENTIFIED", "사용자의 회사 코드(company_code)가 응답에 포함되어 있지 않습니다.")

        if not value.user_email:
            raise CmnAuthError("USER_EMAIL_NOT_IDENTIFIED", "사용자의 이메일(user_email)이 응답에 포함되어 있지 않습니다.")

        return value


class MyAccessTokenResponse(MyAccessToken):
    pass
