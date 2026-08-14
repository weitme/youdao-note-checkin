from __future__ import annotations

import requests


class PushdeerError(RuntimeError):
    pass


def push_markdown(
    key: str,
    title: str,
    body: str,
    endpoint: str = "https://api2.pushdeer.com/message/push",
    timeout: float = 20,
) -> None:
    if not key:
        raise PushdeerError("未设置 PUSHDEER_KEY")
    try:
        response = requests.post(
            endpoint,
            data={"pushkey": key, "text": title, "desp": body, "type": "markdown"},
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise PushdeerError("PushDeer 网络请求失败") from exc
    if response.status_code >= 400:
        raise PushdeerError(f"PushDeer 返回 HTTP {response.status_code}")
    try:
        payload = response.json()
    except ValueError as exc:
        raise PushdeerError("PushDeer 返回格式异常") from exc
    if payload.get("code") != 0:
        raise PushdeerError("PushDeer 推送失败")
