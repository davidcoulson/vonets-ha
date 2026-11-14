"""Read-only client for the VONETS VBG1200 status endpoints (no login needed)."""
import re

import aiohttp

_UNITS = {"day": 86400, "hour": 3600, "min": 60, "sec": 1}


def parse_uptime(text: str) -> int:
    """'1 days, 2 hours, 10 mins, 29 secs' -> seconds."""
    return sum(int(n) * _UNITS[u] for n, u in re.findall(r"(\d+)\s*(day|hour|min|sec)", text))


def parse(link: str, signal: str, refresh: str) -> dict:
    """Turn the three raw endpoint replies into one dict."""
    fields = dict(p.split("=", 1) for p in refresh.split(";") if "=" in p)
    m = re.match(r"(\d+)\((-?\d+)dbm\)", signal.strip(), re.I)
    return {
        "linked": link.strip() == "1",
        "signal_pct": int(m[1]) if m else None,
        "signal_dbm": int(m[2]) if m else None,
        "ssid": fields.get("ssid"),
        "bssid": fields.get("bssid"),
        "channel": int(fields["channel"]) if fields.get("channel", "").isdigit() else None,
        "temperature": int(fields["temp"]) if fields.get("temp", "").isdigit() else None,
        "uptime": parse_uptime(fields.get("time", "")),
    }


class AuthRequired(Exception):
    """The bridge answered with its login redirect."""


class VonetsClient:
    """Link check is open; signal/status need the web login (cookie session)."""

    def __init__(self, session: aiohttp.ClientSession, host: str, username: str = "", password: str = "") -> None:
        self._s, self._host, self._user, self._pw = session, host, username, password

    async def _post(self, name: str, data: dict | None = None) -> str:
        async with self._s.post(f"http://{self._host}/goform/{name}", data=data,
                                timeout=aiohttp.ClientTimeout(total=8)) as r:
            r.raise_for_status()
            return await r.text()

    async def _login(self) -> None:
        await self._post("login", {"username": self._user, "password": self._pw, "z999": "z999",
                                   "platform": "pc", "Login": ""})

    async def _authed(self, name: str) -> str:
        text = await self._post(name)
        if "a3.asp" in text:  # login redirect
            if not self._pw:
                raise AuthRequired
            await self._login()
            text = await self._post(name)
            if "a3.asp" in text:
                raise AuthRequired
        return text

    async def fetch(self) -> dict:
        link = await self._post("getApcliLinkSta")
        try:
            return parse(link, await self._authed("GetCurApcliSignal"), await self._authed("SendStatusRefresh"))
        except AuthRequired:
            return {"linked": link.strip() == "1", "auth_failed": True}
