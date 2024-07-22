from typing import List, Mapping


def censor_ci_dict(d: Mapping[str, str], keys: List[str]) -> dict:
    key_set = {k.lower() for k in keys}
    return {
        k: v if k.lower() not in key_set else "**********" for k, v in d.items()
    }
