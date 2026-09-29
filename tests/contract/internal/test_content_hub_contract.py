"""P06 Content Hub read-adapter contract tests.

PURPOSE: prove creative mapping restricts media to approved HTTPS storage hosts.
RESPONSIBILITY: exercise metadata validation; never fetch a media URL.
DEPENDENCIES: httpx2 mock transport and P06 adapter interfaces.
USED BY: P06 regression suite.
TESTED BY: this module.
"""

from __future__ import annotations

from uuid import uuid4

import httpx2
import pytest

from marketing_ai.core.errors import ApplicationError, ErrorCode
from marketing_ai.infrastructure.integrations.common import (
    InternalReadClientConfig,
    ReadOnlyInternalClient,
)
from marketing_ai.infrastructure.integrations.content_hub.client import ContentHubClient


def creative_payload(seller_id: object, creative_id: object, media_url: str) -> dict[str, object]:
    return {
        "seller_id": str(seller_id),
        "creative_id": str(creative_id),
        "name": "Creative",
        "media_url": media_url,
        "media_type": "image",
    }


@pytest.mark.anyio
async def test_content_hub_accepts_only_selected_creative_from_approved_https_host() -> None:
    seller_id, creative_id = uuid4(), uuid4()
    config = InternalReadClientConfig("https://content.internal.test", "marketing-ai", 1, 0)
    payload = creative_payload(
        seller_id, creative_id, "https://media.approved.test/path.jpg?signature=x"
    )
    async with httpx2.AsyncClient(
        transport=httpx2.MockTransport(lambda request: httpx2.Response(200, json=payload))
    ) as http_client:
        creative = await ContentHubClient(
            ReadOnlyInternalClient(service="content_hub", config=config, http_client=http_client),
            approved_storage_hosts=frozenset({"media.approved.test"}),
        ).get_creative(seller_id=seller_id, creative_id=creative_id)
    assert creative.media_type == "image"


@pytest.mark.anyio
async def test_content_hub_rejects_unapproved_or_non_https_media_without_fetching() -> None:
    seller_id, creative_id = uuid4(), uuid4()
    config = InternalReadClientConfig("https://content.internal.test", "marketing-ai", 1, 0)
    payload = creative_payload(
        seller_id, creative_id, "https://media.approved.test:8443/private.jpg"
    )
    async with httpx2.AsyncClient(
        transport=httpx2.MockTransport(lambda request: httpx2.Response(200, json=payload))
    ) as http_client:
        with pytest.raises(ApplicationError) as raised:
            await ContentHubClient(
                ReadOnlyInternalClient(
                    service="content_hub", config=config, http_client=http_client
                ),
                approved_storage_hosts=frozenset({"media.approved.test"}),
            ).get_creative(seller_id=seller_id, creative_id=creative_id)
    assert raised.value.code == ErrorCode.UPSTREAM_INVALID_RESPONSE


@pytest.mark.anyio
async def test_content_hub_hides_foreign_creative_existence() -> None:
    seller_id, foreign_seller_id, creative_id = uuid4(), uuid4(), uuid4()
    config = InternalReadClientConfig("https://content.internal.test", "marketing-ai", 1, 0)
    payload = creative_payload(
        foreign_seller_id, creative_id, "https://media.approved.test/path.jpg"
    )
    async with httpx2.AsyncClient(
        transport=httpx2.MockTransport(lambda request: httpx2.Response(200, json=payload))
    ) as http_client:
        with pytest.raises(ApplicationError) as raised:
            await ContentHubClient(
                ReadOnlyInternalClient(
                    service="content_hub", config=config, http_client=http_client
                ),
                approved_storage_hosts=frozenset({"media.approved.test"}),
            ).get_creative(seller_id=seller_id, creative_id=creative_id)
    assert raised.value.code == ErrorCode.RESOURCE_NOT_FOUND
