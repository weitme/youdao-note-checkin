import pytest

from youdao_checkin.config import ConfigError, load_accounts


def test_load_accounts_supports_list_and_object_wrapper():
    accounts = load_accounts('[{"name":"主账号","cookie":"A=1; B=2"}]')
    assert accounts[0].name == "主账号"
    assert accounts[0].cookie == "A=1; B=2"

    wrapped = load_accounts('{"accounts":[{"cookie":"A=1"}]}')
    assert wrapped[0].name == "账号1"

    single = load_accounts('{"name":"单账号","cookie":"A=1"}')
    assert single[0].name == "单账号"


@pytest.mark.parametrize("raw", ["", "{}", "[]", "not-json"])
def test_invalid_accounts_are_rejected(raw):
    with pytest.raises(ConfigError):
        load_accounts(raw)
