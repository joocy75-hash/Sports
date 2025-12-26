import { Card } from '@/components/common';
import './AIInsights.css';

export default function AIInsights() {
    const aiModels = [
        { name: 'GPT-4', icon: '🤖', color: '#10B981', specialty: '패턴 분석 및 추론' },
        { name: 'Claude', icon: '🟣', color: '#8B5CF6', specialty: '상대 전적 분석' },
        { name: 'Gemini', icon: '🔵', color: '#3B82F6', specialty: '실시간 데이터 통합' },
        { name: 'Kimi', icon: '🟠', color: '#F97316', specialty: '아시아 리그 전문' },
        { name: 'DeepSeek', icon: '🟢', color: '#22C55E', specialty: '딥러닝 예측' }
    ];

    return (
        <div className="ai-insights">
            <div className="page-header">
                <h1 className="page-title">
                    <span className="title-icon">🤖</span>
                    AI 인사이트
                </h1>
                <p className="page-subtitle">5개 AI 모델의 예측 비교 및 분석</p>
            </div>

            <Card title="AI 앙상블 시스템" icon="🧠">
                <div className="ai-grid">
                    {aiModels.map((ai) => (
                        <div key={ai.name} className="ai-card" style={{ borderColor: ai.color }}>
                            <div className="ai-icon" style={{ background: ai.color }}>{ai.icon}</div>
                            <div className="ai-info">
                                <span className="ai-name">{ai.name}</span>
                                <span className="ai-specialty">{ai.specialty}</span>
                            </div>
                        </div>
                    ))}
                </div>
            </Card>

            <Card title="AI 비교 분석" icon="📊">
                <div className="placeholder-content">
                    <span className="placeholder-icon">🔍</span>
                    <h3>경기를 선택해주세요</h3>
                    <p>회차 분석에서 특정 경기를 선택하면 AI별 상세 분석을 확인할 수 있습니다.</p>
                    <a href="/rounds" className="action-link">
                        회차 분석 페이지로 이동 →
                    </a>
                </div>
            </Card>

            <Card title="앙상블 분석 방법" icon="📋">
                <div className="method-content">
                    <div className="method-step">
                        <div className="step-number">1</div>
                        <div className="step-content">
                            <h4>개별 AI 분석</h4>
                            <p>5개 AI가 각각 독립적으로 경기를 분석하고 홈승/무/원정승 확률을 예측합니다.</p>
                        </div>
                    </div>

                    <div className="method-step">
                        <div className="step-number">2</div>
                        <div className="step-content">
                            <h4>가중치 적용</h4>
                            <p>각 AI의 과거 정확도를 기반으로 가중치를 적용합니다. 더 정확한 AI의 의견이 더 큰 영향을 미칩니다.</p>
                        </div>
                    </div>

                    <div className="method-step">
                        <div className="step-number">3</div>
                        <div className="step-content">
                            <h4>합의도 계산</h4>
                            <p>AI들의 예측이 얼마나 일치하는지 계산합니다. 합의도가 높을수록 예측의 신뢰도가 높습니다.</p>
                        </div>
                    </div>

                    <div className="method-step">
                        <div className="step-number">4</div>
                        <div className="step-content">
                            <h4>최종 예측 도출</h4>
                            <p>가중 평균을 통해 최종 확률을 계산하고, 가장 높은 확률의 결과를 예측으로 선택합니다.</p>
                        </div>
                    </div>
                </div>
            </Card>
        </div>
    );
}
