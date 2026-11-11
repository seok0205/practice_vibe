# ==============================================================================
# [파일 목적]
# MySQL 8.0 데이터베이스와 연동되는 SQLAlchemy 2.0 ORM 테이블 모델 및
# `MySQLWinningRepository` 구현체를 정의하는 인프라스트럭처 모듈입니다.
#
# [아키텍처 내 역할 & DB 스키마 설계]
# 1. 테이블명: `lotto_winning_records`
# 2. 컬럼 구성 (사용자 요구사항 100% 반영):
#    - `id` (BIGINT, PRIMARY KEY, AUTO_INCREMENT): 고유 식별자 및 클러스터드 인덱스
#    - `first_num` ~ `sixth_num` (SMALLINT/TINYINT): 오름차순 정렬된 6개 선택 번호
#    - `rank` (SMALLINT/TINYINT): 당첨 등수 (1~5).
#      * 주의: MySQL 8.0에서 `RANK`는 윈도우 함수 예약어이므로 SQLAlchemy `Column("rank", ...)`와
#        `quote=True` 옵션을 통해 SQL 생성 시 백틱(`` `rank` ``)으로 안전하게 감싸도록 처리했습니다.
#    - `created_at` (DATETIME): 당첨 시각
# 3. 인덱스 전략:
#    - 최신순 조회(`ORDER BY id DESC LIMIT N`)만 수행하므로 Primary Key(`id`) 외에
#      불필요한 보조 인덱스(Secondary Index)를 만들지 않아 INSERT 성능을 극대화합니다.
# ==============================================================================
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Engine,
    SmallInteger,
    create_engine,
    delete,
    func,
    select,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import DatabaseConfig
from app.core.exceptions import StorageOperationError
from app.domain.models import LottoRank, LottoTicket, WinningRecordEntity
from app.domain.repository import WinningRecordRepository


class Base(DeclarativeBase):
    """SQLAlchemy 2.0 선언적 ORM 모델의 기반 클래스입니다."""


class WinningRecordORM(Base):
    """MySQL `lotto_winning_records` 테이블과 매핑되는 ORM 엔티티 클래스입니다.

    도메인 계층(`WinningRecordEntity`)이 SQLAlchemy에 오염되지 않도록
    Data Mapper 패턴을 통해 인프라 계층 내부에서만 사용되고 도메인 엔티티로 변환됩니다.
    """

    __tablename__ = "lotto_winning_records"

    id = Column(
        BigInteger().with_variant(SmallInteger, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    first_num = Column(SmallInteger, nullable=False)
    second_num = Column(SmallInteger, nullable=False)
    third_num = Column(SmallInteger, nullable=False)
    fourth_num = Column(SmallInteger, nullable=False)
    fifth_num = Column(SmallInteger, nullable=False)
    sixth_num = Column(SmallInteger, nullable=False)
    # MySQL 8.0 예약어인 `rank` 컬럼을 백틱(`rank`)으로 안전하게 이스케이프하기 위해 quote=True를 지정합니다.
    rank = Column("rank", SmallInteger, nullable=False, quote=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def to_domain(self) -> WinningRecordEntity:
        """DB ORM 레코드를 순수 도메인 엔티티(`WinningRecordEntity`)로 변환합니다."""
        raw_created_at: datetime = self.created_at  # type: ignore[assignment]
        if raw_created_at.tzinfo is None:
            raw_created_at = raw_created_at.replace(tzinfo=timezone.utc)

        return WinningRecordEntity(
            id=int(self.id),  # type: ignore[arg-type]
            ticket=LottoTicket(
                [
                    int(self.first_num),  # type: ignore[arg-type]
                    int(self.second_num),  # type: ignore[arg-type]
                    int(self.third_num),  # type: ignore[arg-type]
                    int(self.fourth_num),  # type: ignore[arg-type]
                    int(self.fifth_num),  # type: ignore[arg-type]
                    int(self.sixth_num),  # type: ignore[arg-type]
                ]
            ),
            rank=LottoRank.from_tier(int(self.rank)),  # type: ignore[arg-type]
            created_at=raw_created_at,
        )

    @classmethod
    def from_domain(cls, entity: WinningRecordEntity) -> WinningRecordORM:
        """순수 도메인 엔티티(`WinningRecordEntity`)를 DB 저장용 ORM 인스턴스로 변환합니다."""
        n1, n2, n3, n4, n5, n6 = entity.ticket.to_int_tuple()
        return cls(
            first_num=n1,
            second_num=n2,
            third_num=n3,
            fourth_num=n4,
            fifth_num=n5,
            sixth_num=n6,
            rank=entity.rank.tier,
            created_at=entity.created_at,
        )


class MySQLWinningRepository(WinningRecordRepository):
    """SQLAlchemy 2.0을 사용하여 MySQL `lotto_winning_records` 테이블을 관리하는 저장소 구현체입니다.

    Kubernetes 운영 고려사항:
        - `pool_pre_ping=True`: MySQL 파드가 재시작되거나 네트워크 유휴 시간(wait_timeout)이 지나
          커넥션이 끊어졌을 때, 쿼리 실행 전 자동으로 핑을 보내 죽은 커넥션을 교체합니다.
        - `pool_recycle=1800`: 30분마다 커넥션을 갱신하여 MySQL `MySQL server has gone away` 에러를 방지합니다.
    """

    def __init__(self, engine: Engine) -> None:
        self._engine: Engine = engine
        self._schema_ready: bool = False
        self._session_factory: sessionmaker[Session] = sessionmaker(
            bind=self._engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )

    @classmethod
    def from_config(cls, db_config: DatabaseConfig) -> MySQLWinningRepository:
        """DatabaseConfig 설정 객체로부터 SQLAlchemy Engine을 생성하고 저장소를 초기화합니다."""
        engine = create_engine(
            db_config.sqlalchemy_url,
            echo=db_config.echo_sql,
            pool_pre_ping=True,
            pool_recycle=1800,
            pool_size=5,
            max_overflow=10,
        )
        return cls(engine=engine)

    def init_schema(self) -> None:
        """테이블(`lotto_winning_records`)이 존재하지 않으면 자동으로 생성(CREATE TABLE IF NOT EXISTS)합니다.

        Kubernetes Self-Healing 지원:
            백엔드 파드 시작 시점에 MySQL 파드가 아직 준비되지 않아 실패했더라도,
            이후 트래픽 처리 시 `_ensure_schema()`를 통해 자동으로 테이블 생성을 재시도합니다.
        """
        if self._schema_ready:
            return
        try:
            Base.metadata.create_all(bind=self._engine)
            self._schema_ready = True
        except SQLAlchemyError as exc:
            raise StorageOperationError(f"MySQL 테이블 스키마 초기화 실패: {exc}") from exc

    def save(self, record: WinningRecordEntity) -> WinningRecordEntity:
        """5등 이상 당첨 기록을 MySQL에 INSERT하고 자동 생성된 PK(`id`)가 포함된 도메인 엔티티를 반환합니다."""
        self.init_schema()
        try:
            with self._session_factory() as session:
                orm_obj = WinningRecordORM.from_domain(record)
                session.add(orm_obj)
                session.commit()
                session.refresh(orm_obj)
                return orm_obj.to_domain()
        except SQLAlchemyError as exc:
            raise StorageOperationError(
                f"당첨 기록 MySQL 저장 중 오류가 발생했습니다: {exc}"
            ) from exc

    def find_recent(self, limit: int = 50) -> list[WinningRecordEntity]:
        """PK(`id`) 내림차순으로 최근 당첨 기록을 조회합니다."""
        self.init_schema()
        try:
            with self._session_factory() as session:
                stmt = (
                    select(WinningRecordORM)
                    .order_by(WinningRecordORM.id.desc())
                    .limit(limit)
                )
                rows = session.scalars(stmt).all()
                return [row.to_domain() for row in rows]
        except SQLAlchemyError as exc:
            raise StorageOperationError(
                f"당첨 기록 MySQL 조회 중 오류가 발생했습니다: {exc}"
            ) from exc

    def count_all(self) -> int:
        """전체 5등 이상 당첨 기록 수를 반환합니다."""
        self.init_schema()
        try:
            with self._session_factory() as session:
                stmt = select(func.count()).select_from(WinningRecordORM)
                total = session.scalar(stmt)
                return int(total or 0)
        except SQLAlchemyError as exc:
            raise StorageOperationError(
                f"당첨 기록 개수 조회 중 오류가 발생했습니다: {exc}"
            ) from exc

    def clear_all(self) -> int:
        """저장된 모든 당첨 기록을 삭제합니다 (SQLAlchemy 2.0 `delete()` 구문 사용)."""
        self.init_schema()
        try:
            with self._session_factory() as session:
                stmt = delete(WinningRecordORM)
                result = session.execute(stmt)
                session.commit()
                return int(result.rowcount or 0)
        except SQLAlchemyError as exc:
            raise StorageOperationError(
                f"당첨 기록 초기화 중 오류가 발생했습니다: {exc}"
            ) from exc

    def is_healthy(self) -> bool:
        """MySQL 서버 연결 상태를 확인합니다 (Kubernetes readinessProbe 용도)."""
        try:
            with self._engine.connect() as conn:
                conn.exec_driver_sql("SELECT 1")
            return True
        except SQLAlchemyError:
            return False
