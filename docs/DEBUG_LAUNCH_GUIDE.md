# DEBUG_LAUNCH_GUIDE.md

## 문제 정의
- VS Code에서 `launch.json`으로 `uvicorn` 디버깅 실행 시, 앱 가상환경이 아니라 전역 Python이 먼저 선택되면 디버그 런처가 시작 단계에서 실패할 수 있다.
- 이번 사례에서는 `C:\Python314\python.exe`가 디버그 어댑터에 사용되면서 `Could not find platform independent libraries <prefix>` 메시지가 출력됐다.

## 접근 방법
- 워크스페이스 기본 인터프리터를 `.venv`로 고정한다.
- 디버그 대상 Python(`python`)뿐 아니라 디버그 어댑터 Python(`debugAdapterPython`)도 같은 가상환경으로 명시한다.
- `PYTHONPATH`를 워크스페이스 루트로 맞춰 `app.main:app` import 경로를 명확하게 유지한다.

## 코드
### `.vscode/settings.json`
```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}\\.venv\\Scripts\\python.exe",
  "python.terminal.activateEnvironment": true
}
```

### `.vscode/launch.json`
```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "MCP: Debug Server",
      "type": "debugpy",
      "request": "launch",
      "cwd": "${workspaceFolder}",
      "module": "uvicorn",
      "python": "${workspaceFolder}/.venv/Scripts/python.exe",
      "debugAdapterPython": "${workspaceFolder}/.venv/Scripts/python.exe",
      "args": [
        "app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8002"
      ],
      "env": {
        "PYTHONPATH": "${workspaceFolder}"
      },
      "jinja": true
    }
  ]
}
```

문법 설명:
- `cwd`는 current working directory의 약자다. 현재 작업 디렉터리를 워크스페이스 루트로 고정한다.
- `module: "uvicorn"`은 `python -m uvicorn` 형태로 실행하라는 의미다.
- `debugAdapterPython`은 VS Code 디버거 내부 런처가 사용할 Python 경로다.

왜 이렇게 했는지:
- 이번 오류는 앱 코드가 아니라 디버거 시작 해석기가 잘못 선택된 것이 원인이다.
- 그래서 `python`만 지정하는 것보다 디버거 런처까지 같은 `.venv`를 쓰도록 고정하는 편이 재현 방지에 더 직접적이다.

## 검증
### 수동 검증 절차
1. PowerShell에서 `.\.venv\Scripts\python.exe --version`으로 가상환경 Python이 정상인지 확인한다.
2. PowerShell에서 `.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8002`로 서버가 뜨는지 확인한다.
3. VS Code에서 `F5`를 눌러 `MCP: Debug Server`를 실행한다.
4. 터미널 시작 명령에 `C:\Python314\python.exe`가 아니라 `${workspaceFolder}\.venv\Scripts\python.exe`가 사용되는지 확인한다.

성공 기준:
- `http://127.0.0.1:8002`에서 서버가 시작된다.
- 더 이상 `Could not find platform independent libraries <prefix>`가 출력되지 않는다.

실패 기준:
- 여전히 전역 Python 경로가 먼저 출력된다.

## 대안과 트레이드오프
대안:
- VS Code 명령 팔레트에서 `Python: Select Interpreter`로 `.venv\Scripts\python.exe`를 수동 선택할 수 있다.

트레이드오프:
- 수동 선택은 빠르지만, 워크스페이스 설정 파일에 남지 않아 다른 PC나 새 창에서 다시 같은 문제가 날 수 있다.

## 한 줄 요약
- 디버깅 오류의 핵심 원인은 깨진 앱 코드가 아니라 잘못 선택된 디버그 Python이므로, `.vscode/settings.json`과 `.vscode/launch.json` 둘 다 `.venv`로 고정하면 해결된다.
