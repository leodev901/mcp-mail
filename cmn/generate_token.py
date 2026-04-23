import os
import jwt
from jwt import ExpiredSignatureError, InvalidTokenError
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv(".env")


# 이 값들은 나중에 FastAPI 서버 설정(main.py 등)과 반드시 일치해야 합니다.
SECRET_KEY = os.getenv("JWT_SECRET_KEY","your_secret_key")      # 서명용 비밀키
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")                 # 대칭키 암호화 알고리즘

def create_token(
        user_id: str = '20075487',
        company_code: str = 'leodev901',
        user_name: str = 'Leo',
        user_email: str = 'admin@leodev901.onmicrosoft.com',
        expires_in: int = 12     # default: 12시간
    ):
    """JWT 생성 함수"""

    # [학습 포인트] 토큰에 저장할 payload 생성
    payload = {
        "sub": user_id,   # JWT 토큰의 식별은 보통 'sub'를 key 로 사용한다.
        "company_code": company_code,
        "user_name": user_name,
        "user_email": user_email,
        "iat": datetime.now(timezone.utc),  
        "exp": datetime.now(timezone.utc) + timedelta(hours=expires_in), # jwt의 내장된 만료일 검사를 사요하려면 exp 변수에 utc로 설정해야 함
    }
    # [학습 포인트] 서명(Signature) 및 인코딩
    # 헤더(Header) + 페이로드(Payload) + 비밀키(Secret)를 조합하여 암호화
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    

def decode_token(token: str):
    """JWT 해석 및 검증 함수"""
    try:
        # algorithms (복수, 리스트형태)로 명시적 전달해야 합니다.
        # PyJWT 2.0+ 버전의 표준 문법입니다.
        data = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return data
    
    except ExpiredSignatureError:
        print("[Error] 토큰의 유효 기간이 만료되었습니다.")
        return None
    except InvalidTokenError:
        print("[Error] 유효하지 않은 토큰입니다. (서명 불일치 또는 변조)")
        return None
    except Exception as e:
        print(f"[Error] 알 수 없는 오류 발생: {e}")
        return None
        
    
    

if __name__ == "__main__":
    print("\n" + "="*50)
    print("TOKEN GENERATE")
    print("="*50)    
    user_name = "Leo Smith"
    token = create_token()
    print(f"{user_name}'s JWT Token: {token}")
    print("="*50)
    
    print("\n" + "="*50)
    print("TRY TO DECODING TOKEN...")
    print("="*50)
    data = decode_token(token)
    print(data)
    if data:
        print(f"- user_id       : {data['sub']}")
        print(f"- company_code  : {data['company_code']}")
        print(f"- user_name     : {data['user_name']}")
        print(f"- user_email    : {data['user_email']}")
        print(f"- iat           : {data['iat']}")
        print(f"- exp           : {data['exp']}")
    print("="*50)

    print("\n" + "="*50)
    print("\n3. 변조된 토큰 테스트 (토큰 끝에 문자 하나 추가)...")
    print("="*50)
    fake_token = token + "a"
    decode_token(fake_token)
    print("="*50)
    


    