import { useState, useEffect } from 'react';
import { Card } from '@/components/common';
import './RecommendedMatches.css';

interface ConfidenceBadgeProps {
    level: 'HIGH' | 'MEDIUM' | 'LOW';
    score: number;
}

function ConfidenceBadge({ level, score }: ConfidenceBadgeProps) {
    const colors = {
        HIGH: '#10b981',
        MEDIUM: '#f59e0b',
        LOW: '#ef4444'
    };

    const labels = {
        HIGH: '높음',
        MEDIUM: '중간',
        LOW: '낮음'
    };

    return (
        <div className="confidence-badge" style={{ backgroundColor: colors[level] }}>
            <span className="badge-label">{labels[level]}</span>
            <span className="badge-score">{score}%</span>
        </div>
    );
}

interface EVBadgeProps {
    value: number;
}

function EVBadge({ value }: EVBadgeProps) {
    const isPositive = value > 0;
    const className = `ev-badge ${isPositive ? 'positive' : 'negative'}`;

    return (
        <div className={className}>
            <span className="ev-label">EV</span>
            <span className="ev-value">{value > 0 ? '+' : ''}{value.toFixed(1)}%</span>
        </div>
    );
}

interface RecommendedMatch {
    match_id: number;
    home_team: string;
    away_team: string;
    league: string;
    match_time: string;
    confidence_level: 'HIGH' | 'MEDIUM' | 'LOW';
    confidence_score: number;
    ev_percentage: number;
    recommended_outcome: 'H' | 'D' | 'A';
    predicted_probability: number;
    reasoning: string;
}

interface RecommendedMatchesProps {
    limit?: number;
}

export default function RecommendedMatches({ limit = 5 }: RecommendedMatchesProps) {
    const [matches, setMatches] = useState<RecommendedMatch[]>([]);
    const [loading, setLoading] = useState(true);
    const [filter, setFilter] = useState<'all' | 'high-ev' | 'high-confidence' | 'today'>('all');

    useEffect(() => {
        // TODO: API 호출하여 추천 경기 가져오기
        // 임시 데이터
        const mockData: RecommendedMatch[] = [
            {
                match_id: 1,
                home_team: '맨체스터 시티',
                away_team: '첼시',
                league: '프리미어리그',
                match_time: new Date(Date.now() + 3600000).toISOString(),
                confidence_level: 'HIGH',
                confidence_score: 85,
                ev_percentage: 12.5,
                recommended_outcome: 'H',
                predicted_probability: 0.65,
                reasoning: '홈 무패 행진 중, 상대 전적 우세'
            },
            {
                match_id: 2,
                home_team: '레알 마드리드',
                away_team: '바르셀로나',
                league: '라리가',
                match_time: new Date(Date.now() + 7200000).toISOString(),
                confidence_level: 'MEDIUM',
                confidence_score: 72,
                ev_percentage: 8.3,
                recommended_outcome: 'H',
                predicted_probability: 0.55,
                reasoning: '홈 우위, 최근 폼 상승'
            }
        ];

        setTimeout(() => {
            setMatches(mockData);
            setLoading(false);
        }, 500);
    }, [filter]);

    const filteredMatches = matches.slice(0, limit);

    const outcomeLabels = {
        H: '홈승',
        D: '무승부',
        A: '원정승'
    };

    return (
        <Card title="🎯 오늘의 AI 추천 경기" icon="⭐">
            {/* 필터 */}
            <div className="match-filters">
                <button
                    className={`filter-btn ${filter === 'all' ? 'active' : ''}`}
                    onClick={() => setFilter('all')}
                >
                    전체
                </button>
                <button
                    className={`filter-btn ${filter === 'high-ev' ? 'active' : ''}`}
                    onClick={() => setFilter('high-ev')}
                >
                    높은 EV
                </button>
                <button
                    className={`filter-btn ${filter === 'high-confidence' ? 'active' : ''}`}
                    onClick={() => setFilter('high-confidence')}
                >
                    높은 신뢰도
                </button>
                <button
                    className={`filter-btn ${filter === 'today' ? 'active' : ''}`}
                    onClick={() => setFilter('today')}
                >
                    오늘 경기
                </button>
            </div>

            {/* 추천 경기 리스트 */}
            <div className="recommended-matches-list">
                {loading ? (
                    <div className="loading-state">
                        <div className="spinner"></div>
                        <p>AI가 추천 경기를 분석하는 중...</p>
                    </div>
                ) : filteredMatches.length === 0 ? (
                    <div className="empty-state">
                        <span className="empty-icon">🤔</span>
                        <p>현재 추천할 경기가 없습니다</p>
                    </div>
                ) : (
                    filteredMatches.map((match, index) => (
                        <div key={match.match_id} className="recommended-match-card">
                            {/* 랭킹 배지 */}
                            <div className="rank-badge">#{index + 1}</div>

                            {/* 경기 정보 */}
                            <div className="match-header">
                                <div className="teams">
                                    <span className="team home">{match.home_team}</span>
                                    <span className="vs">vs</span>
                                    <span className="team away">{match.away_team}</span>
                                </div>
                                <div className="league">{match.league}</div>
                            </div>

                            {/* 배지들 */}
                            <div className="badges">
                                <ConfidenceBadge
                                    level={match.confidence_level}
                                    score={match.confidence_score}
                                />
                                <EVBadge value={match.ev_percentage} />
                            </div>

                            {/* AI 추천 */}
                            <div className="recommendation">
                                <div className="rec-label">AI 추천</div>
                                <div className="rec-value">
                                    <span className="outcome">{outcomeLabels[match.recommended_outcome]}</span>
                                    <span className="probability">
                                        ({(match.predicted_probability * 100).toFixed(0)}%)
                                    </span>
                                </div>
                            </div>

                            {/* 분석 근거 */}
                            <div className="reasoning">
                                <span className="reasoning-icon">💡</span>
                                <span className="reasoning-text">{match.reasoning}</span>
                            </div>

                            {/* 경기 시간 */}
                            <div className="match-time">
                                <span className="time-icon">⏰</span>
                                <span className="time-text">
                                    {new Date(match.match_time).toLocaleString('ko-KR', {
                                        month: 'short',
                                        day: 'numeric',
                                        hour: '2-digit',
                                        minute: '2-digit'
                                    })}
                                </span>
                            </div>

                            {/* 상세 보기 버튼 */}
                            <button
                                className="analyze-btn"
                                onClick={() => window.location.href = `/match/${match.match_id}`}
                            >
                                상세 분석 보기 →
                            </button>
                        </div>
                    ))
                )}
            </div>
        </Card>
    );
}
