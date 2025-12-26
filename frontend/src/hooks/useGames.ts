import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { gamesApi } from '@/api';

// 경기 목록 조회
export function useGames() {
    return useQuery({
        queryKey: ['games', 'list'],
        queryFn: () => gamesApi.getList(),
        staleTime: 30 * 1000, // 30초
        refetchInterval: 60 * 1000 // 1분마다 갱신
    });
}

// 회차 목록 조회
export function useRounds(category?: string) {
    return useQuery({
        queryKey: ['rounds', category],
        queryFn: () => gamesApi.getRounds(category),
        staleTime: 60 * 1000 // 1분
    });
}

// 회차별 경기 조회
export function useRoundMatches(roundNumber: number | string, category?: string) {
    return useQuery({
        queryKey: ['roundMatches', roundNumber, category],
        queryFn: () => gamesApi.getRoundMatches(roundNumber, category),
        enabled: !!roundNumber,
        staleTime: 30 * 1000
    });
}
