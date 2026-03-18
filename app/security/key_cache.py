import asyncio
from typing import Dict

import httpx
from app.clients.http_client import get_httpx_client



class keyCache:
    """
    PEM 문자열과 kid를 매핑하여 저장하는 캐시 객체 
    """

    def __init__(self, key_api_url:str):
        self._cache: Dict[str, str] = {}
        self._lock = asyncio.Lock()
        self._key_api_url = key_api_url

    async def get_public_key(self, kid:str) -> str:
        """
        캐시에 kid가 있으면 PEM 반환
        없으면 refresh_key로 갱신 후 다시 캐시에서 찾아서 반환
        캐시에도 없으면 400 오류
        """

        if kid in self._cache:
            return self._cache[kid]
        
        # 갱신하기
        await self.__refresh_key()

        # 갱신 후 캐시에서 확인
        if kid in self._cache:
            return self._cache[kid]

        # 여전히 없으면 잘못된 kid
        raise ValueError("Invalid kid")
    
    async def __refresh_key(self) -> None:
        """
        API호출로 키 갱신
        - 단일 잠금으로 동시 요청 방지
        - API 오류 시 기존 캐시 유지
        """

        async with self._lock:
            # 잠근 후 재확인
            try:
                client = await get_httpx_client()
                resp = await client.get(self._key_api_url)
                resp.raise_for_status()
                data = resp.json()

            except(httpx.HTTPerror, ValueError):
                # API 호출 에러시 기존 캐시 유지
                return
            
            # API 겨로가 유효성 검사
            if data and data.get("public_key"):
                kid = data["kid"]
                public_key = data["public_key"]
                return
            # 유효하지 않은 kid는 캐시 업데이트 하지 않음
            return

key_cache = keyCache(key_api_url=f"cmmn.leodev901.com/api/v1/auth/keys_get-pub-key")

