from unittest.mock import Mock

import pytest

from youdao_checkin.client import YoudaoClient, YoudaoError, parse_cookie_header


def test_parse_cookie_header_handles_equals_in_value():
    assert parse_cookie_header("YNOTE_SESS=abc==; YNOTE_LOGIN=true") == {
        "YNOTE_SESS": "abc==",
        "YNOTE_LOGIN": "true",
    }


def test_parse_cookie_header_accepts_request_header_prefix():
    assert parse_cookie_header("Cookie: A=1; B=2") == {"A": "1", "B": "2"}


def test_parse_cookie_header_rejects_empty_value():
    with pytest.raises(YoudaoError):
        parse_cookie_header("")


def test_device_type_is_validated():
    with pytest.raises(YoudaoError):
        from youdao_checkin.client import YoudaoClient

        YoudaoClient("A=1", device_type="Android")


def test_cookie_requires_cstk():
    with pytest.raises(YoudaoError, match="YNOTE_CSTK"):
        YoudaoClient("YNOTE_SESS=abc")


def test_checkin_matches_web_cstk_request(monkeypatch):
    client = YoudaoClient("YNOTE_SESS=abc; YNOTE_CSTK=token")
    response = Mock(status_code=200, text='{"space": 1048576}')
    response.json.return_value = {"space": 1048576}
    request = Mock(return_value=response)
    monkeypatch.setattr(client.session, "request", request)

    result = client.checkin()

    assert result.status == "SUCCESS"
    kwargs = request.call_args.kwargs
    assert kwargs["params"]["method"] == "checkin"
    assert kwargs["params"]["keyfrom"] == "web"
    assert kwargs["params"]["cstk"] == "token"
    assert kwargs["data"] == {"cstk": "token"}
