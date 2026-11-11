// =============================================================================
// [파일 목적]
// FastAPI 백엔드와 HTTP REST 통신을 수행하는 캡슐화된 API 클라이언트 서비스 클래스입니다.
//
// [아키텍처 내 역할]
// - UI 컴포넌트나 Hook이 `fetch` URL이나 HTTP 상태 코드 파싱 로직을 직접 다루지 않도록
//   객체 지향 서비스 레이어로 분리했습니다.
// =============================================================================
import {
  DrawRequestPayload,
  DrawResponseData,
  PodMetadata,
  WinningHistoryResponseData,
} from '../domain/lotto';

export class ApiClientError extends Error {
  public readonly errorCode: string;
  public readonly statusCode: number;

  public constructor(message: string, errorCode = 'UNKNOWN_ERROR', statusCode = 500) {
    super(message);
    this.name = 'ApiClientError';
    this.errorCode = errorCode;
    this.statusCode = statusCode;
  }
}

export class LottoApiClient {
  private readonly baseUrl: string;
  private readonly timeoutMs: number;

  public constructor(baseUrl = '/api/v1', timeoutMs = 8000) {
    this.baseUrl = baseUrl;
    this.timeoutMs = timeoutMs;
  }

  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);

    try {
      const response = await fetch(`${this.baseUrl}${path}`, {
        headers: {
          'Content-Type': 'application/json',
        },
        signal: controller.signal,
        ...init,
      });

      if (!response.ok) {
        let errorMsg = `HTTP 요청 실패 (상태 코드: ${response.status})`;
        let errorCode = 'HTTP_ERROR';
        try {
          const errBody: unknown = await response.json();
          if (typeof errBody === 'object' && errBody !== null && 'message' in errBody) {
            errorMsg = String((errBody as { message: unknown }).message);
          }
          if (typeof errBody === 'object' && errBody !== null && 'error_code' in errBody) {
            errorCode = String((errBody as { error_code: unknown }).error_code);
          }
        } catch {
          // JSON 파싱 실패 시 기본 에러 메시지 유지
        }
        throw new ApiClientError(errorMsg, errorCode, response.status);
      }

      return (await response.json()) as T;
    } catch (err) {
      if (err instanceof ApiClientError) {
        throw err;
      }
      if (err instanceof DOMException && err.name === 'AbortError') {
        throw new ApiClientError(
          '백엔드 서버 응답 시간이 초과되었습니다 (Timeout). 파드 및 DB 상태를 확인해 주세요.',
          'REQUEST_TIMEOUT',
          408
        );
      }
      throw new ApiClientError(
        '백엔드 API 서버에 연결할 수 없습니다.',
        'NETWORK_ERROR',
        503
      );
    } finally {
      clearTimeout(timer);
    }
  }

  /** 로또 번호 추첨 및 당첨 대조를 요청합니다. */
  public async drawLotto(payload: DrawRequestPayload): Promise<DrawResponseData> {
    return this.request<DrawResponseData>('/lotto/draw', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  /** MySQL DB에 저장된 5등 이상 명예의 전당 기록을 조회합니다. */
  public async fetchWinningHistory(limit = 50): Promise<WinningHistoryResponseData> {
    return this.request<WinningHistoryResponseData>(`/lotto/history?limit=${limit}`, {
      method: 'GET',
    });
  }

  /** 저장된 당첨 기록을 모두 초기화합니다. */
  public async clearWinningHistory(): Promise<{ deleted_count: number; pod_hostname: string }> {
    return this.request<{ deleted_count: number; pod_hostname: string }>('/lotto/history', {
      method: 'DELETE',
    });
  }

  /** 현재 응답 파드(HOSTNAME) 및 시스템 메타데이터를 조회합니다. */
  public async fetchSystemInfo(): Promise<PodMetadata> {
    return this.request<PodMetadata>('/system/info', {
      method: 'GET',
    });
  }
}

export const defaultLottoApiClient = new LottoApiClient();
