# ==============================================================================
# [파일 목적]
# `MySQLWinningRepository` ORM 매핑(`id`, `first_num`~`sixth_num`, `rank`),
# `LottoGameService` 유스케이스(5등 이상만 DB 저장), 그리고 FastAPI REST API 엔드포인트를
# 검증하는 통합 테스트(Integration Test) 모듈입니다.
# ==============================================================================
from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.application.service import LottoGameService
from app.core.config import AppConfig, DatabaseConfig, StorageBackendType
from app.domain.models import LottoRank, LottoTicket, WinningRecordEntity
from app.domain.strategies import RandomNumberSource, WinningDrawGenerator
from app.infrastructure.mysql_repository import MySQLWinningRepository
from app.main import create_app


class FixedWinningRandomSource(RandomNumberSource):
    """당첨 번호가 항상 [1, 2, 3, 4, 5, 6] + 보너스 [7]이 나오도록 고정하는 테스트용 난수기입니다."""

    def sample(self, population: Sequence[int], k: int) -> list[int]:
        return list(population)[:k]


def _create_sqlite_backed_mysql_repo() -> MySQLWinningRepository:
    """MySQLWinningRepository의 SQLAlchemy ORM 쿼리(`lotto_winning_records` 테이블 및 `rank` 컬럼)를
    검증하기 위해 인메모리 SQLite 엔진을 주입한 저장소를 생성합니다.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    repo = MySQLWinningRepository(engine=engine)
    repo.init_schema()
    return repo


def _create_test_config() -> AppConfig:
    return AppConfig(
        app_name="Vibe Lotto Test",
        app_version="1.0.0-test",
        app_env="test",
        pod_hostname="test-pod-alpha-1",
        storage_backend=StorageBackendType.MYSQL,
        db_config=DatabaseConfig(
            host="localhost",
            port=3306,
            user="root",
            password="pw",
            database="vibe_lotto",
        ),
        max_history_items=50,
        static_dir=Path("/nonexistent"),
    )


class TestSQLAlchemyRepositoryIntegration:
    """`MySQLWinningRepository`의 테이블 생성, INSERT, 최신순 SELECT, DELETE 동작을 검증합니다."""

    def test_save_and_find_recent_orders_by_id_desc(self) -> None:
        repo = _create_sqlite_backed_mysql_repo()

        rec1 = WinningRecordEntity.create_new(LottoTicket([1, 2, 3, 10, 20, 30]), LottoRank.FIFTH)
        rec2 = WinningRecordEntity.create_new(LottoTicket([1, 2, 3, 4, 5, 6]), LottoRank.FIRST)

        saved1 = repo.save(rec1)
        saved2 = repo.save(rec2)

        assert saved1.id == 1
        assert saved2.id == 2
        assert repo.count_all() == 2

        recent = repo.find_recent(limit=10)
        assert len(recent) == 2
        # 최신 저장된 ID=2(1등)가 먼저 조회되어야 함
        assert recent[0].id == 2
        assert recent[0].rank == LottoRank.FIRST
        assert recent[0].ticket.to_int_tuple() == (1, 2, 3, 4, 5, 6)
        assert recent[1].id == 1
        assert recent[1].rank == LottoRank.FIFTH

        deleted = repo.clear_all()
        assert deleted == 2
        assert repo.count_all() == 0


class TestFastAPIEndpoints:
    """FastAPI 엔드포인트(`POST /api/v1/lotto/draw`, `GET /api/v1/lotto/history`, `/health/*`)를 검증합니다."""

    def _build_client(self) -> TestClient:
        repo = _create_sqlite_backed_mysql_repo()
        fixed_rng = FixedWinningRandomSource()
        service = LottoGameService(
            repository=repo,
            draw_generator=WinningDrawGenerator(rng=fixed_rng),
            rng=fixed_rng,
        )
        app = create_app(
            config=_create_test_config(),
            repository=repo,
            lotto_service=service,
        )
        return TestClient(app)

    def test_draw_winning_fifth_or_higher_is_saved_to_db(self) -> None:
        client = self._build_client()

        # 당첨 번호가 [1, 2, 3, 4, 5, 6] + 보너스 7로 고정되어 있을 때,
        # 수동으로 [1, 2, 3, 40, 41, 42]를 보내면 3개 일치 -> 5등(FIFTH) 당첨 및 DB 저장!
        res = client.post(
            "/api/v1/lotto/draw",
            json={"mode": "MANUAL", "selected_numbers": [42, 1, 40, 2, 41, 3]},
        )
        assert res.status_code == 200
        assert res.headers["X-Pod-Hostname"] == "test-pod-alpha-1"

        body = res.json()
        assert body["rank"]["code"] == "FIFTH"
        assert body["rank"]["tier"] == 5
        assert body["rank"]["is_winning"] is True
        assert body["saved_record_id"] == 1
        assert body["matched_numbers"] == [1, 2, 3]
        assert body["user_numbers"] == [1, 2, 3, 40, 41, 42]

        # 우측 명예의 전당(History) 조회 시 방금 저장된 5등 기록이 존재해야 함
        hist_res = client.get("/api/v1/lotto/history")
        assert hist_res.status_code == 200
        hist_body = hist_res.json()
        assert hist_body["total_count"] == 1
        item = hist_body["items"][0]
        assert item["id"] == 1
        assert item["first_num"] == 1
        assert item["sixth_num"] == 42
        assert item["rank"] == 5

    def test_draw_miss_is_not_saved_to_db(self) -> None:
        client = self._build_client()

        # [10, 11, 12, 13, 14, 15] -> 0개 일치(낙첨) -> DB에 저장되지 않아야 함
        res = client.post(
            "/api/v1/lotto/draw",
            json={"mode": "MANUAL", "selected_numbers": [10, 11, 12, 13, 14, 15]},
        )
        assert res.status_code == 200
        body = res.json()
        assert body["rank"]["code"] == "MISS"
        assert body["saved_record_id"] is None

        hist_res = client.get("/api/v1/lotto/history")
        assert hist_res.json()["total_count"] == 0

    def test_domain_validation_error_returns_400_with_error_code(self) -> None:
        client = self._build_client()

        # 범위 초과 번호(99) 입력 시 400 Bad Request 및 INVALID_NUMBER_RANGE 반환
        res = client.post(
            "/api/v1/lotto/draw",
            json={"mode": "MANUAL", "selected_numbers": [1, 2, 3, 4, 5, 99]},
        )
        assert res.status_code == 400
        err = res.json()
        assert err["error_code"] == "INVALID_NUMBER_RANGE"
        assert err["pod_hostname"] == "test-pod-alpha-1"

    def test_health_probes(self) -> None:
        client = self._build_client()
        live_res = client.get("/api/v1/health/live")
        ready_res = client.get("/api/v1/health/ready")
        assert live_res.status_code == 200
        assert ready_res.status_code == 200
        assert ready_res.json()["status"] == "READY"

