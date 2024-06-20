import json
from typing import Any, List


def set_at_path(obj: dict, keys: List[str], value: Any) -> None:
    assert isinstance(obj, dict)

    key = keys[0]
    rest = keys[1:]

    if len(keys) == 1:
        obj[key] = value
        return

    if key not in obj:
        obj[key] = {}

    set_at_path(obj[key], rest, value)


def get_at_path(obj: dict, keys: List[str]) -> Any:
    assert isinstance(obj, dict)

    key = keys[0]
    rest = keys[1:]

    if key not in obj:
        obj[key] = {}

    if len(keys) == 1:
        return obj[key]

    return get_at_path(obj[key], rest)


def cleanup(obj):
    """Remove None values and empty dictionaries from the object recursively."""

    if isinstance(obj, dict):
        ret = {}
        for k, v in obj.items():
            v = cleanup(v)
            if v not in [{}, None]:
                ret[k] = v
        return ret

    if isinstance(obj, list):
        return [cleanup(item) for item in obj]

    return obj


class CoreConfig:
    obj: dict

    def __init__(self, obj: dict):
        self.obj = obj

    def __setitem__(self, path: str, value: Any) -> None:
        set_at_path(self.obj, path.split("."), value)

    def __getitem__(self, path: str) -> Any:
        return get_at_path(self.obj, path.split("."))

    def add_application(self, name: str, app: dict):
        self["applications"][name] = cleanup(app)
        self["roles.default.limits"][name] = {}

    def add_model(self, name: str, model: dict):
        self["models"][name] = cleanup(model)
        self["roles.default.limits"][name] = {}

    def print(self):
        print(json.dumps(self.obj, indent=2))
