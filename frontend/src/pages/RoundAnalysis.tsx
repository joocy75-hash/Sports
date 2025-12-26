import { useState } from 'react';
import { useGames, useAnalyzeRound } from '@/hooks';
import { Card, Button, Loading, Badge } from '@/components/common';
import { ConfidenceGauge } from '@/components/charts';
import './RoundAnalysis.css';

export default function RoundAnalysis() {
    const { data: gamesData, isLoading: gamesLoading } = useGames();
    const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
    const [analysisResult, setAnalysisResult] = useState<any>(null);

    const analyzeMutation = useAnalyzeRound();

    if (gamesLoading) {
        return <Loading fullScreen text="경기 정보를 불러오는 중..." />;
    }

    const categories = gamesData?.categories || [];

    // 선택된 카테고리의 경기들
    const selectedCategoryData = categories.find(c => c.name === selectedCategory);
    const matches = selectedCategoryData?.matches || [];

    const handleAnalyze = async () => {
        if (!selectedCategory || matches.length === 0) return;

        try {
            // 분석 실행
            const result = await analyzeMutation.mutateAsync({
                roundNumber: 1, // 임시 라운드 번호
                category: selectedCategory
            });
            setAnalysisResult(result);
        } catch (error) {
            console.error('분석 실패:', error);
        }
    };

    return (
        <div className="round-analysis">
            <div className="page-header">
                <h1 className="page-title">
                    <span className="title-icon">📊</span>
                    회차 분석
                </h1>
                <p className="page-subtitle">AI 앙상블 기반 경기 분석</p>
            </div>

            {/* 카테고리 선택 */}
            <Card title="카테고리 선택" icon="📂">
                <div className="category-tabs">
                    {categories.map((cat) => (
                        <button
                            key={cat.name}
                            className={`category-tab ${selectedCategory === cat.name ? 'active' : ''}`}
                            onClick={() => {
                                setSelectedCategory(cat.name);
                                setAnalysisResult(null);
                            }}
                        >
                            <span className="tab-name">{cat.product_name || cat.name}</span>
                            <span className="tab-count">{cat.count || cat.matches?.length || 0}경기</span>
                        </button>
                    ))}
                </div>
            </Card>

            {/* 분석 버튼 및 경기 목록 */}
            {selectedCategory && matches.length > 0 && (
                <>
                    <div className="analysis-action">
                        <Button
                            variant="primary"
                            size="lg"
                            icon="🔍"
                            onClick={handleAnalyze}
                            loading={analyzeMutation.isPending}
                        >
                            {analyzeMutation.isPending ? 'AI 분석 중...' : `${matches.length}경기 AI 분석 시작`}
                        </Button>

                        {analysisResult && (
                            <Badge variant="success" size="lg">✅ 분석 완료</Badge>
                        )}
                    </div>

                    {/* 분석 결과 요약 */}
                    {analysisResult && (
                        <Card title="분석 결과 요약" icon="📈">
                            <div className="analysis-summary">
                                <div className="summary-stat">
                                    <span className="stat-label">분석 경기</span>
                                    <span className="stat-value">{analysisResult.summary?.total_matches || matches.length}경기</span>
                                </div>
                                <div className="summary-stat">
                                    <span className="stat-label">고신뢰도</span>
                                    <span className="stat-value highlight">{analysisResult.summary?.high_confidence_count || 0}개</span>
                                </div>
                                <div className="summary-stat">
                                    <span className="stat-label">Value Bet</span>
                                    <span className="stat-value success">{analysisResult.summary?.value_bets_count || 0}개</span>
                                </div>
                                <div className="summary-stat">
                                    <span className="stat-label">AI 합의도</span>
                                    <ConfidenceGauge
                                        value={analysisResult.summary?.ai_consensus_avg || 0}
                                        size="sm"
                                        showValue={true}
                                    />
                                </div>
                            </div>
                        </Card>
                    )}

                    {/* 경기 목록 */}
                    <Card title={`경기 목록 (${matches.length}경기)`} icon="⚽">
                        <div className="matches-list">
                            {matches.map((match) => (
                                <div key={match.match_id} className="match-row">
                                    <div className="match-info">
                                        <span className="match-teams">
                                            {match.home_team} vs {match.away_team}
                                        </span>
                                        <span className="match-time">
                                            {new Date(match.match_time).toLocaleString('ko-KR', {
                                                month: 'short',
                                                day: 'numeric',
                                                hour: '2-digit',
                                                minute: '2-digit'
                                            })}
                                        </span>
                                    </div>
                                    <div className="match-odds">
                                        <span className="odds home">{match.home_odds?.toFixed(2) || '-'}</span>
                                        <span className="odds draw">{match.draw_odds?.toFixed(2) || '-'}</span>
                                        <span className="odds away">{match.away_odds?.toFixed(2) || '-'}</span>
                                    </div>
                                    <span className={`match-status status-${match.status}`}>
                                        {match.status}
                                    </span>
                                </div>
                            ))}
                        </div>
                    </Card>
                </>
            )}

            {/* 빈 상태 */}
            {!selectedCategory && (
                <div className="empty-state">
                    <span className="empty-icon">👆</span>
                    <p>분석할 카테고리를 선택해주세요</p>
                </div>
            )}

            {selectedCategory && matches.length === 0 && (
                <div className="empty-state">
                    <span className="empty-icon">📭</span>
                    <p>해당 카테고리에 분석 가능한 경기가 없습니다</p>
                </div>
            )}
        </div>
    );
}
