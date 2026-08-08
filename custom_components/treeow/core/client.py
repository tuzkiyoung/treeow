import asyncio
import hashlib
import json
import logging
import threading
import time
import uuid
from typing import List, Dict, Any, Optional
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from .device import TreeowDevice
from .event import listen_event, fire_event
from custom_components.treeow import const
from custom_components.treeow.const import (
    EVENT_DEVICE_CONTROL,
    EVENT_DEVICE_DATA_CHANGED,
    EVENT_DEVICE_STATUS_CHANGED,
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

    __slots__ = ('_access_token', '_app_version', '_ios_version', '_hass', '_session', '_header_cache')

    def __init__(self, hass: HomeAssistant, access_token: str, app_version: str = DEFAULT_APP_VERSION, ios_version: str = DEFAULT_IOS_VERSION):
        self._access_token = access_token
        self._app_version = app_version
        self._ios_version = ios_version
        self._hass = hass
        self._session = async_get_clientsession(hass)
        self._header_cache = None

    async def _request(
        self,
        url: str,
        what: str,
        payload: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        log=None,
        parse=None,
        method: str = 'post'
    ) -> Any:
        """POST and return the parsed body, normalising failures.

        An API-level failure propagates unchanged (its own 'API response error'
        message is the useful one); anything else is wrapped as
        '<what>: <cause>'. Either way the failure is logged with `what` as the
        prefix, at `log`'s level (default error).

        `parse` runs inside the same protected block, so a malformed body is
        reported the same way a failed request is -- the server's response
        shapes vary enough that callers rely on this.
        """
        if log is None:
            log = _LOGGER.error

        try:
            if headers is None:
                headers = await self._generate_common_headers()

            request = getattr(self._session, method)
            async with request(url=url, headers=headers, json=payload) as response:
                content = await response.json(content_type=None)
                self._assert_response_successful(content)
                return parse(content) if parse else content
        except TreeowClientException as e:
            log(f'{what}: {e}')
            raise
        except Exception as e:
            log(f'{what}: {e}')
            raise TreeowClientException(f'{what}: {e}')

    @staticmethod
    def _token_from(content: Dict[str, Any]) -> TokenInfo:
        data = content.get('data', {})
        return TokenInfo(
            data.get('accessToken', ''),
            data.get('refreshToken', ''),
            int(time.time()) + int(data.get('expiresIn', 0))
        )

    async def login(self, account: str, password: str) -> TokenInfo:
        headers = (await self._generate_common_headers()).copy()
        headers.pop("authorization", None)  # Safe removal

        payload = {
            "terminalIdentifier": str(uuid.uuid5(uuid.NAMESPACE_DNS, account)).upper(),
            "account": account,
            "password": hashlib.md5(password.encode()).hexdigest(),
            "terminalName": "iPhone"
        }

        return await self._request(
            const.LOGIN_API, 'Login failed', payload, headers, parse=self._token_from
        )

    async def refresh_token(self, refresh_token: str) -> TokenInfo:
        return await self._request(
            const.REFRESH_TOKEN_API, 'Token refresh failed', {'refreshToken': refresh_token},
            parse=self._token_from
        )

    async def verify_token(self) -> None:
        # Logged at warning, not error: this fires on every startup with an
        # expired token, which __init__ handles by re-logging in.
        await self._request(
            const.VERIFY_TOKEN_API, 'Token verification failed', {}, log=_LOGGER.warning
        )

    async def get_devices(self) -> List[TreeowDevice]:
        """Get all devices from all groups with parallel processing."""
        try:
            group_ids = await self.get_groups()
            if not group_ids:
                _LOGGER.warning('No device groups found')
                return []

            headers = await self._generate_common_headers()
            
            tasks = [self._get_devices_for_group(group_id, headers) for group_id in group_ids]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            devices = []
            for i, result in enumerate(results):
                if isinstance(result, list):
                    devices.extend(result)
                elif isinstance(result, Exception):
                    # The cause is already logged in detail further down the stack,
                    # but this is the only line that says the whole group was
                    # dropped -- one failing device discards all of its siblings.
                    _LOGGER.warning(f'Dropping all devices in group {group_ids[i]}: {result}')

            return devices
            
        except TreeowClientException as e:
            _LOGGER.error(f'Failed to get device list: {e}')
            raise
        except Exception as e:
            _LOGGER.error(f'Failed to get device list: {e}')
            raise TreeowClientException(f'Failed to get device list: {e}')

    async def _get_devices_for_group(self, group_id: str, headers: Dict[str, str]) -> List[TreeowDevice]:
        """Helper method to get devices for a specific group with parallel initialization."""
        payload = {
            "pageSize": str(const.DEFAULT_PAGE_SIZE),
            "groupId": group_id,
            "pageNo": "1"
        }
        
        content = await self._request(
            const.LIST_DEVICES_API, f'Failed to get devices for group {group_id}', payload, headers
        )

        if not content.get('data'):
            return []

        # This response already carries the product spec blob; hand it to the
        # devices so they don't each re-issue this same request.
        profiles = content.get('profiles', {})

        devices = []
        for raw_device in content['data']:
            raw_device['groupId'] = group_id
            devices.append(TreeowDevice(self, raw_device))

        await asyncio.gather(*[device.async_init(profiles) for device in devices])

        return devices

    @staticmethod
    def _group_ids_from(content: Dict[str, Any]) -> List[str]:
        group_ids = []
        for home in content.get('data', []):
            for group in home.get('homeGroups', []):
                group_ids.append(group['id'])
        return group_ids

    async def get_groups(self) -> List[str]:
        return await self._request(
            const.LIST_HOME_API, 'Failed to get device groups', parse=self._group_ids_from
        )

    async def _fetch_profiles(self, group_id: str, what: str) -> Dict[str, Any]:
        payload = {
            "pageSize": str(const.DEFAULT_PAGE_SIZE),
            "groupId": group_id,
            "pageNo": "1"
        }

        return await self._request(
            const.LIST_DEVICES_API, what, payload, parse=lambda c: c.get('profiles', {})
        )

    async def get_digital_model(self, device: TreeowDevice, profiles: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        try:
            device_serial = device.device_serial
            if not device_serial or ':' not in device_serial:
                _LOGGER.warning(f'Device {device.id} invalid serial number: {device_serial}')
                return []

            product_id = device_serial.split(':')[0]
            pv = f"PV(productId={product_id}, version={device.version})"

            if profiles is None:
                profiles = await self._fetch_profiles(
                    device.group_id, f'Failed to get digital model for device {device.id}'
                )

            if pv not in profiles:
                return []

            attributes = []
            for resource in profiles[pv].get('resources', []):
                for domain in resource.get('domains', []):
                    if domain.get('identifier') == device.category:
                        attributes.extend(domain.get('props', []))

            return attributes

        except TreeowClientException as e:
            _LOGGER.error(f'Failed to get digital model for device {device.id}: {e}')
            raise
        except Exception as e:
            _LOGGER.error(f'Failed to get digital model for device {device.id}: {e}')
            raise TreeowClientException(f'Failed to get digital model for device {device.id}: {e}')

    async def get_digital_model_from_cache(self, device: TreeowDevice, profiles: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
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
        attributes = await self.get_digital_model(device, profiles)
        
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


    async def get_device_snapshot_data(self, device: TreeowDevice, profiles: Optional[Dict[str, Any]] = None) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
        try:
            payload = {"id": device.id}
            headers = await self._generate_common_headers()
            
            async with self._session.post(url=const.DESCRIBE_DEVICES_API, json=payload, headers=headers) as response:
                content = await response.json(content_type=None)
                self._assert_response_successful(content)
                
                data = content.get('data')
                if not data:
                    return {}, []

                # Seed availability from the same payload the poll loop will use,
                # so a device that is already offline at startup never presents as
                # available on the strength of the cached props below.
                self._publish_availability(device, self._is_device_online(data))

                # Parse device data
                props = data.get('props', [])
                if not props:
                    return {}, []
                
                value_data = json.loads(props[0]['value']).get(device.category, {})
                
                # Get attributes and build snapshot
                attributes = await self.get_digital_model_from_cache(device, profiles)
                values = {}
                
                for attribute in attributes:
                    identifier = attribute.get('identifier')
                    if identifier and identifier in value_data:
                        values[identifier] = value_data[identifier]
                
                return values, attributes
                
        except TreeowClientException as e:
            _LOGGER.error(f'Failed to get snapshot data for device {device.id}: {e}')
            raise
        except Exception as e:
            _LOGGER.error(f'Failed to get snapshot data for device {device.id}: {e}')
            raise TreeowClientException(f'Failed to get snapshot data for device {device.id}: {e}')

    async def listen_devices(self, target_devices: List[TreeowDevice], signal: threading.Event, poll_interval: int = const.DEFAULT_POLL_INTERVAL) -> None:
        process_id = str(uuid.uuid4())
        self._hass.data.setdefault(const.DOMAIN, {})['listen_devices_process_id'] = process_id
        
        cancel_control_listen = None
        heartbeat_tasks = []

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
                command_attrs = event.data['attributes']
                
                try:
                    await self._send_command(device_dict, command_attrs)
                    _LOGGER.debug(f'Command sent successfully for device {device_id}: {command_attrs}')
                        
                except Exception as e:
                    _LOGGER.error(f'Failed to send command for device {device_id} with attributes {command_attrs}: {e}')

                try:
                    if device_id in device_map:
                        headers = await self._generate_common_headers()
                        await self._poll_device(device_map[device_id], headers)
                        
                except Exception as e:
                    _LOGGER.error(f'Failed to poll device {device_id} after control: {e}')

            cancel_control_listen = listen_event(self._hass, EVENT_DEVICE_CONTROL, control_callback)
            
            # Signal gateway is online
            fire_event(self._hass, EVENT_GATEWAY_STATUS_CHANGED, {'status': True})

            # Generate headers once before loop (token refresh will reload integration)
            headers = await self._generate_common_headers()

            # Main listening loop. _poll_device swallows its own exceptions, so this
            # loop only exits via `signal` or cancellation.
            while not signal.is_set():
                await asyncio.gather(
                    *[self._poll_device(device, headers) for device in target_devices],
                    return_exceptions=True
                )
                await asyncio.sleep(poll_interval)

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
            current_process = self._hass.data.get(const.DOMAIN, {}).get('listen_devices_process_id')
            if process_id == current_process:
                fire_event(self._hass, EVENT_GATEWAY_STATUS_CHANGED, {'status': False})

    async def _poll_device(self, device: TreeowDevice, headers: Dict[str, str]) -> None:
        """Poll one device. Never raises: one bad device must not stop the poll loop."""
        try:
            content = await self._request(
                const.DESCRIBE_DEVICES_API, f'Failed to poll device {device.id}',
                {"id": device.id}, headers
            )
        except TreeowClientException:
            # Already logged by _request. The device is not necessarily offline --
            # the cloud may just be unreachable -- so only give up after several
            # consecutive misses.
            self._register_poll_failure(device)
            return

        # isinstance guard, not just truthiness: _is_device_online below indexes
        # into this, and unlike _parse_message it has no exception handler of its
        # own. A malformed body must land on the failure path, not raise out of
        # here into the gather that silently drops it.
        data = content.get('data')
        if not isinstance(data, dict) or not data:
            self._register_poll_failure(device)
            return

        device.poll_failures = 0

        # The cloud keeps serving a disconnected device's last known props, so a
        # successful poll says nothing about the device itself -- only this flag does.
        online = self._is_device_online(data)
        if online:
            # Parse before publishing, so that on recovery the state write
            # triggered by becoming available already carries the fresh values
            # instead of the ones cached from before the outage. While offline
            # the parse is skipped outright: every entity is unavailable, so the
            # decode and the resulting fan-out would be discarded.
            await self._parse_message(device, data)

        self._publish_availability(device, online)

    @staticmethod
    def _is_device_online(data: Dict[str, Any]) -> bool:
        """Read the device-level online flag out of a device/info payload.

        Absent or unparseable means 'this endpoint did not tell us', which must
        read as online: inventing an offline state would black out every entity
        of any device whose response omits the field.
        """
        status = data.get('status')
        if status is None:
            return True

        try:
            return int(status) == const.DEVICE_STATUS_ONLINE
        except (TypeError, ValueError):
            _LOGGER.debug(f'Unparseable device status {status!r}, assuming online')
            return True

    def _register_poll_failure(self, device: TreeowDevice) -> None:
        device.poll_failures += 1

        if device.poll_failures >= const.MAX_POLL_FAILURES:
            self._publish_availability(device, False)

    def _publish_availability(self, device: TreeowDevice, available: bool) -> None:
        """Fire only on an actual transition -- polling is every few seconds and
        entities re-render on each event."""
        if device.available == available:
            return

        device.available = available
        _LOGGER.info(
            f'Device {device.id} is now {"online" if available else "offline"}'
        )
        fire_event(self._hass, EVENT_DEVICE_STATUS_CHANGED, {
            'deviceId': str(device.id),
            'status': available
        })

    async def _send_heartbeat(self, device: TreeowDevice, event: threading.Event) -> None:
        heartbeat_retry_delay = 1  # Start with 1 second for fast heartbeat recovery
        
        # Prepare fixed payload and headers once before loop
        payload = {"value": 0}
        headers = await self._device_headers(device.to_dict(), 'online_state')

        # Deliberately not routed through _request: the except below drives the
        # retry backoff, and _request would log every failed beat a second time.

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

    async def _device_headers(self, device: Dict[str, Any], prop_identifier: str) -> Dict[str, str]:
        """Common headers plus the routing headers a per-device write needs.

        Takes the TreeowDevice.to_dict() shape, which is what the control event
        carries; _send_heartbeat passes device.to_dict() for the same reason.
        """
        headers = (await self._generate_common_headers()).copy()
        headers.update({
            'domainidentifier': str(device.get('category', '') or ''),
            'propidentifier': str(prop_identifier),
            'localindex': str(device.get('localIndex', '') or ''),
            'deviceserial': str(device.get('device_serial', '') or ''),
            'resourcecategory': str(device.get('resourceCategory', '') or '')
        })
        return headers

    async def _send_command(self, device: Dict[str, Any], command: Dict[str, Any]) -> None:
        # One request per property: the target prop is named in the headers, so
        # the API has no way to accept several at once. Insertion order is
        # meaningful -- callers put 'switch' first so the device is powered on
        # before a gear or mode is applied to it. A failure aborts the rest,
        # which is what we want: there is no point setting a speed on a device
        # that just refused to turn on.
        for identifier, value in command.items():
            headers = await self._device_headers(device, identifier)

            await self._request(
                const.SYNC_DEVICES_API, 'Failed to send command', {"value": value}, headers, method='put'
            )

            def verify(content, expected=value):
                if content.get('data') != expected:
                    message = content.get('meta', {}).get('message', 'Unknown error')
                    raise TreeowClientException(f'Command send failed: {message}')
                return content

            # verify runs inside _request's protected block, so a mismatch is logged
            # with the same 'Failed to send command' prefix the caller has always seen.
            await self._request(
                const.SYNC_DEVICES_API, 'Failed to send command', headers=headers,
                method='get', parse=verify
            )

    async def _generate_common_headers(self) -> Dict[str, str]:
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
        # The server returns success/failure in several different envelope shapes,
        # so each branch is tolerant on purpose. The 'error' in str(...) checks scan
        # the whole envelope deliberately: some failures carry no non-200 code and
        # only surface as an error string somewhere inside. Do not "unify" these.
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
