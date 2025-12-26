import apiClient from './client';
import { ENDPOINTS } from './endpoints';
import type { RoundAnalysis, MatchAnalysisResult } from '@/types';

export const analysisApi = {
    // 회차 분석
    analyzeRound: (roundNumber: number | string, category?: string) =>
        apiClient.post<never, RoundAnalysis>(
            ENDPOINTS.ANALYSIS.ROUND(roundNumber),
            { category }
        ),

    // 개별 경기 분석
    analyzeMatch: (matchId: string) =>
        apiClient.post<never, MatchAnalysisResult>(
            ENDPOINTS.ANALYSIS.MATCH(matchId)
        ),

    // 승무패 14경기 분석
    analyzeToto: (roundNumber: number) =>
        apiClient.post(ENDPOINTS.ANALYSIS.TOTO, { round_number: roundNumber }),

    // 전체 파이프라인 실행
    runPipeline: (roundId: string) =>
        apiClient.post(ENDPOINTS.PIPELINE.ANALYZE, { round_id: roundId }),
};

export default analysisApi;
