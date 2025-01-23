import asyncio
import hashlib
import json
import logging
import threading
import time
import uuid
from typing import List
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
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


class TokenInfo:

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
    pass


class TreeowClient:

    def __init__(self, hass: HomeAssistant, access_token: str):
        self._access_token = access_token
        self._app_version = '1.1.3'
        self._hass = hass
        self._session = async_get_clientsession(hass)

    @property
    def hass(self):
        return self._hass

    async def get_app_version(self):
        async with self._session.post(url=GET_APP_VERSION_API) as response:
            content = await response.json(content_type=None)
            if content['results'] and content['results'][0]['trackName'] == 'Treeow Home':
                self._app_version = content['results'][0]['version']

    async def login(self, account: str, password: str) -> TokenInfo:
        """
        登陆获取token
        :return:
        """
        headers = await self._generate_common_headers()
        headers.pop("authorization")
        payload = {
            "terminalIdentifier": str(uuid.uuid5(uuid.NAMESPACE_DNS, account)).upper(),
            "account": account,
            "password": hashlib.md5(password.encode()).hexdigest(),
            "terminalName": "iPhone"
        }
        async with self._session.post(url=LOGIN_API, headers=headers, json=payload) as response:
            content = await response.json(content_type=None)
            self._assert_response_successful(content)

            return TokenInfo(
                content['data']['accessToken'],
                content['data']['refreshToken'],
                int(time.time()) + int(content['data']['expiresIn'])
            )

    async def refresh_token(self, refresh_token: str) -> TokenInfo:
        """
        刷新token
        :return:
        """
        payload = {
            'refreshToken': refresh_token
        }

        headers = await self._generate_common_headers()
        async with self._session.post(url=REFRESH_TOKEN_API, headers=headers, json=payload) as response:
            content = await response.json(content_type=None)
            self._assert_response_successful(content)

            return TokenInfo(
                content['data']['accessToken'],
                content['data']['refreshToken'],
                int(time.time()) + int(content['data']['expiresIn'])
            )

    async def verify_token(self):
        """
        验证token是否有效
        :return:
        """
        req_headers = await self._generate_common_headers()
        payload = {}
        async with self._session.post(url=VERIFY_TOKEN_API, headers=req_headers, json=payload) as response:
            content = await response.json(content_type=None)
            self._assert_response_successful(content)

    async def get_devices(self) -> List[TreeowDevice]:
        """
        获取设备列表
        """
        # 获取 groupId 列表
        group_ids = await self.get_groups()
        devices = []
        req_headers = await self._generate_common_headers()
        for group_id in group_ids:
            payload = {
                "pageSize": "50",
                "groupId": group_id,
                "pageNo": "1"
            }
            async with self._session.post(url=LIST_DEVICES_API, headers=req_headers, json=payload) as response:
                content = await response.json(content_type=None)
                self._assert_response_successful(content)
                if content['data']:
                    for raw in content['data']:
                        raw['groupId']=group_id
                        single_device = TreeowDevice(self, raw)
                        await single_device.async_init()
                        devices.append(single_device)
        return devices

    async def get_groups(self) -> list:
        """
        获取groupId 列表
        :return:
        """
        req_headers = await self._generate_common_headers()
        # 获取 groupId 列表
        async with self._session.post(url=LIST_HOME_API, headers=req_headers) as response:
            content = await response.json(content_type=None)
            self._assert_response_successful(content)
            group_ids = [group['id'] for home in content['data'] for group in home['homeGroups']]
            return group_ids

    async def get_digital_model(self, device: TreeowDevice) -> list:
        """
        获取设备attributes
        :param device:
        :return:
        """
        attributes = []
        pv = f"PV(productId={device.device_serial.split(':')[0]}, version={device.version})"
        payload = {
            "pageSize": "50",
            "groupId": device.group_id,
            "pageNo": "1"
        }
        req_headers = await self._generate_common_headers()
        async with self._session.post(url=LIST_DEVICES_API, json=payload, headers=req_headers) as response:
            content = await response.json(content_type=None)
            self._assert_response_successful(content)
            if content['profiles']:
                resources = content['profiles'][pv]['resources']
                for resource in resources:
                    domains = resource.get('domains', [])
                    for domain in domains:
                        if domain.get('identifier') == device.category:
                            attributes.extend(domain['props'])
        return attributes

    async def get_digital_model_from_cache(self, device: TreeowDevice) -> list:
        store = Store(self._hass, 1, 'treeow/device_{}.json'.format(device.id))
        cache = None
        try:
            cache = await store.async_load()
            if isinstance(cache, str):
                raise RuntimeError('cache is invalid')
        except Exception:
            _LOGGER.warning("Device {} cache is invalid".format(device.id))
            await store.async_remove()

        if cache:
            # 检查缓存是否过期，假设缓存中存储了一个 'timestamp' 字段表示存储时间
            current_time = int(time.time())
            cache_expiration = 3600  # 缓存过期时间，单位为秒，这里设置为 1 小时
            if 'timestamp' in cache and (current_time - cache['timestamp'] < cache_expiration):
                _LOGGER.debug("Device {} get digital model from cache successful".format(device.id))
                return cache['attributes']
            else:
                _LOGGER.info("Device {} cache has expired, attempting to refresh".format(device.id))
                await store.async_remove()
                cache = None

        _LOGGER.info("Device {} get digital model from cache fail, attempt to obtain remotely".format(device.id))
        attributes = await self.get_digital_model(device)
        # 存储缓存时添加时间戳
        await store.async_save({
            'device': {
                'name': device.name,
                'device_serial': device.device_serial,
                'category': device.category,
                'version': device.version,
                'group_id': device.group_id,
                'resourceCategory': device.resourceCategory,
                'localIndex': device.localIndex
            },
            'attributes': attributes,
            'timestamp': int(time.time())  # 存储当前时间戳
        })
        
        return attributes

    async def get_device_snapshot_data(self, device: TreeowDevice) -> dict:
        """
        获取指定设备最新的属性数据
        :param device:
        :return:
        """
        values = {}
        payload = {
            "id": device.id
        }
        req_headers = await self._generate_common_headers()
        async with self._session.post(url=DESCRIBE_DEVICES_API, json=payload, headers=req_headers) as response:
            content = await response.json(content_type=None)
            self._assert_response_successful(content)
            if content['data']:
                value_data = json.loads(content['data']['props'][0]['value'])['Air_Purifier']

        attributes = await self.get_digital_model(device)

        for attribute in attributes:
            identifier = attribute['identifier']
            if identifier not in value_data:
                continue
            values[identifier] = value_data[identifier]

        return values

    async def listen_devices(self, targetDevices: List[TreeowDevice], signal: threading.Event):
        # 为当前的监听进程生成一个唯一的进程 ID，用于识别当前正在运行的 listen_device
        process_id = str(uuid.uuid4())
        self._hass.data['current_listen_devices_process_id'] = process_id
        cancel_control_listen = None

        # 心跳任务列表
        heartbeat_tasks = []
        try:
            req_headers = await self._generate_common_headers()

            # 启动心跳任务
            for device in targetDevices:
                heartbeat_signal = threading.Event()
                task = self._hass.async_create_background_task(
                    self._send_heartbeat(self, device, heartbeat_signal),  # 将 self 传递给 _send_heartbeat
                    'treeow-http-heartbeat'
                )
                heartbeat_tasks.append((task, heartbeat_signal))

            # 监听事件总线 EVENT_DEVICE_CONTROL 事件，并使用定义的控制回调函数
            async def control_callback(e):
                await self._send_command(self, e.data['device'], e.data['attributes'])

            # 设置事件监听，并存储取消监听的函数
            cancel_control_listen = listen_event(self._hass, EVENT_DEVICE_CONTROL, control_callback)
            fire_event(self._hass, EVENT_GATEWAY_STATUS_CHANGED, {
                'status': True
            })

            while not signal.is_set():
                try:
                    for device in targetDevices:
                        payload = {"id": device.id}
                        async with self._session.post(url=DESCRIBE_DEVICES_API, json=payload, headers=req_headers) as response:
                            content = await response.json(content_type=None)
                            self._assert_response_successful(content)
                            if content['data']:
                                await self._parse_message(device, content['data'])
                    await asyncio.sleep(1)

                except Exception as e:
                    _LOGGER.exception("Connection disconnected. Waiting to retry.")
                    await asyncio.sleep(5)

        finally:
            if cancel_control_listen:
                cancel_control_listen()
            # 触发心跳信号，停止心跳任务
            for task, heartbeat_signal in heartbeat_tasks:
                heartbeat_signal.set()
                try:
                    task.cancel()
                    await task
                except asyncio.CancelledError:
                    pass
            # 如果当前进程 ID 与存储的进程 ID 匹配，触发 EVENT_GATEWAY_STATUS_CHANGED 事件并将状态设置为 False
            if process_id == self._hass.data['current_listen_devices_process_id']:
                fire_event(self._hass, EVENT_GATEWAY_STATUS_CHANGED, {
                    'status': False
                })
            else:
                _LOGGER.debug('process_id not match, skip...')
            # 打印监听设备停止的信息
            _LOGGER.info('listen device stopped.')

    @staticmethod
    async def _send_heartbeat(self, device: TreeowDevice, event: threading.Event):
        while not event.is_set():
            payload = {"value": 0}
            req_headers = await self._generate_common_headers()
            req_headers.update({
                'domainidentifier': device.category,
                'propidentifier': 'online_state',
                'localindex': device.localIndex,
                'deviceserial': device.device_serial,
                'resourcecategory': device.resourceCategory
            })
            _LOGGER.debug('client._send_heartbeat: {}'.format(req_headers))
            async with self._session.put(url=SYNC_DEVICES_API, json=payload, headers=req_headers) as response:
                content = await response.json(content_type=None)
                self._assert_response_successful(content)
                _LOGGER.debug(f'Heartbeat sent for device {device.id}: {content["meta"]["message"]}')
            await asyncio.sleep(10)
        _LOGGER.info(f"Heartbeat stopped for device {device.id}")

    async def _parse_message(self, device: TreeowDevice, msg):
        data = json.loads(msg['props'][0]['value'])[msg['category']]
        values = {}
        attributes = await self.get_digital_model_from_cache(device)
        for attribute in attributes:
            name = attribute['identifier']
            if name not in data:
                continue
            values[name] = data[name]

        fire_event(self._hass, EVENT_DEVICE_DATA_CHANGED, {
            'deviceId': msg['id'],
            'attributes': values
        })

    @staticmethod
    async def _send_command(self, device: dict, command: dict):
        """
        发送命令到设备
        :param device:
        :param command: 执行的命令
        """
        identifier = list(command.keys())[0]
        payload = {"value": command[identifier]}
        req_headers = await self._generate_common_headers()
        req_headers.update({
            'domainidentifier': device['category'],
            'propidentifier': identifier,
            'localindex': device['localIndex'],
            'deviceserial': device['device_serial'],
            'resourcecategory': device['resourceCategory']
        })
        _LOGGER.debug('client._send_command.identifier: {}'.format(identifier))
        _LOGGER.debug('client._send_command.payload: {}'.format(payload))
        async with self._session.put(url=SYNC_DEVICES_API, json=payload, headers=req_headers) as response:
            content = await response.json(content_type=None)
            self._assert_response_successful(content)
        async with self._session.get(url=SYNC_DEVICES_API, headers=req_headers) as get_response:
            get_content = await get_response.json(content_type=None)
            self._assert_response_successful(get_content)
            if get_content['data'] and get_content['data'] != command[identifier]:
                raise TreeowClientException('send_command异常: ' + get_content['meta']['message'])

    async def _generate_common_headers(self):
        return {
            "content-type": "application/json;charset=utf8",
            "authorization": f"Bearer {self._access_token}",
            "accept": "*/*",
            "accept-encoding": "gzip, deflate, br",
            "accept-language": "zh-Hans-CN;q=1, en-US;q=0.9",
            "clienttype": "2",
            "user-agent": f"Treeow/{self._app_version} (iPhone; iOS 18.2.1; Scale/3.00)"
        }

    @staticmethod
    def _assert_response_successful(resp):
        if 'meta' in resp:
            if int(resp['meta']['code']) != 200 or '错误' in resp['meta']:
                raise TreeowClientException('接口返回异常: ' + resp['meta']['message'])
        elif 'result' in resp:
            if int(resp['result']['code']) != 200 or 'error' in resp['result']:
                raise TreeowClientException('接口返回异常: ' + resp['result']['msg'])
        else:
            if int(resp['code']) != 200 or '错误' in resp['msg']:
                raise TreeowClientException('接口返回异常: ' + resp['msg'])
