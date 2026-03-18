## 🚀 Grafana Cloud (SaaS) 연동 완벽 가이드

서버에 무거운 인프라를 직접 구축하지 않고, Grafana Cloud를 통해 10분 만에 로그 모니터링 시스템을 구축하는 방법입니다.

---

### Step 0. 필수 패키지 설치
OpenTelemetry 로그를 HTTP로 전송하기 위해서는 아래 패키지들이 반드시 필요합니다.

1. `requirements.txt`에 다음 라인을 추가하거나 직접 터미널에 입력하세요:
   ```bash
   pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp-proto-http
   ```
   > [!IMPORTANT]
   > `opentelemetry-exporter-otlp-proto-http` 패키지가 누락되면 `ModuleNotFoundError`가 발생합니다.

---

### Step 1. Grafana Cloud 계정 및 엔드포인트 준비
1. **[Grafana Cloud](https://grafana.com/products/cloud/)**에서 무료 계정을 생성합니다.
2. 대시보드에서 **`Connections` -> `Add new connection` -> `OpenTelemetry`**를 선택합니다.
3. **`Generate Token`**을 눌러 다음 정보를 확보합니다:
   - `OTLP Endpoint`: (예: `https://otlp-gateway-.../otlp`)
   - `Instance ID` (Username): (숫자로 된 ID)
   - `API Token` (Password): (`glc_...`로 시작하는 토큰)

---

### Step 2. 환경 설정 (`.env`)
프로젝트 루트의 `.env` 파일에 발급받은 정보를 입력합니다.

```env
# .env 파일
ENV=production  # 로컬에서 Grafana로 전송하려면 production으로 설정 (또는 local 외의 값)

GRAFANA_ENDPOINT=https://otlp-gateway-prod-ap-northeast-0.grafana.net/otlp/v1/logs
GRAFANA_INSTANCE_ID=1556283
GRAFANA_API_TOKEN=glc_eyJvIjoi... (실제 토큰 전체 입력)
```
> [!TIP]
> 값 뒤에 `# 주소`와 같은 주석이나 공백을 넣지 마세요. 인증 오류(401)의 원인이 됩니다.
> 파이썬 SDK 사용 시 엔드포인트 끝에 `/v1/logs`를 명시하는 것이 가장 정확합니다.

---

### Step 3. 코드 구현 (`logger.py`)
Grafana Cloud는 **HTTPS** 연결과 **Basic Auth** 인증을 요구합니다.

```python
import base64
import logging
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
# (... 기타 import)

def _init_open_telemetry_provider():
    # (... Resource 설정 생략)
    
    # 인증 토큰 생성 (.strip()으로 공백 방지)
    username = settings.GRAFANA_INSTANCE_ID.strip()
    password = settings.GRAFANA_API_TOKEN.strip()
    auth_string = base64.b64encode(f"{username}:{password}".encode()).decode()

    exporter = OTLPLogExporter(
        endpoint=settings.GRAFANA_ENDPOINT,
        headers={"Authorization": f"Basic {auth_string}"} # HTTP 전송 시 딕셔너리 형식 권장
    )
    # (... 이하 동일)
```
> [!NOTE]
> `proto.http._log_exporter`와 같이 언더바(`_`)가 포함된 정확한 경로를 사용해야 모듈 참조 오류를 방지할 수 있습니다.

---

### Step 4. 실행 및 로그 확인
1. 서버를 실행합니다: `uvicorn app.main:app ...`
2. 터미널에 `✅ OpenTelemetry(OTLP) Exporter initialized` 메시지가 뜨는지 확인합니다.
3. Grafana 웹사이트 좌측 메뉴에서 **Explore** (나침반 아이콘)를 클릭합니다.
4. 상단 데이터 소스에서 **Loki**를 선택한 후 다음 쿼리를 입력합니다:
   `{service_name="mcp-sample"}`

> [!WARNING]
> **전송 지연**: 로그는 실시간(Live) 모드에서도 클라우드 처리 과정에 따라 **약 30초~1분 정도의 지연**이 발생할 수 있습니다. 로그가 즉시 보이지 않더라도 잠시만 기다려 주세요.
