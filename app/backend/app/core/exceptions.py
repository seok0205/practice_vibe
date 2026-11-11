# ==============================================================================
# [파일 목적]
# 도메인 계층 및 인프라 계층에서 발생하는 예외(Exception) 계층 구조 모듈입니다.
#
# [아키텍처 내 역할]
# - 파이썬 내장 `ValueError`를 그대로 노출하지 않고, 구체적인 도메인 에러 코드(`error_code`)와
#   메시지를 가진 예외 계층을 설계하여 객체 지향의 다형적 예외 처리를 구현합니다.
# - Presentation 계층(FastAPI Exception Handler)은 이 예외를 받아 일관된 HTTP 응답으로 변환합니다.
# ==============================================================================
from __future__ import annotations


class LottoDomainError(Exception):
    """로또 도메인에서 발생하는 모든 비즈니스 규칙 위반 예외의 최상위 기반 클래스입니다."""

    error_code: str = "LOTTO_DOMAIN_ERROR"

    def __init__(self, message: str, *, error_code: str | None = None) -> None:
        super().__init__(message)
        self.message: str = message
        if error_code is not None:
            self.error_code = error_code


class InvalidLottoNumberRangeError(LottoDomainError):
    """로또 번호가 허용 범위(1 ~ 45)를 벗어났을 때 발생하는 예외입니다."""

    error_code = "INVALID_NUMBER_RANGE"

    def __init__(self, invalid_value: int, min_val: int = 1, max_val: int = 45) -> None:
        super().__init__(
            f"로또 번호는 {min_val}부터 {max_val} 사이의 정수여야 합니다. (입력값: {invalid_value})"
        )
        self.invalid_value = invalid_value


class InvalidTicketSizeError(LottoDomainError):
    """로또 한 게임(티켓)의 번호 개수가 6개가 아닐 때 발생하는 예외입니다."""

    error_code = "INVALID_TICKET_SIZE"

    def __init__(self, actual_count: int, expected_count: int = 6) -> None:
        super().__init__(
            f"로또 티켓은 정확히 {expected_count}개의 번호로 구성되어야 합니다. (현재 개수: {actual_count})"
        )
        self.actual_count = actual_count


class DuplicateLottoNumberError(LottoDomainError):
    """하나의 티켓이나 추첨 번호 내에 중복된 숫자가 포함되었을 때 발생하는 예외입니다."""

    error_code = "DUPLICATE_LOTTO_NUMBER"

    def __init__(self, message: str = "로또 번호에는 중복된 숫자가 포함될 수 없습니다.") -> None:
        super().__init__(message)


class InvalidGenerationStrategyError(LottoDomainError):
    """선택 모드(AUTO, SEMI_AUTO, MANUAL)와 입력된 고정수/선택 번호 조건이 맞지 않을 때 발생합니다."""

    error_code = "INVALID_GENERATION_STRATEGY"


class StorageOperationError(LottoDomainError):
    """데이터베이스(MySQL) 저장 또는 조회 중 인프라 오류가 발생했을 때 던지는 예외입니다."""

    error_code = "STORAGE_OPERATION_ERROR"
