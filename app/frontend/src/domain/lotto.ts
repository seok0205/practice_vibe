// =============================================================================
// [파일 목적]
// 프론트엔드 도메인 모델, 불변(Immutable) 상태 클래스(`TicketSelectionModel`),
// 그리고 백엔드 API 통신 DTO 타입을 정의하는 모듈입니다.
//
// [TypeScript 컨벤션 및 OOP 설계]
// 1. `any` 타입을 일절 사용하지 않고, `as const` 상수 객체와 Union 타입으로 엄격한 타입 안정성을 보장합니다.
// 2. `TicketSelectionModel` 클래스를 통해 번호 선택/해제, 고정수(Pin) 지정, 번호 유지(Keep),
//    자동 모드 추론(`inferSelectionMode`) 등 클라이언트 도메인 규칙을 UI(React)로부터 완전히 분리했습니다.
// =============================================================================

export const SelectionMode = {
  AUTO: 'AUTO',
  SEMI_AUTO: 'SEMI_AUTO',
  MANUAL: 'MANUAL',
} as const;

export type SelectionModeType = (typeof SelectionMode)[keyof typeof SelectionMode];

export const LottoRankCode = {
  FIRST: 'FIRST',
  SECOND: 'SECOND',
  THIRD: 'THIRD',
  FOURTH: 'FOURTH',
  FIFTH: 'FIFTH',
  MISS: 'MISS',
} as const;

export type LottoRankCodeType = (typeof LottoRankCode)[keyof typeof LottoRankCode];

export interface PodMetadata {
  readonly pod_hostname: string;
  readonly app_version: string;
  readonly app_env: string;
  readonly storage_backend: string;
}

export interface RankInfo {
  readonly code: LottoRankCodeType;
  readonly tier: number;
  readonly label: string;
  readonly description: string;
  readonly is_winning: boolean;
}

export interface DrawRequestPayload {
  readonly mode: SelectionModeType;
  readonly selected_numbers: readonly number[];
}

export interface DrawResponseData {
  readonly mode: SelectionModeType;
  readonly user_numbers: readonly number[];
  readonly winning_numbers: readonly number[];
  readonly bonus_number: number;
  readonly matched_numbers: readonly number[];
  readonly bonus_matched: boolean;
  readonly rank: RankInfo;
  readonly saved_record_id: number | null;
  readonly drawn_at: string;
  readonly metadata: PodMetadata;
}

export interface WinningRecordItem {
  readonly id: number;
  readonly first_num: number;
  readonly second_num: number;
  readonly third_num: number;
  readonly fourth_num: number;
  readonly fifth_num: number;
  readonly sixth_num: number;
  readonly numbers: readonly number[];
  readonly rank: number;
  readonly rank_label: string;
  readonly rank_code: LottoRankCodeType;
  readonly created_at: string;
}

export interface WinningHistoryResponseData {
  readonly total_count: number;
  readonly items: readonly WinningRecordItem[];
  readonly metadata: PodMetadata;
}

/**
 * 로또 공 번호의 구간(1~10, 11~20, 21~30, 31~40, 41~45)에 따른 표준 색상 테마를 반환합니다.
 */
export function getBallColorClass(num: number): string {
  if (num <= 10) return 'ball-yellow';
  if (num <= 20) return 'ball-blue';
  if (num <= 30) return 'ball-red';
  if (num <= 40) return 'ball-gray';
  return 'ball-green';
}

/**
 * 사용자의 번호 선택 상태(선택된 번호 + 고정수 Pin)를 불변(Immutable) 객체로 캡슐화한 도메인 클래스입니다.
 *
 * 모든 상태 변경 메서드는 기존 인스턴스를 수정하지 않고 새로운 `TicketSelectionModel`을 반환하여
 * React의 상태 변경 감지(Referential Equality)와 완벽히 호환됩니다.
 */
export class TicketSelectionModel {
  public static readonly MIN_NUMBER = 1;
  public static readonly MAX_NUMBER = 45;
  public static readonly MAX_SELECT_COUNT = 6;

  private readonly _selected: ReadonlySet<number>;
  private readonly _pinned: ReadonlySet<number>;

  public constructor(
    selected: Iterable<number> = [],
    pinned: Iterable<number> = [],
  ) {
    const validSelected = new Set<number>();
    for (const n of selected) {
      if (TicketSelectionModel.isValidNumber(n) && validSelected.size < TicketSelectionModel.MAX_SELECT_COUNT) {
        validSelected.add(n);
      }
    }

    const validPinned = new Set<number>();
    for (const p of pinned) {
      if (validSelected.has(p)) {
        validPinned.add(p);
      }
    }

    this._selected = validSelected;
    this._pinned = validPinned;
  }

  public static isValidNumber(num: number): boolean {
    return (
      Number.isInteger(num) &&
      num >= TicketSelectionModel.MIN_NUMBER &&
      num <= TicketSelectionModel.MAX_NUMBER
    );
  }

  /** 오름차순으로 정렬된 현재 선택 번호 배열을 반환합니다. */
  public get selectedNumbers(): readonly number[] {
    return Array.from(this._selected).sort((a, b) => a - b);
  }

  /** 오름차순으로 정렬된 고정수(Pin) 배열을 반환합니다. */
  public get pinnedNumbers(): readonly number[] {
    return Array.from(this._pinned).sort((a, b) => a - b);
  }

  public get count(): number {
    return this._selected.size;
  }

  public isSelected(num: number): boolean {
    return this._selected.has(num);
  }

  public isPinned(num: number): boolean {
    return this._pinned.has(num);
  }

  /**
   * 현재 선택된 번호 개수에 따라 백엔드에 요청할 추첨 모드(AUTO / SEMI_AUTO / MANUAL)를 자동 추론합니다.
   * - 0개 선택 -> AUTO (완전 자동)
   * - 1~5개 선택 -> SEMI_AUTO (선택한 번호는 고정하고 나머지만 자동 생성)
   * - 6개 선택 -> MANUAL (수동 확정)
   */
  public inferSelectionMode(): SelectionModeType {
    if (this._selected.size === 0) return SelectionMode.AUTO;
    if (this._selected.size < TicketSelectionModel.MAX_SELECT_COUNT) return SelectionMode.SEMI_AUTO;
    return SelectionMode.MANUAL;
  }

  /** 번호 하나를 선택하거나 해제한 새 모델 인스턴스를 반환합니다. */
  public toggleNumber(num: number): TicketSelectionModel {
    if (!TicketSelectionModel.isValidNumber(num)) {
      return this;
    }
    const nextSelected = new Set(this._selected);
    const nextPinned = new Set(this._pinned);

    if (nextSelected.has(num)) {
      nextSelected.delete(num);
      nextPinned.delete(num);
    } else {
      if (nextSelected.size >= TicketSelectionModel.MAX_SELECT_COUNT) {
        return this;
      }
      nextSelected.add(num);
    }
    return new TicketSelectionModel(nextSelected, nextPinned);
  }

  /** 이미 선택된 번호를 고정수(Pin)로 잠그거나 해제한 새 모델 인스턴스를 반환합니다. */
  public togglePin(num: number): TicketSelectionModel {
    if (!this._selected.has(num)) {
      return this;
    }
    const nextPinned = new Set(this._pinned);
    if (nextPinned.has(num)) {
      nextPinned.delete(num);
    } else {
      nextPinned.add(num);
    }
    return new TicketSelectionModel(this._selected, nextPinned);
  }

  /**
   * 추첨 완료 후 다음 라운드를 준비할 때 호출됩니다.
   * - `keepNumbers === true`이면 현재 6개 번호와 고정수를 그대로 유지합니다.
   * - `keepNumbers === false`이면 고정수(Pin)로 지정한 번호만 남기고 나머지 번호는 비웁니다.
   */
  public prepareAfterDraw(drawnUserNumbers: readonly number[], keepNumbers: boolean): TicketSelectionModel {
    if (keepNumbers) {
      return new TicketSelectionModel(drawnUserNumbers, this._pinned);
    }
    return new TicketSelectionModel(this._pinned, this._pinned);
  }

  /**
   * 이전 회차 번호 조합 또는 명예의 전당 번호를 불러올 때 호출됩니다.
   * 기존 고정수(Pin)로 인해 6개 번호 중 일부가 잘리는(Truncate) 현상을 방지하기 위해,
   * 요청받은 6개 번호를 온전히 선택 상태에 담고 기존 고정수 중 해당 번호에 포함되는 것만 유지합니다.
   */
  public restoreNumbers(previousNumbers: readonly number[]): TicketSelectionModel {
    const overlappingPins = Array.from(this._pinned).filter((p) => previousNumbers.includes(p));
    return new TicketSelectionModel(previousNumbers, overlappingPins);
  }

  /** 고정수(Pin)를 포함한 모든 선택을 초기화합니다. */
  public clearAll(): TicketSelectionModel {
    return new TicketSelectionModel([], []);
  }
}
