"""Connector utilities for instantiating Nox transports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .transport import LLMTransport

__all__ = ["ConnectorConfig", "NoxConnector", "build_connector"]


@dataclass(slots=True)
class ConnectorConfig:
    """Configuration bundle describing how Nox should connect to an LLM."""

    url: str
    api_key: Optional[str] = None


class NoxConnector:
    """Factory responsible for creating the transport that backs ChatClient."""

    def __init__(self, config: ConnectorConfig) -> None:
        self.config = config

    def connect(self) -> LLMTransport:
        """Return an ``LLMTransport`` instance configured for Nox."""

        return LLMTransport(self.config.url, self.config.api_key)


def build_connector(*, url: str, api_key: Optional[str]) -> NoxConnector:
    """Return the default connector used by Nox.

    Edit this function (or replace ``NoxConnector``) to swap out the
    transport implementation application-wide without touching other modules.
    """

    return NoxConnector(ConnectorConfig(url=url, api_key=api_key))
