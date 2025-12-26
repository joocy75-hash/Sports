import { Card } from '@/components/common';
import { STRATEGY_INFO } from '@/types';
import './Combinations.css';

export default function Combinations() {
    return (
        <div className="combinations">
            <div className="page-header">
                <h1 className="page-title">
                    <span className="title-icon">🎲</span>
                    조합 최적화
                </h1>
                <p className="page-subtitle">5가지 전략별 최적 조합 추천</p>
            </div>

            <Card title="전략 선택" icon="🎯">
                <div className="strategy-grid">
                    {Object.entries(STRATEGY_INFO).map(([key, info]) => (
                        <button key={key} className="strategy-card">
                            <span className="strategy-icon">{info.icon}</span>
                            <span className="strategy-name">{info.name}</span>
                            <p className="strategy-desc">{info.description}</p>
                        </button>
                    ))}
                </div>
            </Card>

            <Card title="조합 결과" icon="📊">
                <div className="placeholder-content">
                    <span className="placeholder-icon">🎲</span>
                    <h3>분석을 먼저 실행해주세요</h3>
                    <p>회차 분석 완료 후 조합 최적화가 자동으로 수행됩니다.</p>
                    <a href="/rounds" className="action-link">
                        회차 분석 페이지로 이동 →
                    </a>
                </div>
            </Card>

            <Card title="조합 전략 상세" icon="📋">
                <div className="strategy-details">
                    <div className="detail-item">
                        <div className="detail-header">
                            <span className="detail-icon">🎯</span>
                            <h4>고신뢰도 전략</h4>
                        </div>
                        <ul>
                            <li>AI 신뢰도 80% 이상 경기만 선택</li>
                            <li>AI 합의도 85% 이상 우선</li>
                            <li>안정적인 적중률 추구</li>
                        </ul>
                    </div>

                    <div className="detail-item">
                        <div className="detail-header">
                            <span className="detail-icon">💰</span>
                            <h4>고가치 전략</h4>
                        </div>
                        <ul>
                            <li>Value +5% 이상 경기 우선</li>
                            <li>높은 기대값 중심</li>
                            <li>장기적 수익 극대화</li>
                        </ul>
                    </div>

                    <div className="detail-item">
                        <div className="detail-header">
                            <span className="detail-icon">⚖️</span>
                            <h4>균형 전략</h4>
                        </div>
                        <ul>
                            <li>신뢰도와 가치의 균형</li>
                            <li>적정 리스크 관리</li>
                            <li>안정적인 ROI 추구</li>
                        </ul>
                    </div>

                    <div className="detail-item">
                        <div className="detail-header">
                            <span className="detail-icon">🛡️</span>
                            <h4>안전 전략</h4>
                        </div>
                        <ul>
                            <li>낮은 배당, 높은 승률 경기</li>
                            <li>리스크 최소화</li>
                            <li>자금 보존 중심</li>
                        </ul>
                    </div>

                    <div className="detail-item">
                        <div className="detail-header">
                            <span className="detail-icon">🔥</span>
                            <h4>공격적 전략</h4>
                        </div>
                        <ul>
                            <li>높은 배당 경기 포함</li>
                            <li>높은 리스크, 높은 수익</li>
                            <li>소액 베팅 권장</li>
                        </ul>
                    </div>
                </div>
            </Card>
        </div>
    );
}
