import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from . import async_register_entity
from .core.attribute import TreeowAttribute
from .core.device import TreeowDevice
from .entity import TreeowAbstractEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    """Optimized select setup with batch processing."""
    await async_register_entity(
        hass,
        entry,
        async_add_entities,
        Platform.SELECT,
        TreeowSelect
    )


class TreeowSelect(TreeowAbstractEntity, SelectEntity):
    """Optimized select entity with cached comparison table."""

    __slots__ = ('_attr_key', '_value_comparison_table', '_reverse_comparison_table')

    def __init__(self, device: TreeowDevice, attribute: TreeowAttribute):
        super().__init__(device, attribute)
        
        # Cache attribute key to avoid repeated property access
        self._attr_key = attribute.key
        
        # Validate and cache comparison table
        if 'value_comparison_table' not in attribute.ext:
            raise ValueError(f'Device [{device.id}] attribute [{attribute.key}] missing value_comparison_table')
            
        self._value_comparison_table = attribute.ext['value_comparison_table']
        
        # Create reverse lookup table for better performance
        self._reverse_comparison_table = {}
        for key, value in self._value_comparison_table.items():
            self._reverse_comparison_table[value] = key

    def _update_value(self):
        """Optimized value update with cached lookup tables."""
        value = self._attributes_data.get(self._attr_key)
        if value is None:
            self._attr_current_option = None
            return
            
        # Use cached lookup for better performance
        if value in self._value_comparison_table:
            self._attr_current_option = self._value_comparison_table[value]
        else:
            _LOGGER.warning(f'Select [{self._attr_unique_id}] value [{value}] not in options list')
            self._attr_current_option = str(value)

    def select_option(self, option: str) -> None:
        """Select an option with optimized reverse lookup."""
        # Use cached reverse lookup for better performance
        if option in self._reverse_comparison_table:
            command_value = self._reverse_comparison_table[option]
        else:
            _LOGGER.warning(f'Select [{self._attr_unique_id}] option [{option}] not in available list')
            command_value = option
            
        self._send_command({self._attr_key: command_value})
