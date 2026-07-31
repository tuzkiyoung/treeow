from typing import Callable, Coroutine, Any, Optional, Union
import asyncio
import logging

from homeassistant.core import HomeAssistant, CALLBACK_TYPE, Event, callback

from custom_components.treeow import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Cache for wrapped event names
_EVENT_NAME_CACHE = {}


def wrap_event(name: str) -> str:
    if name not in _EVENT_NAME_CACHE:
        _EVENT_NAME_CACHE[name] = f'{DOMAIN}_{name}'
    return _EVENT_NAME_CACHE[name]


def fire_event(hass: HomeAssistant, event: str, data: Optional[dict] = None) -> None:
    if data is None:
        data = {}

    try:
        hass.bus.fire(wrap_event(event), data)
    except Exception as e:
        _LOGGER.error(f'Failed to fire event: {event}, error: {e}')


def listen_event(
        hass: HomeAssistant,
        event: str,
        target: Union[Callable[[Event], Coroutine[Any, Any, None]], Callable[[Event], None]],
        event_filter: Optional[Callable[[dict], bool]] = None
) -> CALLBACK_TYPE:
    """Listen to an event.

    Sync targets are registered as HA callbacks so they run inline on the event
    loop; without this HA classifies them as HassJobType.Executor and pushes
    every single dispatch to the thread pool. Coroutine targets are registered
    as-is so HA schedules them as tasks.

    event_filter runs before the Event object is built and must be a HA
    callback; use it to drop non-matching events as cheaply as possible.
    """
    wrapped_event = wrap_event(event)

    if asyncio.iscoroutinefunction(target):
        async def listener(fired: Event) -> None:
            try:
                await target(fired)
            except Exception as e:
                _LOGGER.error(f'Event callback execution failed: {wrapped_event}, error: {e}')
    else:
        @callback
        def listener(fired: Event) -> None:
            try:
                target(fired)
            except Exception as e:
                _LOGGER.error(f'Event callback execution failed: {wrapped_event}, error: {e}')

    return hass.bus.async_listen(wrapped_event, listener, event_filter)
