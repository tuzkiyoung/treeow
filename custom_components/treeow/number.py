import logging

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from . import async_register_entity
from .entity import TreeowAbstractEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    await async_register_entity(hass, entry, async_add_entities, Platform.NUMBER, TreeowNumber)


class TreeowNumber(TreeowAbstractEntity, NumberEntity):

    def _update_value(self):
        value = self._attributes_data.get(self._attribute.key)
        if value is None:
            self._attr_native_value = None
            return

        try:
            self._attr_native_value = float(value) if isinstance(value, (int, float, str)) else value
        except (ValueError, TypeError):
            _LOGGER.warning(f'Number [{self._attr_unique_id}] value type conversion failed: {value}')
            self._attr_native_value = None

    def set_native_value(self, value: float) -> None:
        self._send_command({self._attribute.key: int(value)})
