import logging

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from . import async_register_entity
from .core.attribute import TreeowAttribute
from .core.device import TreeowDevice
from .entity import TreeowAbstractEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    """Optimized sensor setup with batch processing."""
    await async_register_entity(
        hass,
        entry,
        async_add_entities,
        Platform.SENSOR,
        TreeowSensor
    )


class TreeowSensor(TreeowAbstractEntity, SensorEntity):
    """Optimized sensor entity with improved value processing."""

    __slots__ = ('_comparison_table', '_is_temp_or_humidity')

    def __init__(self, device: TreeowDevice, attribute: TreeowAttribute):
        super().__init__(device, attribute)
        # Cache comparison table to avoid repeated dict access
        self._comparison_table = attribute.ext.get('value_comparison_table', {})
        # Cache whether this sensor is temperature or humidity for optimization
        device_class = attribute.options.get('device_class')
        self._is_temp_or_humidity = device_class in (SensorDeviceClass.TEMPERATURE, SensorDeviceClass.HUMIDITY)

    def _update_value(self):
        """Optimized value update with temperature/humidity value processing."""
        value = self._attributes_data.get(self._attribute.key)
        if value is None:
            self._attr_native_value = None
            return
            
        # Use cached comparison table for better performance
        if self._comparison_table and value in self._comparison_table:
            processed_value = self._comparison_table[value]
        else:
            processed_value = value

        # Handle temperature/humidity values with absolute value greater than 100
        if self._is_temp_or_humidity and isinstance(processed_value, (int, float)):
            if abs(processed_value) > 100:
                processed_value = processed_value / 10
                _LOGGER.debug(f'Sensor [{self._attr_unique_id}] temperature/humidity value {value} adjusted to {processed_value}')
            
        self._attr_native_value = processed_value
