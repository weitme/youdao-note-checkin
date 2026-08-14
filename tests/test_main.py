from youdao_checkin.client import CheckinResult
from youdao_checkin.main import format_report


def test_format_report_does_not_include_cookie():
    report = format_report(
        [
            ("主账号", CheckinResult("SUCCESS", "签到成功，获得 10 MB")),
            ("备用账号", CheckinResult("COOKIE_EXPIRED", "登录态失效，请更新 Cookie")),
        ]
    )
    assert "主账号" in report
    assert "Cookie" in report
    assert "YNOTE_SESS" not in report
