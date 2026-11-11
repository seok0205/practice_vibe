# ==============================================================================
# [파일 목적]
# 도메인 객체(`LottoTicket`, `WinningDrawGenerator`, `RankEvaluationPolicy`, `WinningRecordRepository`)들을
# 조율하여 사용자의 유스케이스(추첨 실행, 명예의 전당 조회, 이력 초기화)를 처리하는
# 애플리케이션 서비스(Application Service / Facade Pattern) 모듈입니다.
#
# [아키텍처 내 역할 & 디자인 패턴]
# 1. Facade Pattern (퍼사드 패턴):
#    - Presentation 계층(FastAPI 라우터)이 복잡한 도메인 전략 선택, 추첨 생성, 등수 판정,
#      조건부 DB 저장(5등 이상만 저장) 절차를 일일이 알 필요 없이 `play_round()` 단일 메서드로 호출하게 합니다.
# 2. Dependency Injection (생성자 주입):
#    - 전략 팩토리, 추첨 생성기, 등수 평가 정책, 저장소 인터페이스를 모두 생성자 주입으로 받아
#      단위 테스트 시 원하는 컴포넌트만 손쉽게 교체(Mock/Stub)할 수 있습니다.
# ==============================================================================
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

from app.domain.evaluator import RankEvaluationPolicy, StandardKoreanLottoRankPolicy
from app.domain.models import (
    DrawEvaluationResult,
    SelectionMode,
    WinningRecordEntity,
)
from app.domain.repository import WinningRecordRepository
from app.domain.strategies import (
    RandomNumberSource,
    SystemRandomSource,
    TicketGenerationStrategyFactory,
    WinningDrawGenerator,
)


class LottoGameService:
    """로또 6/45 게임 진행 및 당첨 기록 관리를 총괄하는 애플리케이션 서비스 클래스입니다."""

    def __init__(
        self,
        repository: WinningRecordRepository,
        strategy_factory: TicketGenerationStrategyFactory | None = None,
        draw_generator: WinningDrawGenerator | None = None,
        rank_policy: RankEvaluationPolicy | None = None,
        rng: RandomNumberSource | None = None,
    ) -> None:
        self._repository: WinningRecordRepository = repository
        self._rng: RandomNumberSource = rng if rng is not None else SystemRandomSource()
        self._strategy_factory: TicketGenerationStrategyFactory = (
            strategy_factory
            if strategy_factory is not None
            else TicketGenerationStrategyFactory()
        )
        self._draw_generator: WinningDrawGenerator = (
            draw_generator
            if draw_generator is not None
            else WinningDrawGenerator(rng=self._rng)
        )
        self._rank_policy: RankEvaluationPolicy = (
            rank_policy
            if rank_policy is not None
            else StandardKoreanLottoRankPolicy()
        )

    def play_round(
        self,
        mode: SelectionMode,
        selected_numbers: Sequence[int] = (),
    ) -> DrawEvaluationResult:
        """사용자의 선택 모드와 번호를 받아 즉시 시스템 추첨 및 대조를 수행합니다.

        비즈니스 워크플로우:
            1. 요청된 `SelectionMode`(`AUTO`, `SEMI_AUTO`, `MANUAL`)에 맞는 전략으로 사용자 티켓 생성
            2. 시스템이 즉시 당첨 번호 6개 + 보너스 번호 1개 추첨 (`WinningDraw`)
            3. 등수 평가 정책(`RankEvaluationPolicy`)을 통해 1등 ~ 5등 또는 낙첨 판정
            4. **5등 이상(`is_winning_tier == True`)인 경우에만** 저장소(MySQL DB)에 기록 영속화
        """
        user_ticket = self._strategy_factory.resolve_and_generate(
            mode=mode,
            selected_numbers=selected_numbers,
            rng=self._rng,
        )
        winning_draw = self._draw_generator.draw()
        result = self._rank_policy.evaluate(
            user_ticket=user_ticket,
            winning_draw=winning_draw,
            selection_mode=mode,
        )

        if result.is_winning_tier:
            entity_to_save = WinningRecordEntity.create_new(
                ticket=result.user_ticket,
                rank=result.rank,
            )
            saved_entity = self._repository.save(entity_to_save)
            return replace(result, saved_record_id=saved_entity.id)

        return result

    def get_winning_history(self, limit: int = 50) -> list[WinningRecordEntity]:
        """우측 사이드바(명예의 전당)에 표시할 최근 5등 이상 당첨 기록을 조회합니다."""
        safe_limit = max(1, min(limit, 200))
        return self._repository.find_recent(limit=safe_limit)

    def get_total_winning_count(self) -> int:
        """누적 5등 이상 당첨 건수를 반환합니다."""
        return self._repository.count_all()

    def clear_winning_history(self) -> int:
        """저장된 모든 당첨 기록을 삭제하고 삭제된 건수를 반환합니다."""
        return self._repository.clear_all()

    def check_storage_health(self) -> bool:
        """연결된 저장소(MySQL 또는 InMemory)의 정상 동작 여부를 반환합니다."""
        return self._repository.is_healthy()

