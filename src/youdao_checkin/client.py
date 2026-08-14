from __future__ import annotations

from dataclasses import dataclass
from http.cookies import SimpleCookie
import hashlib
import os
import platform
import time
from typing import Any

import requests


class YoudaoError(RuntimeError):
    def __init__(self, status: str, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


@dataclass(frozen=True)
class CheckinResult:
    status: str
    message: str
    reward_mb: int | None = None


def parse_cookie_header(cookie_header: str) -> dict[str, str]:
    """把浏览器复制的 Cookie 请求头解析为键值对。"""
    cookie_header = cookie_header.strip()
    if cookie_header.lower().startswith("cookie:"):
        cookie_header = cookie_header.split(":", 1)[1].strip()
    parsed = SimpleCookie()
    parsed.load(cookie_header)
    result = {key: morsel.value for key, morsel in parsed.items()}
    # SimpleCookie 遇到少数非标准值时可能整段解析失败，按 Cookie 头的
    # 分号分隔规则回退解析；只保留键和值，不打印原始内容。
    if not result:
        for item in cookie_header.split(";"):
            key, separator, value = item.strip().partition("=")
            if separator and key:
                result[key.strip()] = value.strip()
    if not result:
        raise YoudaoError("CONFIG_ERROR", "Cookie 格式无效")
    return result


class YoudaoClient:
    """有道网页版签到接口适配器。

    该接口不是公开稳定 API，所有接口细节集中在此处，便于后续调整。
    """

    session_endpoint = "https://note.youdao.com/login/acc/pe/getsess?product=YNOTE"
    sync_endpoint = "https://note.youdao.com/yws/api/daupromotion?method=sync"
    checkin_endpoint = "https://note.youdao.com/yws/mapi/user"
    ad_endpoint = "https://note.youdao.com/yws/mapi/user?method=adRandomPrompt"

    def __init__(
        self,
        cookie: str,
        timeout: float = 20,
        ad_rewards: bool = False,
        device_type: str | None = None,
    ):
        self.timeout = timeout
        self.ad_rewards = ad_rewards
        self.device_type = device_type or os.environ.get("YOUDAO_DEVICE_TYPE", "PC")
        if self.device_type not in {"PC", "Mac", "Linux"}:
            raise YoudaoError("CONFIG_ERROR", "YOUDAO_DEVICE_TYPE 必须是 PC、Mac 或 Linux")
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "Chrome/131.0 Safari/537.36"
                ),
                "Referer": "https://note.youdao.com/web/",
                "Accept": "application/json, text/plain, */*",
                "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
            }
        )
        normalized_cookie = cookie.strip()
        if normalized_cookie.lower().startswith("cookie:"):
            normalized_cookie = normalized_cookie.split(":", 1)[1].strip()
        self.session.headers["Cookie"] = normalized_cookie
        parsed_cookie = parse_cookie_header(normalized_cookie)
        self.session.cookies.update(parsed_cookie)
        self.cstk = parsed_cookie.get("YNOTE_CSTK", "")
        if not self.cstk:
            raise YoudaoError("CONFIG_ERROR", "Cookie 缺少 YNOTE_CSTK，请重新复制完整 Cookie")
        seed = str(time.time_ns()).encode()
        self.app_user = hashlib.md5(seed).hexdigest()
        self.device_id = hashlib.md5(seed + b"device").hexdigest()[:16]
        self._debug(f"cookie_names={','.join(sorted(parsed_cookie))}")

    @staticmethod
    def _debug(message: str) -> None:
        if os.environ.get("YOUDAO_DEBUG", "").lower() in {"1", "true", "yes", "on"}:
            print(f"[youdao-debug] {message}")

    def _request(
        self,
        method: str,
        url: str,
        params: dict[str, str] | None = None,
        data: dict[str, str] | None = None,
    ) -> requests.Response:
        try:
            response = self.session.request(
                method,
                url,
                params=params,
                data=data,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise YoudaoError("NETWORK_ERROR", "网络请求失败") from exc
        if response.status_code >= 400:
            try:
                data = response.json()
            except ValueError:
                data = {}
            error = str(data.get("error", "")) if isinstance(data, dict) else ""
            message = str(data.get("message", "")) if isinstance(data, dict) else ""
            self._debug(
                f"{method} {url.split('?')[0]} -> HTTP {response.status_code}, "
                f"error={error or '-'}, message_class={'AUTHENTICATION_FAILURE' if 'AUTHENTICATION_FAILURE' in message else '-'}"
            )
            auth_failure = error in {"207", "401", "403"} or "AUTHENTICATION_FAILURE" in message
            if response.status_code in (401, 403) or auth_failure:
                raise YoudaoError("COOKIE_EXPIRED", "登录态失效，请更新 Cookie")
            if response.status_code >= 500:
                raise YoudaoError("REMOTE_ERROR", "有道服务暂时不可用或请求被安全策略拒绝")
            raise YoudaoError("HTTP_ERROR", f"有道接口返回 HTTP {response.status_code}")
        return response

    @staticmethod
    def _json(response: requests.Response) -> dict[str, Any]:
        try:
            data = response.json()
        except ValueError as exc:
            raise YoudaoError("INVALID_RESPONSE", "有道接口返回格式异常") from exc
        if not isinstance(data, dict):
            raise YoudaoError("INVALID_RESPONSE", "有道接口返回内容异常")
        return data

    @staticmethod
    def _number(data: dict[str, Any], key: str) -> int:
        value = data.get(key, 0)
        try:
            return max(0, int(value))
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _is_already_signed(data: dict[str, Any], text: str = "") -> bool:
        lowered = text.lower()
        markers = ("already", "today", "已签到", "今日已签", "重复签到")
        if any(marker in lowered for marker in markers):
            return True
        for key in ("message", "msg", "error"):
            value = data.get(key)
            if isinstance(value, str) and any(marker in value.lower() for marker in markers):
                return True
        return False

    def checkin(self) -> CheckinResult:
        # 与当前网页版 HTTP 拦截器保持一致。cstk 既出现在查询串中，
        # 也出现在 application/x-www-form-urlencoded 表单体中。
        system_name = platform.system().lower() or "linux"
        web_params = {
            "method": "checkin",
            "device_type": self.device_type,
            "_system": system_name,
            "_systemVersion": "",
            "_screenWidth": "1920",
            "_screenHeight": "1080",
            "_appName": "ynote",
            "_appuser": self.app_user,
            "_vendor": "official-website",
            "_launch": "0",
            "_firstTime": "",
            "_deviceId": self.device_id,
            "_platform": "web",
            "_cityCode": "",
            "_cityName": "",
            "_product": "YNote-Web",
            "_version": "",
            "sev": "j1",
            "sec": "v1",
            "keyfrom": "web",
            "cstk": self.cstk,
        }
        checkin_response = self._request(
            "POST",
            self.checkin_endpoint,
            params=web_params,
            data={"cstk": self.cstk},
        )
        checkin_data = self._json(checkin_response)
        if "error" in checkin_data:
            self._debug(
                f"POST {self.checkin_endpoint.split('?')[0]} -> HTTP {checkin_response.status_code}, "
                f"error={checkin_data.get('error', '-')}, message_class="
                f"{'AUTHENTICATION_FAILURE' if 'AUTHENTICATION_FAILURE' in checkin_response.text else '-'}"
            )
            if self._is_already_signed(checkin_data, checkin_response.text):
                return CheckinResult("ALREADY", "今日已签到")
            raise YoudaoError("REMOTE_ERROR", "有道签到接口拒绝请求")
        if self._is_already_signed(checkin_data, checkin_response.text):
            return CheckinResult("ALREADY", "今日已签到")

        reward_bytes = self._number(checkin_data, "space") or self._number(
            checkin_data, "rewardSpace"
        )
        if self.ad_rewards:
            for _ in range(3):
                ad_data = self._json(self._request("POST", self.ad_endpoint))
                reward_bytes += self._number(ad_data, "space")

        reward_mb = reward_bytes // 1048576
        return CheckinResult("SUCCESS", f"签到成功，获得 {reward_mb} MB", reward_mb)
