from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """SkyMind application settings."""

    # Database
    DATABASE_URL: str = "postgresql://skymind:skymind_dev@localhost:5432/skymind"

    # API Keys
    OPENWEATHER_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    CESIUM_ION_TOKEN: str = ""

    # Simulation
    SIM_TICK_RATE_HZ: int = 10
    SIM_DEFAULT_DRONES: int = 5

    # DAA Parameters
    SEPARATION_HORIZONTAL_M: float = 100.0
    SEPARATION_VERTICAL_M: float = 30.0
    CPA_LOOKAHEAD_SEC: float = 120.0
    CPA_WARNING_SEC: float = 60.0

    # Altitude Layers
    ALTITUDE_MIN_M: float = 30.0
    ALTITUDE_MAX_M: float = 400.0
    ALTITUDE_LAYER_STEP_M: float = 10.0

    # Seoul metropolitan center (default simulation region)
    DEFAULT_CENTER_LAT: float = 37.5665
    DEFAULT_CENTER_LON: float = 126.9780

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
