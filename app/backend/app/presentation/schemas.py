# ==============================================================================
# [파일 목적]
# 클라이언트(React+TypeScript 프론트엔드)와 백엔드 간 HTTP JSON 통신 규격을 정의하는
# Pydantic v2 기반 Data Transfer Object(DTO) 모듈입니다.
#
# [아키텍처 내 역할]
# - 도메인 엔티티(`DrawEvaluationResult`, `WinningRecordEntity`)를 외부에 직접 노출하지 않고,
#   API 스펙에 맞는 전용 DTO로 변환하여 계층 간 결합도를 낮춥니다.
# - 모든 응답에 `pod_hostname`, `app_version`, `app_env` 메타데이터를 포함하여
#   Kubernetes 실습 중 파드 로드밸런싱과 롤링 업데이트를 시각적으로 확인할 수 있게 합니다.
# ==============================================================================
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.config import AppConfig
from app.domain.models import DrawEvaluationResult, SelectionMode, WinningRecordEntity


class PodMetadataDTO(BaseModel):
    """요청을 처리한 Kubernetes Pod 및 애플리케이션 런타임 메타데이터입니다."""

    model_config = ConfigDict(frozen=True)

    pod_hostname: str = Field(..., description="요청을 처리한 파드/컨테이너 호스트네임")
    app_version: str = Field(..., description="배포된 애플리케이션 버전")
    app_env: str = Field(..., description="실행 환경 (dev, staging, prod)")
    storage_backend: str = Field(..., description="현재 활성화된 저장소 백엔드 (mysql / memory)")

    @classmethod
    def from_config(cls, config: AppConfig) -> PodMetadataDTO:
        return cls(
            pod_hostname=config.pod_hostname,
            app_version=config.app_version,
            app_env=config.app_env,
            storage_backend=config.storage_backend.value,
        )


class DrawRequestDTO(BaseModel):
    """로또 번호 추첨 및 대조 요청 DTO입니다."""

    model_config = ConfigDict(extra="forbid")

    mode: SelectionMode = Field(
        default=SelectionMode.AUTO,
        description="번호 선택 모드: AUTO(자동), SEMI_AUTO(반자동/고정수), MANUAL(수동)",
    )
    selected_numbers: list[int] = Field(
        default_factory=list,
        description="수동(6개) 또는 반자동(1~5개 고정수) 모드에서 사용자가 선택한 번호 목록",
    )


class RankInfoDTO(BaseModel):
    """당첨 등수 상세 정보 DTO입니다."""

    model_config = ConfigDict(frozen=True)

    code: str = Field(..., description="등수 영문 코드 (FIRST ~ FIFTH, MISS)")
    tier: int = Field(..., description="등수 숫자 (1~5, 낙첨은 0)")
    label: str = Field(..., description="한국어 표시 라벨 (예: '1등', '5등', '낙첨')")
    description: str = Field(..., description="당첨 조건 설명")
    is_winning: bool = Field(..., description="5등 이상 당첨(DB 기록 대상) 여부")


class DrawResponseDTO(BaseModel):
    """로또 추첨 및 즉석 대조 결과 응답 DTO입니다."""

    model_config = ConfigDict(frozen=True)

    mode: SelectionMode
    user_numbers: list[int] = Field(..., description="사용자의 최종 6개 번호 (오름차순)")
    winning_numbers: list[int] = Field(..., description="시스템이 추첨한 당첨 번호 6개 (오름차순)")
    bonus_number: int = Field(..., description="시스템이 추첨한 보너스 번호 1개")
    matched_numbers: list[int] = Field(..., description="일치한 번호 목록")
    bonus_matched: bool = Field(..., description="보너스 번호 일치 여부")
    rank: RankInfoDTO
    saved_record_id: int | None = Field(
        default=None,
        description="5등 이상 당첨 시 MySQL DB에 저장된 고유 레코드 ID (낙첨 시 null)",
    )
    drawn_at: datetime
    metadata: PodMetadataDTO

    @classmethod
    def from_domain(
        cls,
        result: DrawEvaluationResult,
        config: AppConfig,
    ) -> DrawResponseDTO:
        return cls(
            mode=result.selection_mode,
            user_numbers=result.user_ticket.to_int_list(),
            winning_numbers=result.winning_draw.main_ticket.to_int_list(),
            bonus_number=result.winning_draw.bonus_number.value,
            matched_numbers=[n.value for n in result.matched_numbers],
            bonus_matched=result.bonus_matched,
            rank=RankInfoDTO(
                code=result.rank.name,
                tier=result.rank.tier,
                label=result.rank.label,
                description=result.rank.description,
                is_winning=result.rank.is_winning,
            ),
            saved_record_id=result.saved_record_id,
            drawn_at=result.drawn_at,
            metadata=PodMetadataDTO.from_config(config),
        )


class WinningRecordItemDTO(BaseModel):
    """우측 명예의 전당(MySQL `lotto_winning_records` 테이블) 개별 항목 DTO입니다."""

    model_config = ConfigDict(frozen=True)

    id: int
    first_num: int
    second_num: int
    third_num: int
    fourth_num: int
    fifth_num: int
    sixth_num: int
    numbers: list[int] = Field(..., description="프론트엔드 렌더링 편의를 위한 6개 번호 배열")
    rank: int = Field(..., description="DB에 저장된 당첨 등수 정수값 (1~5)")
    rank_label: str = Field(..., description="한국어 등수 표시명 (1등 ~ 5등)")
    rank_code: str = Field(..., description="등수 영문 코드 (FIRST ~ FIFTH)")
    created_at: datetime

    @classmethod
    def from_domain(cls, entity: WinningRecordEntity) -> WinningRecordItemDTO:
        n1, n2, n3, n4, n5, n6 = entity.ticket.to_int_tuple()
        return cls(
            id=entity.id if entity.id is not None else 0,
            first_num=n1,
            second_num=n2,
            third_num=n3,
            fourth_num=n4,
            fifth_num=n5,
            sixth_num=n6,
            numbers=[n1, n2, n3, n4, n5, n6],
            rank=entity.rank.tier,
            rank_label=entity.rank.label,
            rank_code=entity.rank.name,
            created_at=entity.created_at,
        )


class WinningHistoryResponseDTO(BaseModel):
    """명예의 전당(5등 이상 당첨 기록 목록) 조회 응답 DTO입니다."""

    model_config = ConfigDict(frozen=True)

    total_count: int
    items: list[WinningRecordItemDTO]
    metadata: PodMetadataDTO


class ErrorResponseDTO(BaseModel):
    """도메인 규칙 위반 또는 서버 에러 발생 시 반환되는 표준 에러 응답 DTO입니다."""

    model_config = ConfigDict(frozen=True)

    error_code: str
    message: str
    pod_hostname: str

