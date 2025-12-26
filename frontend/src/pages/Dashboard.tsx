import { useGames } from '@/hooks';
import { StatCard, Card, Loading } from '@/components/common';
import RecommendedMatches from '@/components/RecommendedMatches';
import './Dashboard.css';

export default function Dashboard() {
    const { data: gamesData, isLoading, error } = useGames();

    if (isLoading) {
        return <Loading fullScreen text="경기 정보를 불러오는 중..." />;
    }

    if (error) {
        return (
            <div className="error-container">
                <div className="error-icon">⚠️</div>
                <h2>데이터를 불러올 수 없습니다</h2>
                <p>백엔드 서버가 실행 중인지 확인해주세요.</p>
                <button className="btn btn-primary" onClick={() => window.location.reload()}>
                    다시 시도
                </button>
            </div>
        );
    }

    // 모든 경기 추출
    const allMatches = gamesData?.categories?.flatMap(
        cat => cat.matches || []
    ) || [];

    const totalMatches = gamesData?.total_matches || allMatches.length;
    const upcomingMatches = allMatches.filter(m => m.status === '예정').length;

    return (
        <div className="dashboard">
            <div className="page-header">
                <h1 className="page-title">
                    <span className="title-icon">🏠</span>
                    대시보드
                </h1>
                <p className="page-subtitle">AI 앙상블 기반 스포츠 배당률 분석 시스템</p>
            </div>

            {/* 통계 카드 */}
            <div className="stats-grid">
                <StatCard
                    title="전체 경기"
                    value={`${totalMatches}경기`}
                    icon="📊"
                    color="primary"
                    subtitle={gamesData?.fetched_at ? `마지막 업데이트: ${new Date(gamesData.fetched_at).toLocaleTimeString('ko-KR')}` : undefined}
                />
                <StatCard
                    title="예정 경기"
                    value={`${upcomingMatches}경기`}
                    icon="⏰"
                    color="success"
                    subtitle="분석 가능"
                />
                <StatCard
                    title="Value Bet"
                    value="분석 필요"
                    icon="💰"
                    color="warning"
                    subtitle="회차 분석 후 확인"
                />
                <StatCard
                    title="AI 합의도"
                    value="-"
                    icon="🎯"
                    color="primary"
                    subtitle="분석 후 표시"
                />
            </div>

            {/* AI 추천 경기 */}
            <RecommendedMatches limit={5} />

            {/* 카테고리별 경기 현황 */}
            <Card title="카테고리별 현황" icon="📋">
                <div className="category-list">
                    {gamesData?.categories?.map((category) => (
                        <div key={category.name} className="category-item">
                            <div className="category-info">
                                <span className="category-name">{category.product_name || category.name}</span>
                                <span className="category-code">{category.name}</span>
                            </div>
                            <div className="category-stats">
                                <span className="match-count">
                                    {category.count || category.matches?.length || 0}경기
                                </span>
                            </div>
                        </div>
                    ))}

                    {(!gamesData?.categories || gamesData.categories.length === 0) && (
                        <div className="empty-state">
                            <span className="empty-icon">📭</span>
                            <p>조회된 경기가 없습니다</p>
                        </div>
                    )}
                </div>
            </Card>

            {/* 최근 경기 */}
            {allMatches.length > 0 && (
                <Card title="최근 경기" icon="⚽">
                    <div className="matches-preview">
                        {allMatches.slice(0, 6).map(match => (
                            <div key={match.match_id} className="match-preview-item">
                                <div className="match-teams">
                                    <span className="team home">{match.home_team}</span>
                                    <span className="vs">vs</span>
                                    <span className="team away">{match.away_team}</span>
                                </div>
                                <div className="match-meta">
                                    <span className={`match-status status-${match.status}`}>
                                        {match.status}
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
                            </div>
                        ))}
                    </div>
                </Card>
            )}

            {/* 빠른 시작 가이드 */}
            <Card title="빠른 시작" icon="🚀">
                <div className="quick-start">
                    <div className="step">
                        <div className="step-number">1</div>
                        <div className="step-content">
                            <h4>회차 선택</h4>
                            <p>분석할 경기 회차를 선택합니다</p>
                        </div>
                    </div>
                    <div className="step">
                        <div className="step-number">2</div>
                        <div className="step-content">
                            <h4>AI 분석 실행</h4>
                            <p>5개 AI가 각 경기를 분석합니다</p>
                        </div>
                    </div>
                    <div className="step">
                        <div className="step-number">3</div>
                        <div className="step-content">
                            <h4>Value Bet 확인</h4>
                            <p>가치 있는 베팅 기회를 발견합니다</p>
                        </div>
                    </div>
                    <div className="step">
                        <div className="step-number">4</div>
                        <div className="step-content">
                            <h4>최적 조합 선택</h4>
                            <p>전략별 최적 조합을 확인합니다</p>
                        </div>
                    </div>
                </div>
            </Card>
        </div>
    );
}
