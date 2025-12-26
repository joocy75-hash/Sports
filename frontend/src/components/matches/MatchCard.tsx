import { format } from 'date-fns';
import { ko } from 'date-fns/locale';
import Badge from '../common/Badge';
import './MatchCard.css';
import type { Match, MatchAnalysis } from '@/types';

interface MatchCardProps {
    match: Match;
    analysis?: MatchAnalysis;
    showAnalysis?: boolean;
    onClick?: () => void;
}

const predictionLabels: Record<string, string> = {
    home: '홈승',
    draw: '무',
    away: '원정승'
};

const predictionColors: Record<string, 'primary' | 'info' | 'warning'> = {
    home: 'primary',
    draw: 'info',
    away: 'warning'
};

export default function MatchCard({
    match,
    analysis,
    showAnalysis = true,
    onClick
}: MatchCardProps) {
    const matchTime = new Date(match.match_time);

    const getStatusBadge = (status: string) => {
        switch (status) {
            case '진행중':
                return <Badge variant="success" icon="🔴">LIVE</Badge>;
            case '종료':
                return <Badge variant="default">종료</Badge>;
            case '마감':
                return <Badge variant="danger">마감</Badge>;
            default:
                return <Badge variant="primary">{format(matchTime, 'HH:mm')}</Badge>;
        }
    };

    return (
        <div className="match-card" onClick={onClick}>
            <div className="match-header">
                <span className="match-number">#{match.match_id.slice(-3)}</span>
                {getStatusBadge(match.status)}
                {match.league && (
                    <span className="match-league">{match.league}</span>
                )}
            </div>

            <div className="match-teams">
                <div className="team home">
                    <div className="team-logo">🏠</div>
                    <span className="team-name">{match.home_team}</span>
                </div>

                <div className="vs-badge">VS</div>

                <div className="team away">
                    <span className="team-name">{match.away_team}</span>
                    <div className="team-logo">✈️</div>
                </div>
            </div>

            {match.odds && (
                <div className="match-odds">
                    <div className="odds-item home">
                        <span className="odds-label">홈승</span>
                        <span className="odds-value">{match.odds.home_win.toFixed(2)}</span>
                    </div>
                    <div className="odds-item draw">
                        <span className="odds-label">무</span>
                        <span className="odds-value">{match.odds.draw.toFixed(2)}</span>
                    </div>
                    <div className="odds-item away">
                        <span className="odds-label">원정</span>
                        <span className="odds-value">{match.odds.away_win.toFixed(2)}</span>
                    </div>
                </div>
            )}

            {showAnalysis && analysis && (
                <div className="match-analysis">
                    <div className="analysis-row">
                        <span className="analysis-label">AI 예측</span>
                        <Badge variant={predictionColors[analysis.prediction]}>
                            {predictionLabels[analysis.prediction]}
                        </Badge>
                    </div>
                    <div className="analysis-row">
                        <span className="analysis-label">신뢰도</span>
                        <div className="confidence-bar">
                            <div
                                className="confidence-fill"
                                style={{
                                    width: `${analysis.confidence}%`,
                                    background: analysis.confidence >= 80
                                        ? 'var(--success-500)'
                                        : analysis.confidence >= 60
                                            ? 'var(--primary-500)'
                                            : 'var(--warning-500)'
                                }}
                            />
                        </div>
                        <span className="confidence-value">{analysis.confidence}%</span>
                    </div>
                    {analysis.consensus && (
                        <div className="analysis-row">
                            <span className="analysis-label">AI 합의</span>
                            <span className="consensus-value">{analysis.consensus}%</span>
                        </div>
                    )}
                </div>
            )}

            <div className="match-footer">
                <span className="match-time">
                    {format(matchTime, 'M월 d일 (EEE) HH:mm', { locale: ko })}
                </span>
            </div>
        </div>
    );
}
