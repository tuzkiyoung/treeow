import json
import logging
from typing import List

from .attribute import TreeowAttribute, V1SpecAttributeParser

_LOGGER = logging.getLogger(__name__)


class TreeowDevice:
    """Optimized TreeowDevice with manual caching for better __slots__ compatibility."""
    
    __slots__ = ('_client', '_raw_data', '_attributes', '_attribute_snapshot_data', 
                 '_device_dict_cache', '_cached_id', '_cached_name', '_cached_device_serial',
                 '_cached_category', '_cached_version', '_cached_group_id', 
                 '_cached_resource_category', '_cached_local_index')

    def __init__(self, client, raw: dict):
        self._client = client
        self._raw_data = raw
        self._attributes = []
        self._attribute_snapshot_data = {}
        self._device_dict_cache = None
        
        # Initialize cache attributes
        self._cached_id = None
        self._cached_name = None
        self._cached_device_serial = None
        self._cached_category = None
        self._cached_version = None
        self._cached_group_id = None
        self._cached_resource_category = None
        self._cached_local_index = None

    @property
    def id(self):
        """Cached device ID to avoid repeated dictionary access."""
        if self._cached_id is None:
            self._cached_id = self._raw_data['id']
        return self._cached_id

    @property
    def name(self):
        """Cached device name with optimized fallback."""
        if self._cached_name is None:
            device_name = self._raw_data.get('deviceName')
            if device_name:
                self._cached_name = device_name
            else:
                # Fallback to ID without causing circular dependency
                self._cached_name = self._raw_data.get('id', 'unknown')
        return self._cached_name

    @property
    def device_serial(self):
        """Cached device serial number."""
        if self._cached_device_serial is None:
            self._cached_device_serial = self._raw_data.get('deviceSerial')
        return self._cached_device_serial

    @property
    def category(self):
        """Cached device category."""
        if self._cached_category is None:
            self._cached_category = self._raw_data.get('category')
        return self._cached_category

    @property
    def version(self):
        """Cached device version."""
        if self._cached_version is None:
            self._cached_version = self._raw_data.get('version')
        return self._cached_version

    @property
    def group_id(self):
        """Cached group ID."""
        if self._cached_group_id is None:
            self._cached_group_id = self._raw_data.get('groupId')
        return self._cached_group_id

    @property
    def resourceCategory(self):
        """Cached resource category with safe property access."""
        if self._cached_resource_category is None:
            props = self._raw_data.get('props')
            if props and len(props) > 0:
                self._cached_resource_category = props[0].get('resourceCategory')
        return self._cached_resource_category
    
    @property
    def localIndex(self):
        """Cached local index with safe property access."""
        if self._cached_local_index is None:
            props = self._raw_data.get('props')
            if props and len(props) > 0:
                self._cached_local_index = props[0].get('localIndex')
        return self._cached_local_index

    @property
    def attributes(self) -> List[TreeowAttribute]:
        """Direct access to attributes list."""
        return self._attributes

    @property
    def attribute_snapshot_data(self) -> dict:
        """Direct access to snapshot data."""
        return self._attribute_snapshot_data

    async def async_init(self):
        """Optimized initialization with better error handling."""
        try:
            # Get snapshot data
            snapshot_data = await self._client.get_device_snapshot_data(self)

            # Initialize parser once
            parser = V1SpecAttributeParser()
            attributes = await self._client.get_digital_model_from_cache(self)
            
            # Pre-allocate list with expected size
            parsed_attributes = []
            
            # Process attributes with optimized error handling
            for item in attributes:
                try:
                    attr = parser.parse_attribute(item, snapshot_data)
                    if attr:
                        parsed_attributes.append(attr)
                except Exception as e:
                    _LOGGER.warning("Device %s attribute %s parsing failed: %s", 
                                   self.id, item.get('identifier', 'unknown'), str(e))

            # Add parsed attributes in batch
            self._attributes.extend(parsed_attributes)

            # Process global attributes
            try:
                global_attrs = parser.parse_global(attributes)
                if global_attrs:
                    self._attributes.extend(global_attrs)
            except Exception as e:
                _LOGGER.warning("Device %s global attribute parsing failed: %s", self.id, str(e))

            # Store snapshot data
            self._attribute_snapshot_data = snapshot_data
            
        except Exception as e:
            _LOGGER.error('Device %s initialization failed: %s', self.id, str(e))
            raise

    def __str__(self) -> str:
        """Optimized string representation using cached dict."""
        return json.dumps(self.to_dict())

    def to_dict(self) -> dict:
        """Cached dictionary representation for better performance."""
        if self._device_dict_cache is None:
            self._device_dict_cache = {
                "id": self.id,
                "name": self.name,
                "device_serial": self.device_serial,
                "version": self.version,
                "category": self.category,
                "group_id": self.group_id,
                "resourceCategory": self.resourceCategory,
                "localIndex": self.localIndex
            }
        return self._device_dict_cache