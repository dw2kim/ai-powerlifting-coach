"""Thin Hevy API client.

Auth: header `api-key: <HEVY_API_KEY>`. Base URL https://api.hevyapp.com/v1.
"""
from __future__ import annotations

import os
import time
from typing import Any, Iterator

import requests
from dotenv import load_dotenv

BASE_URL = "https://api.hevyapp.com/v1"
DEFAULT_PAGE_SIZE = 10
MAX_RETRIES = 3


class HevyError(RuntimeError):
    pass


class HevyClient:
    def __init__(self, api_key: str | None = None, timeout: float = 30.0):
        load_dotenv()
        self.api_key = api_key or os.environ.get("HEVY_API_KEY")
        if not self.api_key:
            raise HevyError(
                "HEVY_API_KEY not set. Copy .env.example to .env and paste your key."
            )
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {"api-key": self.api_key, "Accept": "application/json"}
        )

    def _request(self, method: str, path: str, **kwargs) -> Any:
        url = f"{BASE_URL}{path}"
        for attempt in range(MAX_RETRIES):
            resp = self.session.request(method, url, timeout=self.timeout, **kwargs)
            if resp.status_code == 429 or resp.status_code >= 500:
                if attempt == MAX_RETRIES - 1:
                    resp.raise_for_status()
                time.sleep(2**attempt)
                continue
            if not resp.ok:
                raise HevyError(f"{method} {path} -> {resp.status_code}: {resp.text}")
            return resp.json() if resp.content else None
        raise HevyError(f"{method} {path}: retries exhausted")

    def get(self, path: str, **params) -> Any:
        return self._request("GET", path, params=params)

    def post(self, path: str, body: dict) -> Any:
        return self._request("POST", path, json=body)

    def put(self, path: str, body: dict) -> Any:
        return self._request("PUT", path, json=body)

    def paginate(
        self, path: str, key: str, page_size: int = DEFAULT_PAGE_SIZE, **params
    ) -> Iterator[dict]:
        """Iterate items across all pages. `key` is the list field in the response
        (e.g. "workouts", "routines", "exercise_templates")."""
        page = 1
        while True:
            data = self.get(path, page=page, pageSize=page_size, **params)
            items = data.get(key, [])
            for item in items:
                yield item
            page_count = data.get("page_count", 1)
            if page >= page_count or not items:
                return
            page += 1
