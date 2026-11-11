// =============================================================================
// [파일 목적]
// 방금 수행한 추첨의 당첨 번호 6개 + 보너스 번호와 사용자의 선택 번호를 대조하여
// 일치한 번호를 하이라이트하고 최종 등수(1등~5등, 낙첨)를 보여주는 컴포넌트입니다.
// =============================================================================
import React from 'react';
import { DrawResponseData } from '../domain/lotto';
import { LottoBall } from './LottoBall';

export interface DrawResultCardProps {
  readonly result: DrawResponseData | null;
}

export const DrawResultCard: React.FC<DrawResultCardProps> = ({ result }) => {
  if (!result) {
    return (
      <section className="panel result-panel result-empty">
        <h3>추첨 대기 중</h3>
        <p>번호를 선택하거나 자동 추첨 버튼을 누르면 시스템 추첨 번호와 대조 결과가 즉시 표시됩니다.</p>
      </section>
    );
  }

  const matchedSet = new Set(result.matched_numbers);
  const isWin = result.rank.is_winning;

  return (
    <section className={`panel result-panel ${isWin ? 'result-winning' : 'result-miss'}`}>
      <div className="result-header">
        <div className={`rank-banner rank-tier-${result.rank.tier}`}>
          <span className="rank-title">{result.rank.label}</span>
          <span className="rank-desc">{result.rank.description}</span>
        </div>
        {result.saved_record_id !== null && (
          <span className="db-saved-badge">
            MySQL DB 기록 완료 (#ID: {result.saved_record_id})
          </span>
        )}
      </div>

      <div className="comparison-grid">
        <div className="comparison-row">
          <span className="row-label">시스템 당첨 번호</span>
          <div className="balls-row">
            {result.winning_numbers.map((num) => (
              <LottoBall
                key={`win-${num}`}
                number={num}
                size="md"
                isMatched={matchedSet.has(num)}
              />
            ))}
            <span className="plus-sign">+</span>
            <div className="bonus-wrapper">
              <LottoBall
                number={result.bonus_number}
                size="md"
                isMatched={result.bonus_matched}
              />
              <small className="bonus-label">보너스</small>
            </div>
          </div>
        </div>

        <div className="comparison-row">
          <span className="row-label">나의 선택 번호 ({result.mode})</span>
          <div className="balls-row">
            {result.user_numbers.map((num) => (
              <LottoBall
                key={`user-${num}`}
                number={num}
                size="md"
                isMatched={matchedSet.has(num) || (result.bonus_matched && num === result.bonus_number)}
              />
            ))}
          </div>
        </div>
      </div>

      <div className="match-summary">
        <span>
          기본 번호 <strong>{result.matched_numbers.length}개</strong> 일치
          {result.bonus_matched ? ' + 보너스 번호 일치!' : ''}
        </span>
        <span className="pod-stamp">
          처리 파드(Pod): <code>{result.metadata.pod_hostname}</code>
        </span>
      </div>
    </section>
  );
};

