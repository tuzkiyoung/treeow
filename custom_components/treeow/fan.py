import logging
import math
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
    """Enhanced fan entity with speed control and preset modes."""

    __slots__ = (
        '_attr_key',
        '_switch_key',
        '_speed_key',
        '_mode_key',
        '_speed_options',
        '_mode_options',
        '_speed_comparison_table',
        '_speed_reverse_table',
        '_mode_comparison_table',
        '_mode_reverse_table',
    )

    def __init__(self, device: TreeowDevice, attribute: TreeowAttribute):
        super().__init__(device, attribute)
        # Cache attribute key to avoid repeated property access
        self._attr_key = attribute.key
        
        # Find related attributes in the device
        self._switch_key = None
        self._speed_key = None
        self._mode_key = None
        self._speed_options = []
        self._mode_options = []
        self._speed_comparison_table = {}
        self._speed_reverse_table = {}
        self._mode_comparison_table = {}
        self._mode_reverse_table = {}
        
        # Search for switch, fan_speed_enum, and mode attributes
        for attr in device.attributes:
            if attr.key == 'switch':
                self._switch_key = attr.key
            elif attr.key == 'fan_speed_enum':
                self._speed_key = attr.key
                self._speed_options = attr.options.get('options', [])
                if 'value_comparison_table' in attr.ext:
                    self._speed_comparison_table = attr.ext['value_comparison_table']
                    # Create reverse lookup
                    for key, value in self._speed_comparison_table.items():
                        if isinstance(key, int):
                            self._speed_reverse_table[value] = key
            elif attr.key == 'mode':
                self._mode_key = attr.key
                self._mode_options = attr.options.get('options', [])
                if 'value_comparison_table' in attr.ext:
                    self._mode_comparison_table = attr.ext['value_comparison_table']
                    # Create reverse lookup
                    for key, value in self._mode_comparison_table.items():
                        if isinstance(key, int):
                            self._mode_reverse_table[value] = key
        
        # Set up fan features
        self._attr_supported_features = 0
        if self._speed_key and self._speed_options:
            self._attr_supported_features |= FanEntityFeature.SET_SPEED
            self._attr_speed_count = len(self._speed_options)
        if self._mode_key and self._mode_options:
            self._attr_supported_features |= FanEntityFeature.PRESET_MODE
            self._attr_preset_modes = self._mode_options
        
        _LOGGER.debug(
            f'Fan [{self._attr_unique_id}] initialized with switch={self._switch_key}, '
            f'speed={self._speed_key}, mode={self._mode_key}, '
            f'speed_options={self._speed_options}, mode_options={self._mode_options}'
        )

    def _update_value(self):
        """Update fan state from all related attributes."""
        # Update on/off state from switch or fallback to fan attribute
        switch_key = self._switch_key or self._attr_key
        value = self._attributes_data.get(switch_key)
        
        if value is None:
            self._attr_is_on = False
        else:
            try:
                self._attr_is_on = try_read_as_bool(value)
                if not self._attr_available:
                    self._attr_available = True
            except ValueError:
                _LOGGER.warning(f'Fan [{self._attr_unique_id}] failed to read switch value: {value}')
                self._attr_available = False
        
        # Update speed percentage
        if self._speed_key and self._speed_options:
            speed_value = self._attributes_data.get(self._speed_key)
            if speed_value is not None:
                # Convert device value to display name
                display_value = self._speed_comparison_table.get(speed_value)
                if display_value and display_value in self._speed_options:
                    try:
                        # Convert to percentage based on position in ordered list
                        self._attr_percentage = ordered_list_item_to_percentage(
                            self._speed_options, display_value
                        )
                    except ValueError:
                        self._attr_percentage = 0
                        _LOGGER.warning(
                            f'Fan [{self._attr_unique_id}] failed to convert speed: {display_value}'
                        )
                else:
                    self._attr_percentage = 0
            else:
                self._attr_percentage = 0
        
        # Update preset mode
        if self._mode_key and self._mode_options:
            mode_value = self._attributes_data.get(self._mode_key)
            if mode_value is not None:
                display_mode = self._mode_comparison_table.get(mode_value)
                if display_mode in self._mode_options:
                    self._attr_preset_mode = display_mode
                else:
                    self._attr_preset_mode = None
            else:
                self._attr_preset_mode = None

    def turn_on(
        self,
        percentage: Optional[int] = None,
        preset_mode: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        commands = {}
        
        # Turn on switch
        switch_key = self._switch_key or self._attr_key
        if not self._attr_is_on:
            commands[switch_key] = True
        
        # Set speed if provided
        if percentage is not None and self._speed_key and self._speed_options:
            speed_option = percentage_to_ordered_list_item(self._speed_options, percentage)
            if speed_option in self._speed_reverse_table:
                commands[self._speed_key] = self._speed_reverse_table[speed_option]
        
        # Set mode if provided
        if preset_mode is not None and self._mode_key and preset_mode in self._mode_reverse_table:
            commands[self._mode_key] = self._mode_reverse_table[preset_mode]
        
        if commands:
            self._send_command(commands)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn off the fan."""
        if not self._attr_is_on:
            return
        switch_key = self._switch_key or self._attr_key
        self._send_command({switch_key: False})

    def set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        if not self._speed_key or not self._speed_options:
            _LOGGER.warning(f'Fan [{self._attr_unique_id}] does not support speed control')
            return
        
        if percentage == 0:
            self.turn_off()
            return
        
        # Ensure fan is on
        commands = {}
        if not self._attr_is_on:
            switch_key = self._switch_key or self._attr_key
            commands[switch_key] = True
        
        # Convert percentage to speed option
        speed_option = percentage_to_ordered_list_item(self._speed_options, percentage)
        if speed_option in self._speed_reverse_table:
            commands[self._speed_key] = self._speed_reverse_table[speed_option]
            self._send_command(commands)
        else:
            _LOGGER.warning(f'Fan [{self._attr_unique_id}] invalid speed option: {speed_option}')

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
        if not self._mode_key or not self._mode_options:
            _LOGGER.warning(f'Fan [{self._attr_unique_id}] does not support preset modes')
            return
        
        if preset_mode not in self._mode_reverse_table:
            _LOGGER.warning(f'Fan [{self._attr_unique_id}] invalid preset mode: {preset_mode}')
            return
        
        # Ensure fan is on
        commands = {}
        if not self._attr_is_on:
            switch_key = self._switch_key or self._attr_key
            commands[switch_key] = True
        
        commands[self._mode_key] = self._mode_reverse_table[preset_mode]
        self._send_command(commands)

