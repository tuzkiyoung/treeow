import json
import logging
from abc import abstractmethod, ABC
from typing import List

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

class TreeowAttribute:

    def __init__(self, key: str, display_name: str, platform: Platform, options: dict = {}, ext: dict = {}):
        self._key = key
        self._display_name = display_name
        self._platform = platform
        self._options = options
        self._ext = ext

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
    def parse_attribute(self, attribute: dict, snapshot_data: dict) -> TreeowAttribute:
        pass

    @abstractmethod
    def parse_global(self, attributes: List[dict]):
        pass

class V1SpecAttributeParser(TreeowAttributeParser, ABC):

    def parse_attribute(self, attribute: dict, snapshot_data: dict) -> TreeowAttribute:
        # 没有的attribute后续无法正常使用，所以需要过滤掉
        if attribute["identifier"] not in snapshot_data :
            return None
        # _LOGGER.debug('attribute: '.format(attribute))
        if attribute["identifier"] in ('wifi_info', 'timestamp'):
            return None

        if attribute['access'] == 'r':
            return self._parse_as_sensor(attribute)

        if attribute['access'] == 'rw' and 'step' in attribute['schema'] and contains_any_ignore_case(attribute['schema']['type'], ['Integer', 'Double']):
            return self._parse_as_number(attribute)

        if attribute['access'] == 'rw' and attribute['schema']['type'] == 'boolean':
            return self._parse_as_switch(attribute)

        if attribute['access'] == 'rw' and attribute['schema']['type'] == 'integer' and isinstance(attribute['schema']['enum'], list):
            return self._parse_as_select(attribute)

        return None

    def parse_global(self, attributes: List[dict]):
        all_attribute_keys = [attribute['identifier'] for attribute in attributes]

        # 空气净化器
        if 'pm25' in all_attribute_keys and 'filter' in all_attribute_keys and 'fan' in all_attribute_keys:
            yield self._parse_as_fan(attributes)

    @staticmethod
    def _parse_as_fan(attribute):
        display_name = json.loads(attribute['title'])['zh']
        # if V1SpecAttributeParser._is_binary_attribute(attribute):
        #     return TreeowAttribute(attribute['identifier'], display_name, Platform.BINARY_SENSOR)

        options = {}
        ext = {}

        return TreeowAttribute(attribute['identifier'], display_name, Platform.SENSOR, options, ext)

    @staticmethod
    def _parse_as_sensor(attribute):
        display_name = json.loads(attribute['title'])['zh']
        # if V1SpecAttributeParser._is_binary_attribute(attribute):
        #     return TreeowAttribute(attribute['identifier'], attribute['desc'], Platform.BINARY_SENSOR)

        options = {}
        ext = {}

        if equals_ignore_case(attribute['schema']['type'], 'integer'):
            state_class, device_class, unit = V1SpecAttributeParser._guess_state_class_device_class_and_unit(attribute)
            if device_class:
                options['device_class'] = device_class

            if state_class:
                options['state_class'] = state_class

            if unit:
                options['native_unit_of_measurement'] = unit

        return TreeowAttribute(attribute['identifier'], display_name, Platform.SENSOR, options, ext)

    @staticmethod
    def _parse_as_number(attribute):
        display_name = json.loads(attribute['title'])['zh']
        step = attribute['schema']
        options = {
            'native_min_value': float(step['minimum']),
            'native_max_value': float(step['maximum']),
            'native_step': step['step']
        }

        _, _, unit = V1SpecAttributeParser._guess_state_class_device_class_and_unit(attribute)
        if unit:
            options['native_unit_of_measurement'] = unit

        return TreeowAttribute(attribute['identifier'], display_name, Platform.NUMBER, options)

    @staticmethod
    def _parse_as_select(attribute):
        display_name = json.loads(attribute['title'])['zh']
        enum = attribute["schema"]["enum"]
        enum_desc = attribute["schema"]["enumDesc"]
        if attribute['identifier'] == 'fan_speed_enum':
            enum.insert(0, 255)
            enum_desc.insert(0, '0gear')
        combined = list(zip(enum, enum_desc))
        combined.extend(list(zip(enum_desc, enum)))
        value_comparison_table = dict(combined)

        ext = {
            'value_comparison_table': value_comparison_table
        }

        options = {
            'options': [item for item in attribute['schema']['enumDesc']]
        }

        return TreeowAttribute(attribute['identifier'], display_name, Platform.SELECT, options, ext)

    @staticmethod
    def _parse_as_switch(attribute):
        display_name = json.loads(attribute['title'])['zh']
        options = {
            'device_class': SwitchDeviceClass.SWITCH
        }

        return TreeowAttribute(attribute['identifier'], display_name, Platform.SWITCH, options)

    # @staticmethod
    # def _is_binary_attribute(attribute):
    #     valueRange = attribute['valueRange']
    #
    #     return (equals_ignore_case(valueRange['type'], 'LIST')
    #             and len(valueRange['dataList']) == 2
    #             and contains_any_ignore_case(valueRange['dataList'][0]['data'], ['true', 'false'])
    #             and contains_any_ignore_case(valueRange['dataList'][1]['data'], ['true', 'false']))

    @staticmethod
    def _guess_state_class_device_class_and_unit(attribute) -> (str, str, str):
        """
        猜测 state class, device class和unit
        :return:
        """
        identifier = attribute['identifier']
        display_name = json.loads(attribute['title'])['zh']
        state_class = None

        if '累计' in display_name:
            state_class = SensorStateClass.TOTAL

        if '天数' in display_name:
            state_class = SensorStateClass.MEASUREMENT
            return state_class, SensorDeviceClass.DURATION, UnitOfTime.DAYS

        if '温度' in display_name:
            return state_class, SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS

        if '湿度' in display_name:
            return state_class, SensorDeviceClass.HUMIDITY, PERCENTAGE

        if '寿命' in display_name:
            return state_class, SensorDeviceClass.BATTERY, PERCENTAGE

        if 'pm25' in identifier:
            state_class = SensorStateClass.MEASUREMENT
            return state_class, SensorDeviceClass.PM25, CONCENTRATION_MICROGRAMS_PER_CUBIC_METER

        if 'aal' in identifier:
            state_class = SensorStateClass.MEASUREMENT
            return state_class, SensorDeviceClass.AQI, None

        return state_class, None, None
