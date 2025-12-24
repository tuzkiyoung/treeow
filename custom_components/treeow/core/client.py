import asyncio
import hashlib
import json
import logging
import threading
import time
import uuid
from typing import List, Dict, Optional, Any
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .device import TreeowDevice
from .event import EVENT_DEVICE_CONTROL, EVENT_DEVICE_DATA_CHANGED, EVENT_GATEWAY_STATUS_CHANGED
from .event import listen_event, fire_event

_LOGGER = logging.getLogger(__name__)

LOGIN_API = 'https://eziotes.treeow.com.cn/api/user/account/login'
REFRESH_TOKEN_API = 'https://eziotes.treeow.com.cn/api/user/account/refresh/token'
VERIFY_TOKEN_API = 'https://eziotes.treeow.com.cn/api/msg/unread/count'
DESCRIBE_DEVICES_API = 'https://eziotes.treeow.com.cn/api/resource/device/info'
SYNC_DEVICES_API = 'https://eziotes.treeow.com.cn/api/v3/device/otap/prop'
LIST_DEVICES_API = 'https://eziotes.treeow.com.cn/api/resource/v3/device/list/page'
LIST_HOME_API = 'https://eziotes.treeow.com.cn/api/resource/home/list'
GET_APP_VERSION_API = 'https://itunes.apple.com/cn/lookup?id=6505056723'
GET_IOS_VERSION_API = 'https://api.ipsw.me/v4/releases'

CACHE_EXPIRATION = 3600  # 1 hour
HEARTBEAT_INTERVAL = 10  # seconds
DEVICE_POLL_INTERVAL = 1  # seconds
RETRY_DELAY = 5  # seconds
RETRY_MULTIPLIER = 2  # retry delay multiplier
MAX_RETRY_DELAY = 60  # seconds
DEFAULT_PAGE_SIZE = 50


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

    __slots__ = ('_access_token', '_app_version', '_ios_version', '_hass', '_session', 
                 '_header_cache', '_group_cache', '_group_cache_time', '_versions_initialized',
                 '_digital_model_cache', '_digital_model_cache_time')

    def __init__(self, hass: HomeAssistant, access_token: str):
        self._access_token = access_token
        self._app_version = '1.1.8'
        self._ios_version = '18.5'
        self._hass = hass
        self._session = async_get_clientsession(hass)
        self._header_cache = None
        self._group_cache = None
        self._group_cache_time = 0
        self._versions_initialized = False
        # 内存缓存，完全替代文件缓存
        self._digital_model_cache = {}
        self._digital_model_cache_time = {}

    @property
    def hass(self) -> HomeAssistant:
        return self._hass

    async def initialize_versions(self) -> None:
        """Initialize versions once during service startup."""
        if self._versions_initialized:
            return
            
        try:
            # Get versions concurrently for better performance
            await asyncio.gather(
                self.get_app_version(),
                self.get_ios_version()
            )
            
            if not self._app_version.replace('.', '').isdigit():
                _LOGGER.warning(f'Invalid app version format: {self._app_version}, using default')
                self._app_version = '1.1.8'
            
            if not self._ios_version.replace('.', '').isdigit():
                _LOGGER.warning(f'Invalid iOS version format: {self._ios_version}, using default')
                self._ios_version = '18.5'
            
            self._versions_initialized = True
        except Exception as e:
            _LOGGER.warning(f'Failed to initialize versions: {e}')

    async def get_app_version(self) -> None:
        """Get app version with optimized error handling."""
        try:
            async with self._session.get(url=GET_APP_VERSION_API) as response:
                content = await response.json(content_type=None)
                results = content.get('results', [])
                if results and results[0].get('trackName') == 'Treeow Home':
                    self._app_version = results[0].get('version', self._app_version)
                    self._header_cache = None  # Invalidate cache
        except Exception as e:
            _LOGGER.warning(f'Failed to get app version: {e}')

    async def get_ios_version(self) -> None:
        """Get iOS version with optimized parsing."""
        try:
            async with self._session.get(url=GET_IOS_VERSION_API) as response:
                content = await response.json(content_type=None)
                if content:
                    # More efficient version parsing
                    for item in content:
                        releases = item.get('releases', [])
                        for release in releases:
                            if release.get('type') == 'iOS':
                                name = release.get('name', '')
                                if name and ' ' in name:
                                    version_part = name.split(' ')[1]
                                    if '(' in version_part:
                                        self._ios_version = version_part.split('(')[0]
                                    else:
                                        self._ios_version = version_part
                                    
                                    self._header_cache = None  # Invalidate cache
                                    return
        except Exception as e:
            _LOGGER.warning(f'Failed to get iOS version: {e}')

    async def login(self, account: str, password: str) -> TokenInfo:
        """Optimized login with better error handling."""
        try:
            headers = await self._generate_common_headers()
            headers.pop("authorization", None)  # Safe removal
            
            terminal_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, account)).upper()
            password_hash = hashlib.md5(password.encode()).hexdigest()
            
            payload = {
                "terminalIdentifier": terminal_id,
                "account": account,
                "password": password_hash,
                "terminalName": "iPhone"
            }
            
            async with self._session.post(url=LOGIN_API, headers=headers, json=payload) as response:
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
            
            async with self._session.post(url=REFRESH_TOKEN_API, headers=headers, json=payload) as response:
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
            async with self._session.post(url=VERIFY_TOKEN_API, headers=headers, json={}) as response:
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
            "pageSize": str(DEFAULT_PAGE_SIZE),
            "groupId": group_id,
            "pageNo": "1"
        }
        
        async with self._session.post(url=LIST_DEVICES_API, headers=headers, json=payload) as response:
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
        """Optimized group retrieval with caching."""
        current_time = time.time()
        
        # Return cached result if still valid
        if (self._group_cache is not None and 
            current_time - self._group_cache_time < CACHE_EXPIRATION):
            return self._group_cache

        try:
            headers = await self._generate_common_headers()
            async with self._session.post(url=LIST_HOME_API, headers=headers) as response:
                content = await response.json(content_type=None)
                self._assert_response_successful(content)
                
                # Optimized group ID extraction
                group_ids = []
                for home in content.get('data', []):
                    for group in home.get('homeGroups', []):
                        group_ids.append(group['id'])
                
                # Cache the result
                self._group_cache = group_ids
                self._group_cache_time = current_time
                
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
                "pageSize": str(DEFAULT_PAGE_SIZE),
                "groupId": device.group_id,
                "pageNo": "1"
            }
            
            headers = await self._generate_common_headers()
            async with self._session.post(url=LIST_DEVICES_API, json=payload, headers=headers) as response:
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
        """完全基于内存缓存的数字模型获取，缓存时间1小时。"""
        device_id = device.id
        current_time = int(time.time())
        
        # 检查内存缓存
        if device_id in self._digital_model_cache:
            cache_time = self._digital_model_cache_time.get(device_id, 0)
            if current_time - cache_time < CACHE_EXPIRATION:
                # 缓存有效，直接返回
                return self._digital_model_cache[device_id]
            else:
                # 缓存过期，清理
                del self._digital_model_cache[device_id]
                del self._digital_model_cache_time[device_id]
        
        # 缓存未命中或过期，从API获取数据
        attributes = await self.get_digital_model(device)
        
        # 更新内存缓存
        self._digital_model_cache[device_id] = attributes
        self._digital_model_cache_time[device_id] = current_time
        
        return attributes

    def _cleanup_expired_cache(self) -> None:
        """清理过期的内存缓存，防止内存泄漏。"""
        current_time = int(time.time())
        expired_devices = []
        
        for device_id, cache_time in self._digital_model_cache_time.items():
            if current_time - cache_time >= CACHE_EXPIRATION:
                expired_devices.append(device_id)
        
        for device_id in expired_devices:
            del self._digital_model_cache[device_id]
            del self._digital_model_cache_time[device_id]
        
        if expired_devices:
            _LOGGER.debug(f'Cleaned up {len(expired_devices)} expired cache entries')

    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息，用于调试和监控。"""
        current_time = int(time.time())
        total_entries = len(self._digital_model_cache)
        expired_entries = 0
        valid_entries = 0
        
        for cache_time in self._digital_model_cache_time.values():
            if current_time - cache_time >= CACHE_EXPIRATION:
                expired_entries += 1
            else:
                valid_entries += 1
        
        return {
            'total_entries': total_entries,
            'valid_entries': valid_entries,
            'expired_entries': expired_entries,
            'memory_usage_mb': sum(len(str(v)) for v in self._digital_model_cache.values()) / (1024 * 1024)
        }

    async def get_device_snapshot_data(self, device: TreeowDevice) -> Dict[str, Any]:
        """Optimized snapshot data retrieval."""
        try:
            payload = {"id": device.id}
            headers = await self._generate_common_headers()
            
            async with self._session.post(url=DESCRIBE_DEVICES_API, json=payload, headers=headers) as response:
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

    async def listen_devices(self, target_devices: List[TreeowDevice], signal: threading.Event) -> None:
        """Optimized device listening with better resource management and exponential backoff retry."""
        process_id = str(uuid.uuid4())
        self._hass.data['current_listen_devices_process_id'] = process_id
        
        cancel_control_listen = None
        heartbeat_tasks = []
        retry_delay = RETRY_DELAY  # Initial retry delay
        cache_cleanup_counter = 0  # 缓存清理计数器
        
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
                """Handle device control events asynchronously."""
                try:
                    await self._send_command(event.data['device'], event.data['attributes'])
                except Exception as e:
                    _LOGGER.error(f'Failed to handle device control event: {e}')

            cancel_control_listen = listen_event(self._hass, EVENT_DEVICE_CONTROL, control_callback)
            
            # Signal gateway is online
            fire_event(self._hass, EVENT_GATEWAY_STATUS_CHANGED, {'status': True})

            # Main listening loop
            while not signal.is_set():
                try:
                    # Refresh headers each iteration to ensure token is current
                    headers = await self._generate_common_headers()
                    
                    # Poll devices concurrently for better performance
                    tasks = []
                    for device in target_devices:
                        task = self._poll_device(device, headers)
                        tasks.append(task)
                    
                    await asyncio.gather(*tasks, return_exceptions=True)
                    await asyncio.sleep(DEVICE_POLL_INTERVAL)
                    
                    # 定期清理过期缓存（每60次轮询清理一次，约1分钟）
                    cache_cleanup_counter += 1
                    if cache_cleanup_counter >= 60:
                        self._cleanup_expired_cache()
                        cache_cleanup_counter = 0
                    
                    # Reset retry delay on successful operation
                    retry_delay = RETRY_DELAY

                except Exception as e:
                    _LOGGER.error(f'Device listening error: {e}, retrying in {retry_delay} seconds')
                    await asyncio.sleep(retry_delay)
                    
                    # Exponential backoff: double the delay for next retry
                    retry_delay = min(retry_delay * RETRY_MULTIPLIER, MAX_RETRY_DELAY)
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
            async with self._session.post(url=DESCRIBE_DEVICES_API, json=payload, headers=headers) as response:
                content = await response.json(content_type=None)
                self._assert_response_successful(content)
                
                if content.get('data'):
                    await self._parse_message(device, content['data'])
                    
        except Exception as e:
            _LOGGER.error(f'Failed to poll device {device.id}: {e}')

    async def _send_heartbeat(self, device: TreeowDevice, event: threading.Event) -> None:
        """Optimized heartbeat sending with fast retry on failure."""
        heartbeat_retry_delay = 1  # Start with 1 second for fast heartbeat recovery
        
        while not event.is_set():
            try:
                payload = {"value": 0}
                headers = await self._generate_common_headers()
                headers.update({
                    'domainidentifier': str(device.category or ''),
                    'propidentifier': 'online_state',
                    'localindex': str(device.localIndex or ''),
                    'deviceserial': str(device.device_serial or ''),
                    'resourcecategory': str(device.resourceCategory or '')
                })
                
                async with self._session.put(url=SYNC_DEVICES_API, json=payload, headers=headers) as response:
                    content = await response.json(content_type=None)
                    self._assert_response_successful(content)
                    
                # Reset retry delay on successful heartbeat, then wait normal interval
                heartbeat_retry_delay = 1
                await asyncio.sleep(HEARTBEAT_INTERVAL)
                    
            except Exception as e:
                _LOGGER.error(f'Device {device.id} heartbeat failed: {e}, retrying in {heartbeat_retry_delay} seconds')
                await asyncio.sleep(heartbeat_retry_delay)
                
                # Fast retry with small increments, but don't exceed heartbeat interval
                heartbeat_retry_delay = min(heartbeat_retry_delay * 2, HEARTBEAT_INTERVAL)
                _LOGGER.debug(f'Device {device.id} heartbeat next retry delay set to {heartbeat_retry_delay} seconds')

    async def _parse_message(self, device: TreeowDevice, msg: Dict[str, Any]) -> None:
        """Optimized message parsing."""
        try:
            props = msg.get('props', [])
            if not props:
                return
                
            data = json.loads(props[0]['value']).get(msg['category'], {})
            attributes = await self.get_digital_model_from_cache(device)
            
            values = {}
            for attribute in attributes:
                identifier = attribute.get('identifier')
                if identifier and identifier in data:
                    values[identifier] = data[identifier]

            fire_event(self._hass, EVENT_DEVICE_DATA_CHANGED, {
                'deviceId': msg['id'],
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
            headers = await self._generate_common_headers()
            headers.update({
                'domainidentifier': str(device.get('category', '')),
                'propidentifier': str(identifier),
                'localindex': str(device.get('localIndex', '')),
                'deviceserial': str(device.get('device_serial', '')),
                'resourcecategory': str(device.get('resourceCategory', ''))
            })
            
            # Send command
            async with self._session.put(url=SYNC_DEVICES_API, json=payload, headers=headers) as response:
                content = await response.json(content_type=None)
                self._assert_response_successful(content)
            
            # Verify command
            async with self._session.get(url=SYNC_DEVICES_API, headers=headers) as response:
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
        """Optimized header generation with caching and version auto-initialization."""
        if not self._versions_initialized:
            await self.initialize_versions()
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
        return self._header_cache.copy()

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
