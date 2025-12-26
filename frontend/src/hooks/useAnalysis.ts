import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { analysisApi } from '@/api';

// 회차 분석 요청
export function useRoundAnalysis(roundNumber: number | string, category?: string) {
    return useQuery({
        queryKey: ['analysis', 'round', roundNumber, category],
        queryFn: () => analysisApi.analyzeRound(roundNumber, category),
        enabled: false, // 수동 트리거
        staleTime: 5 * 60 * 1000 // 5분
    });
}

// 분석 실행 뮤테이션
export function useAnalyzeRound() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ roundNumber, category }: { roundNumber: number | string; category?: string }) =>
            analysisApi.analyzeRound(roundNumber, category),
        onSuccess: (data, variables) => {
            queryClient.setQueryData(
                ['analysis', 'round', variables.roundNumber, variables.category],
                data
            );
        }
    });
}

// 승무패 14경기 분석
export function useTotoAnalysis(roundNumber: number) {
    return useQuery({
        queryKey: ['analysis', 'toto', roundNumber],
        queryFn: () => analysisApi.analyzeToto(roundNumber),
        enabled: false,
        staleTime: 5 * 60 * 1000
    });
}

// 승무패 분석 뮤테이션
export function useAnalyzeToto() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (roundNumber: number) => analysisApi.analyzeToto(roundNumber),
        onSuccess: (data, roundNumber) => {
            queryClient.setQueryData(['analysis', 'toto', roundNumber], data);
        }
    });
}
