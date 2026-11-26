"""Shared fixtures: a fake bridge at the HTTP level."""
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.vonets import DOMAIN

HOST = "192.0.2.1"
BASE = f"http://{HOST}/goform"
SIGNAL = "100(-40dbm)"
REFRESH = ("1;ssid=Test IoT;bssid=96:ed:e1:00:de:f0;auth=WPA2PSK;enc=TKIPAES;channel=44;connsch=;"
           "time=10 mins, 29 secs;temp=61;icmp=ICMP is disabled.;d1xcli=8021x Client Disabled")
LOGIN_PAGE = "<html><body onLoad=\"top.location.href='/a3.asp'\"></body></html>"
DATA = {"host": HOST, "username": "admin", "password": "pw"}


def mock_bridge(aioclient_mock, link="1", signal=SIGNAL, refresh=REFRESH, **kwargs):
    """Replace the fake bridge's answers; kwargs (exc=, status=) apply to every endpoint."""
    aioclient_mock.clear_requests()
    for name, text in (("getApcliLinkSta", link), ("GetCurApcliSignal", signal),
                       ("SendStatusRefresh", refresh), ("login", "")):
        aioclient_mock.post(f"{BASE}/{name}", text=text, **kwargs)


@pytest.fixture(autouse=True)
def _custom_integrations(enable_custom_integrations):
    """Let Home Assistant load custom_components/vonets."""


@pytest.fixture
def entry(hass):
    entry = MockConfigEntry(domain=DOMAIN, version=2, title=f"VONETS {HOST}", unique_id=HOST, data=DATA)
    entry.add_to_hass(hass)
    return entry
