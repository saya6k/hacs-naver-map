"""Base tool class for naver_map LLM tools."""

from __future__ import annotations

from typing import Any, cast

from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm

from custom_components.naver_map.const import DOMAIN
from custom_components.naver_map.services import NaverClients

from .const import SOURCE


class BaseNaverTool(llm.Tool):
    """Reads its bound config entry's API clients via hass.data."""

    integration = DOMAIN
    annotations = llm.ToolAnnotations(
        read_only=True, destructive=False, idempotent=True, open_world=True
    )

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        super().__init__()
        self.hass = hass
        self.entry_id = entry_id

    @property
    def clients(self) -> NaverClients:
        store = cast("dict[str, Any]", self.hass.data.get(DOMAIN, {}).get(self.entry_id, {}))
        return cast(NaverClients, store["clients"])

    def envelope(self, **fields: Any) -> llm.ToolResult:
        """Build a standard response envelope."""
        out: dict[str, Any] = {"source": SOURCE}
        out.update(fields)
        return llm.ToolResult(data=out)
