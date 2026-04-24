import jwt
from jwt import InvalidTokenError, ExpiredSignatureError
from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials


from cmn.core.config import settings
from cmn.base.logger import logger
from cmn.schemas.user import User
from cmn.utils.user_cache import get_user_form_cache, set_user_to_cache







SECRET_KEY = getattr(settings, "JWT_SECRET_KEY", "your_jwt_decode_secret_key")
ALGORITHM = getattr(settings, "JWT_ALGORITHM", "HS256")

security = HTTPBearer(auto_error=True)


def encode(user: User)->str:
    """JWT 생성 함수"""
    print(user)
    payload = {
        "sub": user.user_id,   # JWT 토큰의 식별은 보통 'sub'
        "company_code": user.company_code,
        "user_name": user.user_name,
        "user_email": user.user_email,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode(token: str):
    """JWT 해석 및 검증 함수"""
    try:
        # algorithms (복수, 리스트형태)로 명시적 전달해야 합니다.
        # PyJWT 2.0+ 버전의 표준 문법입니다.
        data = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        print(data)
        return data
    
    except ExpiredSignatureError as exc:
        logger.error(f"[Error] 토큰의 유효 기간이 만료되었습니다. {exc}")
        raise exc
    except InvalidTokenError as exc:
        logger.error(f"[Error] 유효하지 않은 토큰입니다. (서명 불일치 또는 변조) {exc}")
        raise exc
    except Exception as e:
        logger.error(f"[Error] 알 수 없는 오류 발생: {exc}")
        raise exc
    
def decode_without_key(token: str):
    """JWT 해석 함수"""
    return jwt.decode(token, options={"verify_signature": False})




async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security))->User:
    data = decode(credentials.credentials)
    
    # fetch user
    user_info = await get_user_form_cache( data.get("company_code"), data.get("sub") )
    if user_info:
       return user_info
    
    # 원래는 공통 서비스를 통해 유효한 user_info롤 호출(http)해야 함 여기선 mock으로 구현
    user_info = _mock_fetch_user(data)
    # 캐싱
    set_user_to_cache(user_info)
    
    return user_info

def _mock_fetch_user(data: dict[str, any]) -> User:
    return User(
        user_id=data.get("sub","N/A"),
        company_code=data.get("company_code","N/A"),
        user_name=data.get("user_name","N/A"),
        user_email=data.get("user_email","N/A"),
    )

