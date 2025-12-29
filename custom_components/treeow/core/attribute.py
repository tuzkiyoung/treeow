import json
import logging
from abc import abstractmethod, ABC
from typing import List, Tuple, Optional
from functools import lru_cache

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.components.switch import SwitchDeviceClass
from homeassistant.const import (
    Platform,
    UnitOfTemperature,
    PERCENTAGE,
    UnitOfTime,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
)

from custom_components.treeow.helpers import equals_ignore_case, contains_any_ignore_case

_LOGGER = logging.getLogger(__name__)

# Constants for optimization
EXCLUDED_ATTRIBUTES = frozenset(('wifi_info', 'timestamp'))
SENSOR_KEYWORDS = {
    '累计': (SensorStateClass.TOTAL, None, None),
    '天数': (SensorStateClass.MEASUREMENT, SensorDeviceClass.DURATION, UnitOfTime.DAYS),
    '小时': (SensorStateClass.MEASUREMENT, SensorDeviceClass.DURATION, UnitOfTime.HOURS),
    '温度': (None, SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS),
    '湿度': (None, SensorDeviceClass.HUMIDITY, PERCENTAGE),
    '寿命': (None, SensorDeviceClass.BATTERY, PERCENTAGE),
    '甲醛': (SensorStateClass.MEASUREMENT, SensorDeviceClass.AQI, None),
    '水位': (SensorStateClass.MEASUREMENT, None, PERCENTAGE),
    '水量': (SensorStateClass.MEASUREMENT, None, PERCENTAGE),
    '液位': (SensorStateClass.MEASUREMENT, None, PERCENTAGE),
}

IDENTIFIER_MAPPINGS = {
    'pm25': (SensorStateClass.MEASUREMENT, SensorDeviceClass.PM25, CONCENTRATION_MICROGRAMS_PER_CUBIC_METER),
    'aal': (SensorStateClass.MEASUREMENT, SensorDeviceClass.AQI, None),
}


class TreeowAttribute:
    """Optimized attribute class with slots for better memory usage."""

    __slots__ = ('_key', '_display_name', '_platform', '_options', '_ext')

    def __init__(self, key: str, display_name: str, platform: Platform, options: Optional[dict] = None, ext: Optional[dict] = None):
        self._key = key
        self._display_name = display_name
        self._platform = platform
        self._options = options or {}
        self._ext = ext or {}

    @property
    def key(self) -> str:
        return self._key

    @property
    def display_name(self) -> str:
        return self._display_name

    @property
    def platform(self) -> Platform:
        return self._platform

    @property
    def options(self) -> dict:
        return self._options

    @property
    def ext(self) -> dict:
        return self._ext


class TreeowAttributeParser(ABC):

    @abstractmethod
    def parse_attribute(self, attribute: dict, snapshot_data: dict) -> Optional[TreeowAttribute]:
        pass

    @abstractmethod
    def parse_global(self, attributes: List[dict]):
        pass


class V1SpecAttributeParser(TreeowAttributeParser):
    """Optimized parser with caching and improved performance."""

    def __init__(self):
        # Cache for parsed display names
        self._display_name_cache = {}

    @lru_cache(maxsize=128)
    def _get_display_name(self, title: str) -> str:
        """Cached display name extraction."""
        try:
            return json.loads(title)['zh']
        except (json.JSONDecodeError, KeyError) as e:
            _LOGGER.warning(f'Failed to parse display name: {title}, error: {e}')
            return title

    def parse_attribute(self, attribute: dict, snapshot_data: dict) -> Optional[TreeowAttribute]:
        """Optimized attribute parsing with early returns."""
        identifier = attribute.get("identifier")
        if not identifier or identifier not in snapshot_data:
            return None

        # Fast exclusion check
        if identifier in EXCLUDED_ATTRIBUTES:
            return None

        access = attribute.get('access')
        schema = attribute.get('schema', {})
        
        # Parse based on access type with optimized branching
        if access == 'r':
            return self._parse_as_sensor(attribute)
        elif access == 'rw':
            return self._parse_readwrite_attribute(attribute, schema)
        
        return None

    def _parse_readwrite_attribute(self, attribute: dict, schema: dict) -> Optional[TreeowAttribute]:
        """Optimized parsing for read-write attributes."""
        schema_type = schema.get('type')
        
        if schema_type == 'boolean':
            return self._parse_as_switch(attribute)
        elif 'step' in schema and contains_any_ignore_case(schema_type, ['Integer', 'Double']):
            return self._parse_as_number(attribute)
        elif schema_type == 'integer' and isinstance(schema.get('enum'), list):
            return self._parse_as_select(attribute)
        
        return None

    def parse_global(self, attributes: List[dict]):
        """Optimized global attribute parsing."""
        # Use set for O(1) lookup, filter out attributes without identifier
        attribute_keys = {attr.get('identifier') for attr in attributes if attr.get('identifier')}
        
        # Check for air purifier pattern
        if {'pm25', 'filter', 'fan'}.issubset(attribute_keys):
            # Find the first matching attribute for the fan
            for attr in attributes:
                if attr['identifier'] == 'fan':
                    yield self._parse_as_fan(attr)
                    break

    def _parse_as_fan(self, attribute: dict) -> TreeowAttribute:
        """Optimized fan parsing."""
        display_name = self._get_display_name(attribute.get('title', ''))
        return TreeowAttribute(attribute['identifier'], display_name, Platform.FAN)

    def _parse_as_sensor(self, attribute: dict) -> TreeowAttribute:
        """Optimized sensor parsing with cached lookups."""
        display_name = self._get_display_name(attribute.get('title', ''))
        options = {}
        ext = {}

        schema = attribute.get('schema', {})
        if equals_ignore_case(schema.get('type'), 'integer'):
            state_class, device_class, unit = self._guess_state_class_device_class_and_unit(attribute)
            
            # Batch option assignment
            if device_class:
                options['device_class'] = device_class
            if state_class:
                options['state_class'] = state_class
            if unit:
                options['native_unit_of_measurement'] = unit

        return TreeowAttribute(attribute['identifier'], display_name, Platform.SENSOR, options, ext)

    def _parse_as_number(self, attribute: dict) -> TreeowAttribute:
        """Optimized number parsing."""
        display_name = self._get_display_name(attribute.get('title', ''))
        schema = attribute.get('schema', {})
        
        options = {
            'native_min_value': float(schema.get('minimum', 0)),
            'native_max_value': float(schema.get('maximum', 100)),
            'native_step': schema.get('step', 1)
        }

        # Add unit if available
        _, _, unit = self._guess_state_class_device_class_and_unit(attribute)
        if unit:
            options['native_unit_of_measurement'] = unit

        return TreeowAttribute(attribute['identifier'], display_name, Platform.NUMBER, options)

    def _parse_as_select(self, attribute: dict) -> TreeowAttribute:
        """Optimized select parsing with better error handling."""
        display_name = self._get_display_name(attribute.get('title', ''))
        schema = attribute.get('schema', {})
        
        enum = schema.get('enum', [])
        enum_desc = schema.get('enumDesc', [])
        
        # Special handling for fan speed
        if attribute['identifier'] == 'fan_speed_enum':
            enum = [255] + enum
            enum_desc = ['0gear'] + enum_desc
        
        # Create bidirectional mapping for better performance
        value_comparison_table = {}
        for i, (val, desc) in enumerate(zip(enum, enum_desc)):
            value_comparison_table[val] = desc
            value_comparison_table[desc] = val

        ext = {'value_comparison_table': value_comparison_table}
        options = {'options': list(enum_desc)}

        return TreeowAttribute(attribute['identifier'], display_name, Platform.SELECT, options, ext)

    def _parse_as_switch(self, attribute: dict) -> TreeowAttribute:
        """Optimized switch parsing."""
        display_name = self._get_display_name(attribute.get('title', ''))
        options = {'device_class': SwitchDeviceClass.SWITCH}
        return TreeowAttribute(attribute['identifier'], display_name, Platform.SWITCH, options)

    def _guess_state_class_device_class_and_unit(self, attribute: dict) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Optimized state class, device class and unit detection."""
        identifier = attribute.get('identifier', '')
        display_name = self._get_display_name(attribute.get('title', ''))
        
        # Check identifier mappings first (faster)
        if identifier in IDENTIFIER_MAPPINGS:
            return IDENTIFIER_MAPPINGS[identifier]
        
        # Check display name keywords
        for keyword, (state_class, device_class, unit) in SENSOR_KEYWORDS.items():
            if keyword in display_name:
                return state_class, device_class, unit
        
        return None, None, None
