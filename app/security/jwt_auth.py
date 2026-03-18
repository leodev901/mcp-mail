from app.models.user_info import UserInfo
from app.core.config import settings
from app.clients.http_client import get_httpx_client
from app.security import key_cache
from http import HTTPStatus

import jwt

from loguru import logger


class AuthError(Exception):
    """JWT 인증 처리 전반에서 사용하는 기본 예외."""


class InvalidTokenError(AuthError):
    """토큰 형식, 서명, 만료 등 검증 실패를 나타낸다."""


class UserLookupError(AuthError):
    """토큰 해석 후 사용자 조회에 실패했음을 나타낸다."""


async def get_user_from_token(token:str) -> UserInfo:

    if settings.AUTH_JWT_USER_TOKEN == False:
        return UserInfo(    
            user_id="20075487",
            email="admin@leodev901.onmicrosoft.com",
            username="김레오",
            company_cd="leodev901",
            department="플랫폼개발팀",
            profile="none",
        )
    else :
        payload = await verify_sso_jwt_token(token)
        user_id= payload.get("empno")
        company_cd = payload.get("company_cd")
        return await fetch_user(company_cd, user_id)
    
async def verify_sso_jwt_token(token:str) -> dict:
    try:
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        algorithm = header.get("alg")

        if not kid:
            raise ValueError("Missing kid in JWT header")
        if not algorithm:
            raise ValueError("Missing alg in JWT header")
        
        public_key = await key_cache.get_public_key(kid)
        payload = jwt.decode(token, public_key, algorithms=[algorithm])

        if not payload.get("empno") or not payload.get("company_cd"):
            raise ValueError("empno or company_cd in JWT payload is required")
        
        return payload
    
    except jwt.ExpiredSignatureError as e:
        logger.warning("Token has expired")
        raise InvalidTokenError(f"Token has expired: {e}") from e
    except jwt.PyJWTError as e:
        logger.warning(f"Invalid verification failed - Invalid token: {e}")
        raise InvalidTokenError(f"Invalid token: {e}") from e
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid verification failed - Invalid token: {e}")
        raise InvalidTokenError(f"Invalid token: {e}") from e
    except ValueError as e:
        logger.warning(f"Invalid verification failed - Invalid token: {str(e)}")
        raise InvalidTokenError(f"Invalid token: {e}") from e
    except Exception as e:
        logger.exception(f"Internal error during token verification: {e}")
        raise AuthError(f"Internal error during token verification: {e}") from e

async def fetch_user(company_cd: str, user_id: str) -> UserInfo:
    url = f"cmmn.leodev901.com/api/v1/user?company_cd={company_cd}&user_id={user_id}"
    headers = {"cmmn-api-key": "sk"}

    logger.info(f"Fetch in user info from {url}")
    try:
        client = await get_httpx_client()
        resp = await client.get(url, headers=headers)
        # resp.raise_for_status()

        if resp.status_code == HTTPStatus.ok:
            data = resp.json()
            if not data:
                logger.error(f"User not found: {user_id}")
                raise UserLookupError(f"User not found: {user_id}")
            user_info = UserInfo(
                user_id=user_id,
                email=data.get("email"),
                username=data.get("user_nm"),
                company_cd=company_cd,
                department=data.get("dept_cd"),
                # profile=data.get("profile"),
            )
            return user_info
        else:
            logger.error(f"Response text: {resp.text}")
            raise UserLookupError(
                f"Failed to fetch user info. Status code: {resp.status_code}"
            )
            
    except Exception as e:
        raise UserLookupError(f"Failed to fetch user info: {e}") from e    
    
    
