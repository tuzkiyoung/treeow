import asyncio
import logging
import threading
import time
from typing import Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from .const import DOMAIN, SUPPORTED_PLATFORMS, FILTER_TYPE_EXCLUDE
from .core.client import TreeowClient, TreeowClientException
from .core.config import AccountConfig, DeviceFilterConfig, EntityFilterConfig

_LOGGER = logging.getLogger(__name__)

# Constants for optimization
TOKEN_CHECK_INTERVAL = 3600  # 1 hour
TOKEN_REFRESH_THRESHOLD = 86400  # 1 day
TOKEN_RETRY_DELAY = 30  # seconds (initial retry delay for token operations)
TOKEN_RETRY_MULTIPLIER = 2  # retry delay multiplier
TOKEN_MAX_RETRY_DELAY = 300  # seconds (5 minutes max retry delay)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Optimized setup entry with reduced initialization time."""
    # Initialize domain data with pre-allocated structures
    hass.data.setdefault(DOMAIN, {
        'devices': [],
        'signals': [],
        'client': None
    })

    # Initialize client and token management
    account_cfg = AccountConfig(hass, entry)
    
    # Try to update token first
    await _try_update_token(hass, entry, account_cfg)
    
    # Create client once and reuse
    client = TreeowClient(hass, account_cfg.access_token)
    hass.data[DOMAIN]['client'] = client
    
    try:
        # Get devices
        devices = await client.get_devices()
        _LOGGER.debug(f'Retrieved {len(devices)} devices')
        hass.data[DOMAIN]['devices'] = devices
        
    except Exception as e:
        _LOGGER.error(f'Device initialization failed: {e}')
        hass.data.pop(DOMAIN, None)
        return False

    # Start background tasks with optimized signal handling
    signals = hass.data[DOMAIN]['signals']
    
    # Token updater task
    token_signal = threading.Event()
    signals.append(token_signal)
    hass.async_create_background_task(
        _token_updater(hass, entry, token_signal, account_cfg), 
        'treeow-token-updater'
    )

    # Device listener task
    device_signal = threading.Event()
    signals.append(device_signal)
    hass.async_create_background_task(
        client.listen_devices(devices, device_signal), 
        'treeow-listener'
    )

    # Setup platforms
    await hass.config_entries.async_forward_entry_setups(entry, SUPPORTED_PLATFORMS)

    # Register update listener
    entry.async_on_unload(entry.add_update_listener(_entry_update_listener))

    return True


async def _token_updater(hass: HomeAssistant, entry: ConfigEntry, signal: threading.Event, account_cfg: Optional[AccountConfig] = None):
    """Optimized token updater with exponential backoff retry."""
    token_retry_delay = TOKEN_RETRY_DELAY
    
    while not signal.is_set():
        try:
            if await _try_update_token(hass, entry, account_cfg):
                _LOGGER.info('Token refreshed, reloading integration...')
                await hass.config_entries.async_reload(entry.entry_id)
                break
            
            # Reset retry delay on successful token update
            token_retry_delay = TOKEN_RETRY_DELAY
            
        except Exception as e:
            _LOGGER.error(f'Token update failed: {e}, retrying in {token_retry_delay} seconds')
            
            # Wait with exponential backoff
            await asyncio.sleep(token_retry_delay)
            
            # Exponential backoff: double the delay for next retry
            token_retry_delay = min(token_retry_delay * TOKEN_RETRY_MULTIPLIER, TOKEN_MAX_RETRY_DELAY)
            _LOGGER.debug(f'Token updater next retry delay set to {token_retry_delay} seconds')
            continue
            
        # Wait for next check or signal
        await asyncio.sleep(TOKEN_CHECK_INTERVAL)


async def _try_update_token(hass: HomeAssistant, entry: ConfigEntry, account_cfg: Optional[AccountConfig] = None) -> bool:
    """Optimized token update with better error handling."""
    if account_cfg is None:
        account_cfg = AccountConfig(hass, entry)
    
    client = hass.data[DOMAIN].get('client')
    if client is None:
        client = TreeowClient(hass, account_cfg.access_token)
    
    try:
        # Check token validity
        try:
            await client.verify_token()
        except TreeowClientException:
            # Token invalid, refresh using login
            _LOGGER.info('Token invalid, re-login with username and password')
            token_info = await client.login(account_cfg.account, account_cfg.password)
            account_cfg.access_token = token_info.access_token
            account_cfg.refresh_token = token_info.refresh_token
            account_cfg.expires_at = token_info.expires_at
            account_cfg.save()
            return True

        # Check if token needs refresh (less than 1 day remaining)
        time_until_expiry = account_cfg.expires_at - int(time.time())
        if time_until_expiry > TOKEN_REFRESH_THRESHOLD:
            return False

        # Refresh token proactively
        token_info = await client.refresh_token(account_cfg.refresh_token)
        account_cfg.access_token = token_info.access_token
        account_cfg.refresh_token = token_info.refresh_token
        account_cfg.expires_at = token_info.expires_at
        account_cfg.save()

        return True
        
    except Exception as e:
        _LOGGER.error(f'Token update process failed: {e}')
        raise


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Optimized cleanup with proper resource management."""
    # Unload platforms in parallel for faster cleanup
    unload_results = await asyncio.gather(
        *[hass.config_entries.async_forward_entry_unload(entry, platform) for platform in SUPPORTED_PLATFORMS],
        return_exceptions=True
    )
    unload_ok = all(result is True for result in unload_results)

    if unload_ok:
        # Signal all background tasks to stop
        signals = hass.data[DOMAIN].get('signals', [])
        for signal in signals:
            signal.set()

        # Clean up domain data
        hass.data.pop(DOMAIN, None)

    return unload_ok


async def _entry_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Optimized update listener."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_remove_config_entry_device(hass: HomeAssistant, config: ConfigEntry, device: DeviceEntry) -> bool:
    """Optimized device removal with better error handling."""
    device_identifiers = list(device.identifiers)
    if not device_identifiers:
        _LOGGER.error('Device identifier is empty')
        return False
        
    device_id = device_identifiers[0][1]

    # Find target device efficiently
    devices = hass.data[DOMAIN].get('devices', [])
    target_device = None
    
    for dev in devices:
        _LOGGER.debug(f'Comparing device: cloud_id={dev.id}, target_id={device_id}')
        if str(dev.id) == str(device_id):
            target_device = dev
            break
    
    if target_device is None:
        _LOGGER.warning(f'Device [{device_id}] not found in app, allowing removal from Home Assistant')
        return True

    # Update device filter configuration
    try:
        cfg = DeviceFilterConfig(hass, config)
        if cfg.filter_type == FILTER_TYPE_EXCLUDE:
            cfg.add_device(target_device.id)
        else:
            cfg.remove_device(target_device.id)
        cfg.save()
        
        return True
        
    except Exception as e:
        _LOGGER.error(f'Failed to remove device [{device_id}]: {e}')
        return False


async def async_register_entity(hass: HomeAssistant, entry: ConfigEntry, async_add_entities, platform, setup) -> None:
    """Optimized entity registration with batch processing."""
    devices = hass.data[DOMAIN].get('devices', [])
    if not devices:
        _LOGGER.warning('No devices available')
        return

    # Pre-allocate entities list
    entities = []
    device_filter_config = DeviceFilterConfig(hass, entry)
    entity_filter_config = EntityFilterConfig(hass, entry)
    
    for device in devices:
        # Skip filtered devices
        if device_filter_config.is_skip(device.id):
            continue

        # Process device attributes
        for attribute in device.attributes:
            if attribute.platform != platform:
                continue

            # Skip filtered entities
            if entity_filter_config.is_skip(device.id, attribute.key):
                continue

            try:
                entity = setup(device, attribute)
                entities.append(entity)
            except Exception as e:
                _LOGGER.warning(f'Failed to create entity - device: {device.id}, attribute: {attribute.key}, error: {e}')

    # Batch add entities
    if entities:
        async_add_entities(entities)
