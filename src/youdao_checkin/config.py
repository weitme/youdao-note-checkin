from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any


class ConfigError(ValueError):
    """用户配置无效。"""


@dataclass(frozen=True)
class Account:
    name: str
    cookie: str


def load_accounts(raw: str | None = None) -> list[Account]:
    """从 YOUDAO_ACCOUNTS 读取账户列表，不返回或打印敏感值。"""
    value = os.environ.get("YOUDAO_ACCOUNTS") if raw is None else raw
    if not value or not value.strip():
        raise ConfigError("未设置 YOUDAO_ACCOUNTS")

    try:
        payload: Any = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ConfigError("YOUDAO_ACCOUNTS 不是有效 JSON") from exc

    if isinstance(payload, dict):
        if "accounts" in payload:
            payload = payload.get("accounts")
        elif "cookie" in payload:
            # PowerShell ConvertTo-Json 在只有一个对象时可能输出对象而非数组。
            payload = [payload]
        else:
            payload = None
    if not isinstance(payload, list) or not payload:
        raise ConfigError("YOUDAO_ACCOUNTS 必须是非空账户数组")

    accounts: list[Account] = []
    for index, item in enumerate(payload, start=1):
        if not isinstance(item, dict):
            raise ConfigError(f"第 {index} 个账户必须是对象")
        name = str(item.get("name") or f"账号{index}").strip()
        cookie = item.get("cookie")
        if not name:
            raise ConfigError(f"第 {index} 个账户缺少 name")
        if not isinstance(cookie, str) or not cookie.strip():
            raise ConfigError(f"账户 {name} 缺少 cookie")
        accounts.append(Account(name=name, cookie=cookie.strip()))
    return accounts


@dataclass(frozen=True)
class Settings:
    accounts: list[Account]
    pushdeer_key: str | None
    pushdeer_endpoint: str
    timeout_seconds: float
    ad_rewards: bool


def load_settings() -> Settings:
    timeout_raw = os.environ.get("YOUDAO_TIMEOUT", "20")
    try:
        timeout = float(timeout_raw)
    except ValueError as exc:
        raise ConfigError("YOUDAO_TIMEOUT 必须是数字") from exc
    if timeout <= 0:
        raise ConfigError("YOUDAO_TIMEOUT 必须大于 0")

    ad_rewards = os.environ.get("YOUDAO_AD_REWARDS", "false").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    return Settings(
        accounts=load_accounts(),
        pushdeer_key=os.environ.get("PUSHDEER_KEY") or None,
        pushdeer_endpoint=os.environ.get(
            "PUSHDEER_ENDPOINT", "https://api2.pushdeer.com/message/push"
        ),
        timeout_seconds=timeout,
        ad_rewards=ad_rewards,
    )
