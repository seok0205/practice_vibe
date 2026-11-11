# ==============================================================================
# [파일 목적]
# 외부 패키지(FastAPI, SQLAlchemy 등)가 설치되지 않은 순수 Python 표준 라이브러리 환경에서도
# 도메인 계층(`domain/`), 애플리케이션 서비스(`application/`), 인메모리 저장소(`infrastructure/`)의
# 모든 OOP 비즈니스 규칙을 즉시 검증할 수 있는 `unittest` 기반 테스트 스위트입니다.
# ==============================================================================
from __future__ import annotations

import unittest
from collections.abc import Sequence

from app.application.service import LottoGameService
from app.core.exceptions import (
    DuplicateLottoNumberError,
    InvalidGenerationStrategyError,
    InvalidLottoNumberRangeError,
    InvalidTicketSizeError,
    LottoDomainError,
)
from app.domain.evaluator import StandardKoreanLottoRankPolicy
from app.domain.models import (
    LottoNumber,
    LottoRank,
    LottoTicket,
    SelectionMode,
    WinningDraw,
    WinningRecordEntity,
)
from app.domain.strategies import (
    RandomNumberSource,
    TicketGenerationStrategyFactory,
    WinningDrawGenerator,
)
from app.infrastructure.memory_repository import InMemoryWinningRepository


class DeterministicRandomSource(RandomNumberSource):
    """앞에서부터 순서대로 k개의 번호를 반환하는 결정론적 테스트용 난수 생성기입니다."""

    def sample(self, population: Sequence[int], k: int) -> list[int]:
        return list(population)[:k]


class DomainAndServiceStdlibTest(unittest.TestCase):
    """순수 Python 표준 라이브러리 `unittest` 기반 도메인 및 서비스 검증 테스트입니다."""

    def test_lotto_number_range_and_boolean_guard(self) -> None:
        self.assertEqual(int(LottoNumber(1)), 1)
        self.assertEqual(int(LottoNumber(45)), 45)
        with self.assertRaises(InvalidLottoNumberRangeError):
            LottoNumber(0)
        with self.assertRaises(InvalidLottoNumberRangeError):
            LottoNumber(46)
        with self.assertRaises(InvalidLottoNumberRangeError):
            LottoNumber(True)  # type: ignore[arg-type]

    def test_lotto_ticket_immutability_and_sorting(self) -> None:
        ticket = LottoTicket([45, 2, 19, 1, 33, 10])
        self.assertEqual(ticket.to_int_tuple(), (1, 2, 10, 19, 33, 45))
        with self.assertRaises(InvalidTicketSizeError):
            LottoTicket([1, 2, 3, 4, 5])
        with self.assertRaises(DuplicateLottoNumberError):
            LottoTicket([1, 2, 3, 4, 5, 5])

    def test_all_ranks_evaluation(self) -> None:
        draw = WinningDraw.from_raw([1, 2, 3, 4, 5, 6], bonus_number=7)
        policy = StandardKoreanLottoRankPolicy()

        cases = [
            ([1, 2, 3, 4, 5, 6], LottoRank.FIRST),
            ([1, 2, 3, 4, 5, 7], LottoRank.SECOND),
            ([1, 2, 3, 4, 5, 8], LottoRank.THIRD),
            ([1, 2, 3, 4, 8, 9], LottoRank.FOURTH),
            ([1, 2, 3, 8, 9, 10], LottoRank.FIFTH),
            ([1, 2, 7, 8, 9, 10], LottoRank.MISS),
        ]
        for nums, expected_rank in cases:
            res = policy.evaluate(LottoTicket(nums), draw, SelectionMode.MANUAL)
            self.assertEqual(res.rank, expected_rank)

    def test_winning_record_entity_invariant(self) -> None:
        ticket = LottoTicket([1, 2, 3, 4, 5, 6])
        with self.assertRaises(LottoDomainError):
            WinningRecordEntity.create_new(ticket, LottoRank.MISS)

    def test_strategies_and_service_workflow(self) -> None:
        repo = InMemoryWinningRepository()
        rng = DeterministicRandomSource()
        service = LottoGameService(
            repository=repo,
            strategy_factory=TicketGenerationStrategyFactory(),
            draw_generator=WinningDrawGenerator(rng=rng),
            rng=rng,
        )

        # 1. 자동(AUTO) 추첨 -> DeterministicRandomSource에 의해 사용자 번호도 [1..6], 당첨 번호도 [1..6]+7 -> 1등!
        win_result = service.play_round(SelectionMode.AUTO)
        self.assertEqual(win_result.rank, LottoRank.FIRST)
        self.assertEqual(win_result.saved_record_id, 1)
        self.assertEqual(service.get_total_winning_count(), 1)

        # 2. 수동(MANUAL) 낙첨 추첨 -> [10, 11, 12, 13, 14, 15] -> 0개 일치(MISS) -> 저장되지 않아야 함!
        miss_result = service.play_round(SelectionMode.MANUAL, [10, 11, 12, 13, 14, 15])
        self.assertEqual(miss_result.rank, LottoRank.MISS)
        self.assertIsNone(miss_result.saved_record_id)
        self.assertEqual(service.get_total_winning_count(), 1)

        # 3. 반자동(SEMI_AUTO) 추첨 -> 고정수 [1, 2, 3, 40, 41] + 자동 [4] -> 4개 일치(4등, FOURTH) -> 저장됨!
        semi_result = service.play_round(SelectionMode.SEMI_AUTO, [1, 2, 3, 40, 41])
        self.assertEqual(semi_result.rank, LottoRank.FOURTH)
        self.assertEqual(semi_result.saved_record_id, 2)
        self.assertEqual(service.get_total_winning_count(), 2)

        # 4. 잘못된 반자동 입력 시 예외 발생 확인
        with self.assertRaises(InvalidGenerationStrategyError):
            service.play_round(SelectionMode.SEMI_AUTO, [])


if __name__ == "__main__":
    unittest.main()

