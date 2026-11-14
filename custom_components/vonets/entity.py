from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DOMAIN, VonetsCoordinator


class VonetsEntity(CoordinatorEntity[VonetsCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: VonetsCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._key = key
        self._attr_unique_id = f"{coordinator.host}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.host)}, name=f"VONETS {coordinator.host}",
            manufacturer="VONETS", model="VBG1200", configuration_url=f"http://{coordinator.host}/")
