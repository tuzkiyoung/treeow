import logging
from typing import List, Optional

from .attribute import TreeowAttribute, V1SpecAttributeParser

_LOGGER = logging.getLogger(__name__)


class TreeowDevice:

    # `available` and `poll_failures` are the two halves of one state machine and
    # live here, not in a side table on the client, so they are reachable from
    # anything holding the device and are collected along with it. Plain
    # attributes rather than properties: unlike the accessors below they are
    # mutable runtime state, not read-only views over _raw_data.
    __slots__ = ('_client', '_raw_data', '_attributes', '_attribute_snapshot_data',
                 'available', 'poll_failures')

    def __init__(self, client, raw: dict):
        self._client = client
        self._raw_data = raw
        self._attributes = []
        self._attribute_snapshot_data = {}
        self.available = True
        self.poll_failures = 0

    @property
    def id(self):
        return self._raw_data['id']

    @property
    def name(self):
        return self._raw_data.get('deviceName') or self._raw_data.get('id', 'unknown')

    @property
    def device_serial(self):
        return self._raw_data.get('deviceSerial')

    @property
    def category(self):
        return self._raw_data.get('category')

    @property
    def version(self):
        return self._raw_data.get('version')

    @property
    def group_id(self):
        return self._raw_data.get('groupId')

    @property
    def resourceCategory(self):
        props = self._raw_data.get('props')
        if props:
            return props[0].get('resourceCategory')
        return None

    @property
    def localIndex(self):
        props = self._raw_data.get('props')
        if props:
            return props[0].get('localIndex')
        return None

    @property
    def attributes(self) -> List[TreeowAttribute]:
        return self._attributes

    @property
    def attribute_snapshot_data(self) -> dict:
        return self._attribute_snapshot_data

    async def async_init(self, profiles: Optional[dict] = None):
        try:
            snapshot_data, attributes = await self._client.get_device_snapshot_data(self, profiles)

            parser = V1SpecAttributeParser()
            parsed_attributes = []

            for item in attributes:
                try:
                    attr = parser.parse_attribute(item, snapshot_data)
                    if attr:
                        parsed_attributes.append(attr)
                except Exception as e:
                    _LOGGER.warning("Device %s attribute %s parsing failed: %s",
                                   self.id, item.get('identifier', 'unknown'), str(e))

            self._attributes.extend(parsed_attributes)

            try:
                self._attributes.extend(parser.parse_global(attributes, self.category))
            except Exception as e:
                _LOGGER.warning("Device %s global attribute parsing failed: %s", self.id, str(e))

            self._attribute_snapshot_data = snapshot_data

        except Exception as e:
            _LOGGER.error('Device %s initialization failed: %s', self.id, str(e))
            raise

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
