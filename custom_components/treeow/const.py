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

DEFAULT_POLL_INTERVAL = 5  # seconds
