from neatsprint_lib.settings import ServiceSettings


class Settings(ServiceSettings):
    service_name: str = "core"
    api_prefix: str = "core"


settings = Settings()
