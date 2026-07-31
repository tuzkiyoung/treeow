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
    await async_register_entity(hass, entry, async_add_entities, Platform.SELECT, TreeowSelect)


class TreeowSelect(TreeowAbstractEntity, SelectEntity):

    def __init__(self, device: TreeowDevice, attribute: TreeowAttribute):
        super().__init__(device, attribute)

        if 'value_comparison_table' not in attribute.ext:
            raise ValueError(f'Device [{device.id}] attribute [{attribute.key}] missing value_comparison_table')

        # Built bidirectionally by V1SpecAttributeParser._parse_as_select: raw <-> display
        self._value_comparison_table = attribute.ext['value_comparison_table']

    def _update_value(self):
        value = self._attributes_data.get(self._attribute.key)
        if value is None:
            self._attr_current_option = None
            return

        if value in self._value_comparison_table:
            self._attr_current_option = self._value_comparison_table[value]
        else:
            _LOGGER.warning(f'Select [{self._attr_unique_id}] value [{value}] not in options list')
            self._attr_current_option = str(value)

    def select_option(self, option: str) -> None:
        if option == self._attr_current_option:
            return

        if option in self._value_comparison_table:
            command_value = self._value_comparison_table[option]
        else:
            _LOGGER.warning(f'Select [{self._attr_unique_id}] option [{option}] not in available list')
            command_value = option

        self._send_command({self._attribute.key: command_value})
