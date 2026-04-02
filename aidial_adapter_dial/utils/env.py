import os
from typing import List, Optional


def get_env(name: str, err_msg: Optional[str] = None) -> str:
    val = os.getenv(name)
    if val is not None:
        return val

    raise Exception(err_msg or f"{name} env variable is not set")


def get_env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).lower() == "true"


def get_env_list(name: str, default: List[str] | None = None) -> List[str]:
    val = os.getenv(name)
    if val is not None:
        return val.split(",")
    return default or []
