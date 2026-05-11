from datetime import date, datetime, timedelta, timezone


def _format_date(value: date, date_format: str = "%Y-%m-%d") -> str:
    """
    date 객체를 문자열로 바꿉니다.
    별도 함수를 두면 주간/월간 범위 계산 함수가 같은 출력 형식을 사용하게 되어 실수를 줄일 수 있습니다.
    """

    return value.strftime(date_format)


def _today_kst() -> date:
    """
    KST 기준 오늘 날짜를 반환합니다.
    Graph 조회 서비스도 KST 날짜를 UTC 필터로 바꾸므로, 리포트 기간 계산도 같은 기준을 사용합니다.
    """

    return datetime.now(timezone(timedelta(hours=9))).date()


def get_week_date_range(week_offset: int = 0, date_format: str = "%Y-%m-%d") -> tuple[str, str]:
    """
    오늘 날짜 기준 offset 주의 월요일부터 일요일까지 날짜를 반환합니다.
    week_offset 은 이번주를 0, 지난주를 -1 로 표현하는 정수입니다.
    """

    today = _today_kst()

    # weekday() 는 월요일을 0, 일요일을 6 으로 반환하므로 오늘에서 weekday 값을 빼면 이번주 월요일입니다.
    this_monday = today - timedelta(days=today.weekday())
    target_monday = this_monday + timedelta(weeks=week_offset)
    target_sunday = target_monday + timedelta(days=6)

    return _format_date(target_monday, date_format), _format_date(target_sunday, date_format)


def get_month_date_range(month_offset: int = 0, date_format: str = "%Y-%m-%d") -> tuple[str, str]:
    """
    오늘 날짜 기준 offset 월의 시작일부터 마지막일까지 날짜를 반환합니다.
    month_offset 은 이번달을 0, 지난달을 -1 로 표현하는 정수입니다.
    """

    today = _today_kst()

    # 월 이동은 연도 경계를 넘을 수 있으므로 전체 월 번호로 바꾼 뒤 다시 year/month 로 환산합니다.
    month_index = today.year * 12 + (today.month - 1) + month_offset
    target_year = month_index // 12
    target_month = month_index % 12 + 1

    first_day = date(target_year, target_month, 1)

    # 다음 달 1일에서 하루를 빼면 target 월의 마지막 날이 됩니다.
    next_month_index = month_index + 1
    next_month_year = next_month_index // 12
    next_month = next_month_index % 12 + 1
    last_day = date(next_month_year, next_month, 1) - timedelta(days=1)

    return _format_date(first_day, date_format), _format_date(last_day, date_format)
