# ==============================================================================
# [파일 목적]
# FastAPI REST API 엔드포인트를 정의하는 프레젠테이션 계층 라우터 모듈입니다.
#
# [제공 엔드포인트]
# 1. `POST /api/v1/lotto/draw`: 사용자 번호(자동/반자동/수동) 추첨 및 당첨 결과 반환 (5등 이상 DB 저장)
# 2. `GET  /api/v1/lotto/history`: MySQL에 저장된 5등 이상 당첨 기록 조회
# 3. `DELETE /api/v1/lotto/history`: 저장된 당첨 기록 전체 초기화
# 4. `GET  /api/v1/system/info`: 현재 응답 파드(HOSTNAME), 버전, DB 백엔드 상태 조회
# 5. `GET  /api/v1/health/live`: Kubernetes `livenessProbe`용 엔드포인트
# 6. `GET  /api/v1/health/ready`: Kubernetes `readinessProbe`용 엔드포인트 (DB 연결 검사 포함)
# ==============================================================================
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response, status

from app.application.service import LottoGameService
from app.core.config import AppConfig
from app.presentation.schemas import (
    DrawRequestDTO,
    DrawResponseDTO,
    PodMetadataDTO,
    WinningHistoryResponseDTO,
    WinningRecordItemDTO,
)

api_router = APIRouter(prefix="/api/v1")


def get_app_config(request: Request) -> AppConfig:
    """FastAPI `app.state`에 등록된 불변 설정 객체를 주입받습니다."""
    config: AppConfig = request.app.state.config
    return config


def get_lotto_service(request: Request) -> LottoGameService:
    """FastAPI `app.state`에 조립된 LottoGameService 인스턴스를 주입받습니다."""
    service: LottoGameService = request.app.state.lotto_service
    return service


ConfigDep = Annotated[AppConfig, Depends(get_app_config)]
ServiceDep = Annotated[LottoGameService, Depends(get_lotto_service)]


@api_router.post(
    "/lotto/draw",
    response_model=DrawResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="로또 6/45 즉석 추첨 및 당첨 판정",
)
def draw_lotto(
    payload: DrawRequestDTO,
    config: ConfigDep,
    service: ServiceDep,
) -> DrawResponseDTO:
    """사용자의 선택 모드(AUTO, SEMI_AUTO, MANUAL)와 번호로 추첨을 수행합니다."""
    result = service.play_round(
        mode=payload.mode,
        selected_numbers=payload.selected_numbers,
    )
    return DrawResponseDTO.from_domain(result=result, config=config)


@api_router.get(
    "/lotto/history",
    response_model=WinningHistoryResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="명예의 전당 (5등 이상 당첨 기록) 조회",
)
def get_winning_history(
    config: ConfigDep,
    service: ServiceDep,
    limit: int = Query(default=50, ge=1, le=200, description="조회할 최대 당첨 기록 수"),
) -> WinningHistoryResponseDTO:
    """MySQL DB(`lotto_winning_records`)에 기록된 5등 이상 당첨 내역을 최신순으로 조회합니다."""
    records = service.get_winning_history(limit=limit)
    total = service.get_total_winning_count()
    return WinningHistoryResponseDTO(
        total_count=total,
        items=[WinningRecordItemDTO.from_domain(r) for r in records],
        metadata=PodMetadataDTO.from_config(config),
    )


@api_router.delete(
    "/lotto/history",
    status_code=status.HTTP_200_OK,
    summary="명예의 전당 당첨 기록 초기화",
)
def clear_winning_history(
    config: ConfigDep,
    service: ServiceDep,
) -> dict[str, int | str]:
    """저장된 모든 5등 이상 당첨 기록을 삭제합니다."""
    deleted_count = service.clear_winning_history()
    return {
        "deleted_count": deleted_count,
        "pod_hostname": config.pod_hostname,
    }


@api_router.get(
    "/system/info",
    response_model=PodMetadataDTO,
    status_code=status.HTTP_200_OK,
    summary="Kubernetes 파드 및 애플리케이션 런타임 메타데이터 조회",
)
def get_system_info(config: ConfigDep) -> PodMetadataDTO:
    """현재 요청을 처리한 파드의 호스트네임과 버전 정보를 반환합니다."""
    return PodMetadataDTO.from_config(config)


@api_router.get(
    "/health/live",
    status_code=status.HTTP_200_OK,
    summary="Kubernetes Liveness Probe 엔드포인트",
)
def health_liveness(config: ConfigDep) -> dict[str, str]:
    """프로세스가 살아있는지 확인하는 Liveness 체크입니다."""
    return {"status": "UP", "pod_hostname": config.pod_hostname}


@api_router.get(
    "/health/ready",
    status_code=status.HTTP_200_OK,
    summary="Kubernetes Readiness Probe 엔드포인트 (DB 연결 점검 포함)",
)
def health_readiness(
    response: Response,
    config: ConfigDep,
    service: ServiceDep,
) -> dict[str, str]:
    """파드가 트래픽을 받을 준비가 되었는지(MySQL 연결 포함) 확인하는 Readiness 체크입니다."""
    if not service.check_storage_health():
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "OUT_OF_SERVICE",
            "reason": "Database connection unhealthy",
            "pod_hostname": config.pod_hostname,
        }
    return {
        "status": "READY",
        "storage_backend": config.storage_backend.value,
        "pod_hostname": config.pod_hostname,
    }

