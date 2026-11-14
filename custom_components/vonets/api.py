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


async def post(session: aiohttp.ClientSession, host: str, name: str) -> str:
    async with session.post(f"http://{host}/goform/{name}", timeout=aiohttp.ClientTimeout(total=8)) as r:
        r.raise_for_status()
        return await r.text()


async def fetch(session: aiohttp.ClientSession, host: str) -> dict:
    return parse(
        await post(session, host, "getApcliLinkSta"),
        await post(session, host, "GetCurApcliSignal"),
        await post(session, host, "SendStatusRefresh"),
    )
