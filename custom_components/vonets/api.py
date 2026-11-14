"""Client for the VONETS VBG1200 web endpoints (link check is open; signal/status need the web login)."""
import re

import aiohttp

_UNITS = {"day": 86400, "hour": 3600, "min": 60, "sec": 1}


class VonetsError(Exception):
    """The device replied with something that is not a VONETS status answer."""


class AuthRequired(Exception):
    """Login rejected (wrong or changed password)."""


def parse_uptime(text: str) -> int | None:
    """'1 days, 2 hours, 10 mins, 29 secs' -> seconds; None if nothing recognisable."""
    parts = re.findall(r"(\d+)\s*(day|hour|min|sec)", text, re.I)
    return sum(int(n) * _UNITS[u.lower()] for n, u in parts) if parts else None


def is_login_page(text: str) -> bool:
    """Unauthenticated calls get an HTML redirect; real answers are plain text."""
    return text.lstrip().startswith("<")


def parse(link: str, signal: str, refresh: str) -> dict:
    """Turn the three raw endpoint replies into one dict; raises VonetsError on malformed replies."""
    m = re.match(r"\s*(\d+)\((-?\d+)\s*dbm\)", signal, re.I)
    if link.strip() not in ("0", "1") or not m or not re.match(r"\s*\d;", refresh):
        raise VonetsError("unexpected reply from bridge")
    fields = dict(p.split("=", 1) for p in refresh.split(";") if "=" in p)
    ssid = re.search(r"(?:^|;)ssid=(.*?);bssid=", refresh)  # an SSID may itself contain ';'
    temp = re.match(r"\d+", fields.get("temp", ""))
    chan = re.match(r"\d+", fields.get("channel", ""))
    return {
        "linked": link.strip() == "1",
        "signal_pct": int(m[1]),
        "signal_dbm": int(m[2]),
        "ssid": ssid[1] if ssid else None,
        "bssid": fields.get("bssid"),
        "channel": int(chan[0]) if chan else None,
        "temperature": int(temp[0]) if temp else None,  # first of the 'cpu/board' pair, e.g. '53/35'
        "uptime": parse_uptime(fields.get("time", "")),
    }


class VonetsClient:
    def __init__(self, session: aiohttp.ClientSession, host: str, username: str = "", password: str = "") -> None:
        self._s, self._host, self._user, self._pw = session, host, username, password

    async def _post(self, name: str, data: dict | None = None, total: int = 8) -> str:
        async with self._s.post(f"http://{self._host}/goform/{name}", data=data,
                                timeout=aiohttp.ClientTimeout(total=total)) as r:
            r.raise_for_status()
            return await r.text()

    async def identify(self) -> bool:
        """True if the host looks like a VONETS bridge (used by discovery and scan)."""
        try:
            async with self._s.post(f"http://{self._host}/goform/getApcliLinkSta",
                                    timeout=aiohttp.ClientTimeout(total=2)) as r:
                return "VONETS" in r.headers.get("Server", "").upper() and (await r.text()).strip() in ("0", "1")
        except (aiohttp.ClientError, TimeoutError):
            return False

    async def _protected(self, name: str) -> str:
        text = await self._post(name)
        if is_login_page(text):
            if not self._pw:
                raise AuthRequired
            await self._post("login", {"username": self._user, "password": self._pw, "z999": "z999",
                                       "platform": "pc", "Login": ""})
            text = await self._post(name)
            if is_login_page(text):
                raise AuthRequired
        return text

    async def fetch(self) -> dict:
        """Full status. Without a password only the open link check is returned. Raises AuthRequired
        only when a password was given and the bridge still wants a login."""
        link = await self._post("getApcliLinkSta")
        if link.strip() not in ("0", "1"):
            raise VonetsError("unexpected reply from bridge")
        if not self._pw:
            if is_login_page(await self._post("GetCurApcliSignal")):
                return {"linked": link.strip() == "1"}
        return parse(link, await self._protected("GetCurApcliSignal"), await self._protected("SendStatusRefresh"))
