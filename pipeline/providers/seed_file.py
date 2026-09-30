"""
pipeline/providers/seed_file.py
───────────────────────────────
Demo-only Seed File Provider.
Exclusively used when --demo-mode flag is explicitly passed.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from pipeline.providers.base import DiscoveryProvider

logger = logging.getLogger(__name__)


class SeedFileProvider(DiscoveryProvider):
    """Historical demo seed provider (used ONLY in --demo-mode)."""

    def __init__(self, seed_path: Path) -> None:
        self.seed_path = seed_path

    @property
    def name(self) -> str:
        return "seed_file_demo"

    def discover(self, target_config: Dict[str, Any], max_leads: int) -> List[Dict[str, Any]]:
        if not self.seed_path.exists():
            logger.error("Seed file not found: %s", self.seed_path)
            return []

        with self.seed_path.open(encoding="utf-8") as fh:
            raw = json.load(fh)

        results = []
        for item in raw[:max_leads]:
            c = dict(item)
            c["discovery_source"] = self.name
            c["discovery_query"] = "demo_seed_dataset"
            c["source_url"] = item.get("website", "")
            c["discovered_at"] = datetime.now(timezone.utc).isoformat()
            c["raw_source_reference"] = str(self.seed_path)
            results.append(c)

        logger.info("SeedFileProvider (Demo Mode) loaded %d records", len(results))
        return results
