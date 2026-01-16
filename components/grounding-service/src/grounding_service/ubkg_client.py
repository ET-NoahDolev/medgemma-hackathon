"""UBKG REST client stub."""

from typing import List


class UbkgClient:
    def __init__(self, base_url: str = "https://ubkg-api.xconsortia.org") -> None:
        self.base_url = base_url

    def search_snomed(self, query: str, limit: int = 5) -> List[dict]:
        """Search SNOMED concepts via UBKG."""
        return []
