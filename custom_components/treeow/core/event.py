from typing import Callable, Coroutine, Any, Optional, Union
import asyncio
import logging

from homeassistant.core import HomeAssistant, CALLBACK_TYPE, Event
from homeassistant.util.async_ import run_callback_threadsafe

from custom_components.treeow import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Event constants for better performance
EVENT_DEVICE_CONTROL = 'device_control'
EVENT_DEVICE_DATA_CHANGED = 'device_data_changed'
EVENT_GATEWAY_STATUS_CHANGED = 'gateway_status_changed'

# Cache for wrapped event names
_EVENT_NAME_CACHE = {}


def wrap_event(name: str) -> str:
    """Cached event name wrapping for better performance."""
    if name not in _EVENT_NAME_CACHE:
        _EVENT_NAME_CACHE[name] = f'{DOMAIN}_{name}'
    return _EVENT_NAME_CACHE[name]


def fire_event(hass: HomeAssistant, event: str, data: Optional[dict] = None) -> None:
    """Fire an event with optional data and better error handling."""
    if data is None:
        data = {}
    
    try:
        hass.bus.fire(wrap_event(event), data)
    except Exception as e:
        _LOGGER.error(f'Failed to fire event: {event}, error: {e}')


def listen_event(
        hass: HomeAssistant,
        event: str,
        callback: Union[Callable[[Event], Coroutine[Any, Any, None]], Callable[[Event], None]]
) -> CALLBACK_TYPE:
    """Listen to an event with proper async callback handling and thread safety."""
    wrapped_event = wrap_event(event)
    
    def thread_safe_callback_wrapper(event: Event) -> None:
        """Thread-safe wrapper for callbacks."""
        try:
            result = callback(event)
            # If callback returns a coroutine, handle it safely
            if asyncio.iscoroutine(result):
                # Use run_callback_threadsafe to ensure thread safety
                def schedule_coroutine():
                    """Schedule the coroutine in the event loop thread."""
                    hass.async_create_task(
                        _handle_async_callback(result, wrapped_event),
                        f"treeow-event-{wrapped_event}"
                    )
                
                # Ensure we're running in the event loop thread
                if hass.loop.is_running():
                    try:
                        run_callback_threadsafe(hass.loop, schedule_coroutine)
                    except Exception as e:
                        _LOGGER.error(f'Failed to schedule async callback: {wrapped_event}, error: {e}')
                        # Fallback: try to close the coroutine to avoid warnings
                        try:
                            result.close()
                        except Exception:
                            pass
                else:
                    _LOGGER.warning(f'Event loop not running, cannot handle async callback: {wrapped_event}')
                    try:
                        result.close()
                    except Exception:
                        pass
        except Exception as e:
            _LOGGER.error(f'Event callback execution failed: {wrapped_event}, error: {e}')
    
    return hass.bus.async_listen(wrapped_event, thread_safe_callback_wrapper)


async def _handle_async_callback(coro: Coroutine[Any, Any, None], event_name: str) -> None:
    """Handle async callback execution with error handling."""
    try:
        await coro
    except Exception as e:
        _LOGGER.error(f'Async event callback execution failed: {event_name}, error: {e}')
