# ==============================================================================
# [파일 목적]
# 5등 이상 당첨 기록을 영속화(Persistence)하기 위한 저장소 추상 인터페이스(Repository ABC)입니다.
#
# [아키텍처 내 역할 & 디자인 패턴]
# - Repository Pattern & Dependency Inversion Principle (DIP, 의존성 역전 원칙):
#   Domain 및 Application 계층은 데이터가 MySQL(`lotto_winning_records`)에 저장되는지,
#   인메모리에 저장되는지 전혀 알 필요가 없습니다.
#   고수준 모듈(Domain/Application)이 저수준 모듈(Infrastructure SQLAlchemy)에 의존하지 않고,
#   양쪽 모두 이 추상 인터페이스(`WinningRecordRepository`)에 의존하도록 설계합니다.
# ==============================================================================
from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.models import WinningRecordEntity


class WinningRecordRepository(ABC):
    """5등 이상 당첨 기록을 관리하는 저장소 인터페이스입니다."""

    @abstractmethod
    def save(self, record: WinningRecordEntity) -> WinningRecordEntity:
        """새로운 5등 이상 당첨 기록을 저장하고, 생성된 ID가 부여된 엔티티를 반환합니다."""

    @abstractmethod
    def find_recent(self, limit: int = 50) -> list[WinningRecordEntity]:
        """최신 당첨 기록을 ID 역순(최신순)으로 최대 `limit`개까지 조회합니다."""

    @abstractmethod
    def count_all(self) -> int:
        """저장된 총 당첨 기록(5등 이상) 건수를 반환합니다."""

    @abstractmethod
    def clear_all(self) -> int:
        """저장된 모든 당첨 기록을 초기화하고 삭제된 건수를 반환합니다."""

    @abstractmethod
    def is_healthy(self) -> bool:
        """저장소(예: MySQL DB 커넥션)가 정상적으로 읽기/쓰기 가능한 상태인지 확인합니다.

        Kubernetes `readinessProbe` (`/api/v1/health/ready`)에서 DB 연결 상태를 점검할 때 호출됩니다.
        """

