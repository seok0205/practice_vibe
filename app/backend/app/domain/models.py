# ==============================================================================
# [파일 목적]
# Vibe Lotto 6/45의 핵심 도메인 모델(Value Objects, First-Class Collection, Entity)을
# 정의하는 순수 객체 지향(Pure OOP) 모듈입니다.
#
# [아키텍처 내 역할 & 디자인 패턴]
# 1. Value Object (값 객체 패턴):
#    - `LottoNumber`: 원시 타입(`int`) 집착(Primitive Obsession)을 제거하고,
#      생성 시점에 `1 <= value <= 45` 불변식을 강제합니다.
# 2. First-Class Collection (일급 컬렉션 패턴):
#    - `LottoTicket`: 6개의 `LottoNumber` 튜플을 캡슐화하여 중복 방지, 오름차순 자동 정렬,
#      외부에서의 리스트 변경 차단(Immutability), 그리고 다른 티켓과의 일치 번호 계산 로직을
#      데이터와 한곳에 응집시킵니다.
# 3. Tell, Don't Ask 원칙:
#    - `WinningDraw`: 당첨 번호 6개와 보너스 번호 1개를 보유하며, 외부에서 getter로 숫자를 꺼내
#      비교하는 대신 `winning_draw.evaluate(user_ticket)` 메시지를 통해 스스로 결과를 판정합니다.
# ==============================================================================
from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import ClassVar

from app.core.exceptions import (
    DuplicateLottoNumberError,
    InvalidLottoNumberRangeError,
    InvalidTicketSizeError,
)


class SelectionMode(str, Enum):
    """사용자가 로또 번호를 선택한 방식을 나타내는 열거형입니다."""

    AUTO = "AUTO"  # 6개 모두 시스템 자동 생성
    SEMI_AUTO = "SEMI_AUTO"  # 사용자가 1~5개 선택(고정수) 후 나머지를 자동 생성
    MANUAL = "MANUAL"  # 사용자가 6개 모두 직접 수동 선택


class LottoRank(Enum):
    """로또 6/45 당첨 등수 및 메타데이터를 캡슐화한 열거형(Rich Enum)입니다.

    백엔드 DB 저장 시에는 `tier` 정수값(1~5)을 사용하여 MySQL `TINYINT` 컬럼(`rank`)에 매핑합니다.
    """

    FIRST = (1, "1등", "6개 번호 모두 일치", True)
    SECOND = (2, "2등", "5개 번호 + 보너스 번호 일치", True)
    THIRD = (3, "3등", "5개 번호 일치", True)
    FOURTH = (4, "4등", "4개 번호 일치", True)
    FIFTH = (5, "5등", "3개 번호 일치", True)
    MISS = (0, "낙첨", "2개 이하 일치", False)

    def __init__(
        self,
        tier: int,
        label: str,
        description: str,
        is_winning: bool,
    ) -> None:
        self.tier: int = tier
        self.label: str = label
        self.description: str = description
        self.is_winning: bool = is_winning

    @classmethod
    def from_tier(cls, tier: int) -> LottoRank:
        """MySQL DB에 저장된 정수 등수(1~5)로부터 LottoRank 열거형 객체를 복원합니다."""
        for rank in cls:
            if rank.tier == tier:
                return rank
        return cls.MISS


@dataclass(frozen=True, order=True)
class LottoNumber:
    """로또 공 하나(1 ~ 45)를 표현하는 불변 값 객체(Value Object)입니다.

    `@dataclass(frozen=True, order=True)`를 통해 불변성(Immutability), 값 기반 동등성 비교(`==`),
    해시 가능성(`set`에 넣기 가능), 그리고 크기 비교(`<`, `>`, `sorted()`)를 자동으로 지원합니다.
    """

    MIN_VALUE: ClassVar[int] = 1
    MAX_VALUE: ClassVar[int] = 45

    value: int

    def __post_init__(self) -> None:
        # bool은 파이썬에서 int의 서브클래스(isinstance(True, int) == True)이므로 명시적으로 차단합니다.
        if isinstance(self.value, bool) or not isinstance(self.value, int):
            raise InvalidLottoNumberRangeError(invalid_value=-1)
        if not (self.MIN_VALUE <= self.value <= self.MAX_VALUE):
            raise InvalidLottoNumberRangeError(
                invalid_value=self.value,
                min_val=self.MIN_VALUE,
                max_val=self.MAX_VALUE,
            )

    def __int__(self) -> int:
        return self.value


@dataclass(frozen=True)
class LottoTicket:
    """6개의 중복 없는 로또 번호 묶음을 표현하는 일급 컬렉션(First-Class Collection)입니다.

    불변성(Immutability) 보장:
        내부 컬렉션으로 가변 `list` 대신 불변 `tuple[LottoNumber, ...]`을 사용하며,
        생성 시 항상 오름차순으로 정렬하여 보관합니다.
    """

    TICKET_SIZE: ClassVar[int] = 6

    _numbers: tuple[LottoNumber, ...]

    def __init__(self, numbers: Iterable[int | LottoNumber]) -> None:
        parsed: list[LottoNumber] = [
            n if isinstance(n, LottoNumber) else LottoNumber(n) for n in numbers
        ]
        if len(parsed) != self.TICKET_SIZE:
            raise InvalidTicketSizeError(
                actual_count=len(parsed),
                expected_count=self.TICKET_SIZE,
            )
        if len(set(parsed)) != self.TICKET_SIZE:
            raise DuplicateLottoNumberError("티켓 내에 중복된 로또 번호가 존재합니다.")

        sorted_tuple = tuple(sorted(parsed))
        object.__setattr__(self, "_numbers", sorted_tuple)

    @property
    def numbers(self) -> tuple[LottoNumber, ...]:
        """불변 튜플 형태의 LottoNumber 목록을 반환합니다."""
        return self._numbers

    def to_int_tuple(self) -> tuple[int, int, int, int, int, int]:
        """DB 컬럼(first_num ~ sixth_num) 매핑 및 직렬화를 위해 정렬된 6개 정수 튜플을 반환합니다."""
        vals = tuple(n.value for n in self._numbers)
        return (vals[0], vals[1], vals[2], vals[3], vals[4], vals[5])

    def to_int_list(self) -> list[int]:
        """JSON 응답 직렬화를 위해 새로운 정수 리스트 복사본을 반환합니다."""
        return [n.value for n in self._numbers]

    def contains(self, number: LottoNumber) -> bool:
        """특정 번호가 이 티켓에 포함되어 있는지 확인합니다."""
        return number in self._numbers

    def count_matches(self, other: LottoTicket) -> int:
        """다른 티켓과 일치하는 번호의 개수를 반환합니다."""
        return len(self.find_matched_numbers(other))

    def find_matched_numbers(self, other: LottoTicket) -> tuple[LottoNumber, ...]:
        """다른 티켓(예: 당첨 번호)과 일치하는 번호들의 정렬된 튜플을 반환합니다."""
        matched = set(self._numbers).intersection(other._numbers)
        return tuple(sorted(matched))


@dataclass(frozen=True)
class WinningDraw:
    """시스템이 추첨한 당첨 번호 6개(`main_ticket`)와 보너스 번호 1개(`bonus_number`)를 표현합니다.

    Tell, Don't Ask 원칙 적용:
        외부 객체가 `winning_draw.main_ticket`과 `winning_draw.bonus_number`를 각각 꺼내서
        비교 연산을 수행하는 대신, `winning_draw.match_against(user_ticket)`에 위임하여
        일치 번호 목록과 보너스 번호 일치 여부를 한 번에 계산합니다.
    """

    main_ticket: LottoTicket
    bonus_number: LottoNumber

    def __post_init__(self) -> None:
        if self.main_ticket.contains(self.bonus_number):
            raise DuplicateLottoNumberError(
                f"보너스 번호({self.bonus_number.value})는 당첨 번호 6개와 중복될 수 없습니다."
            )

    def match_against(self, user_ticket: LottoTicket) -> tuple[tuple[LottoNumber, ...], bool]:
        """사용자 티켓과 대조하여 (일치한 당첨 번호 튜플, 보너스 번호 일치 여부)를 반환합니다."""
        matched_numbers = user_ticket.find_matched_numbers(self.main_ticket)
        bonus_matched = user_ticket.contains(self.bonus_number)
        return matched_numbers, bonus_matched

    @classmethod
    def from_raw(cls, main_numbers: Sequence[int], bonus_number: int) -> WinningDraw:
        """원시 정수 리스트와 보너스 번호로부터 WinningDraw 도메인 객체를 생성합니다."""
        return cls(
            main_ticket=LottoTicket(main_numbers),
            bonus_number=LottoNumber(bonus_number),
        )


@dataclass(frozen=True)
class DrawEvaluationResult:
    """사용자 티켓과 당첨 번호를 대조한 최종 추첨 결과 값 객체입니다."""

    user_ticket: LottoTicket
    winning_draw: WinningDraw
    selection_mode: SelectionMode
    rank: LottoRank
    matched_numbers: tuple[LottoNumber, ...]
    bonus_matched: bool
    drawn_at: datetime
    saved_record_id: int | None = None

    @property
    def is_winning_tier(self) -> bool:
        """5등 이상 당첨(우측 명예의 전당 및 MySQL DB 저장 대상) 여부를 반환합니다."""
        return self.rank.is_winning


@dataclass(frozen=True)
class WinningRecordEntity:
    """MySQL `lotto_winning_records` 테이블의 한 행(Row)과 1:1 매핑되는 도메인 엔티티입니다.

    사용자 요구사항 스키마 반영:
        - `id`: 고유 PK
        - `first_num` ~ `sixth_num`: 사용자가 선택한 6개 번호 (`ticket` 일급 컬렉션으로 보관)
        - `rank`: 당첨 등수 (1등 ~ 5등)
        - `created_at`: 기록 생성 시각 (UI 표시용)
    """

    id: int | None
    ticket: LottoTicket
    rank: LottoRank
    created_at: datetime

    @classmethod
    def create_new(cls, ticket: LottoTicket, rank: LottoRank) -> WinningRecordEntity:
        """새로 당첨된 5등 이상 결과를 저장하기 위한 엔티티를 생성합니다.

        도메인 불변식(Invariant) 검증:
            낙첨(`LottoRank.MISS`) 결과는 명예의 전당(MySQL DB)에 저장될 수 없으므로
            생성 시점에 도메인 예외를 발생시켜 잘못된 엔티티 생성을 원천 차단합니다.
        """
        if not rank.is_winning:
            from app.core.exceptions import LottoDomainError

            raise LottoDomainError(
                f"5등 이상 당첨 결과만 명예의 전당에 기록할 수 있습니다. (입력 등수: {rank.label})",
                error_code="NON_WINNING_RECORD_NOT_ALLOWED",
            )
        return cls(
            id=None,
            ticket=ticket,
            rank=rank,
            created_at=datetime.now(timezone.utc),
        )
