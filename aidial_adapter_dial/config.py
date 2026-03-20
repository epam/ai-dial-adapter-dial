from dataclasses import dataclass

from aidial_adapter_dial.utils.env import get_env, get_env_list


@dataclass
class AppConfig:
    local_dial_url: str
    headers_to_proxy: list[str]

    @classmethod
    def from_env(cls) -> "AppConfig":
        return cls(
            local_dial_url=get_env("DIAL_URL"),
            headers_to_proxy=get_env_list("HEADERS_TO_PROXY", ["Accept"]),
        )
