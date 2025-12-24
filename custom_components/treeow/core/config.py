import logging
import time
from typing import List

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from custom_components.treeow.const import FILTER_TYPE_EXCLUDE, FILTER_TYPE_INCLUDE

_LOGGER = logging.getLogger(__name__)

class AccountConfig:
    """
    账户配置
    """

    def __init__(self, hass: HomeAssistant, config: ConfigEntry):
        self._hass = hass
        self._config = config

        cfg = config.data.get('account', {})
        self.account: str = cfg.get('account', '')
        self.password: str = cfg.get('password', '')
        self.access_token: str = cfg.get('access_token', '')
        self.refresh_token: str = cfg.get('refresh_token', '')
        self.expires_at: int = cfg.get('expires_at', 0)
        self.default_load_all_entity: bool = cfg.get('default_load_all_entity', True)

    def save(self):
        self._hass.config_entries.async_update_entry(
            self._config,
            # title='Treeow: {}'.format(mobile) if mobile else self._config.title,
            data={
                **self._config.data,
                'account': {
                    'account': self.account,
                    'password': self.password,
                    'access_token': self.access_token,
                    'refresh_token': self.refresh_token,
                    'expires_at': self.expires_at,
                    'default_load_all_entity': self.default_load_all_entity
                }
            }
        )


class DeviceFilterConfig:
    """
    设备筛选配置
    """

    def __init__(self, hass: HomeAssistant, config: ConfigEntry):
        self._hass = hass
        self._config = config

        cfg = config.data.get('device_filter', {})
        self._filter_type: str = cfg.get('filter_type', FILTER_TYPE_EXCLUDE)
        self._target_devices: List[str] = cfg.get('target_devices', [])
        # Cache set for O(1) lookup performance
        self._target_devices_set: set = set(self._target_devices)

    def set_filter_type(self, filter_type: str):
        if filter_type not in [FILTER_TYPE_EXCLUDE, FILTER_TYPE_INCLUDE]:
            raise ValueError()

        self._filter_type = filter_type

    @property
    def filter_type(self):
        return self._filter_type

    def set_target_devices(self, devices: List[str]):
        if not isinstance(devices, list):
            raise ValueError()
        self._target_devices = devices
        self._target_devices_set = set(devices)

    @property
    def target_devices(self):
        return self._target_devices

    def add_device(self, device: str):
        if device not in self._target_devices_set:
            self._target_devices.append(device)
            self._target_devices_set.add(device)

    def remove_device(self, device: str):
        if device in self._target_devices_set:
            self._target_devices.remove(device)
            self._target_devices_set.discard(device)

    def is_skip(self, device_id: str) -> bool:
        """Check if a device should be skipped based on filter configuration."""
        # Use set for O(1) lookup
        if self._filter_type == FILTER_TYPE_EXCLUDE:
            return device_id in self._target_devices_set
        else:
            return device_id not in self._target_devices_set

    def save(self):
        self._hass.config_entries.async_update_entry(
            self._config,
            data={
                **self._config.data,
                'device_filter': {
                    'filter_type': self._filter_type,
                    'target_devices': self._target_devices
                }
            }
        )


class EntityFilterConfig:
    """
    实体筛选配置
    """

    def __init__(self, hass: HomeAssistant, config: ConfigEntry):
        self._hass = hass
        self._config = config
        self._account_cfg = AccountConfig(hass, config)
        self._cfg: List[dict] = config.data.get('entity_filter', [])
        # Build index for O(1) lookup
        self._cfg_index: dict = {item['device_id']: item for item in self._cfg}

    def set_filter_type(self, device_id: str, filter_type: str):
        if filter_type not in [FILTER_TYPE_EXCLUDE, FILTER_TYPE_INCLUDE]:
            raise ValueError()

        if device_id in self._cfg_index:
            self._cfg_index[device_id]['filter_type'] = filter_type
        else:
            item = self._generate_entity_filer_item(device_id, filter_type=filter_type)
            self._cfg.append(item)
            self._cfg_index[device_id] = item

    def get_filter_type(self, device_id: str) -> str:
        if device_id in self._cfg_index:
            return self._cfg_index[device_id]['filter_type']
        return FILTER_TYPE_EXCLUDE if self._account_cfg.default_load_all_entity else FILTER_TYPE_INCLUDE

    def set_target_entities(self, device_id: str, entities: List[str]):
        if not isinstance(entities, list):
            raise ValueError()

        if device_id in self._cfg_index:
            self._cfg_index[device_id]['target_entities'] = entities
        else:
            item = self._generate_entity_filer_item(device_id, target_entities=entities)
            self._cfg.append(item)
            self._cfg_index[device_id] = item

    def get_target_entities(self, device_id: str) -> List[str]:
        if device_id in self._cfg_index:
            return self._cfg_index[device_id]['target_entities']
        return []

    def is_skip(self, device_id: str, attr: str) -> bool:
        """Check if an entity should be skipped based on filter configuration."""
        # O(1) lookup using index
        if device_id in self._cfg_index:
            item = self._cfg_index[device_id]
            filter_type = item['filter_type']
            target_entities = item['target_entities']
            if filter_type == FILTER_TYPE_EXCLUDE:
                return attr in target_entities
            else:
                return attr not in target_entities
        
        # Device not in config, use default
        default_filter = FILTER_TYPE_EXCLUDE if self._account_cfg.default_load_all_entity else FILTER_TYPE_INCLUDE
        if default_filter == FILTER_TYPE_EXCLUDE:
            return False  # Empty exclude list means include all
        else:
            return True  # Empty include list means exclude all

    def save(self):
        self._hass.config_entries.async_update_entry(
            self._config,
            data={
                **self._config.data,
                'entity_filter': self._cfg,
                # async_update_entry 内部 entry.data != data 无法识别数组内容修改
                # 所以额外添加更新时间用于修复配置无法保存的问题，没有实际用途
                'entity_filter_updated_at': int(time.time())
            }
        )

    @staticmethod
    def _generate_entity_filer_item(device_id: str, filter_type: str = FILTER_TYPE_INCLUDE, entities: List[str] = None):
        return {
            'device_id': device_id,
            'filter_type': filter_type,
            'target_entities': entities if entities is not None else []
        }
