from __future__ import annotations

import logging

import requests

logger = logging.getLogger(__name__)


class BackendClient:
    def __init__(self, backend_url: str, api_key: str | None = None) -> None:
        self.backend_url = backend_url.rstrip("/")
        self.api_key = api_key

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            return {}
        return {"X-API-Key": self.api_key}

    def post(self, path: str, payload: dict) -> dict:
        response = requests.post(f"{self.backend_url}{path}", json=payload, headers=self._headers(), timeout=15)
        logger.info("OUTPOST agent POST %s -> %s", path, response.status_code)
        if response.status_code >= 400:
            logger.warning("OUTPOST agent POST %s failed: %s", path, response.text[:500])
        response.raise_for_status()
        return response.json()

    def get(self, path: str) -> list | dict:
        response = requests.get(f"{self.backend_url}{path}", headers=self._headers(), timeout=15)
        logger.info("OUTPOST agent GET %s -> %s", path, response.status_code)
        if response.status_code >= 400:
            logger.warning("OUTPOST agent GET %s failed: %s", path, response.text[:500])
        response.raise_for_status()
        return response.json()
