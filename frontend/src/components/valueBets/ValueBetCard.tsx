import './ValueBetCard.css';
import Badge from '../common/Badge';
import type { ValueBet, ValueRecommendation } from '@/types';

interface ValueBetCardProps {
    valueBet: ValueBet;
    onClick?: () => void;
}

const recommendationConfig: Record<ValueRecommendation, {
    icon: string;
    label: string;
    variant: 'success' | 'primary' | 'warning' | 'default' | 'danger';
}> = {
    STRONG_BET: { icon: '🔥', label: '강력 추천', variant: 'success' },
    BET: { icon: '👍', label: '추천', variant: 'primary' },
    CONSIDER: { icon: '🤔', label: '고려', variant: 'warning' },
    SKIP: { icon: '⏭️', label: '패스', variant: 'default' },
    AVOID: { icon: '❌', label: '피해야 함', variant: 'danger' }
};

const outcomeLabels: Record<string, string> = {
    home: '홈승',
    draw: '무승부',
    away: '원정승'
};

export default function ValueBetCard({ valueBet, onClick }: ValueBetCardProps) {
    const config = recommendationConfig[valueBet.recommendation];

    return (
        <div className={`value-bet-card ${valueBet.recommendation.toLowerCase()}`} onClick={onClick}>
            <div className="vb-header">
                <Badge variant={config.variant} size="lg">
                    {config.icon} {config.label}
                </Badge>
                <span className="vb-value">Value +{valueBet.value_percentage.toFixed(1)}%</span>
            </div>

            <div className="vb-match">
                <span className="vb-teams">{valueBet.home_team} vs {valueBet.away_team}</span>
                <span className="vb-outcome">선택: {outcomeLabels[valueBet.outcome]}</span>
            </div>

            <div className="vb-odds">
                <div className="odds-comparison">
                    <div className="odds-item">
                        <span className="odds-label">AI 배당</span>
                        <span className="odds-value ai">{valueBet.calculated_odds.toFixed(2)}</span>
                    </div>
                    <span className="odds-arrow">→</span>
                    <div className="odds-item">
                        <span className="odds-label">공식 배당</span>
                        <span className="odds-value official">{valueBet.official_odds.toFixed(2)}</span>
                    </div>
                </div>
            </div>

            <div className="vb-stats">
                <div className="stat-item">
                    <span className="stat-label">신뢰도</span>
                    <div className="stat-bar">
                        <div
                            className="stat-fill"
                            style={{
                                width: `${valueBet.confidence}%`,
                                background: valueBet.confidence >= 80 ? 'var(--success-500)' : 'var(--primary-500)'
                            }}
                        />
                    </div>
                    <span className="stat-value">{valueBet.confidence}%</span>
                </div>
                <div className="stat-item">
                    <span className="stat-label">기대값</span>
                    <span className="stat-value ev">+{(valueBet.expected_value * 100).toFixed(1)}%</span>
                </div>
                {valueBet.kelly_fraction && (
                    <div className="stat-item">
                        <span className="stat-label">켈리</span>
                        <span className="stat-value">{(valueBet.kelly_fraction * 100).toFixed(1)}%</span>
                    </div>
                )}
            </div>
        </div>
    );
}
