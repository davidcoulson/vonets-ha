"""VONETS WiFi bridge status monitoring."""
import asyncio
from datetime import timedelta

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import fetch

DOMAIN = "vonets"
PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]


class VonetsCoordinator(DataUpdateCoordinator[dict]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, __import__("logging").getLogger(__name__), config_entry=entry,
                         name=DOMAIN, update_interval=timedelta(seconds=60))
        self.host = entry.data[CONF_HOST]

    async def _async_update_data(self) -> dict:
        try:
            return await fetch(async_get_clientsession(self.hass), self.host)
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise UpdateFailed(f"{self.host}: {err}") from err


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = VonetsCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
