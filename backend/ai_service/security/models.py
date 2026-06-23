from dataclasses import asdict, dataclass
from typing import Literal


Role = Literal["viewer", "maintainer", "admin"]


@dataclass(frozen=True)
class User:
    id: str
    email: str
    name: str
    role: Role
    tenant_id: str
    tenant_name: str = ""
    is_platform_admin: bool = False
    is_active: bool = True

    def to_public_dict(self) -> dict:
        return asdict(self)
