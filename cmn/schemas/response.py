from pydantic import BaseModel
from typing import TypeVar, Generic
from http import HTTPStatus



T = TypeVar("T")

class CommonResponse(BaseModel, Generic[T]):
    status: str = "success"
    status_code: int = HTTPStatus.OK
    message: str = "요청이 완료되었습니다."
    data: T | None = None
    

    @staticmethod
    def ok(data):
        return CommonResponse(data=data)
    
    @staticmethod
    def error(message:str):
        return CommonResponse(
            status="error",
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            message=message,
        )

