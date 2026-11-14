"""VONETS WiFi bridge status monitoring."""
import asyncio
import logging
from datetime import timedelta

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

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
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
