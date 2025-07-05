import logging

from homeassistant.components.sensor import SensorEntity
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

    __slots__ = ('_comparison_table',)

    def __init__(self, device: TreeowDevice, attribute: TreeowAttribute):
        super().__init__(device, attribute)
        # Cache comparison table to avoid repeated dict access
        self._comparison_table = attribute.ext.get('value_comparison_table', {})

    def _update_value(self):
        """Optimized value update with cached comparison table."""
        value = self._attributes_data.get(self._attribute.key)
        if value is None:
            self._attr_native_value = None
            return
            
        # Use cached comparison table for better performance
        if self._comparison_table and value in self._comparison_table:
            self._attr_native_value = self._comparison_table[value]
        else:
            self._attr_native_value = value
