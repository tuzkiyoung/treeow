import logging

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from . import async_register_entity
from .core.attribute import TreeowAttribute
from .core.device import TreeowDevice
from .entity import TreeowAbstractEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    """Optimized number setup with batch processing."""
    await async_register_entity(
        hass,
        entry,
        async_add_entities,
        Platform.NUMBER,
        TreeowNumber
    )


class TreeowNumber(TreeowAbstractEntity, NumberEntity):
    """Optimized number entity with improved value processing."""

    __slots__ = ('_attr_key',)

    def __init__(self, device: TreeowDevice, attribute: TreeowAttribute):
        super().__init__(device, attribute)
        # Cache attribute key to avoid repeated property access
        self._attr_key = attribute.key

    def _update_value(self):
        """Optimized value update with safe type conversion."""
        value = self._attributes_data.get(self._attr_key)
        if value is None:
            self._attr_native_value = None
            return
            
        # Ensure value is numeric
        try:
            self._attr_native_value = float(value) if isinstance(value, (int, float, str)) else value
        except (ValueError, TypeError):
            _LOGGER.warning(f'Number [{self._attr_unique_id}] value type conversion failed: {value}')
            self._attr_native_value = None

    def set_native_value(self, value: float) -> None:
        """Set the native value with optimized command sending."""
        self._send_command({self._attr_key: int(value)})
