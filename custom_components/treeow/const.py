from homeassistant.const import Platform

DOMAIN = 'treeow'

SUPPORTED_PLATFORMS = [
    Platform.SELECT,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.FAN
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
RETRY_DELAY = 5  # seconds
RETRY_MULTIPLIER = 2  # retry delay multiplier
MAX_RETRY_DELAY = 60  # seconds

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
EVENT_GATEWAY_STATUS_CHANGED = 'gateway_status_changed'

# Token Management Constants
TOKEN_CHECK_INTERVAL = 3600  # 1 hour
TOKEN_REFRESH_THRESHOLD = 86400  # 1 day
TOKEN_RETRY_DELAY = 30  # seconds (initial retry delay for token operations)
TOKEN_RETRY_MULTIPLIER = 2  # retry delay multiplier
TOKEN_MAX_RETRY_DELAY = 300  # seconds (5 minutes max retry delay)