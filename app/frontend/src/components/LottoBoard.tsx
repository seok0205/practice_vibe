// =============================================================================
// [파일 목적]
// 1부터 45까지의 로또 번호 그리드와 UX 컨트롤(번호 유지 Keep 토글, 고정수 Pin 설정,
// 이전 선택 번호 불러오기, 즉시 추첨 버튼)을 제공하는 메인 보드 컴포넌트입니다.
// =============================================================================
import React from 'react';
import { SelectionMode, TicketSelectionModel } from '../domain/lotto';
import { LottoBall } from './LottoBall';

export interface LottoBoardProps {
  readonly ticketModel: TicketSelectionModel;
  readonly keepNumbers: boolean;
  readonly recentUserTickets: readonly (readonly number[])[];
  readonly isLoading: boolean;
  readonly onToggleNumber: (num: number) => void;
  readonly onTogglePin: (num: number) => void;
  readonly onChangeKeepNumbers: (keep: boolean) => void;
  readonly onClearSelection: () => void;
  readonly onRestoreTicket: (numbers: readonly number[]) => void;
  readonly onExecuteDraw: () => void;
  readonly onExecuteQuickAuto: () => void;
}

const ALL_NUMBERS: readonly number[] = Array.from({ length: 45 }, (_, idx) => idx + 1);

export const LottoBoard: React.FC<LottoBoardProps> = ({
  ticketModel,
  keepNumbers,
  recentUserTickets,
  isLoading,
  onToggleNumber,
  onTogglePin,
  onChangeKeepNumbers,
  onClearSelection,
  onRestoreTicket,
  onExecuteDraw,
  onExecuteQuickAuto,
}) => {
  const currentMode = ticketModel.inferSelectionMode();
  const modeLabel =
    currentMode === SelectionMode.AUTO
      ? '완전 자동 (0/6 선택됨 → 6개 자동 추출)'
      : currentMode === SelectionMode.SEMI_AUTO
        ? `반자동 (${ticketModel.count}/6 선택됨 → 나머지 ${6 - ticketModel.count}개 자동 추출)`
        : '수동 확정 (6/6 선택 완료)';

  return (
    <section className="panel board-panel">
      <div className="panel-header">
        <div>
          <h2>번호 선택 보드 (1 ~ 45)</h2>
          <p className="mode-badge">{modeLabel}</p>
        </div>
        <div className="ux-toggle-group">
          <label className="keep-toggle-label" title="활성화하면 추첨 후에도 선택한 번호가 사라지지 않고 유지되어 연속 추첨이 편리합니다.">
            <input
              type="checkbox"
              checked={keepNumbers}
              onChange={(e) => onChangeKeepNumbers(e.target.checked)}
            />
            <span>추첨 후 번호 유지 (Keep)</span>
          </label>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={onClearSelection}
            disabled={isLoading || ticketModel.count === 0}
          >
            전체 해제
          </button>
        </div>
      </div>

      {/* 1 ~ 45 번호판 그리드 */}
      <div className="number-grid">
        {ALL_NUMBERS.map((num) => {
          const selected = ticketModel.isSelected(num);
          const pinned = ticketModel.isPinned(num);
          const disabled = !selected && ticketModel.count >= TicketSelectionModel.MAX_SELECT_COUNT;

          return (
            <button
              key={num}
              type="button"
              className={`grid-cell ${selected ? 'cell-selected' : ''} ${pinned ? 'cell-pinned' : ''}`}
              disabled={disabled || isLoading}
              onClick={() => onToggleNumber(num)}
            >
              <span className="cell-num">{num}</span>
              {pinned && <span className="cell-pin-tag">📌</span>}
            </button>
          );
        })}
      </div>

      {/* 현재 선택된 번호 슬롯 & 고정수(Pin) 토글 */}
      <div className="selected-tray">
        <div className="tray-header">
          <strong>현재 내 티켓 슬롯</strong>
          <span className="tray-hint">
            선택된 공을 클릭하면 <strong>고정수(📌 Pin)</strong>로 잠글 수 있습니다.
          </span>
        </div>
        <div className="tray-balls">
          {ticketModel.selectedNumbers.length === 0 ? (
            <span className="empty-slot-msg">
              선택된 번호가 없습니다. 바로 추첨을 누르면 6개 모두 자동으로 뽑힙니다!
            </span>
          ) : (
            ticketModel.selectedNumbers.map((num) => (
              <LottoBall
                key={num}
                number={num}
                size="md"
                isPinned={ticketModel.isPinned(num)}
                onClick={() => onTogglePin(num)}
              />
            ))
          )}
        </div>
      </div>

      {/* 메인 액션 버튼 */}
      <div className="action-bar">
        <button
          type="button"
          className="btn btn-primary btn-lg"
          disabled={isLoading}
          onClick={onExecuteDraw}
        >
          {isLoading
            ? '추첨 중...'
            : currentMode === SelectionMode.MANUAL
              ? '선택한 6개 번호로 즉시 추첨하기'
              : currentMode === SelectionMode.SEMI_AUTO
                ? `반자동 추첨하기 (${ticketModel.count}개 유지 + ${6 - ticketModel.count}개 자동)`
                : '자동 6개 생성 및 즉시 추첨하기'}
        </button>
        <button
          type="button"
          className="btn btn-accent"
          disabled={isLoading}
          onClick={onExecuteQuickAuto}
          title="고정수(📌)만 남기고 매번 새로운 번호로 즉시 추첨합니다."
        >
          ⚡ 빠른 새 번호 자동 추첨
        </button>
      </div>

      {/* 이전 선택 번호 원클릭 불러오기 */}
      {recentUserTickets.length > 0 && (
        <div className="recent-tickets-box">
          <span className="recent-title">최근 내가 뽑았던 번호 다시 불러오기:</span>
          <div className="recent-list">
            {recentUserTickets.map((nums, idx) => (
              <button
                key={`${nums.join('-')}-${idx}`}
                type="button"
                className="btn-recent-chip"
                onClick={() => onRestoreTicket(nums)}
                disabled={isLoading}
              >
                [{nums.join(', ')}] 불러오기
              </button>
            ))}
          </div>
        </div>
      )}
    </section>
  );
};

