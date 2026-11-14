import sys; from unittest.mock import MagicMock; sys.modules.setdefault("aiohttp", MagicMock())  # parser test needs no HTTP lib
import sys; sys.path.insert(0, "custom_components/vonets")
from api import parse, parse_uptime
d = parse("1", "100(-40dbm)", "1;ssid=BauerCoulson IoT;bssid=96:ed:e1:00:de:f0;auth=WPA2PSK;enc=TKIPAES;channel=44;connsch=;time=10 mins, 29 secs;temp=61;icmp=ICMP is disabled.;d1xcli=8021x Client Disabled")
assert d == {"linked": True, "signal_pct": 100, "signal_dbm": -40, "ssid": "BauerCoulson IoT", "bssid": "96:ed:e1:00:de:f0", "channel": 44, "temperature": 61, "uptime": 629}, d
assert parse_uptime("1 days, 2 hours, 3 mins, 4 secs") == 93784
print("ok")
