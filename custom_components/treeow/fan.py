import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.components.fan import FanEntity

from . import async_register_entity
from .core.attribute import TreeowAttribute
from .core.device import TreeowDevice
from .entity import TreeowAbstractEntity
from .helpers import try_read_as_bool

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    """Optimized fan setup with batch processing."""
    await async_register_entity(
        hass,
        entry,
        async_add_entities,
        Platform.FAN,
        TreeowFan
    )


class TreeowFan(TreeowAbstractEntity, FanEntity):
    """Optimized fan entity with improved error handling."""

    __slots__ = ('_attr_key',)

    def __init__(self, device: TreeowDevice, attribute: TreeowAttribute):
        super().__init__(device, attribute)
        # Cache attribute key to avoid repeated property access
        self._attr_key = attribute.key

    def _update_value(self):
        """Optimized value update with better error handling."""
        value = self._attributes_data.get(self._attr_key)
        if value is None:
            self._attr_is_on = False
            return
            
        try:
            self._attr_is_on = try_read_as_bool(value)
            # Reset availability if previously failed
            if not self._attr_available:
                self._attr_available = True
        except ValueError:
            _LOGGER.warning(f'Fan [{self._attr_unique_id}] failed to read value: {value}')
            self._attr_available = False

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the fan on."""
        self._send_command({self._attr_key: True})

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        self._send_command({self._attr_key: False})

