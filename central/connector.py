"""Connector utilities for instantiating Central transports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .transport import LLMTransport

__all__ = ["ConnectorConfig", "CentralConnector", "build_connector"]


@dataclass(slots=True)
class ConnectorConfig:
    """Configuration bundle describing how Central should connect to an LLM."""

    url: str
    api_key: Optional[str] = None


class CentralConnector:
    """Factory responsible for creating the transport that backs ChatClient."""

    def __init__(self, config: ConnectorConfig) -> None:
        self.config = config

    def connect(self) -> LLMTransport:
        """Return an ``LLMTransport`` instance configured for Central."""

        return LLMTransport(self.config.url, self.config.api_key)


def build_connector(*, url: str, api_key: Optional[str]) -> CentralConnector:
    """Return the default connector used by Central.

    Edit this function (or replace ``CentralConnector``) to swap out the
    transport implementation application-wide without touching other modules.
    """

    return CentralConnector(ConnectorConfig(url=url, api_key=api_key))

