// 타입 내보내기 - 중복 방지를 위해 명시적 재내보내기
export type {
    Match,
    MatchStatus,
    MatchOdds,
    Round,
    GamesListResponse,
    CategoryGroup,
    MatchWithAnalysis,
    MatchAnalysis
} from './match.types';

export type {
    RoundAnalysis,
    MatchAnalysisResult,
    AIOpinion,
    AnalysisSummary,
    ValueAnalysis,
    ValueRecommendation,
    ValueBet,
    Combination,
    CombinationMatch,
    StrategyType,
    RiskLevel
} from './analysis.types';

export { STRATEGY_INFO, RECOMMENDATION_INFO } from './analysis.types';

// API 응답 공통 타입
export interface ApiResponse<T> {
    success: boolean;
    data: T;
    message?: string;
    error?: string;
}

export interface PaginatedResponse<T> {
    items: T[];
    total: number;
    page: number;
    per_page: number;
    total_pages: number;
}
