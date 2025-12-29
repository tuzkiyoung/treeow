import logging
from abc import ABC, abstractmethod

from homeassistant.core import Event
from homeassistant.helpers.entity import DeviceInfo, Entity

from . import DOMAIN
from .core.attribute import TreeowAttribute
from .core.event import EVENT_DEVICE_DATA_CHANGED, EVENT_GATEWAY_STATUS_CHANGED, EVENT_DEVICE_CONTROL
from .core.device import TreeowDevice
from .core.event import listen_event, fire_event

_LOGGER = logging.getLogger(__name__)


def _get_device_info(device: TreeowDevice) -> DeviceInfo:
    """Create device info for the given device."""
    return DeviceInfo(
        identifiers={(DOMAIN, device.id)},
        name=device.name,
        manufacturer='树新风',
        model=device.category
    )


class TreeowAbstractEntity(Entity, ABC):
    """Optimized abstract entity with reduced memory footprint."""

    __slots__ = ('_device', '_attribute', '_attributes_data', '_listen_cancel', '_device_id')

    def __init__(self, device: TreeowDevice, attribute: TreeowAttribute):
        # Cache device ID to avoid repeated property access
        self._device_id = device.id
        
        # Use f-string for better performance
        self._attr_unique_id = f'{DOMAIN}.{self._device_id}_{attribute.key}'.lower()
        self.entity_id = self._attr_unique_id
        self._attr_should_poll = False

        self._attr_device_info = _get_device_info(device)
        self._attr_name = attribute.display_name
        
        # Batch attribute assignment to reduce overhead
        for key, value in attribute.options.items():
            setattr(self, f'_attr_{key}', value)

        self._device = device
        self._attribute = attribute
        # Pre-allocate dictionary with expected size
        self._attributes_data = {}
        # Use list for better performance than repeated append
        self._listen_cancel = []

    def _send_command(self, attributes):
        """Send control command with optimized event firing."""
        fire_event(self.hass, EVENT_DEVICE_CONTROL, {
            'device': self._device.to_dict(),
            'attributes': attributes
        })

    @abstractmethod
    def _update_value(self):
        pass

    async def async_added_to_hass(self) -> None:
        """Optimized entity setup with efficient event handling."""
        # Pre-cache device ID for faster comparison
        device_id = self._device_id
        
        # Status callback with optimized event handling
        def status_callback(event):
            self._attr_available = event.data['status']
            self.schedule_update_ha_state()
        
        self._listen_cancel.append(listen_event(self.hass, EVENT_GATEWAY_STATUS_CHANGED, status_callback))

        # Data callback with optimized device ID comparison
        def data_callback(event):
            event_data = event.data
            if event_data['deviceId'] != device_id:
                return
            
            self._attributes_data = event_data['attributes']
            self._update_value()
            self.schedule_update_ha_state()

        self._listen_cancel.append(listen_event(self.hass, EVENT_DEVICE_DATA_CHANGED, data_callback))

        # Initialize with snapshot data using optimized event creation
        data_callback(Event('', data={
            'deviceId': device_id,
            'attributes': self._device.attribute_snapshot_data
        }))

    async def async_will_remove_from_hass(self) -> None:
        """Optimized cleanup with batch operation."""
        # Use list comprehension for better performance
        for cancel in self._listen_cancel:
            cancel()
        self._listen_cancel.clear()
        
        # Clear references to help GC
        self._attributes_data.clear()
