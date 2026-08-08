from abc import ABC

from homeassistant.core import Event, callback
from homeassistant.helpers.entity import DeviceInfo, Entity

from . import DOMAIN
from .const import (
    EVENT_DEVICE_CONTROL,
    EVENT_DEVICE_DATA_CHANGED,
    EVENT_DEVICE_STATUS_CHANGED,
    EVENT_GATEWAY_STATUS_CHANGED
)
from .core.attribute import TreeowAttribute
from .core.device import TreeowDevice
from .core.event import listen_event, fire_event


class TreeowAbstractEntity(Entity, ABC):

    def __init__(self, device: TreeowDevice, attribute: TreeowAttribute):
        self._device_id = str(device.id)
        self._attr_unique_id = f'{DOMAIN}_{self._device_id}_{attribute.key}'.lower()
        self.entity_id = f'{attribute.platform}.{self._attr_unique_id}'
        self._attr_name = attribute.display_name
        self._attr_should_poll = False
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=device.name,
            manufacturer='树新风',
            model=device.category
        )

        for key, value in attribute.options.items():
            setattr(self, f'_attr_{key}', value)

        self._device = device
        self._attribute = attribute
        self._attributes_data = {}
        self._listen_cancel = []

        # Availability has three inputs, kept apart so recovering on one axis
        # cannot mask a failure on another. Device reachability is read straight
        # off the device rather than mirrored here -- a copy would go stale
        # whenever something set it without firing the change event.
        self._gateway_available = True   # is the polling loop running at all
        self._value_available = True     # did this attribute's value parse

    @property
    def available(self) -> bool:
        return self._gateway_available and self._device.available and self._value_available

    def _send_command(self, attributes):
        fire_event(self.hass, EVENT_DEVICE_CONTROL, {
            'device': self._device.to_dict(),
            'attributes': attributes
        })

    def _update_value(self):
        """Push device data into _attr_* fields. Property-driven entities need no override."""

    async def async_added_to_hass(self) -> None:
        @callback
        def is_own_device(event_data: dict) -> bool:
            return event_data.get('deviceId') == self._device_id

        def gateway_status_callback(event):
            self._gateway_available = event.data['status']
            self.async_write_ha_state()

        self._listen_cancel.append(
            listen_event(self.hass, EVENT_GATEWAY_STATUS_CHANGED, gateway_status_callback)
        )

        def device_status_callback(event):
            # The new value is already on the device; this only needs to re-render.
            self.async_write_ha_state()

        self._listen_cancel.append(
            listen_event(self.hass, EVENT_DEVICE_STATUS_CHANGED, device_status_callback, is_own_device)
        )

        def data_callback(event):
            self._attributes_data = event.data['attributes']
            self._update_value()
            self.async_write_ha_state()

        self._listen_cancel.append(
            listen_event(self.hass, EVENT_DEVICE_DATA_CHANGED, data_callback, is_own_device)
        )

        # Initialize with snapshot data
        data_callback(Event('', data={
            'deviceId': self._device_id,
            'attributes': self._device.attribute_snapshot_data
        }))

    async def async_will_remove_from_hass(self) -> None:
        for cancel in self._listen_cancel:
            cancel()
        self._listen_cancel.clear()
        # _attributes_data is deliberately left alone: until the first poll it
        # still aliases device.attribute_snapshot_data, which every other entity
        # of this device bootstraps from. Clearing it here would blank them.
