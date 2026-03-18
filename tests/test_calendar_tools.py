from types import SimpleNamespace

from app.models.user_info import UserInfo
from app.tools.calendar_tools import _get_request_current_user


def test_get_request_current_user_reads_request_state(monkeypatch):
    request = SimpleNamespace(
        state=SimpleNamespace(
            current_user=UserInfo(
                user_id="20075487",
                email="admin@leodev901.onmicrosoft.com",
                company_cd="leodev901",
            )
        )
    )
    monkeypatch.setattr("app.tools.calendar_tools.get_http_request", lambda: request)

    current_user = _get_request_current_user()

    assert current_user is not None
    assert current_user.email == "admin@leodev901.onmicrosoft.com"
    assert current_user.company_cd == "leodev901"
