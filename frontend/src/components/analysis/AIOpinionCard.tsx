import './AIOpinionCard.css';
import type { AIOpinion } from '@/types';

interface AIOpinionCardProps {
    opinion: AIOpinion;
    isConsensus?: boolean;
}

const aiColors: Record<string, string> = {
    'GPT-4': '#10B981',
    'Claude': '#8B5CF6',
    'Gemini': '#3B82F6',
    'Kimi': '#F97316',
    'DeepSeek': '#22C55E'
};

const aiIcons: Record<string, string> = {
    'GPT-4': '🤖',
    'Claude': '🟣',
    'Gemini': '🔵',
    'Kimi': '🟠',
    'DeepSeek': '🟢'
};

const predictionLabels: Record<string, string> = {
    home: '홈승',
    draw: '무',
    away: '원정승'
};

export default function AIOpinionCard({ opinion, isConsensus }: AIOpinionCardProps) {
    const color = aiColors[opinion.ai_name] || '#6B7280';
    const icon = aiIcons[opinion.ai_name] || '🤖';

    const maxProb = Math.max(
        opinion.probabilities.home,
        opinion.probabilities.draw,
        opinion.probabilities.away
    );

    return (
        <div className={`ai-opinion-card ${isConsensus ? 'consensus' : ''}`}>
            <div className="aio-header">
                <div className="aio-ai" style={{ borderColor: color }}>
                    <span className="aio-icon">{icon}</span>
                    <span className="aio-name">{opinion.ai_name}</span>
                </div>
                <div className="aio-prediction" style={{ color }}>
                    {predictionLabels[opinion.prediction]}
                </div>
            </div>

            <div className="aio-probabilities">
                <div className="prob-bar-container">
                    <div className="prob-row">
                        <span className="prob-label">홈승</span>
                        <div className="prob-bar">
                            <div
                                className="prob-fill home"
                                style={{
                                    width: `${opinion.probabilities.home}%`,
                                    opacity: opinion.probabilities.home === maxProb ? 1 : 0.5
                                }}
                            />
                        </div>
                        <span className="prob-value">{opinion.probabilities.home.toFixed(0)}%</span>
                    </div>
                    <div className="prob-row">
                        <span className="prob-label">무</span>
                        <div className="prob-bar">
                            <div
                                className="prob-fill draw"
                                style={{
                                    width: `${opinion.probabilities.draw}%`,
                                    opacity: opinion.probabilities.draw === maxProb ? 1 : 0.5
                                }}
                            />
                        </div>
                        <span className="prob-value">{opinion.probabilities.draw.toFixed(0)}%</span>
                    </div>
                    <div className="prob-row">
                        <span className="prob-label">원정</span>
                        <div className="prob-bar">
                            <div
                                className="prob-fill away"
                                style={{
                                    width: `${opinion.probabilities.away}%`,
                                    opacity: opinion.probabilities.away === maxProb ? 1 : 0.5
                                }}
                            />
                        </div>
                        <span className="prob-value">{opinion.probabilities.away.toFixed(0)}%</span>
                    </div>
                </div>
            </div>

            <div className="aio-confidence">
                <span className="conf-label">신뢰도</span>
                <span className="conf-value" style={{ color }}>{opinion.confidence}%</span>
            </div>

            {opinion.reasoning && (
                <div className="aio-reasoning">
                    <p>{opinion.reasoning}</p>
                </div>
            )}
        </div>
    );
}
