// =============================================================================
// [파일 목적]
// Vibe Lotto 6/45 프론트엔드의 전체 게임 상태, UX 편의 기능(번호 유지 Keep, 고정수 Pin,
// 이전 선택 번호 불러오기), 그리고 MySQL 당첨 기록 동기화를 캡슐화한 Custom Hook입니다.
// =============================================================================
import { useCallback, useEffect, useState } from 'react';
import {
  DrawResponseData,
  PodMetadata,
  SelectionMode,
  TicketSelectionModel,
  WinningRecordItem,
} from '../domain/lotto';
import { ApiClientError, defaultLottoApiClient, LottoApiClient } from '../services/LottoApiClient';

const MAX_RECENT_TICKETS = 5;

export interface UseLottoGameReturn {
  readonly ticketModel: TicketSelectionModel;
  readonly keepNumbers: boolean;
  readonly lastDrawResult: DrawResponseData | null;
  readonly winningHistory: readonly WinningRecordItem[];
  readonly totalWinningCount: number;
  readonly recentUserTickets: readonly (readonly number[])[];
  readonly podMetadata: PodMetadata | null;
  readonly isLoading: boolean;
  readonly errorMessage: string | null;
  readonly toggleNumber: (num: number) => void;
  readonly togglePin: (num: number) => void;
  readonly setKeepNumbers: (keep: boolean) => void;
  readonly clearSelection: () => void;
  readonly restorePreviousTicket: (numbers: readonly number[]) => void;
  readonly executeDraw: () => Promise<void>;
  readonly executeQuickAutoDraw: () => Promise<void>;
  readonly resetWinningHistory: () => Promise<void>;
}

export function useLottoGame(apiClient: LottoApiClient = defaultLottoApiClient): UseLottoGameReturn {
  const [ticketModel, setTicketModel] = useState<TicketSelectionModel>(
    () => new TicketSelectionModel()
  );
  // 번호 유지(Keep) 토글: 기본값을 true로 두어 사용자가 매번 번호를 다시 누르지 않아도 바로 연속 추첨 가능하게 함
  const [keepNumbers, setKeepNumbers] = useState<boolean>(true);
  const [lastDrawResult, setLastDrawResult] = useState<DrawResponseData | null>(null);
  const [winningHistory, setWinningHistory] = useState<readonly WinningRecordItem[]>([]);
  const [totalWinningCount, setTotalWinningCount] = useState<number>(0);
  const [recentUserTickets, setRecentUserTickets] = useState<readonly (readonly number[])[]>([]);
  const [podMetadata, setPodMetadata] = useState<PodMetadata | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const refreshHistory = useCallback(async () => {
    try {
      const data = await apiClient.fetchWinningHistory(50);
      setWinningHistory(data.items);
      setTotalWinningCount(data.total_count);
      setPodMetadata(data.metadata);
    } catch (err) {
      const msg = err instanceof ApiClientError ? err.message : '당첨 기록을 불러오지 못했습니다.';
      setErrorMessage(msg);
    }
  }, [apiClient]);

  useEffect(() => {
    void refreshHistory();
  }, [refreshHistory]);

  const toggleNumber = useCallback((num: number) => {
    setErrorMessage(null);
    setTicketModel((prev) => prev.toggleNumber(num));
  }, []);

  const togglePin = useCallback((num: number) => {
    setErrorMessage(null);
    setTicketModel((prev) => prev.togglePin(num));
  }, []);

  const clearSelection = useCallback(() => {
    setErrorMessage(null);
    setTicketModel((prev) => prev.clearAll());
  }, []);

  const restorePreviousTicket = useCallback((numbers: readonly number[]) => {
    setErrorMessage(null);
    setTicketModel((prev) => prev.restoreNumbers(numbers));
  }, []);

  const pushRecentTicket = useCallback((userNumbers: readonly number[]) => {
    setRecentUserTickets((prev) => {
      const key = userNumbers.join(',');
      const filtered = prev.filter((item) => item.join(',') !== key);
      return [userNumbers, ...filtered].slice(0, MAX_RECENT_TICKETS);
    });
  }, []);

  /**
   * 현재 선택 상태에 기반하여 추첨을 수행합니다.
   * - 0개 선택 시: 완전 자동(AUTO)
   * - 1~5개 선택 시: 선택한 번호를 포함하고 나머지만 자동으로 채우는 반자동(SEMI_AUTO)
   * - 6개 선택 시: 수동(MANUAL)
   */
  const executeDraw = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const mode = ticketModel.inferSelectionMode();
      const response = await apiClient.drawLotto({
        mode,
        selected_numbers: ticketModel.selectedNumbers,
      });

      setLastDrawResult(response);
      setPodMetadata(response.metadata);
      pushRecentTicket(response.user_numbers);

      // 번호 유지(Keep) 또는 고정수(Pin) 정책에 따라 다음 라운드 선택 번호 상태 갱신
      setTicketModel((prev) => prev.prepareAfterDraw(response.user_numbers, keepNumbers));

      // 5등 이상 당첨 시 우측 명예의 전당(MySQL DB) 목록 즉시 갱신
      if (response.rank.is_winning) {
        await refreshHistory();
      }
    } catch (err) {
      const msg = err instanceof ApiClientError ? err.message : '추첨 요청 중 오류가 발생했습니다.';
      setErrorMessage(msg);
    } finally {
      setIsLoading(false);
    }
  }, [apiClient, keepNumbers, pushRecentTicket, refreshHistory, ticketModel]);

  /**
   * 현재 고정수(Pin)가 있으면 고정수만 유지한 반자동 추첨을, 없으면 완전 자동 추첨을 즉시 실행합니다.
   */
  const executeQuickAutoDraw = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const pinned = ticketModel.pinnedNumbers;
      const mode = pinned.length > 0 ? SelectionMode.SEMI_AUTO : SelectionMode.AUTO;
      const response = await apiClient.drawLotto({
        mode,
        selected_numbers: pinned,
      });

      setLastDrawResult(response);
      setPodMetadata(response.metadata);
      pushRecentTicket(response.user_numbers);
      setTicketModel((prev) => prev.prepareAfterDraw(response.user_numbers, keepNumbers));

      if (response.rank.is_winning) {
        await refreshHistory();
      }
    } catch (err) {
      const msg = err instanceof ApiClientError ? err.message : '자동 추첨 중 오류가 발생했습니다.';
      setErrorMessage(msg);
    } finally {
      setIsLoading(false);
    }
  }, [apiClient, keepNumbers, pushRecentTicket, refreshHistory, ticketModel]);

  const resetWinningHistory = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      await apiClient.clearWinningHistory();
      await refreshHistory();
    } catch (err) {
      const msg = err instanceof ApiClientError ? err.message : '기록 초기화에 실패했습니다.';
      setErrorMessage(msg);
    } finally {
      setIsLoading(false);
    }
  }, [apiClient, refreshHistory]);

  return {
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
  };
}

