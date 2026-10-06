"""Constants for Home Assistant Water Leak Detection."""

from __future__ import annotations

from enum import StrEnum

from homeassistant.const import Platform

DOMAIN = "water_leak_detection"
NAME = "Home Assistant Water Leak Detection"
VERSION = "0.2.0"

PLATFORMS: tuple[Platform, ...] = (
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
    Platform.NUMBER,
)

CONF_FLOW_ENTITY = "flow_entity"
CONF_TOTAL_ENTITY = "total_entity"
CONF_SOURCE_MODE = "source_mode"
CONF_SOURCE_DEVICE = "source_device"
CONF_NOTIFICATION_RECIPIENTS = "notification_recipients"

RECIPIENT_ID = "id"
RECIPIENT_NAME = "name"
RECIPIENT_NOTIFY_SERVICE = "notify_service"
RECIPIENT_TRACKER_ENTITY = "tracker_entity"
RECIPIENT_CRITICAL_ENABLED = "critical_enabled"
RECIPIENT_ALLOW_GLOBAL_ACK = "allow_global_ack"
RECIPIENT_TRUSTED_STATIONARY = "trusted_stationary"
RECIPIENT_TOKEN = "token"

CONF_SLOW_ENABLED = "slow_enabled"
CONF_SLOW_THRESHOLD_LPH = "slow_threshold_lph"
CONF_SLOW_DETECTION_MIN = "slow_detection_minutes"
CONF_SLOW_RESET_MIN = "slow_reset_minutes"
CONF_LOW_ENABLED = "low_enabled"
CONF_LOW_THRESHOLD_LPH = "low_threshold_lph"
CONF_LOW_DETECTION_MIN = "low_detection_minutes"
CONF_LOW_QUIET_LPH = "low_quiet_lph"
CONF_LOW_RESET_MIN = "low_reset_minutes"
CONF_HIGH_THRESHOLD_LPH = "high_threshold_lph"
CONF_HIGH_DETECTION_MIN = "high_detection_minutes"
CONF_HIGH_VOLUME_L = "high_volume_l"
CONF_HIGH_QUIET_LPH = "high_quiet_lph"
CONF_HIGH_RESET_MIN = "high_reset_minutes"
CONF_BURST_THRESHOLD_LPH = "burst_threshold_lph"
CONF_BURST_DETECTION_SEC = "burst_detection_seconds"
CONF_BURST_RESET_LPH = "burst_reset_lph"
CONF_BURST_RESET_SEC = "burst_reset_seconds"
CONF_BYPASS_DEFAULT_MIN = "bypass_default_minutes"

CONF_SHUTOFF_SLOW = "shutoff_slow"
CONF_SHUTOFF_LOW = "shutoff_low"
CONF_SHUTOFF_HIGH = "shutoff_high"
CONF_SHUTOFF_BURST = "shutoff_burst"

DEFAULT_SLOW_ENABLED = True
DEFAULT_SLOW_THRESHOLD_LPH = 3.0
DEFAULT_SLOW_DETECTION_MIN = 60.0
DEFAULT_SLOW_RESET_MIN = 10.0
DEFAULT_LOW_ENABLED = True
DEFAULT_LOW_THRESHOLD_LPH = 150.0
DEFAULT_LOW_DETECTION_MIN = 60.0
DEFAULT_LOW_QUIET_LPH = 20.0
DEFAULT_LOW_RESET_MIN = 7.0
DEFAULT_HIGH_THRESHOLD_LPH = 600.0
DEFAULT_HIGH_DETECTION_MIN = 45.0
DEFAULT_HIGH_VOLUME_L = 500.0
DEFAULT_HIGH_QUIET_LPH = 100.0
DEFAULT_HIGH_RESET_MIN = 5.0
DEFAULT_BURST_THRESHOLD_LPH = 2000.0
DEFAULT_BURST_DETECTION_SEC = 30.0
DEFAULT_BURST_RESET_LPH = 500.0
DEFAULT_BURST_RESET_SEC = 60.0
DEFAULT_BYPASS_DEFAULT_MIN = 240.0

DEFAULT_SHUTOFF_SLOW = False
DEFAULT_SHUTOFF_LOW = False
DEFAULT_SHUTOFF_HIGH = False
DEFAULT_SHUTOFF_BURST = True

STORAGE_VERSION = 1
STORAGE_KEY_PREFIX = f"{DOMAIN}.runtime"
TICK_SECONDS = 10

SERVICE_START_HIGH_FLOW_BYPASS = "start_high_flow_bypass"
SERVICE_CANCEL_HIGH_FLOW_BYPASS = "cancel_high_flow_bypass"
ATTR_CONFIG_ENTRY_ID = "config_entry_id"
ATTR_DURATION_MINUTES = "duration_minutes"

EVENT_LEAK_STARTED = f"{DOMAIN}_event_started"
EVENT_LEAK_ENDED = f"{DOMAIN}_event_ended"
EVENT_SHUTOFF_REQUESTED = f"{DOMAIN}_shutoff_requested"
EVENT_SHUTOFF_CLEARED = f"{DOMAIN}_shutoff_cleared"
EVENT_ACKNOWLEDGED = f"{DOMAIN}_acknowledged"
EVENT_ACK_REJECTED = f"{DOMAIN}_ack_rejected"

MOBILE_ACTION_EVENT = "mobile_app_notification_action"
ACTION_PREFIX = "WLD"
ACTION_MUTE = "MUTE"
ACTION_ACK_ALL = "ACK_ALL"


class DetectorKind(StrEnum):
    """Leak detector kinds ordered by severity."""

    SLOW_LEAK = "slow_leak"
    LOW_FLOW = "low_flow"
    HIGH_FLOW = "high_flow"
    BURST_LEAK = "burst_leak"


DETECTOR_PRIORITY: tuple[DetectorKind, ...] = (
    DetectorKind.SLOW_LEAK,
    DetectorKind.LOW_FLOW,
    DetectorKind.HIGH_FLOW,
    DetectorKind.BURST_LEAK,
)


class DetectorPhase(StrEnum):
    """Runtime phase of one detector."""

    IDLE = "idle"
    MONITORING = "monitoring"
    ACTIVE = "active"
