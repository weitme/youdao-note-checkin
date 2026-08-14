from __future__ import annotations

import sys
from collections import Counter

from .client import CheckinResult, YoudaoClient, YoudaoError
from .config import ConfigError, Settings, load_settings
from .notifier import PushdeerError, push_markdown


def run(settings: Settings) -> tuple[list[tuple[str, CheckinResult]], int]:
    results: list[tuple[str, CheckinResult]] = []
    for account in settings.accounts:
        try:
            result = YoudaoClient(
                account.cookie,
                timeout=settings.timeout_seconds,
                ad_rewards=settings.ad_rewards,
            ).checkin()
        except YoudaoError as exc:
            result = CheckinResult(exc.status, exc.message)
        except Exception:
            result = CheckinResult("UNEXPECTED_ERROR", "程序异常，请查看 Action 日志")
        results.append((account.name, result))

    failed = sum(result.status not in {"SUCCESS", "ALREADY"} for _, result in results)
    return results, 1 if failed else 0


def format_report(results: list[tuple[str, CheckinResult]]) -> str:
    counts = Counter(result.status for _, result in results)
    lines = [
        "## 有道云笔记签到结果",
        "",
        f"账户数：{len(results)}",
        f"成功：{counts.get('SUCCESS', 0)}，已签到：{counts.get('ALREADY', 0)}，失败：{len(results) - counts.get('SUCCESS', 0) - counts.get('ALREADY', 0)}",
        "",
    ]
    for name, result in results:
        icon = "✅" if result.status == "SUCCESS" else "ℹ️" if result.status == "ALREADY" else "❌"
        lines.append(f"{icon} **{name}**：{result.message}")
    return "\n".join(lines)


def main() -> int:
    try:
        settings = load_settings()
    except ConfigError as exc:
        print(f"配置错误：{exc}", file=sys.stderr)
        return 2

    results, exit_code = run(settings)
    report = format_report(results)
    print(report)

    if settings.pushdeer_key:
        try:
            push_markdown(
                settings.pushdeer_key,
                "有道云笔记签到结果",
                report,
                endpoint=settings.pushdeer_endpoint,
                timeout=settings.timeout_seconds,
            )
            print("PushDeer：推送成功")
        except PushdeerError as exc:
            print(f"PushDeer：{exc}", file=sys.stderr)
            exit_code = max(exit_code, 1)
    else:
        print("PushDeer：未配置 PUSHDEER_KEY，跳过推送")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
