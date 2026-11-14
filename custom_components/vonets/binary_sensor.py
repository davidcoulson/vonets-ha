from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity

from .entity import VonetsEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([VonetsLink(entry.runtime_data)])


class VonetsLink(VonetsEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_name = "Uplink"

    def __init__(self, coordinator):
        super().__init__(coordinator, "linked")

    @property
    def is_on(self):
        return self.coordinator.data["linked"]
