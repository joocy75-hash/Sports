import './CombinationCard.css';
import Badge from '../common/Badge';
import type { Combination, StrategyType, RiskLevel } from '@/types';
import { STRATEGY_INFO } from '@/types';

interface CombinationCardProps {
    combination: Combination;
    isSelected?: boolean;
    onClick?: () => void;
}

const riskConfig: Record<RiskLevel, { label: string; variant: 'success' | 'primary' | 'warning' | 'danger' }> = {
    LOW: { label: '낮음', variant: 'success' },
    MEDIUM: { label: '보통', variant: 'primary' },
    HIGH: { label: '높음', variant: 'warning' },
    VERY_HIGH: { label: '매우 높음', variant: 'danger' }
};

const outcomeLabels: Record<string, string> = {
    home: '홈',
    draw: '무',
    away: '원'
};

export default function CombinationCard({ combination, isSelected, onClick }: CombinationCardProps) {
    const strategyInfo = STRATEGY_INFO[combination.strategy];
    const riskInfo = riskConfig[combination.risk_level];

    return (
        <div className={`combination-card ${isSelected ? 'selected' : ''}`} onClick={onClick}>
            <div className="comb-header">
                <div className="comb-strategy">
                    <span className="strategy-icon">{strategyInfo.icon}</span>
                    <span className="strategy-name">{strategyInfo.name}</span>
                </div>
                <Badge variant={riskInfo.variant}>{riskInfo.label}</Badge>
            </div>

            <div className="comb-matches">
                {combination.matches.map((match, idx) => (
                    <div key={match.match_id} className="comb-match">
                        <span className="match-num">#{idx + 1}</span>
                        <span className="match-teams">{match.home_team} vs {match.away_team}</span>
                        <span className="match-prediction">{outcomeLabels[match.prediction]}</span>
                        <span className="match-odds">{match.odds.toFixed(2)}</span>
                    </div>
                ))}
            </div>

            <div className="comb-stats">
                <div className="stat-group">
                    <div className="stat-box">
                        <span className="stat-label">총 배당률</span>
                        <span className="stat-value highlight">{combination.total_odds.toFixed(2)}</span>
                    </div>
                    <div className="stat-box">
                        <span className="stat-label">승리 확률</span>
                        <span className="stat-value">{(combination.win_probability * 100).toFixed(1)}%</span>
                    </div>
                </div>
                <div className="stat-group">
                    <div className="stat-box">
                        <span className="stat-label">예상 ROI</span>
                        <span className="stat-value success">+{(combination.expected_roi * 100).toFixed(1)}%</span>
                    </div>
                    <div className="stat-box">
                        <span className="stat-label">권장 베팅</span>
                        <span className="stat-value">{combination.recommended_stake_percentage}%</span>
                    </div>
                </div>
            </div>

            <div className="comb-footer">
                <span className="comb-desc">{strategyInfo.description}</span>
            </div>
        </div>
    );
}
