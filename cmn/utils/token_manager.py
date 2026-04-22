
import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


KST = timezone(timedelta(hours=9))

@dataclass
class TokenRecord:
    access_token: str
    expiread_at: datetime

    def is_valid(self, buffer_seconds: int = 300) -> bool:
        """현재 시간이 만료 시각(여유 시간 차감)보다 이전인지 확인"""
        return datetime.now(KST) + timedelta(seconds=buffer_seconds) < (self.expiread_at)


class TokenManager:
    def __init__(self):
        # 타입 힌트는 `변수: 타입 = 값` 형태로 적어야 합니다.
        # `dict[...] = {}` 를 값 대입문 안에 넣으면 타입 객체에 값을 넣으려는 형태가 되어 에러가 납니다.
        self._tokens: dict[str, TokenRecord] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    @staticmethod
    def build_key( company_code: str, app_name: str) -> str:
        # "회사코드:APP이름" 의 구조로 key를 생성합니다.
        return f"{company_code.strip().lower()}:{app_name.strip().lower()}"
    
    
    def get_valid_access_token(self, key: str) -> str | None:
        """캐시에 유효한 토큰이 있을 경우 반환 """
        record = self._tokens.get(key)
        if record and record.is_valid():
            # hit
            return record.access_token
        # miss
        return None
    
    def get_lock(self, key: str) -> asyncio.Lock:
        """같은 키 요청의 경우 동시 처리 방지를 위한 lock"""
        if key not in self._locks:
            self._locks[key] = asyncio.Lock()
        return self._locks[key]
    
    def save_token(self, key: str, access_token: str, expiread_at: datetime) -> None:
        # 새 토큰을 메모리에 저장합니다.
        self._tokens[key] = TokenRecord(access_token=access_token, expiread_at=expiread_at)


token_manager = TokenManager()
