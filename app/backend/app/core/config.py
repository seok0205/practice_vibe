# ==============================================================================
# [파일 목적]
# 애플리케이션 전역 설정 및 환경변수를 관리하는 모듈입니다. (12-Factor App 원칙 준수)
#
# [아키텍처 내 역할]
# - Kubernetes의 ConfigMap(비민감 설정), Secret(MySQL 비밀번호 등), Downward API(HOSTNAME)에서
#   주입되는 환경변수를 타입 안전성이 보장된 불변 객체(AppConfig)로 캡슐화합니다.
# - 저장소 백엔드(MYSQL vs MEMORY)를 코드 수정 없이 환경변수(`LOTTO_STORAGE_BACKEND`)만으로
#   전환할 수 있게 하여 로컬 테스트와 프로덕션 K8s 배포 환경을 유연하게 분리합니다.
# ==============================================================================
from __future__ import annotations

import os
import socket
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from urllib.parse import quote_plus


class StorageBackendType(str, Enum):
    """당첨 기록 저장소 백엔드 유형을 정의하는 열거형 클래스입니다.

    - MYSQL: MySQL 8.0 데이터베이스(`lotto_winning_records` 테이블)에 영구 저장 (실무/K8s 기본값)
    - MEMORY: 파드 재시작 시 초기화되는 인메모리 저장소 (빠른 단위 테스트 및 DB 없는 단독 실행용)
    """

    MYSQL = "mysql"
    MEMORY = "memory"


@dataclass(frozen=True)
class DatabaseConfig:
    """MySQL 데이터베이스 연결 정보를 담는 불변(Immutable) 값 객체입니다.

    Kubernetes 연동 포인트:
        - `host`: K8s 클러스터 내부에서는 MySQL Service 이름(예: `mysql-service`)이 주입됩니다.
        - `user`, `password`: K8s `Secret` 리소스에서 환경변수로 안전하게 주입받습니다.
    """

    host: str
    port: int
    user: str
    password: str
    database: str
    echo_sql: bool = False

    @property
    def sqlalchemy_url(self) -> str:
        """SQLAlchemy + PyMySQL 드라이버용 접속 URL을 안전하게 생성합니다.

        비밀번호에 특수문자('@', ':', '/' 등)가 포함되어 있어도 URL 파싱 오류가 나지 않도록
        `urllib.parse.quote_plus`로 인코딩합니다.
        """
        encoded_user = quote_plus(self.user)
        encoded_pw = quote_plus(self.password)
        return (
            f"mysql+pymysql://{encoded_user}:{encoded_pw}"
            f"@{self.host}:{self.port}/{self.database}?charset=utf8mb4"
        )


@dataclass(frozen=True)
class AppConfig:
    """애플리케이션 런타임 환경설정을 담는 불변(Immutable) 값 객체입니다."""

    app_name: str
    app_version: str
    app_env: str
    pod_hostname: str
    storage_backend: StorageBackendType
    db_config: DatabaseConfig
    max_history_items: int
    static_dir: Path

    @classmethod
    def from_env(cls) -> AppConfig:
        """OS 환경변수(또는 K8s ConfigMap/Secret)로부터 설정을 읽어 불변 인스턴스를 생성합니다."""
        raw_backend = os.getenv("LOTTO_STORAGE_BACKEND", "mysql").strip().lower()
        try:
            backend_type = StorageBackendType(raw_backend)
        except ValueError:
            backend_type = StorageBackendType.MYSQL

        db_config = DatabaseConfig(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", "3306")),
            user=os.getenv("DB_USER", "lotto_user"),
            password=os.getenv("DB_PASSWORD", "lotto_pass"),
            database=os.getenv("DB_NAME", "vibe_lotto"),
            echo_sql=os.getenv("DB_ECHO_SQL", "false").strip().lower() == "true",
        )

        default_static_dir = Path(
            os.getenv(
                "LOTTO_STATIC_DIR",
                str(Path(__file__).resolve().parent.parent / "static"),
            )
        )

        # HOSTNAME 환경변수는 Kubernetes 파드 내부에서 자동으로 파드 이름(예: vibe-lotto-7d9f8b-x9k2p)으로 설정됩니다.
        hostname = os.getenv("HOSTNAME") or socket.gethostname()

        return cls(
            app_name=os.getenv("APP_NAME", "Vibe Lotto 6/45"),
            app_version=os.getenv("APP_VERSION", "1.0.0"),
            app_env=os.getenv("APP_ENV", "dev"),
            pod_hostname=hostname,
            storage_backend=backend_type,
            db_config=db_config,
            max_history_items=int(os.getenv("LOTTO_MAX_HISTORY_ITEMS", "50")),
            static_dir=default_static_dir,
        )
