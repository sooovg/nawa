"""User and project isolation (ROADMAP P7-05, ADR-0009).

Every read and write names a ``Principal`` (user and project). Until OD-12 decides the privacy policy for personal
memory, only the three fixed synthetic users are accepted; any other user id is refused, so real user data cannot enter
the store through this API. The store keeps one physical partition per (user, project), so a query can only touch the
caller's partition; ``can_access`` is a second, independent check on every returned item.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

SYNTHETIC_USERS = ("user_alpha", "user_beta", "user_gamma")
DEFAULT_PROJECT = "project_default"
_PROJECT = re.compile(r"^project_[a-z0-9_]{1,40}$")
OD12_NOTICE = ("OD-12 (personal memory privacy policy) is OPEN: only synthetic users are allowed; "
               "no real user data may be stored before the owner decides it.")


class IsolationError(PermissionError):
    pass


@dataclass(frozen=True, order=True)
class Principal:
    user_id: str
    project_id: str = DEFAULT_PROJECT

    def __post_init__(self) -> None:
        if self.user_id not in SYNTHETIC_USERS:
            raise IsolationError("user_not_synthetic: " + OD12_NOTICE)
        if not isinstance(self.project_id, str) or not _PROJECT.match(self.project_id):
            raise IsolationError("project_id_invalid")

    @property
    def partition(self) -> tuple[str, str]:
        return (self.user_id, self.project_id)


def can_access(principal: Principal, item: object) -> bool:
    """Owner-only access: the item's owner and project must equal the caller's."""
    return getattr(item, "owner", None) == principal.user_id and getattr(item, "project", None) == principal.project_id


def acl(item: object) -> dict:
    """Access list of an item. Sharing with other users is not supported before OD-12."""
    return {"owner": item.owner, "project": item.project, "readers": [item.owner], "writers": [item.owner],
            "sharing": "disabled_until_OD-12"}
