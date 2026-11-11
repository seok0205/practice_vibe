// =============================================================================
// [파일 목적]
// 5등 이상 당첨된 이력만 우측에 기록하는 '명예의 전당(Winning History Sidebar)' 컴포넌트입니다.
// MySQL `lotto_winning_records` 테이블(`id`, `first_num`~`sixth_num`, `rank`)의 데이터를 표시하며,
// 기록된 번호를 클릭하면 즉시 내 번호판으로 다시 불러올 수 있는 UX를 제공합니다.
// =============================================================================
import React from 'react';
import { WinningRecordItem } from '../domain/lotto';
import { LottoBall } from './LottoBall';

export interface WinningHistorySidebarProps {
  readonly items: readonly WinningRecordItem[];
  readonly totalCount: number;
  readonly isLoading: boolean;
  readonly onRestoreNumbers: (numbers: readonly number[]) => void;
  readonly onResetHistory: () => void;
}

export const WinningHistorySidebar: React.FC<WinningHistorySidebarProps> = ({
  items,
  totalCount,
  isLoading,
  onRestoreNumbers,
  onResetHistory,
}) => {
  return (
    <aside className="panel history-sidebar">
      <div className="sidebar-header">
        <div>
          <h2>🏆 명예의 전당 (5등 이상)</h2>
          <p className="sidebar-subtitle">
            MySQL DB 누적 당첨: <strong>{totalCount}</strong>건
          </p>
        </div>
        {items.length > 0 && (
          <button
            type="button"
            className="btn btn-danger-outline btn-sm"
            onClick={onResetHistory}
            disabled={isLoading}
          >
            기록 비우기
          </button>
        )}
      </div>

      {items.length === 0 ? (
        <div className="history-empty">
          <p>아직 5등(3개 일치) 이상 당첨 기록이 없습니다.</p>
          <small>5등 이상 당첨되면 이 영역과 MySQL DB에 자동으로 기록됩니다!</small>
        </div>
      ) : (
        <ul className="history-list">
          {items.map((item) => (
            <li key={item.id} className={`history-card tier-border-${item.rank}`}>
              <div className="history-card-top">
                <span className={`rank-pill tier-bg-${item.rank}`}>{item.rank_label}</span>
                <span className="record-id">DB #{item.id}</span>
                <button
                  type="button"
                  className="btn-apply-history"
                  onClick={() => onRestoreNumbers(item.numbers)}
                  title="이 당첨 번호를 내 선택 보드로 불러옵니다"
                >
                  이 번호 쓰기
                </button>
              </div>
              <div className="history-balls">
                {item.numbers.map((num) => (
                  <LottoBall key={`${item.id}-${num}`} number={num} size="sm" />
                ))}
              </div>
            </li>
          ))}
        </ul>
      )}
    </aside>
  );
};

