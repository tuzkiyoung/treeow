import json
import logging
from typing import List

from .attribute import TreeowAttribute, V1SpecAttributeParser

_LOGGER = logging.getLogger(__name__)


class TreeowDevice:
    _raw_data: dict
    _attributes: List[TreeowAttribute]
    _attribute_snapshot_data: dict

    def __init__(self, client, raw: dict):
        self._client = client
        self._raw_data = raw
        self._attributes = []
        self._attribute_snapshot_data = {}

    @property
    def id(self):
        return self._raw_data['id']

    @property
    def name(self):
        return self._raw_data['deviceName'] if 'deviceName' in self._raw_data else self.id

    @property
    def device_serial(self):
        return self._raw_data['deviceSerial'] if 'deviceSerial' in self._raw_data else None

    @property
    def category(self):
        return self._raw_data['category'] if 'category' in self._raw_data else None

    @property
    def version(self):
        return self._raw_data['version'] if 'version' in self._raw_data else None

    @property
    def group_id(self):
        return self._raw_data['groupId'] if 'groupId' in self._raw_data else None

    @property
    def resourceCategory(self):
        return self._raw_data['props'][0]['resourceCategory'] if 'resourceCategory' in self._raw_data['props'][0] else None
    
    @property
    def localIndex(self):
        return self._raw_data['props'][0]['localIndex'] if 'localIndex' in self._raw_data['props'][0] else None

    @property
    def attributes(self) -> List[TreeowAttribute]:
        return self._attributes

    @property
    def attribute_snapshot_data(self) -> dict:
        return self._attribute_snapshot_data

    async def async_init(self):
        # 解析Attribute
        # noinspection PyBroadException
        try:
            snapshot_data = await self._client.get_device_snapshot_data(self)
            _LOGGER.debug(
                'device %s snapshot data fetch successful. data: %s',
                self.id,
                json.dumps(snapshot_data)
            )

            parser = V1SpecAttributeParser()
            attributes = await self._client.get_digital_model_from_cache(self)
            for item in attributes:
                try:
                    attr = parser.parse_attribute(item, snapshot_data)
                    if attr:
                        self._attributes.append(attr)
                except:
                    _LOGGER.exception("Treeow device %s attribute %s parsing error occurred", self.id, item['identifier'])

            iter = parser.parse_global(attributes)
            if iter:
                for item in iter:
                    self._attributes.append(item)

            _LOGGER.debug(
                'device %s snapshot data fetch successful. data: %s',
                self.id,
                json.dumps(snapshot_data)
            )
            self._attribute_snapshot_data = snapshot_data
        except Exception:
            _LOGGER.exception('Treeow device %s init failed', self.id)

    def __str__(self) -> str:
        return json.dumps({
            'id': self.id,
            'name': self.name,
            'device_serial': self.device_serial,
            'version': self.version,
            'category': self.category,
            'group_id': self.group_id,
            'resourceCategory': self.resourceCategory,
            'localIndex': self.localIndex
        })

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "device_serial": self.device_serial,
            "version": self.version,
            "category": self.category,
            "group_id": self.group_id,
            "resourceCategory": self.resourceCategory,
            "localIndex": self.localIndex
        }