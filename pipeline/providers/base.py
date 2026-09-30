"""
pipeline/providers/base.py
───────────────────────────
Abstract Base Class for Discovery Providers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class DiscoveryProvider(ABC):
    """Abstract interface for lead discovery providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier."""
        pass

    @abstractmethod
    def discover(self, target_config: Dict[str, Any], max_leads: int) -> List[Dict[str, Any]]:
        """
        Execute discovery query based on target configuration.

        Returns list of raw company discovery dicts with mandatory provenance:
          - company
          - website
          - industry
          - location
          - discovery_source
          - discovery_query
          - source_url
          - discovered_at
        """
        pass
