"""UI setup: just the bridge's IP address."""
import aiohttp
import voluptuous as vol
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_HOST
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import DOMAIN
from .api import fetch


class VonetsConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input:
            host = user_input[CONF_HOST].strip()
            await self.async_set_unique_id(host)  # shortcut: keyed on IP, so give each bridge a DHCP reservation
            self._abort_if_unique_id_configured()
            try:
                await fetch(async_get_clientsession(self.hass), host)
            except (aiohttp.ClientError, TimeoutError):
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(title=f"VONETS {host}", data={CONF_HOST: host})
        return self.async_show_form(step_id="user", data_schema=vol.Schema({vol.Required(CONF_HOST): str}), errors=errors)
