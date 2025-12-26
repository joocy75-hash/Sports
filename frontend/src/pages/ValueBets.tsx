import { Card } from '@/components/common';
import './ValueBets.css';

export default function ValueBets() {
    return (
        <div className="value-bets">
            <div className="page-header">
                <h1 className="page-title">
                    <span className="title-icon">💰</span>
                    Value Bet 탐색기
                </h1>
                <p className="page-subtitle">가치 베팅 기회를 발견하세요</p>
            </div>

            <Card title="Value Bet이란?" icon="ℹ️">
                <div className="info-content">
                    <p>
                        <strong>Value Bet</strong>은 AI가 예측한 실제 확률 기반 배당률이
                        공식 배당률보다 낮을 때 발생합니다. 이는 해당 결과에 베팅할 경우
                        장기적으로 양의 기대값(+EV)을 갖는다는 것을 의미합니다.
                    </p>
                    <div className="formula-box">
                        <code>Value % = ((공식 배당 / AI 배당) - 1) × 100</code>
                    </div>
                </div>
            </Card>

            <Card title="Value Bet 현황" icon="📊">
                <div className="placeholder-content">
                    <span className="placeholder-icon">🔍</span>
                    <h3>분석을 먼저 실행해주세요</h3>
                    <p>회차 분석 페이지에서 AI 분석을 실행하면 Value Bet이 자동으로 탐지됩니다.</p>
                    <a href="/rounds" className="action-link">
                        회차 분석 페이지로 이동 →
                    </a>
                </div>
            </Card>

            <Card title="Value Bet 등급 안내" icon="📋">
                <div className="grade-list">
                    <div className="grade-item strong-bet">
                        <span className="grade-badge">🔥 STRONG_BET</span>
                        <span className="grade-range">Value +10% 이상</span>
                        <p>매우 높은 기대값. 적극적인 베팅 권장</p>
                    </div>
                    <div className="grade-item bet">
                        <span className="grade-badge">👍 BET</span>
                        <span className="grade-range">Value +5% ~ +10%</span>
                        <p>좋은 기대값. 베팅 권장</p>
                    </div>
                    <div className="grade-item consider">
                        <span className="grade-badge">🤔 CONSIDER</span>
                        <span className="grade-range">Value +2% ~ +5%</span>
                        <p>고려할만한 기대값. 상황에 따라 결정</p>
                    </div>
                    <div className="grade-item skip">
                        <span className="grade-badge">⏭️ SKIP</span>
                        <span className="grade-range">Value 0% ~ +2%</span>
                        <p>기대값이 미미함. 패스 권장</p>
                    </div>
                    <div className="grade-item avoid">
                        <span className="grade-badge">❌ AVOID</span>
                        <span className="grade-range">Value 0% 미만</span>
                        <p>음의 기대값. 베팅 피해야 함</p>
                    </div>
                </div>
            </Card>
        </div>
    );
}
