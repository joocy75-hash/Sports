// 분석 관련 타입 정의

export interface RoundAnalysis {
    round_id: string;
    round_number: number;
    category: string;
    matches: MatchAnalysisResult[];
    summary: AnalysisSummary;
    value_bets: ValueBet[];
    combinations: Combination[];
    analyzed_at: string;
}

export interface MatchAnalysisResult {
    match_id: string;
    home_team: string;
    away_team: string;
    match_time: string;

    // AI 예측
    prediction: 'home' | 'draw' | 'away';
    probabilities: {
        home: number;
        draw: number;
        away: number;
    };
    confidence: number;
    consensus: number;

    // AI별 의견
    ai_opinions: AIOpinion[];

    // 주요 요인
    key_factors: string[];

    // 배당률
    calculated_odds: {
        home_win: number;
        draw: number;
        away_win: number;
    };
    official_odds?: {
        home_win: number;
        draw: number;
        away_win: number;
    };

    // Value 분석
    value_analysis?: ValueAnalysis;
}

export interface AIOpinion {
    ai_name: string;
    prediction: 'home' | 'draw' | 'away';
    probabilities: {
        home: number;
        draw: number;
        away: number;
    };
    confidence: number;
    reasoning?: string;
}

export interface AnalysisSummary {
    total_matches: number;
    high_confidence_count: number;
    value_bets_count: number;
    ai_consensus_avg: number;
}

export interface ValueAnalysis {
    outcome: 'home' | 'draw' | 'away';
    calculated_odds: number;
    official_odds: number;
    value_percentage: number;
    expected_value: number;
    recommendation: ValueRecommendation;
    kelly_fraction?: number;
}

export type ValueRecommendation =
    | 'STRONG_BET'
    | 'BET'
    | 'CONSIDER'
    | 'SKIP'
    | 'AVOID';

export interface ValueBet {
    id: string;
    match_id: string;
    home_team: string;
    away_team: string;
    match_time: string;
    outcome: 'home' | 'draw' | 'away';
    calculated_odds: number;
    official_odds: number;
    value_percentage: number;
    expected_value: number;
    confidence: number;
    recommendation: ValueRecommendation;
    kelly_fraction?: number;
}

export interface Combination {
    id: string;
    strategy: StrategyType;
    strategy_name: string;
    matches: CombinationMatch[];
    total_odds: number;
    win_probability: number;
    expected_roi: number;
    risk_level: RiskLevel;
    recommended_stake_percentage: number;
}

export interface CombinationMatch {
    match_id: string;
    home_team: string;
    away_team: string;
    prediction: 'home' | 'draw' | 'away';
    odds: number;
    probability: number;
    confidence: number;
}

export type StrategyType =
    | 'high_confidence'
    | 'high_value'
    | 'balanced'
    | 'safe'
    | 'aggressive';

export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'VERY_HIGH';

// 전략 메타데이터
export const STRATEGY_INFO: Record<StrategyType, {
    name: string;
    icon: string;
    color: string;
    description: string;
}> = {
    high_confidence: {
        name: '고신뢰도',
        icon: '🎯',
        color: 'var(--primary-500)',
        description: '신뢰도 80% 이상 경기만 선택'
    },
    high_value: {
        name: '고가치',
        icon: '💰',
        color: 'var(--success-500)',
        description: 'Value가 높은 경기 중심'
    },
    balanced: {
        name: '균형',
        icon: '⚖️',
        color: 'var(--strategy-balanced)',
        description: '신뢰도와 가치의 균형'
    },
    safe: {
        name: '안전',
        icon: '🛡️',
        color: 'var(--strategy-safe)',
        description: '낮은 배당, 높은 승률'
    },
    aggressive: {
        name: '공격적',
        icon: '🔥',
        color: 'var(--strategy-aggressive)',
        description: '높은 배당, 높은 리스크'
    }
};

// 추천 등급 메타데이터
export const RECOMMENDATION_INFO: Record<ValueRecommendation, {
    name: string;
    color: string;
    bgColor: string;
}> = {
    STRONG_BET: {
        name: '강력 추천',
        color: 'var(--success-400)',
        bgColor: 'rgba(34, 197, 94, 0.15)'
    },
    BET: {
        name: '추천',
        color: 'var(--primary-400)',
        bgColor: 'rgba(59, 130, 246, 0.15)'
    },
    CONSIDER: {
        name: '고려',
        color: 'var(--warning-400)',
        bgColor: 'rgba(234, 179, 8, 0.15)'
    },
    SKIP: {
        name: '패스',
        color: 'var(--gray-400)',
        bgColor: 'rgba(107, 114, 128, 0.15)'
    },
    AVOID: {
        name: '피해야 함',
        color: 'var(--danger-400)',
        bgColor: 'rgba(239, 68, 68, 0.15)'
    }
};
