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

# Storage Constants
STORAGE_VERSION = 1
STORAGE_KEY = "treeow"