import logging
from typing import Any, Dict

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.config_validation import multi_select

from .const import DOMAIN, FILTER_TYPE_EXCLUDE, FILTER_TYPE_INCLUDE, DEFAULT_POLL_INTERVAL
from .core.client import TreeowClientException, TreeowClient
from .core.config import AccountConfig, DeviceFilterConfig, EntityFilterConfig

_LOGGER = logging.getLogger(__name__)

account = 'account'
password = 'password'

class TreeowConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 2

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: Dict[str, str] = {}
        if user_input is not None:
            try:
                # 登录获取token
                client = TreeowClient(self.hass, '')
                token_info = await client.login(user_input[account], user_input[password])

                return self.async_create_entry(title="Treeow-{}".format(user_input[account]), data={
                    'account': {
                        'account': user_input[account],
                        'password': user_input[password],
                        'access_token': token_info.access_token,
                        'refresh_token': token_info.refresh_token,
                        'expires_at': token_info.expires_at,
                        'default_load_all_entity': user_input['default_load_all_entity'],
                        'poll_interval': user_input.get('poll_interval', DEFAULT_POLL_INTERVAL)
                    }
                })
            except TreeowClientException as e:
                _LOGGER.warning(str(e))
                errors['base'] = 'auth_error'

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(account): str,
                    vol.Required(password): str,
                    vol.Required('default_load_all_entity', default=True): bool,
                    vol.Required('poll_interval', default=DEFAULT_POLL_INTERVAL): vol.All(vol.Coerce(int), vol.Range(min=1, max=60)),
                }
            ),
            errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        # config_entry is now automatically available through the base class
        super().__init__()

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """
        功能菜单
        :param user_input:
        :return:
        """
        return self.async_show_menu(
            step_id="init",
            menu_options=['account', 'device', 'entity_device_selector']
        )

    async def async_step_account(self,  user_input: dict[str, Any] | None = None) -> FlowResult:
        """
        账号设置
        :param user_input:
        :return:
        """
        errors: Dict[str, str] = {}

        cfg = AccountConfig(self.hass, self.config_entry)

        if user_input is not None:
            try:
                # 获取token
                client = TreeowClient(self.hass, '')
                token_info = await client.login(user_input[account], user_input[password])

                cfg.account = user_input[account]
                cfg.password = user_input[password]
                cfg.access_token = token_info.access_token
                cfg.refresh_token = token_info.refresh_token
                cfg.expires_at = token_info.expires_at
                cfg.default_load_all_entity = user_input['default_load_all_entity']
                cfg.poll_interval = user_input.get('poll_interval', DEFAULT_POLL_INTERVAL)
                cfg.save()

                await self.hass.config_entries.async_reload(self.config_entry.entry_id)

                return self.async_create_entry(title='', data={})
            except TreeowClientException as e:
                _LOGGER.warning(str(e))
                errors['base'] = 'auth_error'

        return self.async_show_form(
            step_id="account",
            data_schema=vol.Schema(
                {
                    vol.Required(account, default=cfg.account): str,
                    vol.Required(password, default=cfg.password): str,
                    vol.Required('default_load_all_entity', default=cfg.default_load_all_entity): bool,
                    vol.Required('poll_interval', default=cfg.poll_interval): vol.All(vol.Coerce(int), vol.Range(min=1, max=60)),
                }
            ),
            errors=errors
        )

    async def async_step_device(self,  user_input: dict[str, Any] | None = None) -> FlowResult:
        """
        筛选设备
        :param user_input:
        :return:
        """
        cfg = DeviceFilterConfig(self.hass, self.config_entry)

        if user_input is not None:
            cfg.set_filter_type(user_input['filter_type'])
            cfg.set_target_devices(user_input['target_devices'])
            cfg.save()

            return self.async_create_entry(title='', data={})

        devices = {}

        for item in self.hass.data.get(DOMAIN, {}).get('devices', []):
            devices[item.id] = item.name

        return self.async_show_form(
            step_id="device",
            data_schema=vol.Schema(
                {
                    vol.Required('filter_type', default=cfg.filter_type): vol.In({
                        FILTER_TYPE_EXCLUDE: 'Exclude',
                        FILTER_TYPE_INCLUDE: 'Include',
                    }),
                    vol.Optional('target_devices', default=cfg.target_devices): multi_select(devices)
                }
            )
        )

    async def async_step_entity_device_selector(self,  user_input: dict[str, Any] | None = None) -> FlowResult:
        """
        筛选实体（设备选择）
        :param user_input:
        :return:
        """
        if user_input is not None:
            self.hass.data.setdefault(DOMAIN, {})['entity_filter_target_device'] = user_input['target_device']
            return await self.async_step_entity_filter()

        devices = {}
        for item in self.hass.data.get(DOMAIN, {}).get('devices', []):
            devices[item.id] = item.name
        return self.async_show_form(
            step_id="entity_device_selector",
            data_schema=vol.Schema(
                {
                    vol.Required('target_device'): vol.In(devices)
                }
            )
        )

    async def async_step_entity_filter(self,  user_input: dict[str, Any] | None = None) -> FlowResult:
        """
        筛选实体
        :param user_input:
        :return:
        """
        cfg = EntityFilterConfig(self.hass, self.config_entry)

        if user_input is not None:
            cfg.set_filter_type(user_input['device_id'], user_input['filter_type'])
            cfg.set_target_entities(user_input['device_id'], user_input['target_entities'])
            cfg.save()

            await self.hass.config_entries.async_reload(self.config_entry.entry_id)

            return self.async_create_entry(title='', data={})

        domain_data = self.hass.data.get(DOMAIN, {})
        target_device_id = domain_data.pop('entity_filter_target_device', '')
        target_device = None
        for device in domain_data.get('devices', []):
            if device.id == target_device_id:
                target_device = device
                break
        
        if target_device is None:
            raise ValueError('Device [{}] not found'.format(target_device_id))

        entities = {}
        for attribute in target_device.attributes:
            entities[attribute.key] = attribute.display_name

        filtered = [item for item in cfg.get_target_entities(target_device_id) if item in entities]

        return self.async_show_form(
            step_id="entity_filter",
            data_schema=vol.Schema(
                {
                    vol.Required('device_id', default=target_device_id): str,
                    vol.Required('filter_type', default=cfg.get_filter_type(target_device_id)): vol.In({
                        FILTER_TYPE_EXCLUDE: 'Exclude',
                        FILTER_TYPE_INCLUDE: 'Include',
                    }),
                    vol.Optional('target_entities', default=filtered): multi_select(
                        entities
                    )
                }
            )
        )
