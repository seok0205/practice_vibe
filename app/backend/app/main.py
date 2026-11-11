# ==============================================================================
# [파일 목적]
# FastAPI 애플리케이션 인스턴스를 생성하고 의존성 주입(Dependency Injection) 컨테이너를
# 조립하는 메인 엔트리포인트(Application Factory Pattern) 모듈입니다.
#
# [아키텍처 내 역할]
# 1. Application Factory (`create_app`):
#    - 런타임 환경변수(`AppConfig.from_env()`) 또는 테스트용 설정/저장소를 주입받아
#      독립적인 FastAPI 앱 인스턴스를 생성합니다.
# 2. Global Exception Handler:
#    - 도메인 계층에서 발생한 `LottoDomainError`를 가로채어 표준화된 HTTP 400(또는 503) JSON 응답으로
#      변환합니다.
# 3. Kubernetes Pod Header Middleware:
#    - 모든 HTTP 응답 헤더에 `X-Pod-Hostname`과 `X-App-Version`을 자동으로 추가하여
#      `curl -I` 명령만으로도 K8s Service 로드밸런싱을 즉시 확인할 수 있게 합니다.
# ==============================================================================
from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.application.service import LottoGameService
from app.core.config import AppConfig, StorageBackendType
from app.core.exceptions import LottoDomainError, StorageOperationError
from app.domain.repository import WinningRecordRepository
from app.infrastructure.memory_repository import InMemoryWinningRepository
from app.infrastructure.mysql_repository import MySQLWinningRepository
from app.presentation.routes import api_router

logger = logging.getLogger("vibe_lotto")


def _build_repository(config: AppConfig) -> WinningRecordRepository:
    """설정에 따라 MySQL 저장소 또는 InMemory 저장소를 생성하여 반환합니다."""
    if config.storage_backend == StorageBackendType.MYSQL:
        mysql_repo = MySQLWinningRepository.from_config(config.db_config)
        return mysql_repo
    return InMemoryWinningRepository(max_items=config.max_history_items)


def create_app(
    config: AppConfig | None = None,
    repository: WinningRecordRepository | None = None,
    lotto_service: LottoGameService | None = None,
) -> FastAPI:
    """의존성을 조립하여 FastAPI 애플리케이션을 생성하는 팩토리 함수입니다."""
    resolved_config = config if config is not None else AppConfig.from_env()
    resolved_repo = repository if repository is not None else _build_repository(resolved_config)
    resolved_service = (
        lotto_service
        if lotto_service is not None
        else LottoGameService(repository=resolved_repo)
    )

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        """애플리케이션 시작 시 MySQL 테이블 자동 생성(init_schema)을 시도합니다."""
        if isinstance(resolved_repo, MySQLWinningRepository):
            try:
                resolved_repo.init_schema()
                logger.info("MySQL schema initialized successfully.")
            except StorageOperationError as exc:
                # Kubernetes 기동 초기 MySQL 파드가 아직 준비 중일 수 있으므로 경고 로그를 남기고
                # readinessProbe가 상태를 제어하도록 허용합니다.
                logger.warning("MySQL schema init deferred: %s", exc.message)
        yield

    app = FastAPI(
        title=resolved_config.app_name,
        version=resolved_config.app_version,
        description="Vibe Lotto 6/45 Full-Stack Application for Kubernetes & DevOps Practice",
        lifespan=lifespan,
    )

    app.state.config = resolved_config
    app.state.repository = resolved_repo
    app.state.lotto_service = resolved_service

    # 로컬 Vite 개발 서버(5173) 연동을 위한 CORS 허용
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def attach_pod_metadata_headers(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """모든 API 응답 헤더에 파드 호스트네임과 앱 버전을 주입합니다."""
        response = await call_next(request)
        response.headers["X-Pod-Hostname"] = resolved_config.pod_hostname
        response.headers["X-App-Version"] = resolved_config.app_version
        response.headers["X-App-Env"] = resolved_config.app_env
        return response

    @app.exception_handler(LottoDomainError)
    async def handle_domain_error(request: Request, exc: LottoDomainError) -> JSONResponse:
        """도메인 규칙 위반 및 저장소 예외를 표준 JSON 에러 응답으로 변환합니다."""
        http_status = (
            status.HTTP_503_SERVICE_UNAVAILABLE
            if isinstance(exc, StorageOperationError)
            else status.HTTP_400_BAD_REQUEST
        )
        return JSONResponse(
            status_code=http_status,
            content={
                "error_code": exc.error_code,
                "message": exc.message,
                "pod_hostname": resolved_config.pod_hostname,
            },
        )

    app.include_router(api_router)

    # 프론트엔드 정적 빌드 파일(static/)이 존재하면 함께 서빙 (단일 컨테이너 배포 지원)
    static_dir = resolved_config.static_dir
    assets_dir = static_dir / "assets"
    if assets_dir.exists() and assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/", include_in_schema=False)
    def serve_spa_index() -> Response:
        index_file = static_dir / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
        return JSONResponse(
            content={
                "service": resolved_config.app_name,
                "version": resolved_config.app_version,
                "pod_hostname": resolved_config.pod_hostname,
                "docs_url": "/docs",
            }
        )

    return app


app = create_app()

