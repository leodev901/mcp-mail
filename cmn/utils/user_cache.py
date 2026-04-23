import asyncio
from collections import defaultdict
from cachetools import TTLCache

from cmn.schemas.user import User
from cmn.base.logger import logger


user_cache = TTLCache[str, User] (maxsize=100, ttl=3600)
locks = defaultdict(asyncio.Lock)


def _build_key(company_code: str, user_id: str) -> str:
    return f"{company_code.strip().lower()}:{user_id.strip().lower()}"

async def get_user_form_cache(company_code: str, user_id: str) -> User | None:
    key = _build_key(company_code, user_id)
    
    if key in user_cache:
        logger.debug(f"Hit user cache - {key}")
        return user_cache[key]
    
    logger.debug(f"Miss user cache - {key}")

    async with locks[key]:
        if key in user_cache:
            logger.debug(f"Hit user cache - {key}")
            return user_cache[key]
        
        return None
    
    return None

def set_user_to_cache(user: User) -> None:
    key = _build_key(user.company_code, user.user_id)
    user_cache[key] = user
        
    