from homeassistant.const import Platform

DOMAIN = 'treeow'

SUPPORTED_PLATFORMS = [
    Platform.FAN,
    Platform.SWITCH,
    Platform.SELECT,
    Platform.NUMBER,
    Platform.SENSOR
]

FILTER_TYPE_INCLUDE = 'include'
FILTER_TYPE_EXCLUDE = 'exclude'

# API Endpoints
LOGIN_API = 'https://eziotes.treeow.com.cn/api/user/account/login'
REFRESH_TOKEN_API = 'https://eziotes.treeow.com.cn/api/user/account/refresh/token'
VERIFY_TOKEN_API = 'https://eziotes.treeow.com.cn/api/msg/unread/count'
DESCRIBE_DEVICES_API = 'https://eziotes.treeow.com.cn/api/resource/device/info'
SYNC_DEVICES_API = 'https://eziotes.treeow.com.cn/api/v3/device/otap/prop'
LIST_DEVICES_API = 'https://eziotes.treeow.com.cn/api/resource/v3/device/list/page'
LIST_HOME_API = 'https://eziotes.treeow.com.cn/api/resource/home/list'
GET_APP_VERSION_API = 'https://itunes.apple.com/cn/lookup?id=6505056723'
GET_IOS_VERSION_API = 'https://endoflife.date/api/v1/products/ios/releases/latest'

# Timing Constants
HEARTBEAT_INTERVAL = 10  # seconds
DEFAULT_POLL_INTERVAL = 5  # seconds

# Consecutive failed polls before a device is marked unavailable. This covers the
# cloud-unreachable case only; a device the cloud reports as offline is marked
# unavailable on the first poll via its `status` field.
MAX_POLL_FAILURES = 3

# Device online flag as returned by DESCRIBE_DEVICES_API's `data.status`.
# Verified against a device cut off from the cloud at the router: the flag goes
# 1 -> 2 about 75s after the device stops reporting, and back to 1 on reconnect.
# Offline is NOT 0, which is why callers must treat anything other than 1 as
# offline rather than comparing against a specific offline value.
DEVICE_STATUS_ONLINE = 1

# Other Constants
DEFAULT_PAGE_SIZE = 50
DEFAULT_APP_VERSION = '1.1.8'
DEFAULT_IOS_VERSION = '18.5'

# Storage Constants
STORAGE_VERSION = 1
STORAGE_KEY = "treeow"

# Event Constants
EVENT_DEVICE_CONTROL = 'device_control'
EVENT_DEVICE_DATA_CHANGED = 'device_data_changed'
# Whether the polling loop itself is running -- says nothing about any one device.
EVENT_GATEWAY_STATUS_CHANGED = 'gateway_status_changed'
# Whether one specific device is reachable. Carries 'deviceId' and 'status'.
EVENT_DEVICE_STATUS_CHANGED = 'device_status_changed'

# Token Management Constants
TOKEN_CHECK_INTERVAL = 3600  # 1 hour
TOKEN_REFRESH_THRESHOLD = 86400  # 1 day
TOKEN_RETRY_DELAY = 30  # seconds (initial retry delay for token operations)
TOKEN_RETRY_MULTIPLIER = 2  # retry delay multiplier
TOKEN_MAX_RETRY_DELAY = 300  # seconds (5 minutes max retry delay)