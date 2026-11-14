"""UI setup: manual IP, network scan, or DHCP discovery; then the bridge's web login."""
import asyncio
from ipaddress import ip_network

import aiohttp
import voluptuous as vol
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_create_clientsession, async_get_clientsession
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig, TextSelectorType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from . import DOMAIN
from .api import AuthRequired, VonetsClient, VonetsError

_PASSWORD = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))


def _schema(host="", user="admin", password="", with_host=True):
    fields = {vol.Required(CONF_HOST, default=host): str} if with_host else {}
    fields[vol.Optional(CONF_USERNAME, default=user)] = str
    fields[vol.Optional(CONF_PASSWORD, default=password)] = _PASSWORD
    return vol.Schema(fields)


async def _validate(hass, host, user, password) -> dict:
    session = async_create_clientsession(hass, cookie_jar=aiohttp.CookieJar(unsafe=True))
    try:
        await VonetsClient(session, host, user, password).fetch()
    except AuthRequired:
        return {"base": "invalid_auth"}
    except (aiohttp.ClientError, TimeoutError, VonetsError):
        return {"base": "cannot_connect"}
    finally:
        await session.close()
    return {}


async def _scan(hass, net) -> list[str]:
    session, sem = async_get_clientsession(hass), asyncio.Semaphore(64)

    async def one(ip):
        async with sem:
            return str(ip) if await VonetsClient(session, str(ip)).identify() else None

    return [h for h in await asyncio.gather(*(one(i) for i in net.hosts())) if h]


class VonetsConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 2
    _host = ""
    _found: list[str] = []

    async def async_step_user(self, user_input=None):
        return self.async_show_menu(step_id="user", menu_options=["manual", "scan"])

    async def async_step_manual(self, user_input=None):
        errors = {}
        if user_input:
            host = user_input[CONF_HOST].strip()
            await self.async_set_unique_id(host)  # keyed on IP for duplicate detection; use a DHCP reservation
            self._abort_if_unique_id_configured()
            user, pw = user_input.get(CONF_USERNAME, ""), user_input.get(CONF_PASSWORD, "")
            errors = await _validate(self.hass, host, user, pw)
            if not errors:
                return self.async_create_entry(title=f"VONETS {host}",
                                               data={CONF_HOST: host, CONF_USERNAME: user, CONF_PASSWORD: pw})
        return self.async_show_form(step_id="manual", data_schema=_schema(self._host), errors=errors)

    async def async_step_scan(self, user_input=None):
        errors = {}
        if user_input:
            try:
                net = ip_network(user_input["network"].strip(), strict=False)
            except ValueError:
                errors["base"] = "invalid_network"
            else:
                if net.version != 4 or net.num_addresses > 1024:
                    errors["base"] = "network_too_big"
                else:
                    known = {e.data[CONF_HOST] for e in self._async_current_entries()}
                    self._found = [h for h in await _scan(self.hass, net) if h not in known]
                    if self._found:
                        return await self.async_step_pick()
                    errors["base"] = "none_found"
        return self.async_show_form(step_id="scan", data_schema=vol.Schema({vol.Required("network"): str}), errors=errors)

    async def async_step_pick(self, user_input=None):
        if user_input:
            self._host = user_input[CONF_HOST]
            return await self.async_step_manual()
        return self.async_show_form(step_id="pick", data_schema=vol.Schema({vol.Required(CONF_HOST): vol.In(self._found)}))

    async def async_step_dhcp(self, discovery_info: DhcpServiceInfo):
        host = discovery_info.ip
        await self.async_set_unique_id(host)
        self._abort_if_unique_id_configured()
        if not await VonetsClient(async_get_clientsession(self.hass), host).identify():
            return self.async_abort(reason="not_vonets")
        self._host = host
        self.context["title_placeholders"] = {"host": host}
        return await self.async_step_manual()

    async def async_step_reauth(self, entry_data):
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        entry, errors = self._get_reauth_entry(), {}
        if user_input:
            data = {**entry.data, **user_input}
            errors = await _validate(self.hass, data[CONF_HOST], data[CONF_USERNAME], data[CONF_PASSWORD])
            if not errors:
                return self.async_update_reload_and_abort(entry, data=data)
        return self.async_show_form(step_id="reauth_confirm", errors=errors, data_schema=_schema(
            user=entry.data.get(CONF_USERNAME, "admin"), with_host=False))

    async def async_step_reconfigure(self, user_input=None):
        entry, errors = self._get_reconfigure_entry(), {}
        if user_input:
            host = user_input[CONF_HOST].strip()
            user, pw = user_input.get(CONF_USERNAME, ""), user_input.get(CONF_PASSWORD, "")
            errors = await _validate(self.hass, host, user, pw)
            if not errors:
                return self.async_update_reload_and_abort(
                    entry, unique_id=host, title=f"VONETS {host}",
                    data={CONF_HOST: host, CONF_USERNAME: user, CONF_PASSWORD: pw})
        return self.async_show_form(step_id="reconfigure", errors=errors, data_schema=_schema(
            entry.data[CONF_HOST], entry.data.get(CONF_USERNAME, "admin"), entry.data.get(CONF_PASSWORD, "")))
