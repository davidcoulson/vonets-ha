from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DOMAIN, VonetsCoordinator


class VonetsEntity(CoordinatorEntity[VonetsCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: VonetsCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._key = key
        entry_id = coordinator.config_entry.entry_id
        self._attr_unique_id = f"{entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)}, name=coordinator.config_entry.title,
            manufacturer="VONETS", model="VBG1200", configuration_url=f"http://{coordinator.host}/")
