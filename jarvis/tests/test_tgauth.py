import json
import time

from jarviscore.tgauth import check, sign

TOKEN = "123456:TEST-token"
OWNER = 777


def data(uid=OWNER, age=10, **extra):
    return {"auth_date": str(int(time.time()) - age), "query_id": "AAF", "user": json.dumps({"id": uid, "first_name": "A"}),
            **extra}


def test_owner_with_valid_signature_passes():
    assert check(sign(data(), TOKEN), TOKEN, OWNER)


def test_other_user_is_rejected():
    assert not check(sign(data(uid=123), TOKEN), TOKEN, OWNER)


def test_forged_or_tampered_signature_is_rejected():
    good = sign(data(), TOKEN)
    assert not check(sign(data(), "999:other-bot"), TOKEN, OWNER)        # подписано чужим ботом
    assert not check(good.replace("%22first_name%22", "%22last_name%22"), TOKEN, OWNER)   # подменили данные
    assert not check(good.split("&hash=")[0], TOKEN, OWNER)              # без подписи


def test_old_or_future_signature_is_rejected():
    assert not check(sign(data(age=2 * 86400), TOKEN), TOKEN, OWNER)
    assert not check(sign(data(age=-3600), TOKEN), TOKEN, OWNER)


def test_garbage_and_missing_config_are_rejected():
    for bad in ("", "abc", "hash=", "%%%", "user=1&hash=00"):
        assert not check(bad, TOKEN, OWNER)
    assert not check(sign(data(), TOKEN), "", OWNER) and not check(sign(data(), TOKEN), TOKEN, None)
