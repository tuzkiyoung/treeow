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
    await async_register_entity(
        hass,
        entry,
        async_add_entities,
        Platform.SENSOR,
        lambda device, attribute: TreeowSensor(device, attribute)
    )


class TreeowSensor(TreeowAbstractEntity, SensorEntity):

    def __init__(self, device: TreeowDevice, attribute: TreeowAttribute):
        super().__init__(device, attribute)

    def _update_value(self):
        comparison_table = self._attribute.ext.get('value_comparison_table', {})

        value = self._attributes_data[self._attribute.key]
        self._attr_native_value = comparison_table[value] if value in comparison_table else value
