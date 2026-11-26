"""Config flow: manual entry against a fake bridge."""
import aiohttp
from homeassistant.config_entries import SOURCE_USER
from homeassistant.data_entry_flow import FlowResultType

from custom_components.vonets import DOMAIN

from .conftest import DATA, HOST, LOGIN_PAGE, mock_bridge


async def _manual(hass, data=DATA):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.MENU
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "manual"})
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "manual"
    return await hass.config_entries.flow.async_configure(result["flow_id"], data)


async def test_success_creates_the_entry(hass, aioclient_mock):
    mock_bridge(aioclient_mock)
    result = await _manual(hass, {**DATA, "host": f" {HOST} "})
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"VONETS {HOST}"
    assert result["data"] == DATA
    assert result["result"].unique_id == HOST


async def test_cannot_connect(hass, aioclient_mock):
    mock_bridge(aioclient_mock, exc=aiohttp.ClientError)
    result = await _manual(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_not_a_bridge_is_cannot_connect(hass, aioclient_mock):
    mock_bridge(aioclient_mock, link="<html>some other device</html>")
    assert (await _manual(hass))["errors"] == {"base": "cannot_connect"}


async def test_bad_credentials(hass, aioclient_mock):
    mock_bridge(aioclient_mock, signal=LOGIN_PAGE)  # still the login page after logging in
    result = await _manual(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}
    assert any(str(url).endswith("/login") and data["password"] == DATA["password"]
               for _, url, data, _ in aioclient_mock.mock_calls)


async def test_error_then_success(hass, aioclient_mock):
    mock_bridge(aioclient_mock, exc=aiohttp.ClientError)
    result = await _manual(hass)
    mock_bridge(aioclient_mock)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], DATA)
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_duplicate_aborts(hass, aioclient_mock, entry):
    mock_bridge(aioclient_mock)
    result = await _manual(hass)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
