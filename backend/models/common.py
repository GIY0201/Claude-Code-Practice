"""공용 데이터 타입 및 열거형."""

from enum import Enum
from pydantic import BaseModel, Field


class Position3D(BaseModel):
    """WGS84 3D 좌표."""
    lat: float = Field(..., ge=-90, le=90, description="위도 (degrees)")
    lon: float = Field(..., ge=-180, le=180, description="경도 (degrees)")
    alt_m: float = Field(0.0, ge=0, description="고도 (meters)")


class Velocity3D(BaseModel):
    """3D 속도 벡터."""
    vx: float = Field(0.0, description="동서 방향 속도 (m/s)")
    vy: float = Field(0.0, description="남북 방향 속도 (m/s)")
    vz: float = Field(0.0, description="수직 속도 (m/s)")


class DroneType(str, Enum):
    MULTIROTOR = "MULTIROTOR"
    FIXED_WING = "FIXED_WING"
    VTOL = "VTOL"


class DroneStatus(str, Enum):
    IDLE = "IDLE"
    TAXIING = "TAXIING"
    AIRBORNE = "AIRBORNE"
    HOLDING = "HOLDING"
    EMERGENCY = "EMERGENCY"
    LANDED = "LANDED"


class PlanStatus(str, Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class Priority(str, Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    EMERGENCY = "EMERGENCY"


class MissionType(str, Enum):
    DELIVERY = "DELIVERY"
    SURVEILLANCE = "SURVEILLANCE"
    INSPECTION = "INSPECTION"
    EMERGENCY_RESPONSE = "EMERGENCY_RESPONSE"


class WaypointType(str, Enum):
    DEPARTURE = "DEPARTURE"
    ENROUTE = "ENROUTE"
    APPROACH = "APPROACH"
    ARRIVAL = "ARRIVAL"
    HOLDING = "HOLDING"
    EMERGENCY = "EMERGENCY"


class ZoneType(str, Enum):
    RESTRICTED = "RESTRICTED"
    CONTROLLED = "CONTROLLED"
    FREE = "FREE"
    EMERGENCY_ONLY = "EMERGENCY_ONLY"


class GPSFixType(str, Enum):
    NO_FIX = "NO_FIX"
    FIX_2D = "2D"
    FIX_3D = "3D"
    RTK = "RTK"


class MotorStatus(str, Enum):
    OK = "OK"
    WARNING = "WARNING"
    FAILURE = "FAILURE"


class AlertLevel(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class Alert(BaseModel):
    """드론 경고."""
    level: AlertLevel
    message: str
    timestamp: str | None = None
