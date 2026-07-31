from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from . import async_register_entity
from .core.attribute import TreeowAttribute
from .core.device import TreeowDevice
from .entity import TreeowAbstractEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    await async_register_entity(hass, entry, async_add_entities, Platform.SENSOR, TreeowSensor)


class TreeowSensor(TreeowAbstractEntity, SensorEntity):

    def __init__(self, device: TreeowDevice, attribute: TreeowAttribute):
        super().__init__(device, attribute)
        device_class = attribute.options.get('device_class')
        self._is_temp_or_humidity = device_class in (SensorDeviceClass.TEMPERATURE, SensorDeviceClass.HUMIDITY)
        self._is_hcho = '甲醛' in attribute.display_name

    def _update_value(self):
        value = self._attributes_data.get(self._attribute.key)
        if value is None:
            self._attr_native_value = None
            return

        # The scaling below is deliberately value-dependent, not spec-driven: the API
        # returns these either pre-scaled or as raw integers depending on the device,
        # so the magnitude check is what tells the two apart. Do not convert these
        # into an unconditional multiplier.
        if self._is_temp_or_humidity and isinstance(value, (int, float)) and abs(value) > 100:
            value = value / 10

        # HCHO (formaldehyde): API may return an integer (e.g. 35) -> mg/m³ (0.035)
        if self._is_hcho and isinstance(value, (int, float)) and value > 1:
            value = value / 1000

        self._attr_native_value = value
