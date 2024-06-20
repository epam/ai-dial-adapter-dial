import re
from typing import Self

from pydantic import BaseModel


class AppData(BaseModel):
    user_bucket: str
    app_name: str

    @classmethod
    def parse(cls, appdata: str) -> Self:
        match = re.match(r"^(.+)/appdata/(.+)$", appdata)
        if not match:
            raise ValueError("Invalid appdata format")

        user_bucket, app_name = match.groups()
        return cls(user_bucket=user_bucket, app_name=app_name)
