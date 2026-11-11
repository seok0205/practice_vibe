# ==============================================================================
# [파일 목적]
# 로또 번호 생성 및 시스템 추첨 번호 생성을 담당하는 전략 패턴(Strategy Pattern)과
# 팩토리 패턴(Factory Pattern) 모듈입니다.
#
# [아키텍처 내 역할 & 디자인 패턴]
# 1. Strategy Pattern (`NumberGenerationStrategy`):
#    - 번호를 어떻게 생성할지(완전 자동, 고정수 기반 반자동, 수동 검증)에 대한 알고리즘을
#      독립된 전략 클래스로 캡슐화하여 개방-폐쇄 원칙(OCP)을 준수합니다.
# 2. Dependency Inversion for Randomness (`RandomNumberSource`):
#    - 난수 생성기를 인터페이스로 분리하여, 프로덕션에서는 암호학적으로 안전한 난수/표준 난수를 쓰고,
#      단위 테스트(Pytest)에서는 결정론적(Deterministic) Mock 난수기를 주입해 1등~5등 시나리오를
#      100% 재현 가능하게 만듭니다.
# 3. Factory Pattern (`TicketGenerationStrategyFactory`):
#    - 클라이언트가 요청한 `SelectionMode`에 알맞은 전략 객체를 생성/반환합니다.
# ==============================================================================
from __future__ import annotations

import random
from abc import ABC, abstractmethod
from collections.abc import Iterable, Sequence
from typing import Protocol

from app.core.exceptions import (
    DuplicateLottoNumberError,
    InvalidGenerationStrategyError,
)
from app.domain.models import (
    LottoNumber,
    LottoTicket,
    SelectionMode,
    WinningDraw,
)


class RandomNumberSource(Protocol):
    """난수 샘플링 동작을 추상화한 프로토콜(인터페이스)입니다."""

    def sample(self, population: Sequence[int], k: int) -> list[int]:
        """주어진 모집단(population)에서 중복 없이 k개의 정수를 무작위로 추출합니다."""
        ...


class SystemRandomSource:
    """운영체제의 엔트로피 소스를 활용하는 안전한 기본 난수 생성기 구현체입니다."""

    def __init__(self) -> None:
        self._rng = random.SystemRandom()

    def sample(self, population: Sequence[int], k: int) -> list[int]:
        return self._rng.sample(list(population), k)


class NumberGenerationStrategy(ABC):
    """사용자 로또 티켓(6개 번호)을 생성하는 전략 인터페이스(Abstract Base Class)입니다."""

    @property
    @abstractmethod
    def mode(self) -> SelectionMode:
        """현재 전략이 담당하는 선택 모드를 반환합니다."""

    @abstractmethod
    def generate_ticket(
        self,
        selected_numbers: Sequence[int],
        rng: RandomNumberSource,
    ) -> LottoTicket:
        """사용자가 입력한 번호(고정수 또는 수동 번호)와 난수 생성기를 이용해 완성된 티켓을 반환합니다."""


class AutoGenerationStrategy(NumberGenerationStrategy):
    """[자동 전략] 사용자의 사전 선택 번호 없이 1~45 중 6개를 완전 무작위로 추출합니다."""

    @property
    def mode(self) -> SelectionMode:
        return SelectionMode.AUTO

    def generate_ticket(
        self,
        selected_numbers: Sequence[int],
        rng: RandomNumberSource,
    ) -> LottoTicket:
        if len(selected_numbers) > 0:
            raise InvalidGenerationStrategyError(
                "자동(AUTO) 모드에서는 수동 선택 번호를 함께 전달할 수 없습니다. "
                "고정수를 사용하려면 반자동(SEMI_AUTO) 모드를 사용하세요."
            )
        all_pool = range(LottoNumber.MIN_VALUE, LottoNumber.MAX_VALUE + 1)
        picked = rng.sample(list(all_pool), LottoTicket.TICKET_SIZE)
        return LottoTicket(picked)


class SemiAutoGenerationStrategy(NumberGenerationStrategy):
    """[반자동 전략] 사용자가 고정(Pin)하거나 선택한 1~5개 번호를 유지하고 나머지만 무작위로 채웁니다."""

    @property
    def mode(self) -> SelectionMode:
        return SelectionMode.SEMI_AUTO

    def generate_ticket(
        self,
        selected_numbers: Sequence[int],
        rng: RandomNumberSource,
    ) -> LottoTicket:
        count = len(selected_numbers)
        if not (1 <= count < LottoTicket.TICKET_SIZE):
            raise InvalidGenerationStrategyError(
                f"반자동(SEMI_AUTO) 모드는 1개 이상 5개 이하의 번호가 필요합니다. (입력 개수: {count})"
            )

        # 먼저 사용자가 고정한 번호들이 유효한 범위(1~45)이고 중복이 없는지 검증합니다.
        fixed_vo_list = [LottoNumber(n) for n in selected_numbers]
        if len(set(fixed_vo_list)) != len(fixed_vo_list):
            raise DuplicateLottoNumberError("반자동 고정수 내에 중복된 번호가 존재합니다.")

        fixed_int_set = {vo.value for vo in fixed_vo_list}
        remaining_pool = [
            num
            for num in range(LottoNumber.MIN_VALUE, LottoNumber.MAX_VALUE + 1)
            if num not in fixed_int_set
        ]
        needed_count = LottoTicket.TICKET_SIZE - len(fixed_vo_list)
        auto_picked = rng.sample(remaining_pool, needed_count)

        combined = [vo.value for vo in fixed_vo_list] + auto_picked
        return LottoTicket(combined)


class ManualGenerationStrategy(NumberGenerationStrategy):
    """[수동 전략] 사용자가 직접 선택한 6개 번호를 검증하여 티켓으로 생성합니다."""

    @property
    def mode(self) -> SelectionMode:
        return SelectionMode.MANUAL

    def generate_ticket(
        self,
        selected_numbers: Sequence[int],
        rng: RandomNumberSource,
    ) -> LottoTicket:
        if len(selected_numbers) != LottoTicket.TICKET_SIZE:
            raise InvalidGenerationStrategyError(
                f"수동(MANUAL) 모드는 정확히 6개의 번호를 선택해야 합니다. "
                f"(입력 개수: {len(selected_numbers)})"
            )
        return LottoTicket(selected_numbers)


class TicketGenerationStrategyFactory:
    """SelectionMode에 알맞은 NumberGenerationStrategy 구현체를 반환하는 팩토리 클래스입니다.

    개방-폐쇄 원칙(OCP) 적용:
        기본 3가지 전략(`AUTO`, `SEMI_AUTO`, `MANUAL`) 외에 커스텀 전략 리스트를 생성자에 주입하거나
        `register_strategy()`로 런타임에 확장할 수 있습니다.
    """

    def __init__(
        self,
        custom_strategies: Iterable[NumberGenerationStrategy] | None = None,
    ) -> None:
        default_strategies: list[NumberGenerationStrategy] = [
            AutoGenerationStrategy(),
            SemiAutoGenerationStrategy(),
            ManualGenerationStrategy(),
        ]
        strategies_to_load = (
            list(custom_strategies) if custom_strategies is not None else default_strategies
        )
        self._strategies: dict[SelectionMode, NumberGenerationStrategy] = {
            strategy.mode: strategy for strategy in strategies_to_load
        }

    def register_strategy(self, strategy: NumberGenerationStrategy) -> None:
        """새로운 번호 생성 전략을 팩토리 레지스트리에 등록합니다."""
        self._strategies[strategy.mode] = strategy

    def get_strategy(self, mode: SelectionMode) -> NumberGenerationStrategy:
        """요청된 모드에 매핑된 전략 인스턴스를 반환합니다."""
        strategy = self._strategies.get(mode)
        if strategy is None:
            raise InvalidGenerationStrategyError(f"지원하지 않는 번호 생성 모드입니다: {mode}")
        return strategy

    def resolve_and_generate(
        self,
        mode: SelectionMode,
        selected_numbers: Sequence[int],
        rng: RandomNumberSource,
    ) -> LottoTicket:
        """모드별 전략을 조회하여 티켓 생성을 위임합니다."""
        strategy = self.get_strategy(mode)
        return strategy.generate_ticket(selected_numbers=selected_numbers, rng=rng)


class WinningDrawGenerator:
    """시스템의 당첨 번호 6개와 보너스 번호 1개(총 7개)를 추첨하는 도메인 서비스입니다."""

    def __init__(self, rng: RandomNumberSource | None = None) -> None:
        self._rng: RandomNumberSource = rng if rng is not None else SystemRandomSource()

    def draw(self) -> WinningDraw:
        """1~45 중 중복 없이 7개를 뽑아 앞의 6개는 당첨 티켓으로, 마지막 1개는 보너스 번호로 구성합니다."""
        all_pool = list(range(LottoNumber.MIN_VALUE, LottoNumber.MAX_VALUE + 1))
        picked_seven = self._rng.sample(all_pool, LottoTicket.TICKET_SIZE + 1)
        main_six = picked_seven[: LottoTicket.TICKET_SIZE]
        bonus_one = picked_seven[LottoTicket.TICKET_SIZE]
        return WinningDraw.from_raw(main_numbers=main_six, bonus_number=bonus_one)
