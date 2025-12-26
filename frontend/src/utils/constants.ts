// API 관련 상수
export const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
export const API_TIMEOUT = 30000;

// 갱신 주기 (밀리초)
export const REFRESH_INTERVALS = {
    GAMES: 60 * 1000,      // 1분
    ANALYSIS: 5 * 60 * 1000, // 5분
    ODDS: 30 * 1000,       // 30초
} as const;

// 예측 레이블
export const PREDICTION_LABELS: Record<string, string> = {
    home: '홈승',
    draw: '무승부',
    away: '원정승'
} as const;

// 예측 색상
export const PREDICTION_COLORS: Record<string, string> = {
    home: 'var(--odds-home)',
    draw: 'var(--odds-draw)',
    away: 'var(--odds-away)'
} as const;

// 리스크 레벨
export const RISK_LEVELS = {
    LOW: { label: '낮음', color: 'var(--success-500)' },
    MEDIUM: { label: '보통', color: 'var(--primary-500)' },
    HIGH: { label: '높음', color: 'var(--warning-500)' },
    VERY_HIGH: { label: '매우 높음', color: 'var(--danger-500)' }
} as const;

// AI 모델 정보
export const AI_MODELS = [
    { id: 'gpt-4', name: 'GPT-4', icon: '🤖', color: '#10B981' },
    { id: 'claude', name: 'Claude', icon: '🟣', color: '#8B5CF6' },
    { id: 'gemini', name: 'Gemini', icon: '🔵', color: '#3B82F6' },
    { id: 'kimi', name: 'Kimi', icon: '🟠', color: '#F97316' },
    { id: 'deepseek', name: 'DeepSeek', icon: '🟢', color: '#22C55E' }
] as const;

// 경기 상태
export const MATCH_STATUS = {
    SCHEDULED: { label: '예정', color: 'var(--primary-500)' },
    LIVE: { label: '진행중', color: 'var(--success-500)' },
    FINISHED: { label: '종료', color: 'var(--gray-500)' },
    CLOSED: { label: '마감', color: 'var(--danger-500)' }
} as const;

// 페이지 메타 정보
export const PAGE_META = {
    dashboard: { title: '대시보드', icon: '🏠' },
    rounds: { title: '회차 분석', icon: '📊' },
    valueBets: { title: 'Value Bet', icon: '💰' },
    combinations: { title: '조합 최적화', icon: '🎲' },
    aiInsights: { title: 'AI 인사이트', icon: '🤖' },
    settings: { title: '설정', icon: '⚙️' }
} as const;
