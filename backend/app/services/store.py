"""Short-lived, in-memory store for what the tour and chat need after a clone is gone."""

import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any

from app.core.errors import AppError
from app.core.limits import (
    ANALYSIS_TTL_SECONDS,
    MAX_STORED_ANALYSES,
    MAX_STORED_TOTAL_BYTES,
)


class AnalysisNotFound(AppError):
    status_code = 404
    code = "analysis_not_found"


@dataclass
class StoredAnalysis:
    analysis_id: str
    full_name: str
    description: str | None
    branch: str
    commit: str | None
    line_counts: dict[str, int]  # every kept file -> number of lines
    tour_material: Any = None  # app.services.tour.material.TourMaterial
    chat_index: Any = None  # app.services.chat.index.ChatIndex
    created: float = field(default_factory=time.monotonic)

    @property
    def size_bytes(self) -> int:
        size = sum(len(p) + 8 for p in self.line_counts)
        if self.chat_index is not None:
            size += self.chat_index.size_bytes
        if self.tour_material is not None:
            size += sum(len(f.text) for f in self.tour_material.files)
        return size

    def has_file(self, path: str) -> bool:
        return path in self.line_counts

    def has_dir(self, path: str) -> bool:
        prefix = path.rstrip("/") + "/"
        return any(p.startswith(prefix) for p in self.line_counts)


class AnalysisStore:
    def __init__(
        self,
        ttl: float = ANALYSIS_TTL_SECONDS,
        max_entries: int = MAX_STORED_ANALYSES,
        max_bytes: int = MAX_STORED_TOTAL_BYTES,
    ) -> None:
        self._ttl = ttl
        self._max_entries = max_entries
        self._max_bytes = max_bytes
        self._items: OrderedDict[str, StoredAnalysis] = OrderedDict()
        self._lock = threading.Lock()

    def _expire(self) -> None:
        now = time.monotonic()
        for key in [k for k, v in self._items.items() if now - v.created > self._ttl]:
            del self._items[key]

    def put(self, item: StoredAnalysis) -> None:
        with self._lock:
            self._expire()
            self._items[item.analysis_id] = item
            self._items.move_to_end(item.analysis_id)
            while len(self._items) > self._max_entries or (
                len(self._items) > 1
                and sum(v.size_bytes for v in self._items.values()) > self._max_bytes
            ):
                self._items.popitem(last=False)

    def get(self, analysis_id: str) -> StoredAnalysis:
        with self._lock:
            self._expire()
            item = self._items.get(analysis_id)
            if item is None:
                raise AnalysisNotFound(
                    "This analysis has expired. Analyse the repository again."
                )
            self._items.move_to_end(analysis_id)
            return item

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


analysis_store = AnalysisStore()
