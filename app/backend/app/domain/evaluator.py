# ==============================================================================
# [파일 목적]
# 사용자의 로또 티켓(`LottoTicket`)과 시스템의 당첨 번호(`WinningDraw`)를 대조하여
# 1등(`FIRST`)부터 5등(`FIFTH`), 낙첨(`MISS`)까지 판정하는 도메인 정책 모듈입니다.
#
# [아키텍처 내 역할 & 디자인 패턴]
# - Strategy / Policy Pattern (`RankEvaluationPolicy`):
#   복잡한 `if-elif-else` 분기문을 도메인 정책 객체로 캡슐화하여,
#   추후 특별상 규칙이나 다른 로또 게임 모드가 추가되더라도 기존 서비스 로직을 변경하지 않고
#   정책 객체만 교체할 수 있도록 설계했습니다.
# ==============================================================================
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone

from app.domain.models import (
    DrawEvaluationResult,
    LottoRank,
    LottoTicket,
    SelectionMode,
    WinningDraw,
)


class RankEvaluationPolicy(ABC):
    """당첨 등수 판정 알고리즘을 정의하는 추상 정책 인터페이스입니다."""

    @abstractmethod
    def determine_rank(self, matched_count: int, bonus_matched: bool) -> LottoRank:
        """일치한 번호 개수와 보너스 번호 일치 여부를 받아 최종 등수를 반환합니다."""

    def evaluate(
        self,
        user_ticket: LottoTicket,
        winning_draw: WinningDraw,
        selection_mode: SelectionMode,
    ) -> DrawEvaluationResult:
        """티켓과 당첨 번호의 교집합 및 보너스 일치 여부를 계산하여 평가 결과 객체를 생성합니다.

        Template Method & Tell, Don't Ask 패턴 적용:
            `winning_draw.match_against(user_ticket)`에 대조 연산을 위임하고,
            구체적인 등수 매핑 규칙(`determine_rank`)은 하위 정책 구현체에 위임합니다.
        """
        matched_numbers, bonus_matched = winning_draw.match_against(user_ticket)
        rank = self.determine_rank(
            matched_count=len(matched_numbers),
            bonus_matched=bonus_matched,
        )
        return DrawEvaluationResult(
            user_ticket=user_ticket,
            winning_draw=winning_draw,
            selection_mode=selection_mode,
            rank=rank,
            matched_numbers=matched_numbers,
            bonus_matched=bonus_matched,
            drawn_at=datetime.now(timezone.utc),
        )


class StandardKoreanLottoRankPolicy(RankEvaluationPolicy):
    """대한민국 동행복권 6/45 표준 당첨 등수 판정 정책 구현체입니다.

    판정 기준:
        - 1등 (FIRST): 당첨 번호 6개 일치
        - 2등 (SECOND): 당첨 번호 5개 일치 + 보너스 번호 일치
        - 3등 (THIRD): 당첨 번호 5개 일치 (보너스 번호 불일치)
        - 4등 (FOURTH): 당첨 번호 4개 일치
        - 5등 (FIFTH): 당첨 번호 3개 일치
        - 낙첨 (MISS): 당첨 번호 2개 이하 일치
    """

    def determine_rank(self, matched_count: int, bonus_matched: bool) -> LottoRank:
        if matched_count == 6:
            return LottoRank.FIRST
        if matched_count == 5:
            return LottoRank.SECOND if bonus_matched else LottoRank.THIRD
        if matched_count == 4:
            return LottoRank.FOURTH
        if matched_count == 3:
            return LottoRank.FIFTH
        return LottoRank.MISS
