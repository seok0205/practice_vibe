// =============================================================================
// [파일 목적]
// 단일 로또 공(1~45)을 색상 테마, 일치 여부 하이라이트, 고정수(Pin) 배지와 함께
// 렌더링하는 순수 프레젠테이션 컴포넌트입니다.
// =============================================================================
import React from 'react';
import { getBallColorClass } from '../domain/lotto';

export interface LottoBallProps {
  readonly number: number;
  readonly size?: 'sm' | 'md' | 'lg';
  readonly isMatched?: boolean;
  readonly isPinned?: boolean;
  readonly onClick?: () => void;
}

export const LottoBall: React.FC<LottoBallProps> = ({
  number,
  size = 'md',
  isMatched = false,
  isPinned = false,
  onClick,
}) => {
  const colorClass = getBallColorClass(number);
  const classNames = [
    'lotto-ball',
    colorClass,
    `ball-${size}`,
    isMatched ? 'ball-matched' : '',
    onClick ? 'ball-clickable' : '',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <span className={classNames} onClick={onClick} title={isPinned ? '고정수(Pin) 설정됨' : undefined}>
      {number}
      {isPinned && <sup className="pin-indicator">📌</sup>}
    </span>
  );
};

