# ==============================================================================
# [파일 목적]
# 도메인 계층(`LottoNumber`, `LottoTicket`, `WinningDraw`, `StandardKoreanLottoRankPolicy`,
# `TicketGenerationStrategyFactory`)의 비즈니스 규칙, 불변성(Immutability),
# 그리고 1등 ~ 5등 / 낙첨 경계값을 검증하는 순수 단위 테스트(Unit Test) 모듈입니다.
# ==============================================================================
from __future__ import annotations

from collections.abc import Sequence

import pytest

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


class DeterministicRandomSource(RandomNumberSource):
    """단위 테스트에서 항상 예측 가능한 순서(앞에서부터 k개)로 번호를 반환하는 Stub 난수 생성기입니다."""

    def sample(self, population: Sequence[int], k: int) -> list[int]:
        return list(population)[:k]


class TestLottoNumberValueObject:
    """`LottoNumber` 값 객체의 범위(1~45) 및 타입 검증 테스트입니다."""

    @pytest.mark.parametrize("valid_num", [1, 7, 25, 45])
    def test_valid_number_creation(self, valid_num: int) -> None:
        vo = LottoNumber(valid_num)
        assert int(vo) == valid_num

    @pytest.mark.parametrize("invalid_num", [0, -5, 46, 100])
    def test_out_of_range_raises_error(self, invalid_num: int) -> None:
        with pytest.raises(InvalidLottoNumberRangeError):
            LottoNumber(invalid_num)

    def test_boolean_rejected_even_though_subclass_of_int(self) -> None:
        with pytest.raises(InvalidLottoNumberRangeError):
            LottoNumber(True)  # type: ignore[arg-type]


class TestLottoTicketFirstClassCollection:
    """`LottoTicket` 일급 컬렉션의 정렬, 중복 차단, 개수 검증 테스트입니다."""

    def test_ticket_sorts_numbers_ascending(self) -> None:
        ticket = LottoTicket([45, 3, 19, 1, 32, 10])
        assert ticket.to_int_list() == [1, 3, 10, 19, 32, 45]
        assert ticket.to_int_tuple() == (1, 3, 10, 19, 32, 45)

    @pytest.mark.parametrize(
        "wrong_size_list",
        [
            [],
            [1, 2, 3, 4, 5],
            [1, 2, 3, 4, 5, 6, 7],
        ],
    )
    def test_invalid_ticket_size_raises_error(self, wrong_size_list: list[int]) -> None:
        with pytest.raises(InvalidTicketSizeError):
            LottoTicket(wrong_size_list)

    def test_duplicate_numbers_in_ticket_raises_error(self) -> None:
        with pytest.raises(DuplicateLottoNumberError):
            LottoTicket([1, 2, 3, 4, 5, 5])


class TestWinningDrawAndRankEvaluator:
    """당첨 번호 생성(`WinningDraw`) 및 1등~5등/낙첨 판정(`StandardKoreanLottoRankPolicy`) 테스트입니다."""

    def test_bonus_duplicate_with_main_numbers_raises_error(self) -> None:
        with pytest.raises(DuplicateLottoNumberError):
            WinningDraw.from_raw(main_numbers=[1, 2, 3, 4, 5, 6], bonus_number=6)

    @pytest.mark.parametrize(
        ("user_nums", "expected_rank", "expected_match_count", "expected_bonus"),
        [
            ([1, 2, 3, 4, 5, 6], LottoRank.FIRST, 6, False),     # 1등: 6개 일치
            ([1, 2, 3, 4, 5, 7], LottoRank.SECOND, 5, True),     # 2등: 5개 + 보너스(7) 일치
            ([1, 2, 3, 4, 5, 8], LottoRank.THIRD, 5, False),     # 3등: 5개 일치 (보너스 불일치)
            ([1, 2, 3, 4, 8, 9], LottoRank.FOURTH, 4, False),    # 4등: 4개 일치
            ([1, 2, 3, 8, 9, 10], LottoRank.FIFTH, 3, False),    # 5등: 3개 일치
            ([1, 2, 7, 8, 9, 10], LottoRank.MISS, 2, True),      # 낙첨: 기본 2개 + 보너스 1개는 여전히 낙첨!
            ([10, 11, 12, 13, 14, 15], LottoRank.MISS, 0, False),
        ],
    )
    def test_rank_evaluation_all_tiers(
        self,
        user_nums: list[int],
        expected_rank: LottoRank,
        expected_match_count: int,
        expected_bonus: bool,
    ) -> None:
        winning_draw = WinningDraw.from_raw(main_numbers=[1, 2, 3, 4, 5, 6], bonus_number=7)
        user_ticket = LottoTicket(user_nums)
        policy = StandardKoreanLottoRankPolicy()

        result = policy.evaluate(
            user_ticket=user_ticket,
            winning_draw=winning_draw,
            selection_mode=SelectionMode.MANUAL,
        )

        assert result.rank == expected_rank
        assert len(result.matched_numbers) == expected_match_count
        assert result.bonus_matched is expected_bonus
        assert result.is_winning_tier is (expected_rank != LottoRank.MISS)

    def test_winning_record_entity_rejects_miss_rank(self) -> None:
        ticket = LottoTicket([1, 2, 3, 4, 5, 6])
        with pytest.raises(LottoDomainError):
            WinningRecordEntity.create_new(ticket=ticket, rank=LottoRank.MISS)


class TestGenerationStrategies:
    """자동(AUTO), 반자동(SEMI_AUTO), 수동(MANUAL) 번호 생성 전략 패턴 테스트입니다."""

    def test_auto_strategy_generates_six_numbers(self) -> None:
        factory = TicketGenerationStrategyFactory()
        rng = DeterministicRandomSource()
        ticket = factory.resolve_and_generate(SelectionMode.AUTO, [], rng)
        assert ticket.to_int_list() == [1, 2, 3, 4, 5, 6]

    def test_auto_strategy_rejects_selected_numbers(self) -> None:
        factory = TicketGenerationStrategyFactory()
        rng = DeterministicRandomSource()
        with pytest.raises(InvalidGenerationStrategyError):
            factory.resolve_and_generate(SelectionMode.AUTO, [10], rng)

    def test_semi_auto_strategy_preserves_pinned_numbers(self) -> None:
        factory = TicketGenerationStrategyFactory()
        rng = DeterministicRandomSource()
        ticket = factory.resolve_and_generate(SelectionMode.SEMI_AUTO, [40, 45], rng)
        assert ticket.to_int_list() == [1, 2, 3, 4, 40, 45]

    @pytest.mark.parametrize("invalid_semi_input", [[], [1, 2, 3, 4, 5, 6]])
    def test_semi_auto_strategy_invalid_count_raises_error(
        self,
        invalid_semi_input: list[int],
    ) -> None:
        factory = TicketGenerationStrategyFactory()
        rng = DeterministicRandomSource()
        with pytest.raises(InvalidGenerationStrategyError):
            factory.resolve_and_generate(SelectionMode.SEMI_AUTO, invalid_semi_input, rng)

    def test_winning_draw_generator(self) -> None:
        generator = WinningDrawGenerator(rng=DeterministicRandomSource())
        draw = generator.draw()
        assert draw.main_ticket.to_int_list() == [1, 2, 3, 4, 5, 6]
        assert draw.bonus_number.value == 7

