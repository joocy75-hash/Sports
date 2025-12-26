import apiClient from './client';
import { ENDPOINTS } from './endpoints';
import type { ValueBet, Combination } from '@/types';

export const valueBetsApi = {
    // 회차별 Value Bet 조회
    getByRound: (roundNumber: number | string) =>
        apiClient.get<never, ValueBet[]>(
            ENDPOINTS.VALUE_BETS.BY_ROUND(roundNumber)
        ),

    // 전체 Value Bet 조회
    getAll: () =>
        apiClient.get<never, ValueBet[]>(ENDPOINTS.VALUE_BETS.ALL),
};

export const combinationsApi = {
    // 조합 최적화 요청
    optimize: (matchAnalyses: unknown[]) =>
        apiClient.post<never, Combination[]>(
            ENDPOINTS.COMBINATIONS.OPTIMIZE,
            { matchAnalyses }
        ),

    // 회차별 최적 조합 조회
    getByRound: (roundNumber: number | string) =>
        apiClient.get<never, Combination[]>(
            ENDPOINTS.COMBINATIONS.BY_ROUND(roundNumber)
        ),
};

export const oddsApi = {
    // 배당률 계산
    calculate: (probabilities: Record<string, number>) =>
        apiClient.post(
            ENDPOINTS.ODDS.CALCULATE,
            { probabilities }
        ),
};

export { valueBetsApi as valueBets, combinationsApi as combinations, oddsApi as odds };
