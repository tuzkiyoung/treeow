import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from . import async_register_entity
from .entity import TreeowAbstractEntity
from .helpers import try_read_as_bool

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    await async_register_entity(hass, entry, async_add_entities, Platform.SWITCH, TreeowSwitch)


class TreeowSwitch(TreeowAbstractEntity, SwitchEntity):

    def _update_value(self):
        value = self._attributes_data.get(self._attribute.key)
        if value is None:
            self._attr_is_on = False
            return

        try:
            self._attr_is_on = try_read_as_bool(value)
            if not self._attr_available:
                self._attr_available = True
        except ValueError:
            _LOGGER.warning(f'Switch [{self._attr_unique_id}] failed to read value: {value}')
            self._attr_available = False

    def turn_on(self, **kwargs: Any) -> None:
        if self._attr_is_on:
            return
        self._send_command({self._attribute.key: True})

    def turn_off(self, **kwargs: Any) -> None:
        if not self._attr_is_on:
            return
        self._send_command({self._attribute.key: False})
