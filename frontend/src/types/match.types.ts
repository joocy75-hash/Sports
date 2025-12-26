// 경기 관련 타입 정의

export interface Match {
    id?: string;
    match_id: string;
    round_id?: string;
    round_number?: number;
    home_team: string;
    away_team: string;
    match_time: string;
    status: MatchStatus;
    category_name?: string;
    league?: string;
    odds?: MatchOdds;
    home_odds?: number;
    draw_odds?: number;
    away_odds?: number;
}

export type MatchStatus = '예정' | '진행중' | '종료' | '마감' | string;

export interface MatchOdds {
    home_win: number;
    draw: number;
    away_win: number;
    timestamp?: string;
}

export interface Round {
    round_number: number;
    round_id: string;
    category: string;
    matches: Match[];
    match_count: number;
    deadline?: string;
}

// 백엔드 API 응답 형식에 맞춤
export interface GamesListResponse {
    success: boolean;
    total_matches: number;
    categories: CategoryGroup[];
    fetched_at: string;
}

export interface CategoryGroup {
    name: string;           // 카테고리 코드 예: "승무패"
    product_name: string;   // 제품명 예: "축구 승무패"
    sport_type?: string;    // 스포츠 종류
    count: number;          // 경기 수
    matches: Match[];       // 해당 카테고리의 경기들
}

export interface MatchWithAnalysis extends Match {
    analysis?: MatchAnalysis;
}

export interface MatchAnalysis {
    match_id: string;
    prediction: 'home' | 'draw' | 'away';
    probabilities: {
        home: number;
        draw: number;
        away: number;
    };
    confidence: number;
    consensus?: number;
    factors?: string[];
    ai_opinions?: AIOpinion[];
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
