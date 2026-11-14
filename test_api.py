import sys; from unittest.mock import MagicMock; sys.modules.setdefault("aiohttp", MagicMock())  # parser test needs no HTTP lib
sys.path.insert(0, "custom_components/vonets")
from api import VonetsError, is_login_page, parse, parse_uptime

R = "1;ssid=BauerCoulson IoT;bssid=96:ed:e1:00:de:f0;auth=WPA2PSK;enc=TKIPAES;channel=44;connsch=;time=10 mins, 29 secs;temp=61;icmp=ICMP is disabled.;d1xcli=8021x Client Disabled"
d = parse("1", "100(-40dbm)", R)
assert d == {"linked": True, "signal_pct": 100, "signal_dbm": -40, "ssid": "BauerCoulson IoT", "bssid": "96:ed:e1:00:de:f0", "channel": 44, "temperature": 61, "uptime": 629}, d
assert parse_uptime("1 days, 2 hours, 3 mins, 4 secs") == 93784 and parse_uptime("1 Days") == 86400
assert parse_uptime("") is None and parse_uptime("garbage") is None
assert parse("1", "100(-40dbm)", R.replace("temp=61", "temp=53/35"))["temperature"] == 53
assert parse("0", "0(-90dbm)", R.replace("time=10 mins, 29 secs;", ""))["uptime"] is None
assert parse("1", "100(-40dbm)", R.replace("BauerCoulson IoT", "a;b a3.asp"))["ssid"] == "a;b a3.asp"
assert is_login_page("<html><body onLoad=\"top.location.href='/a3.asp'\"></body></html>") and not is_login_page(R) and not is_login_page("100(-40dbm)")
for bad in (("1", "<html>", R), ("x", "100(-40dbm)", R), ("1", "100(-40dbm)", "<html>")):
    try: parse(*bad)
    except VonetsError: pass
    else: raise AssertionError(bad)
print("ok")
