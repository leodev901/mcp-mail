from fastapi import APIRouter, Depends

from cmn.schemas.user import User
from cmn.schemas.response import CommonResponse
from cmn.utils import jwt_manager

utils_router = APIRouter(prefix="/utils",tags=["utils"])


@utils_router.post("/jwt/encode", response_model=CommonResponse)
async def jwt_encode(user: User):
    return CommonResponse.ok(jwt_manager.encode(user))


@utils_router.get("/jwt/decode", response_model=CommonResponse)
async def jwt_decode(user: User = Depends(jwt_manager.get_current_user)):
    return CommonResponse.ok(user)



