# ==============================================================================
# [파일 목적]
# 외부 MySQL 서버 없이 로컬 단위 테스트(Pytest)나 단독 컨테이너 실행 시 사용할 수 있는
# 스레드 안전(Thread-safe) 인메모리 당첨 기록 저장소 구현체입니다.
#
# [아키텍처 내 역할]
# - `WinningRecordRepository` 추상 인터페이스를 구현하여 Liskov 치환 원칙(LSP)을 만족합니다.
# - `threading.Lock`을 통해 멀티스레드 환경에서도 레이스 컨디션(Race Condition) 없이
#   Auto-Increment ID 부여와 최대 개수 유지(`max_items`)를 수행합니다.
# ==============================================================================
from __future__ import annotations

import threading
from collections import deque
from dataclasses import replace

from app.domain.models import WinningRecordEntity
from app.domain.repository import WinningRecordRepository


class InMemoryWinningRepository(WinningRecordRepository):
    """메모리 내부 `deque`에 5등 이상 당첨 기록을 보관하는 저장소 구현체입니다."""

    def __init__(self, max_items: int = 100) -> None:
        self._max_items: int = max_items
        self._records: deque[WinningRecordEntity] = deque(maxlen=max_items)
        self._next_id: int = 1
        self._lock = threading.Lock()
        self._healthy: bool = True

    def set_health_status(self, healthy: bool) -> None:
        """Kubernetes Liveness/Readiness Probe 장애 시뮬레이션을 위해 상태를 강제 변경합니다."""
        self._healthy = healthy

    def save(self, record: WinningRecordEntity) -> WinningRecordEntity:
        with self._lock:
            saved_entity = replace(record, id=self._next_id)
            self._next_id += 1
            # 최신 기록이 맨 앞(인덱스 0)에 오도록 appendleft 사용
            self._records.appendleft(saved_entity)
            return saved_entity

    def find_recent(self, limit: int = 50) -> list[WinningRecordEntity]:
        with self._lock:
            return list(self._records)[:limit]

    def count_all(self) -> int:
        with self._lock:
            return len(self._records)

    def clear_all(self) -> int:
        with self._lock:
            count = len(self._records)
            self._records.clear()
            return count

    def is_healthy(self) -> bool:
        return self._healthy

