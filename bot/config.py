from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    bot_token: str

    support_username: str = "FominovTrade"
    po_register_url: str = "https://stocks-n-stuff.cash/register"
    po_register_video: str = "https://youtu.be/UpudE4bzVS4"
    bot_guide_video: str = "https://youtu.be/qFhXjZFwAog"
    how_find_id_url: str = "https://telegra.ph/REGISTRACIYA-04-10"

    # PocketOption verification
    pocketoption_min_deposit_usd: float = 50.0
    pocketoption_deposit_instruction_url: str = ""
    pocketoption_deposit_instruction_image_url: str = ""
    pocketoption_store_path: str = "./data/pocketoption_store.json"
    pocketoption_postback_secret: str = ""
    pocketoption_postback_path: str = "/pocketoption/postback"
    pocketoption_postback_port: int = 9009
    pocketoption_postback_host_port: int | None = None

    # Анализатор
    analyzer_backend: str = "stub"
    tv_exchange: str = "FX_IDC"
    tv_screener: str = "forex"
    tv_exchange_fallback: str = ""
    tv_cache_ttl_sec: int = 21600
    tv_cache_file: str = ".tv_cache.json"

    # OANDA
    oanda_api_token: str = ""
    oanda_env: str = "practice"
    oanda_candles_count: int = 200

    # CHARTIMG
    chartimg_api_key: str = ""
    chartimg_theme: str = "dark"
    chartimg_width: int = 900
    chartimg_height: int = 650
    chartimg_studies: str = "BB,MACD,Stoch,RSI"

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_timeout_sec: int = 25
    openai_temperature: float = 0.2

    # Формат сигнала
    signal_style: str = "default"

    # Логирование AI
    ai_debug: bool = False
    ai_log_level: str = "INFO"
    ai_log_save_json: bool = False
    ai_log_dir: str = "./data/ai_logs"

    bot_admin_ids: str = ""
    user_store_path: str = "./data/users.json"
    approved_store_path: str = "./data/approved_users.json"

    @property
    def admin_ids(self) -> list[int]:
        raw = (self.bot_admin_ids or "").strip()
        if not raw:
            return []
        result: list[int] = []
        for part in raw.split(","):
            part = part.strip()
            if part.isdigit():
                result.append(int(part))
        return result


settings = Settings()
