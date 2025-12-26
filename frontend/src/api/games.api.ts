import apiClient from './client';
import { ENDPOINTS } from './endpoints';
import type { GamesListResponse, Round } from '@/types';

export const gamesApi = {
    // 경기 목록 조회
    getList: () =>
        apiClient.get<never, GamesListResponse>(ENDPOINTS.GAMES.LIST),

    // 회차 목록 조회
    getRounds: (category?: string) =>
        apiClient.get(ENDPOINTS.GAMES.ROUNDS, { params: { category } }),

    // 회차별 경기 조회
    getRoundMatches: (roundNumber: number | string, category?: string) =>
        apiClient.get<never, Round>(ENDPOINTS.GAMES.ROUND_DETAIL(roundNumber), {
            params: { category }
        }),
};

export default gamesApi;
