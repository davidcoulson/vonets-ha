"""VONETS WiFi bridge status monitoring."""
import asyncio
import importlib
import importlib.util
import json
import logging
import sys
from datetime import timedelta
from pathlib import Path

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.loader import BASE_PRELOAD_PLATFORMS

from .api import AuthRequired, VonetsClient, VonetsError

DOMAIN = "vonets"
PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]
_LOGGER = logging.getLogger(__name__)


class VonetsCoordinator(DataUpdateCoordinator[dict]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, _LOGGER, config_entry=entry, name=DOMAIN, update_interval=timedelta(seconds=60))
        self.host = entry.data[CONF_HOST]
        # own session: the bridge login is cookie based and HA's shared session drops cookies
        self.client = VonetsClient(async_create_clientsession(hass, cookie_jar=aiohttp.CookieJar(unsafe=True)),
                                   self.host, entry.data.get(CONF_USERNAME, ""), entry.data.get(CONF_PASSWORD, ""))

    async def _async_update_data(self) -> dict:
        try:
            return await self.client.fetch()
        except AuthRequired as err:
            raise ConfigEntryAuthFailed(f"{self.host} rejected the login") from err
        except (aiohttp.ClientError, asyncio.TimeoutError, VonetsError) as err:
            raise UpdateFailed(f"{self.host}: {err}") from err


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """v1 keyed entities on the IP; v2 keys them on the entry id so an IP change keeps history."""
    if entry.version < 2:
        reg, host = er.async_get(hass), entry.data[CONF_HOST]
        for e in er.async_entries_for_config_entry(reg, entry.entry_id):
            if e.unique_id in (f"{host}_uptime", f"{host}_uptime_text"):
                reg.async_remove(e.entity_id)  # uptime sensors were reshuffled; recreated under new ids
            elif e.unique_id.startswith(f"{host}_"):
                reg.async_update_entity(e.entity_id, new_unique_id=f"{entry.entry_id}{e.unique_id[len(host):]}")
        hass.config_entries.async_update_entry(entry, version=2)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = VonetsCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _register_reload_code(hass)
    _clear_marketplace_restart(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


def _import_code(package: str) -> None:
    """Import the new code in the import executor, not the event loop.

    After an unload HA still lists "<domain>.<platform>" as loaded, so it
    would import the new modules in the event loop (and warn about it);
    once they are in sys.modules its own import is a cache hit.
    """
    module = importlib.import_module(package)
    # The new module's list, plus what HA preloads with a package (diagnostics, ...).
    for name in (*module.PLATFORMS, *BASE_PRELOAD_PLATFORMS):
        if importlib.util.find_spec(f"{package}.{name}") is not None:
            importlib.import_module(f"{package}.{name}")


def _forget_code(hass: HomeAssistant, package: str, domain: str) -> None:
    """Drop a package's modules so the next setup imports them from disk again.

    Home Assistant keeps its own copy of each imported integration module
    (hass.data["components"], keyed "<domain>" and "<domain>.<platform>") next to
    sys.modules; both have to go.
    """
    for cache, root in ((sys.modules, package), (hass.data.get("components", {}), domain),
                        (hass.data.get("missing_platforms", {}), domain)):
        for key in [n for n in cache if n == root or n.startswith(root + ".")]:
            del cache[key]
    importlib.invalidate_caches()  # or a file added since the last import may not be found


_CODE_VERSION = json.loads((Path(__file__).parent / "manifest.json").read_text())["version"]


def _clear_marketplace_restart(hass: HomeAssistant) -> None:
    """Drop Marketplace's "restart to finish the update" repairs for Vonets.

    Marketplace cannot see reload_code, so they would stay until a restart. Called from
    entry setup, it uses the new code's version even when the old handler did the reload;
    a repair for any other version still waits.
    """
    for (domain, issue_id), issue in list(ir.async_get(hass).issues.items()):
        if (
            domain == "marketplace"
            and issue_id.startswith("restart_required_")
            and issue.issue_domain == DOMAIN
            and issue_id.rsplit("/", 1)[-1].removeprefix("v") == _CODE_VERSION
        ):
            ir.async_delete_issue(hass, domain, issue_id)


def _register_reload_code(hass: HomeAssistant) -> None:
    """Dev: vonets.reload_code loads the Python files from disk without a restart."""

    async def _reload_code(call: ServiceCall) -> None:
        # Disabled and ignored entries are never set up, so they are not ours to reload.
        entries = hass.config_entries.async_entries(
            DOMAIN, include_ignore=False, include_disabled=False
        )
        for entry in entries:
            if not await hass.config_entries.async_unload(entry.entry_id):
                raise HomeAssistantError(f"{DOMAIN} did not unload; restart Home Assistant instead")
        _forget_code(hass, __name__, DOMAIN)
        try:
            await hass.async_add_import_executor_job(_import_code, __name__)
        except Exception as err:
            # This handler stays registered, so the action works again once the code is fixed.
            raise HomeAssistantError(f"{DOMAIN} is unloaded: the new code did not load ({err}). "
                                     f"Fix it and call {DOMAIN}.reload_code again") from err
        failed = [e.title for e in entries if not await hass.config_entries.async_setup(e.entry_id)]
        if failed:
            raise HomeAssistantError(f"{DOMAIN} did not set up again for {failed}; see the log")

    async_register_admin_service(hass, DOMAIN, "reload_code", _reload_code)
