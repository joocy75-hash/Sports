// API 엔드포인트 정의
export const ENDPOINTS = {
    // 경기 관련
    GAMES: {
        LIST: '/api/v1/games/list',
        ROUNDS: '/api/v1/games/rounds',
        ROUND_DETAIL: (round: number | string) => `/api/v1/games/rounds/${round}`,
    },

    // 분석 관련
    ANALYSIS: {
        ROUND: (round: number | string) => `/api/v1/analyze/round/${round}`,
        MATCH: (matchId: string) => `/api/v1/analyze/match/${matchId}`,
        TOTO: '/api/v1/toto/analyze',
    },

    // 배당률 관련
    ODDS: {
        CALCULATE: '/api/v1/odds/calculate',
    },

    // Value Bet 관련
    VALUE_BETS: {
        BY_ROUND: (round: number | string) => `/api/v1/value-bets/${round}`,
        ALL: '/api/v1/value-bets',
    },

    // 조합 최적화 관련
    COMBINATIONS: {
        OPTIMIZE: '/api/v1/combinations/optimize',
        BY_ROUND: (round: number | string) => `/api/v1/combinations/${round}`,
    },

    // 파이프라인
    PIPELINE: {
        ANALYZE: '/api/v1/pipeline/analyze',
    },

    // 헬스체크
    HEALTH: '/health',
} as const;
