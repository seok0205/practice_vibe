// =============================================================================
// [파일 목적]
// Vibe Lotto 6/45 애플리케이션의 최상위 레이아웃 컴포넌트입니다.
// 좌측/중앙에는 번호 선택 보드와 즉석 추첨 대조 결과 카드를 배치하고,
// 우측에는 MySQL DB와 연동된 5등 이상 당첨 명예의 전당 사이드바를 배치합니다.
// 상단 헤더에는 Kubernetes Pod 호스트네임과 버전, DB 모드를 실시간으로 표시합니다.
// =============================================================================
import React from 'react';
import { DrawResultCard } from './components/DrawResultCard';
import { LottoBoard } from './components/LottoBoard';
import { WinningHistorySidebar } from './components/WinningHistorySidebar';
import { useLottoGame } from './hooks/useLottoGame';

export const App: React.FC = () => {
  const {
    ticketModel,
    keepNumbers,
    lastDrawResult,
    winningHistory,
    totalWinningCount,
    recentUserTickets,
    podMetadata,
    isLoading,
    errorMessage,
    toggleNumber,
    togglePin,
    setKeepNumbers,
    clearSelection,
    restorePreviousTicket,
    executeDraw,
    executeQuickAutoDraw,
    resetWinningHistory,
  } = useLottoGame();

  return (
    <div className="app-container">
      <header className="app-header">
        <div className="brand-title">
          <h1>🎱 Vibe Lotto 6/45</h1>
          <span className="subtitle">FastAPI OOP + MySQL + React/TS (K8s DevOps Practice)</span>
        </div>
        {podMetadata && (
          <div className="k8s-status-bar">
            <span className="status-chip">
              Pod: <strong>{podMetadata.pod_hostname}</strong>
            </span>
            <span className="status-chip">
              Version: <strong>v{podMetadata.app_version}</strong>
            </span>
            <span className="status-chip">
              Env: <strong>{podMetadata.app_env.toUpperCase()}</strong>
            </span>
            <span className="status-chip">
              Storage: <strong>{podMetadata.storage_backend.toUpperCase()}</strong>
            </span>
          </div>
        )}
      </header>

      {errorMessage && (
        <div className="error-banner" role="alert">
          ⚠️ {errorMessage}
        </div>
      )}

      <main className="main-layout">
        <div className="left-column">
          <LottoBoard
            ticketModel={ticketModel}
            keepNumbers={keepNumbers}
            recentUserTickets={recentUserTickets}
            isLoading={isLoading}
            onToggleNumber={toggleNumber}
            onTogglePin={togglePin}
            onChangeKeepNumbers={setKeepNumbers}
            onClearSelection={clearSelection}
            onRestoreTicket={restorePreviousTicket}
            onExecuteDraw={() => void executeDraw()}
            onExecuteQuickAuto={() => void executeQuickAutoDraw()}
          />

          <DrawResultCard result={lastDrawResult} />
        </div>

        <WinningHistorySidebar
          items={winningHistory}
          totalCount={totalWinningCount}
          isLoading={isLoading}
          onRestoreNumbers={restorePreviousTicket}
          onResetHistory={() => void resetWinningHistory()}
        />
      </main>
    </div>
  );
};

export default App;

