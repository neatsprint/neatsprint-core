from neatsprint_lib.settings import ServiceSettings


class Settings(ServiceSettings):
    service_name: str = "core"
    api_prefix: str = "core"
    bootstrap_token: str | None = None
    outbox_enabled: bool = True
    outbox_stream: str = "neatsprint.events"


settings = Settings()
