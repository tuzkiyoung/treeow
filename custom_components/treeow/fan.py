from typing import Any, Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from . import async_register_entity
from .core.attribute import TreeowAttribute
from .core.device import TreeowDevice
from .entity import TreeowAbstractEntity
from .helpers import try_read_as_bool

SWITCH_KEY = 'switch'
SPEED_KEY = 'fan_speed_enum'
MODE_KEY = 'mode'


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    await async_register_entity(hass, entry, async_add_entities, Platform.FAN, TreeowFan)


def _enum_spec(attribute: Optional[TreeowAttribute]) -> tuple[list, dict]:
    """Selectable options and the bidirectional value/label table.

    Any option the spec flags as 'off' is dropped from the option list but kept
    in the table: HA's ordered-list percentage helpers require a list of real
    speeds only, while reading state still has to resolve the off value.
    """
    if not attribute:
        return [], {}

    options = attribute.options.get('options', [])
    off_option = attribute.ext.get('off_option')
    if off_option is not None:
        options = [option for option in options if option != off_option]

    return options, attribute.ext.get('value_comparison_table', {})


class TreeowFan(TreeowAbstractEntity, FanEntity):

    def __init__(self, device: TreeowDevice, attribute: TreeowAttribute):
        super().__init__(device, attribute)
        self._attr_name = device.name
        self._attr_key = attribute.key

        # Read straight off the device rather than through the entity filter on
        # purpose: hiding the redundant fan_speed_enum/mode select entities should
        # declutter the UI, not strip this fan of speed and preset control.
        attributes = {attr.key: attr for attr in device.attributes}
        self._has_switch = SWITCH_KEY in attributes
        self._speed_options, self._speed_table = _enum_spec(attributes.get(SPEED_KEY))
        self._mode_options, self._mode_table = _enum_spec(attributes.get(MODE_KEY))
        self._speed_percentages = {
            option: ordered_list_item_to_percentage(self._speed_options, option)
            for option in self._speed_options
        }

        self._attr_supported_features = FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF

        if self._speed_options:
            self._attr_supported_features |= FanEntityFeature.SET_SPEED
            self._attr_speed_count = len(self._speed_options)

        if self._mode_options:
            self._attr_supported_features |= FanEntityFeature.PRESET_MODE
            self._attr_preset_modes = self._mode_options

    @property
    def is_on(self) -> bool:
        value = self._attributes_data.get(SWITCH_KEY if self._has_switch else self._attr_key)
        if value is None:
            return False

        try:
            return try_read_as_bool(value)
        except ValueError:
            return False

    @property
    def percentage(self) -> Optional[int]:
        if not self.is_on or not self._speed_options:
            return 0

        display_value = self._speed_table.get(self._attributes_data.get(SPEED_KEY))
        return self._speed_percentages.get(display_value, 0)

    @property
    def preset_mode(self) -> Optional[str]:
        if not self._mode_options:
            return None

        display_mode = self._mode_table.get(self._attributes_data.get(MODE_KEY))
        return display_mode if display_mode in self._mode_options else None

    def _power_on_command(self) -> dict:
        if self._has_switch and not self.is_on:
            return {SWITCH_KEY: True}
        return {}

    def _speed_command(self, percentage: int) -> dict:
        if not self._speed_options:
            return {}

        option = percentage_to_ordered_list_item(self._speed_options, percentage)
        if option in self._speed_table:
            return {SPEED_KEY: self._speed_table[option]}
        return {}

    def _mode_command(self, preset_mode: str) -> dict:
        if preset_mode in self._mode_table:
            return {MODE_KEY: self._mode_table[preset_mode]}
        return {}

    async def async_turn_on(
        self,
        percentage: Optional[int] = None,
        preset_mode: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        commands = self._power_on_command()

        if percentage is not None:
            commands.update(self._speed_command(percentage))

        if preset_mode is not None:
            commands.update(self._mode_command(preset_mode))

        if commands:
            self._send_command(commands)

    async def async_turn_off(self, **kwargs: Any) -> None:
        if self._has_switch and self.is_on:
            self._send_command({SWITCH_KEY: False})

    async def async_set_percentage(self, percentage: int) -> None:
        if not self._speed_options:
            return

        if percentage == 0:
            await self.async_turn_off()
            return

        commands = self._speed_command(percentage)
        if commands:
            self._send_command({**self._power_on_command(), **commands})

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        commands = self._mode_command(preset_mode)
        if commands:
            self._send_command({**self._power_on_command(), **commands})
