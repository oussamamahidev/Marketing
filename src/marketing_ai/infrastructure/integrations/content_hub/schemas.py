"""Content Hub response schema with approved-host media URL validation.

PURPOSE: map selected creative metadata and prevent untrusted media URLs crossing the boundary.
RESPONSIBILITY: validate metadata and storage host; never fetch media or perform HTTP.
DEPENDENCIES: Python standard library and canonical application errors.
USED BY: ContentHubClient and ProductAdvertisingContextService.
TESTED BY: tests/contract/internal/test_content_hub_contract.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping
from urllib.parse import urlsplit
from uuid import UUID

from marketing_ai.core.errors import ApplicationError, ErrorCode


def _invalid() -> ApplicationError:
    return ApplicationError(ErrorCode.UPSTREAM_INVALID_RESPONSE)


@dataclass(frozen=True)
class CreativeMetadata:
    creative_id: UUID
    seller_id: UUID
    name: str
    media_url: str
    media_type: str

    @classmethod
    def from_payload(
        cls, payload: Mapping[str, object], *, approved_storage_hosts: frozenset[str]
    ) -> "CreativeMetadata":
        creative_id = payload.get("creative_id")
        seller_id = payload.get("seller_id")
        name = payload.get("name")
        media_url = payload.get("media_url")
        media_type = payload.get("media_type")
        if (
            not isinstance(creative_id, str)
            or not isinstance(seller_id, str)
            or not isinstance(name, str)
            or not name.strip()
            or not isinstance(media_url, str)
            or not isinstance(media_type, str)
            or not media_type.strip()
        ):
            raise _invalid()
        parsed = urlsplit(media_url)
        default_https_port = 443
        try:
            port = parsed.port
        except ValueError:
            raise _invalid() from None
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.hostname.lower() not in approved_storage_hosts
            or parsed.username is not None
            or parsed.password is not None
            or parsed.fragment
            or port not in {None, default_https_port}
        ):
            raise _invalid()
        try:
            return cls(
                creative_id=UUID(creative_id),
                seller_id=UUID(seller_id),
                name=name,
                media_url=media_url,
                media_type=media_type,
            )
        except ValueError:
            raise _invalid() from None
