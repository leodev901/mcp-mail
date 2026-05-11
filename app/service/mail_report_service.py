from collections import Counter

from app.schema.mail import MailMessage, MailMonthlyReport, MailPeriodSummary, MailSenderSummary, MailWeeklyReport
from app.service.mail_service import MailService
from app.utils.date_utils import get_month_date_range, get_week_date_range


class MailReportService:
    """
    보고서 작성용 메일 유스케이스를 담당하는 service 계층입니다.
    실제 Graph 조회는 기존 MailService 를 재사용하고, 이 클래스는 기간 계산과 요약 생성만 담당합니다.
    """

    def __init__(self) -> None:
        # 조회 로직을 새로 만들지 않고 기존 service 를 재사용하면 인증/blacklist/Graph 호출 패턴이 흔들리지 않습니다.
        self.mail_service = MailService()

    def _get_sender_label(self, mail: MailMessage) -> str:
        """
        MailMessage 의 발신자 정보를 보고서에 표시할 문자열로 바꿉니다.
        이름이 있으면 이름을 우선하고, 없으면 이메일 주소를 사용해 빈 값 노출을 줄입니다.
        """

        email_address = mail.sender.email_address if mail.sender else None
        if not email_address:
            return "알 수 없음"

        return email_address.name or email_address.address or "알 수 없음"

    def _build_period_summary(
        self,
        *,
        period_label: str,
        from_date: str,
        to_date: str,
        mails: list[MailMessage],
    ) -> MailPeriodSummary:
        """
        한 기간의 메일 목록을 집계 정보와 함께 MailPeriodSummary 로 변환합니다.
        단순 문자열 요약도 함께 넣어 LLM 이 후속 보고서 문장으로 확장하기 쉽게 합니다.
        """

        unread_mails = [mail for mail in mails if not mail.is_read]
        important_mails = [mail for mail in mails if mail.importance == "high"]
        attachment_mails = [mail for mail in mails if mail.has_attachments]

        # Counter 는 리스트 안 값의 등장 횟수를 세는 표준 도구입니다.
        # 발신자별 메일 수를 뽑아 보고서의 "많이 온 곳"을 빠르게 보여주기 위해 사용합니다.
        sender_counter = Counter(self._get_sender_label(mail) for mail in mails)
        top_senders = [
            MailSenderSummary(sender=sender, count=count)
            for sender, count in sender_counter.most_common(5)
        ]

        summary_text = (
            f"{period_label}({from_date}~{to_date}) 메일은 총 {len(mails)}건입니다. "
            f"안 읽은 메일 {len(unread_mails)}건, 중요 메일 {len(important_mails)}건, "
            f"첨부파일 포함 메일 {len(attachment_mails)}건입니다."
        )

        return MailPeriodSummary(
            period_label=period_label,
            from_date=from_date,
            to_date=to_date,
            listed_count=len(mails),
            unread_count=len(unread_mails),
            important_count=len(important_mails),
            attachment_count=len(attachment_mails),
            top_senders=top_senders,
            important_mails=important_mails,
            recent_mails=mails,
            summary_text=summary_text,
        )

    async def _fetch_period_summary(
        self,
        *,
        period_label: str,
        from_date: str,
        to_date: str,
        top_k: int,
    ) -> MailPeriodSummary:
        """
        지정 기간의 메일 목록을 조회한 뒤 보고서용 요약 모델로 변환합니다.
        top_k 는 Graph 과다 조회를 막기 위해 MailService 와 동일하게 1~50 범위로 제한됩니다.
        """

        normalized_top_k = max(1, min(top_k, 50))
        mails = await self.mail_service.fetch_my_mails(
            top_k=normalized_top_k,
            from_date=from_date,
            to_date=to_date,
        )

        return self._build_period_summary(
            period_label=period_label,
            from_date=from_date,
            to_date=to_date,
            mails=mails,
        )

    async def fetch_weekly_report(self, *, top_k: int = 50) -> MailWeeklyReport:
        """
        지난주와 이번주 메일 목록 및 요약 정보를 반환합니다.
        주간보고 작성 시 두 기간을 나란히 비교할 수 있게 한 응답에 함께 담습니다.
        """

        last_week_from, last_week_to = get_week_date_range(week_offset=-1)
        this_week_from, this_week_to = get_week_date_range(week_offset=0)

        last_week = await self._fetch_period_summary(
            period_label="지난주",
            from_date=last_week_from,
            to_date=last_week_to,
            top_k=top_k,
        )
        this_week = await self._fetch_period_summary(
            period_label="이번주",
            from_date=this_week_from,
            to_date=this_week_to,
            top_k=top_k,
        )

        report_content = (
            f"지난주 메일 {last_week.listed_count}건, 이번주 메일 {this_week.listed_count}건입니다. "
            f"이번주 안 읽은 메일은 {this_week.unread_count}건, 중요 메일은 {this_week.important_count}건입니다."
        )

        return MailWeeklyReport(
            last_week=last_week,
            this_week=this_week,
            report_content=report_content,
        )

    async def fetch_monthly_report(self, *, top_k: int = 50) -> MailMonthlyReport:
        """
        지난달과 이번달 메일 목록 및 요약 정보를 반환합니다.
        월간보고 작성 시 월 단위 흐름을 비교할 수 있도록 두 기간을 함께 담습니다.
        """

        last_month_from, last_month_to = get_month_date_range(month_offset=-1)
        this_month_from, this_month_to = get_month_date_range(month_offset=0)

        last_month = await self._fetch_period_summary(
            period_label="지난달",
            from_date=last_month_from,
            to_date=last_month_to,
            top_k=top_k,
        )
        this_month = await self._fetch_period_summary(
            period_label="이번달",
            from_date=this_month_from,
            to_date=this_month_to,
            top_k=top_k,
        )

        report_content = (
            f"지난달 메일 {last_month.listed_count}건, 이번달 메일 {this_month.listed_count}건입니다. "
            f"이번달 안 읽은 메일은 {this_month.unread_count}건, 중요 메일은 {this_month.important_count}건입니다."
        )

        return MailMonthlyReport(
            last_month=last_month,
            this_month=this_month,
            report_content=report_content,
        )
