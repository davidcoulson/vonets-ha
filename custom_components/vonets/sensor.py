from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import PERCENTAGE, SIGNAL_STRENGTH_DECIBELS_MILLIWATT, UnitOfTemperature, UnitOfTime
from homeassistant.helpers.entity import EntityCategory

from .entity import VonetsEntity

# key, name, device_class, unit, diagnostic?
SENSORS = [
    ("signal_dbm", "Uplink signal", SensorDeviceClass.SIGNAL_STRENGTH, SIGNAL_STRENGTH_DECIBELS_MILLIWATT, False),
    ("signal_pct", "Uplink signal quality", None, PERCENTAGE, True),
    ("temperature", "Temperature", SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS, False),
    ("uptime", "Uptime", SensorDeviceClass.DURATION, UnitOfTime.SECONDS, False),
    ("channel", "Channel", None, None, True),
    ("bssid", "Connected AP", None, None, True),
    ("ssid", "SSID", None, None, True),
]


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(VonetsSensor(entry.runtime_data, *s) for s in SENSORS)


class VonetsSensor(VonetsEntity, SensorEntity):
    def __init__(self, coordinator, key, name, dev_class, unit, diag):
        super().__init__(coordinator, key)
        self._attr_name = name
        self._attr_device_class = dev_class
        self._attr_native_unit_of_measurement = unit
        if diag:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        if unit is not None:
            self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        return self.coordinator.data.get(self._key)  # None (unknown) if the bridge login failed
