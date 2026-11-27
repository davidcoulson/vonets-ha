"""Entry setup and unload, coordinator updates, entity states, reload_code."""
import sys
from unittest.mock import patch

import aiohttp
import pytest
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.helpers import entity_registry as er

from custom_components.vonets import DOMAIN
from custom_components.vonets.api import VonetsClient

from .conftest import LOGIN_PAGE, mock_bridge

PACKAGE = "custom_components.vonets"


async def _setup(hass, entry):
    ok = await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return ok


def _state(hass, entry, platform, key):
    entity_id = er.async_get(hass).async_get_entity_id(platform, DOMAIN, f"{entry.entry_id}_{key}")
    return hass.states.get(entity_id)


async def test_setup_and_unload(hass, aioclient_mock, entry):
    mock_bridge(aioclient_mock)
    assert await _setup(hass, entry)
    assert entry.state is ConfigEntryState.LOADED
    assert hass.services.has_service(DOMAIN, "reload_code")
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert _state(hass, entry, "binary_sensor", "linked").state == "unavailable"


# aioclient_mock replaces Home Assistant's session factory and with it the cleanup under test,
# so these two patch the client's fetch and keep the real session.
async def test_unload_closes_the_session(hass, entry):
    with patch.object(VonetsClient, "fetch", return_value={"linked": True}):
        assert await _setup(hass, entry)
    session = entry.runtime_data.client._s
    assert not session.closed
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert session.closed


async def test_failed_setup_closes_the_session(hass, entry):
    sessions = []

    async def fetch(self):
        sessions.append(self._s)
        raise aiohttp.ClientError

    with patch.object(VonetsClient, "fetch", fetch):
        assert not await _setup(hass, entry)
    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert sessions and sessions[0].closed


async def test_setup_retries_when_the_bridge_is_down(hass, aioclient_mock, entry):
    mock_bridge(aioclient_mock, exc=aiohttp.ClientError)
    assert not await _setup(hass, entry)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_rejected_login_starts_reauth(hass, aioclient_mock, entry):
    mock_bridge(aioclient_mock, signal=LOGIN_PAGE)
    assert not await _setup(hass, entry)
    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert [f["context"]["source"] for f in hass.config_entries.flow.async_progress()] == [SOURCE_REAUTH]


async def test_entity_states(hass, aioclient_mock, entry):
    mock_bridge(aioclient_mock)
    assert await _setup(hass, entry)
    assert _state(hass, entry, "binary_sensor", "linked").state == "on"
    expected = {"signal_dbm": "-40", "signal_pct": "100", "temperature": "61", "uptime": "10m 29s",
                "channel": "44", "bssid": "96:ed:e1:00:de:f0", "ssid": "Test IoT"}
    assert {k: _state(hass, entry, "sensor", k).state for k in expected} == expected
    raw = er.async_get(hass).async_get(
        er.async_get(hass).async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_uptime_seconds"))
    assert raw.disabled_by is er.RegistryEntryDisabler.INTEGRATION


async def test_without_password_only_the_link_is_known(hass, aioclient_mock, entry):
    hass.config_entries.async_update_entry(entry, data={**entry.data, "password": ""})
    mock_bridge(aioclient_mock, link="0", signal=LOGIN_PAGE)
    assert await _setup(hass, entry)
    assert _state(hass, entry, "binary_sensor", "linked").state == "off"
    assert _state(hass, entry, "sensor", "signal_dbm").state == "unknown"
    assert _state(hass, entry, "sensor", "uptime").state == "unknown"


@pytest.mark.parametrize("broken", [{"exc": aiohttp.ClientError}, {"exc": TimeoutError}, {"status": 500},
                                    {"refresh": "garbage"}])
async def test_update_failure_and_recovery(hass, aioclient_mock, entry, broken):
    mock_bridge(aioclient_mock)
    assert await _setup(hass, entry)
    coordinator = entry.runtime_data

    mock_bridge(aioclient_mock, **broken)
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert not coordinator.last_update_success
    assert _state(hass, entry, "sensor", "signal_dbm").state == "unavailable"

    mock_bridge(aioclient_mock, signal="55(-70dbm)")
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert coordinator.last_update_success
    assert _state(hass, entry, "sensor", "signal_dbm").state == "-70"


async def test_reload_code_replaces_the_modules(hass, aioclient_mock, entry):
    mock_bridge(aioclient_mock)
    assert await _setup(hass, entry)
    old = {n: m for n, m in sys.modules.items() if n == PACKAGE or n.startswith(PACKAGE + ".")}
    try:
        await hass.services.async_call(DOMAIN, "reload_code", {}, blocking=True)
        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.LOADED
        assert sys.modules[PACKAGE] is not old[PACKAGE]
        assert type(entry.runtime_data).__module__ == PACKAGE
        assert type(entry.runtime_data) is not old[PACKAGE].VonetsCoordinator
        assert hass.services.has_service(DOMAIN, "reload_code")
        assert _state(hass, entry, "sensor", "signal_dbm").state == "-40"
    finally:
        # later tests hold the classes they imported at collection: put those modules back
        await hass.config_entries.async_unload(entry.entry_id)
        for name in [n for n in sys.modules if n == PACKAGE or n.startswith(PACKAGE + ".")]:
            del sys.modules[name]
        sys.modules.update(old)


def test_marketplace_restart_cleanup_matches_only_the_running_version(hass, monkeypatch):
    """Only Marketplace's restart repairs for this version of this integration are dropped."""
    from homeassistant.helpers import issue_registry as ir

    import custom_components.vonets as integration

    monkeypatch.setattr(integration, "_CODE_VERSION", "1.2.3")
    kept = {
        ("marketplace", "restart_required_1_tags/1.2.4"),
        ("marketplace", "restart_required_2_tags/1.2.3"),
        ("marketplace", "critical_x"),
        ("vonets", "restart_required_x"),
    }
    for domain, issue_id, issue_domain in (
        ("marketplace", "restart_required_1_tags/1.2.3", "vonets"),
        ("marketplace", "restart_required_1_tags/v1.2.3", "vonets"),
        ("marketplace", "restart_required_1_tags/1.2.4", "vonets"),
        ("marketplace", "restart_required_2_tags/1.2.3", "ssh"),
        ("marketplace", "critical_x", "vonets"),
        ("vonets", "restart_required_x", "vonets"),
    ):
        ir.async_create_issue(
            hass,
            domain,
            issue_id,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="x",
            issue_domain=issue_domain,
        )
    integration._clear_marketplace_restart(hass)
    assert set(ir.async_get(hass).issues) == kept


def test_code_version_is_the_manifest_version():
    import json
    from pathlib import Path

    import custom_components.vonets as integration

    manifest = Path(integration.__file__).parent / "manifest.json"
    assert json.loads(manifest.read_text())["version"] == integration._CODE_VERSION
