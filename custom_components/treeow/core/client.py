import asyncio
import hashlib
import json
import logging
import threading
import time
import uuid
from typing import List, Dict, Any
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from .device import TreeowDevice
from .event import listen_event, fire_event
from custom_components.treeow import const
from custom_components.treeow.const import (
    EVENT_DEVICE_CONTROL,
    EVENT_DEVICE_DATA_CHANGED,
    EVENT_GATEWAY_STATUS_CHANGED,
    DEFAULT_APP_VERSION,
    DEFAULT_IOS_VERSION
)

_LOGGER = logging.getLogger(__name__)


async def initialize_versions(hass: HomeAssistant) -> tuple[str, str]:
    app_version = DEFAULT_APP_VERSION
    ios_version = DEFAULT_IOS_VERSION

    session = async_get_clientsession(hass)
    async def get_app_version():
        nonlocal app_version
        try:
            async with session.get(url=const.GET_APP_VERSION_API) as response:
                content = await response.json(content_type=None)
                results = content.get('results', [])
                if results and results[0].get('trackName') == 'Treeow Home':
                    version = results[0].get('version')
                    if version and version.replace('.', '').isdigit():
                        app_version = version
                    else:
                        _LOGGER.warning(f'Invalid app version format: {version}, using default')
        except Exception as e:
            _LOGGER.warning(f'Failed to get app version: {e}')
    
    async def get_ios_version():
        nonlocal ios_version
        try:
            async with session.get(url=const.GET_IOS_VERSION_API) as response:
                content = await response.json(content_type=None)
                if content:
                    result = content.get('result', {})
                    latest = result.get('latest', {})
                    version = latest.get('name')
                    if version:
                        if version.replace('.', '').isdigit():
                            ios_version = version
                        else:
                            _LOGGER.warning(f'Invalid iOS version format: {version}, using default')
        except Exception as e:
            _LOGGER.warning(f'Failed to get iOS version: {e}')
    
    try:
        # Get versions concurrently with timeout
        await asyncio.wait_for(
            asyncio.gather(get_app_version(), get_ios_version()),
            timeout=10.0
        )
    except asyncio.TimeoutError:
        _LOGGER.warning('Version initialization timed out after 10 seconds, using defaults')
    except Exception as e:
        _LOGGER.warning(f'Failed to initialize versions: {e}, using defaults')
    _LOGGER.debug(f'Initialized versions: app_version={app_version}, ios_version={ios_version}')
    return app_version, ios_version


class TokenInfo:
    """Optimized token info with slots for better memory usage."""
    
    __slots__ = ('_access_token', '_refresh_token', '_expires_at')

    def __init__(self, access_token: str, refresh_token: str, expires_at: int):
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._expires_at = expires_at

    @property
    def access_token(self) -> str:
        return self._access_token

    @property
    def refresh_token(self) -> str:
        return self._refresh_token

    @property
    def expires_at(self) -> int:
        return self._expires_at


class TreeowClientException(Exception):
    """Custom exception for TreeowClient operations."""
    pass


class TreeowClient:
    """Optimized TreeowClient with improved performance and error handling."""

    __slots__ = ('_access_token', '_app_version', '_ios_version', '_hass', '_session', '_header_cache')

    def __init__(self, hass: HomeAssistant, access_token: str, app_version: str = DEFAULT_APP_VERSION, ios_version: str = DEFAULT_IOS_VERSION):
        self._access_token = access_token
        self._app_version = app_version
        self._ios_version = ios_version
        self._hass = hass
        self._session = async_get_clientsession(hass)
        self._header_cache = None

    @property
    def hass(self) -> HomeAssistant:
        return self._hass

    async def login(self, account: str, password: str) -> TokenInfo:
        """Optimized login with better error handling."""
        try:
            headers = (await self._generate_common_headers()).copy()
            headers.pop("authorization", None)  # Safe removal
            
            terminal_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, account)).upper()
            password_hash = hashlib.md5(password.encode()).hexdigest()
            
            payload = {
                "terminalIdentifier": terminal_id,
                "account": account,
                "password": password_hash,
                "terminalName": "iPhone"
            }
            
            async with self._session.post(url=const.LOGIN_API, headers=headers, json=payload) as response:
                content = await response.json(content_type=None)
                self._assert_response_successful(content)

                data = content.get('data', {})
                return TokenInfo(
                    data.get('accessToken', ''),
                    data.get('refreshToken', ''),
                    int(time.time()) + int(data.get('expiresIn', 0))
                )
        except TreeowClientException as e:
            _LOGGER.error(f'Login failed: {e}')
            raise
        except Exception as e:
            _LOGGER.error(f'Login failed: {e}')
            raise TreeowClientException(f'Login failed: {e}')

    async def refresh_token(self, refresh_token: str) -> TokenInfo:
        """Optimized token refresh."""
        try:
            payload = {'refreshToken': refresh_token}
            headers = await self._generate_common_headers()
            
            async with self._session.post(url=const.REFRESH_TOKEN_API, headers=headers, json=payload) as response:
                content = await response.json(content_type=None)
                self._assert_response_successful(content)

                data = content.get('data', {})
                return TokenInfo(
                    data.get('accessToken', ''),
                    data.get('refreshToken', ''),
                    int(time.time()) + int(data.get('expiresIn', 0))
                )
        except TreeowClientException as e:
            _LOGGER.error(f'Token refresh failed: {e}')
            raise
        except Exception as e:
            _LOGGER.error(f'Token refresh failed: {e}')
            raise TreeowClientException(f'Token refresh failed: {e}')

    async def verify_token(self) -> None:
        """Optimized token verification."""
        try:
            headers = await self._generate_common_headers()
            async with self._session.post(url=const.VERIFY_TOKEN_API, headers=headers, json={}) as response:
                content = await response.json(content_type=None)
                self._assert_response_successful(content)
        except TreeowClientException as e:
            _LOGGER.warning(f'Token verification failed: {e}')
            raise
        except Exception as e:
            _LOGGER.warning(f'Token verification failed: {e}')
            raise TreeowClientException(f'Token verification failed: {e}')

    async def get_devices(self) -> List[TreeowDevice]:
        """Optimized device retrieval with parallel processing."""
        try:
            group_ids = await self.get_groups()
            if not group_ids:
                _LOGGER.warning('No device groups found')
                return []

            headers = await self._generate_common_headers()
            devices = []
            
            # Process groups in parallel for better performance
            tasks = []
            for group_id in group_ids:
                task = self._get_devices_for_group(group_id, headers)
                tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, list):
                    devices.extend(result)
                elif isinstance(result, Exception):
                    _LOGGER.error(f'Failed to get device group: {result}')

            return devices
            
        except TreeowClientException as e:
            _LOGGER.error(f'Failed to get device list: {e}')
            raise
        except Exception as e:
            _LOGGER.error(f'Failed to get device list: {e}')
            raise TreeowClientException(f'Failed to get device list: {e}')

    async def _get_devices_for_group(self, group_id: str, headers: Dict[str, str]) -> List[TreeowDevice]:
        """Helper method to get devices for a specific group."""
        payload = {
            "pageSize": str(const.DEFAULT_PAGE_SIZE),
            "groupId": group_id,
            "pageNo": "1"
        }
        
        async with self._session.post(url=const.LIST_DEVICES_API, headers=headers, json=payload) as response:
            content = await response.json(content_type=None)
            self._assert_response_successful(content)
            
            devices = []
            if content.get('data'):
                for raw_device in content['data']:
                    raw_device['groupId'] = group_id
                    device = TreeowDevice(self, raw_device)
                    await device.async_init()
                    devices.append(device)
            
            return devices

    async def get_groups(self) -> List[str]:
        """Get device groups from API."""
        try:
            headers = await self._generate_common_headers()
            async with self._session.post(url=const.LIST_HOME_API, headers=headers) as response:
                content = await response.json(content_type=None)
                self._assert_response_successful(content)
                
                group_ids = []
                for home in content.get('data', []):
                    for group in home.get('homeGroups', []):
                        group_ids.append(group['id'])
                
                return group_ids
                
        except TreeowClientException as e:
            _LOGGER.error(f'Failed to get device groups: {e}')
            raise
        except Exception as e:
            _LOGGER.error(f'Failed to get device groups: {e}')
            raise TreeowClientException(f'Failed to get device groups: {e}')

    async def get_digital_model(self, device: TreeowDevice) -> List[Dict[str, Any]]:
        """Optimized digital model retrieval."""
        try:
            device_serial = device.device_serial
            if not device_serial or ':' not in device_serial:
                _LOGGER.warning(f'Device {device.id} invalid serial number: {device_serial}')
                return []
                
            product_id = device_serial.split(':')[0]
            pv = f"PV(productId={product_id}, version={device.version})"
            
            payload = {
                "pageSize": str(const.DEFAULT_PAGE_SIZE),
                "groupId": device.group_id,
                "pageNo": "1"
            }
            
            headers = await self._generate_common_headers()
            async with self._session.post(url=const.LIST_DEVICES_API, json=payload, headers=headers) as response:
                content = await response.json(content_type=None)
                self._assert_response_successful(content)
                
                profiles = content.get('profiles', {})
                if pv in profiles:
                    resources = profiles[pv].get('resources', [])
                    attributes = []
                    
                    for resource in resources:
                        for domain in resource.get('domains', []):
                            if domain.get('identifier') == device.category:
                                attributes.extend(domain.get('props', []))
                    
                    return attributes
                
                return []
                
        except TreeowClientException as e:
            _LOGGER.error(f'Failed to get digital model for device {device.id}: {e}')
            raise
        except Exception as e:
            _LOGGER.error(f'Failed to get digital model for device {device.id}: {e}')
            raise TreeowClientException(f'Failed to get digital model for device {device.id}: {e}')

    async def get_digital_model_from_cache(self, device: TreeowDevice) -> List[Dict[str, Any]]:
        """从缓存获取数字模型，若不存在或版本不匹配则从 API 获取并缓存"""
        store = Store(
            self._hass, 
            const.STORAGE_VERSION, 
            f'{const.STORAGE_KEY}/{device.category}_{device.id}.json'.lower()
        )
        
        cache = None
        try:
            cache = await store.async_load()
            if isinstance(cache, str):
                raise RuntimeError('Cache is invalid')
        except Exception as e:
            _LOGGER.warning(f'Device {device.id} cache is invalid: {e}')
            await store.async_remove()
            cache = None
        
        # 检查缓存是否存在且版本匹配
        if cache and cache.get('version') == device.version:
            _LOGGER.debug(f'Device {device.id} get digital model from cache (version {device.version})')
            return cache['attributes']
        
        # 从 API 获取
        _LOGGER.info(f'Device {device.id} fetching digital model from API (version {device.version})')
        attributes = await self.get_digital_model(device)
        
        # 保存到缓存
        await store.async_save({
            'device': {
                'id': device.id,
                'name': device.name,
                'category': device.category
            },
            'version': device.version,
            'attributes': attributes
        })
        
        return attributes


    async def get_device_snapshot_data(self, device: TreeowDevice) -> Dict[str, Any]:
        """Optimized snapshot data retrieval."""
        try:
            payload = {"id": device.id}
            headers = await self._generate_common_headers()
            
            async with self._session.post(url=const.DESCRIBE_DEVICES_API, json=payload, headers=headers) as response:
                content = await response.json(content_type=None)
                self._assert_response_successful(content)
                
                data = content.get('data')
                if not data:
                    return {}
                
                # Parse device data
                props = data.get('props', [])
                if not props:
                    return {}
                
                value_data = json.loads(props[0]['value']).get(device.category, {})
                
                # Get attributes and build snapshot
                attributes = await self.get_digital_model_from_cache(device)
                values = {}
                
                for attribute in attributes:
                    identifier = attribute.get('identifier')
                    if identifier and identifier in value_data:
                        values[identifier] = value_data[identifier]
                
                return values
                
        except TreeowClientException as e:
            _LOGGER.error(f'Failed to get snapshot data for device {device.id}: {e}')
            raise
        except Exception as e:
            _LOGGER.error(f'Failed to get snapshot data for device {device.id}: {e}')
            raise TreeowClientException(f'Failed to get snapshot data for device {device.id}: {e}')

    async def listen_devices(self, target_devices: List[TreeowDevice], signal: threading.Event, poll_interval: int = const.DEFAULT_POLL_INTERVAL) -> None:
        """Optimized device listening with better resource management and exponential backoff retry."""
        process_id = str(uuid.uuid4())
        self._hass.data['current_listen_devices_process_id'] = process_id
        
        cancel_control_listen = None
        heartbeat_tasks = []
        retry_delay = const.RETRY_DELAY  # Initial retry delay
        
        # Create device ID to TreeowDevice mapping for quick lookup during control
        device_map = {str(device.id): device for device in target_devices}
        
        try:
            # Start heartbeat tasks
            for device in target_devices:
                heartbeat_signal = threading.Event()
                task = self._hass.async_create_background_task(
                    self._send_heartbeat(device, heartbeat_signal),
                    f'treeow-heartbeat-{device.id}'
                )
                heartbeat_tasks.append((task, heartbeat_signal))

            # Set up control event listener
            async def control_callback(event):
                """Handle device control events asynchronously with immediate state polling."""
                device_dict = event.data['device']
                device_id = str(device_dict.get('id'))
                
                try:
                    await self._send_command(device_dict, event.data['attributes'])
                    _LOGGER.debug(f'Command sent successfully for device {device_id}')
                        
                except Exception as e:
                    _LOGGER.error(f'Failed to send command for device {device_id}: {e}')

                try:
                    if device_id in device_map:
                        headers = await self._generate_common_headers()
                        await self._poll_device(device_map[device_id], headers)
                        _LOGGER.debug(f'Immediately polled device {device_id} after control command')
                        
                except Exception as e:
                    _LOGGER.error(f'Failed to poll device {device_id} after control: {e}')

            cancel_control_listen = listen_event(self._hass, EVENT_DEVICE_CONTROL, control_callback)
            
            # Signal gateway is online
            fire_event(self._hass, EVENT_GATEWAY_STATUS_CHANGED, {'status': True})

            # Generate headers once before loop (token refresh will reload integration)
            headers = await self._generate_common_headers()

            # Main listening loop
            while not signal.is_set():
                try:
                    # Poll devices concurrently for better performance
                    tasks = []
                    for device in target_devices:
                        task = self._poll_device(device, headers)
                        tasks.append(task)
                    
                    await asyncio.gather(*tasks, return_exceptions=True)
                    _LOGGER.debug(f'Polled {len(target_devices)} devices, next poll in {poll_interval}s')
                    await asyncio.sleep(poll_interval)
                    
                    # Reset retry delay on successful operation
                    retry_delay = const.RETRY_DELAY

                except Exception as e:
                    _LOGGER.error(f'Device listening error: {e}, retrying in {retry_delay} seconds')
                    await asyncio.sleep(retry_delay)
                    
                    # Exponential backoff: double the delay for next retry
                    retry_delay = min(retry_delay * const.RETRY_MULTIPLIER, const.MAX_RETRY_DELAY)
                    _LOGGER.debug(f'Next retry delay set to {retry_delay} seconds')

        finally:
            # Cleanup
            if cancel_control_listen:
                cancel_control_listen()
                
            # Stop heartbeat tasks
            for task, heartbeat_signal in heartbeat_tasks:
                heartbeat_signal.set()
                try:
                    task.cancel()
                    await task
                except asyncio.CancelledError:
                    pass
                    
            # Signal gateway is offline
            current_process = self._hass.data.get('current_listen_devices_process_id')
            if process_id == current_process:
                fire_event(self._hass, EVENT_GATEWAY_STATUS_CHANGED, {'status': False})

    async def _poll_device(self, device: TreeowDevice, headers: Dict[str, str]) -> None:
        """Helper method to poll a single device."""
        try:
            payload = {"id": device.id}
            async with self._session.post(url=const.DESCRIBE_DEVICES_API, json=payload, headers=headers) as response:
                content = await response.json(content_type=None)
                self._assert_response_successful(content)
                
                if content.get('data'):
                    await self._parse_message(device, content['data'])
                    
        except Exception as e:
            _LOGGER.error(f'Failed to poll device {device.id}: {e}')

    async def _send_heartbeat(self, device: TreeowDevice, event: threading.Event) -> None:
        """Optimized heartbeat sending with fast retry on failure."""
        heartbeat_retry_delay = 1  # Start with 1 second for fast heartbeat recovery
        
        # Prepare fixed payload and headers once before loop
        payload = {"value": 0}
        headers = (await self._generate_common_headers()).copy()
        headers.update({
            'domainidentifier': str(device.category or ''),
            'propidentifier': 'online_state',
            'localindex': str(device.localIndex or ''),
            'deviceserial': str(device.device_serial or ''),
            'resourcecategory': str(device.resourceCategory or '')
        })
        
        while not event.is_set():
            try:
                async with self._session.put(url=const.SYNC_DEVICES_API, json=payload, headers=headers) as response:
                    content = await response.json(content_type=None)
                    self._assert_response_successful(content)
                    
                # Reset retry delay on successful heartbeat, then wait normal interval
                heartbeat_retry_delay = 1
                await asyncio.sleep(const.HEARTBEAT_INTERVAL)
                    
            except Exception as e:
                _LOGGER.error(f'Device {device.id} heartbeat failed: {e}, retrying in {heartbeat_retry_delay} seconds')
                await asyncio.sleep(heartbeat_retry_delay)
                
                # Fast retry with small increments, but don't exceed heartbeat interval
                heartbeat_retry_delay = min(heartbeat_retry_delay * 2, const.HEARTBEAT_INTERVAL)
                _LOGGER.debug(f'Device {device.id} heartbeat next retry delay set to {heartbeat_retry_delay} seconds')

    async def _parse_message(self, device: TreeowDevice, msg: Dict[str, Any]) -> None:
        """Optimized message parsing."""
        try:
            props = msg.get('props', [])
            if not props:
                return
                
            data = json.loads(props[0]['value']).get(msg['category'], {})
            values = {}
            for attribute in device.attributes:
                identifier = attribute.key
                if identifier in data:
                    values[identifier] = data[identifier]

            fire_event(self._hass, EVENT_DEVICE_DATA_CHANGED, {
                'deviceId': str(msg['id']),
                'attributes': values
            })
            
        except Exception as e:
            _LOGGER.error(f'Failed to parse device message: {e}')

    async def _send_command(self, device: Dict[str, Any], command: Dict[str, Any]) -> None:
        """Optimized command sending."""
        try:
            if not command:
                return
                
            identifier = next(iter(command.keys()))
            value = command[identifier]
            
            payload = {"value": value}
            headers = (await self._generate_common_headers()).copy()
            headers.update({
                'domainidentifier': str(device.get('category', '')),
                'propidentifier': str(identifier),
                'localindex': str(device.get('localIndex', '')),
                'deviceserial': str(device.get('device_serial', '')),
                'resourcecategory': str(device.get('resourceCategory', ''))
            })
            
            # Send command
            async with self._session.put(url=const.SYNC_DEVICES_API, json=payload, headers=headers) as response:
                content = await response.json(content_type=None)
                self._assert_response_successful(content)
            
            # Verify command
            async with self._session.get(url=const.SYNC_DEVICES_API, headers=headers) as response:
                content = await response.json(content_type=None)
                self._assert_response_successful(content)
                
                if content.get('data') != value:
                    message = content.get('meta', {}).get('message', 'Unknown error')
                    raise TreeowClientException(f'Command send failed: {message}')
                    
        except TreeowClientException as e:
            _LOGGER.error(f'Failed to send command: {e}')
            raise
        except Exception as e:
            _LOGGER.error(f'Failed to send command: {e}')
            raise TreeowClientException(f'Failed to send command: {e}')

    async def _generate_common_headers(self) -> Dict[str, str]:
        """Optimized header generation with caching."""
        if self._header_cache is None:
            self._header_cache = {
                "content-type": "application/json;charset=utf8",
                "authorization": f"Bearer {self._access_token}",
                "accept": "*/*",
                "accept-encoding": "gzip, deflate, br",
                "accept-language": "zh-Hans-CN;q=1, en-US;q=0.9",
                "clienttype": "2",
                "user-agent": f"Treeow/{self._app_version} (iPhone; iOS {self._ios_version}; Scale/3.00)"
            }
        return self._header_cache

    @staticmethod
    def _assert_response_successful(resp: Dict[str, Any]) -> None:
        """Optimized response validation."""
        if 'meta' in resp:
            meta = resp['meta']
            if int(meta.get('code', 0)) != 200 or 'error' in str(meta):
                raise TreeowClientException(f'API response error: {meta.get("message", "Unknown error")}')
        elif 'result' in resp:
            result = resp['result']
            if int(result.get('code', 0)) != 200 or 'error' in str(result):
                raise TreeowClientException(f'API response error: {result.get("msg", "Unknown error")}')
        else:
            code = resp.get('code', 0)
            msg = resp.get('msg', '')
            if int(code) != 200 or 'error' in msg:
                raise TreeowClientException(f'API response error: {msg or "Unknown error"}')
