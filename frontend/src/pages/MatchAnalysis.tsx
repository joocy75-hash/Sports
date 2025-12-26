import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar, LineChart, Line } from 'recharts';
import { Card, Loading } from '@/components/common';
import './MatchAnalysis.css';

interface MatchAnalysisData {
    match_id: number;
    home_team: string;
    away_team: string;
    league: string;
    match_time: string;
    probabilities: {
        home: number;
        draw: number;
        away: number;
    };
    confidence_score: number;
    confidence_level: string;
    ev_percentage: number;
    recommended_outcome: string;
    ai_opinions: Array<{
        provider: string;
        winner: string;
        confidence: number;
        reasoning: string;
    }>;
    team_stats: {
        home: any;
        away: any;
    };
    recent_form: {
        home: string[];
        away: string[];
    };
    head_to_head: Array<{
        date: string;
        home_score: number;
        away_score: number;
        winner: string;
    }>;
    deepseek_analysis: string;
}

export default function MatchAnalysis() {
    const { id } = useParams<{ id: string }>();
    const [data, setData] = useState<MatchAnalysisData | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        // TODO: API 호출
        // 임시 목 데이터
        setTimeout(() => {
            setData({
                match_id: parseInt(id || '1'),
                home_team: '맨체스터 시티',
                away_team: '첼시',
                league: '프리미어리그',
                match_time: new Date(Date.now() + 3600000).toISOString(),
                probabilities: {
                    home: 0.65,
                    draw: 0.20,
                    away: 0.15
                },
                confidence_score: 85,
                confidence_level: 'HIGH',
                ev_percentage: 12.5,
                recommended_outcome: '홈승',
                ai_opinions: [
                    {
                        provider: 'GPT-4',
                        winner: '홈승',
                        confidence: 87,
                        reasoning: '홈 어드밴티지와 최근 폼 고려 시 홈팀 우세'
                    },
                    {
                        provider: 'Claude',
                        winner: '홈승',
                        confidence: 83,
                        reasoning: '상대전적에서 홈팀이 압도적 우위'
                    },
                    {
                        provider: 'Gemini',
                        winner: '홈승',
                        confidence: 85,
                        reasoning: '선수 부상 상황 고려 시 홈팀 유리'
                    }
                ],
                team_stats: {
                    home: {
                        goals_avg: 2.5,
                        conceded_avg: 0.8,
                        possession: 65,
                        shots: 18,
                        shots_on_target: 8
                    },
                    away: {
                        goals_avg: 1.2,
                        conceded_avg: 1.5,
                        possession: 45,
                        shots: 10,
                        shots_on_target: 4
                    }
                },
                recent_form: {
                    home: ['W', 'W', 'D', 'W', 'W'],
                    away: ['L', 'D', 'L', 'W', 'D']
                },
                head_to_head: [
                    { date: '2024-11-10', home_score: 3, away_score: 1, winner: 'home' },
                    { date: '2024-08-15', home_score: 2, away_score: 0, winner: 'home' },
                    { date: '2024-05-20', home_score: 1, away_score: 1, winner: 'draw' },
                    { date: '2024-02-12', home_score: 4, away_score: 2, winner: 'home' },
                    { date: '2023-11-25', home_score: 2, away_score: 1, winner: 'home' }
                ],
                deepseek_analysis: '맨체스터 시티는 홈에서 무패 행진을 이어가고 있으며, 첼시는 원정에서 3연패 중입니다. 핵심 선수인 할란드와 데 브라위너가 모두 출전 가능하며, 첼시는 주전 수비수 2명이 부상으로 결장합니다. 최근 5경기 상대전적에서 맨시티가 4승 1무로 압도적 우위를 보이고 있습니다.'
            });
            setLoading(false);
        }, 800);
    }, [id]);

    if (loading) {
        return <Loading fullScreen text="경기 분석을 불러오는 중..." />;
    }

    if (!data) {
        return <div className="error-container">경기 데이터를 찾을 수 없습니다.</div>;
    }

    // 승률 차트 데이터
    const probabilityData = [
        {
            name: '홈승',
            probability: data.probabilities.home * 100,
            fill: '#10b981'
        },
        {
            name: '무승부',
            probability: data.probabilities.draw * 100,
            fill: '#f59e0b'
        },
        {
            name: '원정승',
            probability: data.probabilities.away * 100,
            fill: '#ef4444'
        }
    ];

    // 팀 스탯 비교 레이더 차트 데이터
    const statsComparisonData = [
        {
            stat: '득점',
            home: (data.team_stats.home.goals_avg / 3) * 100,
            away: (data.team_stats.away.goals_avg / 3) * 100
        },
        {
            stat: '실점',
            home: 100 - (data.team_stats.home.conceded_avg / 3) * 100,
            away: 100 - (data.team_stats.away.conceded_avg / 3) * 100
        },
        {
            stat: '점유율',
            home: data.team_stats.home.possession,
            away: data.team_stats.away.possession
        },
        {
            stat: '슈팅',
            home: (data.team_stats.home.shots / 25) * 100,
            away: (data.team_stats.away.shots / 25) * 100
        },
        {
            stat: '유효슛',
            home: (data.team_stats.home.shots_on_target / 12) * 100,
            away: (data.team_stats.away.shots_on_target / 12) * 100
        }
    ];

    // 최근 폼 데이터
    const formData = [1, 2, 3, 4, 5].map(i => ({
        match: `${6 - i}경기 전`,
        home: data.recent_form.home[5 - i] === 'W' ? 3 : data.recent_form.home[5 - i] === 'D' ? 1 : 0,
        away: data.recent_form.away[5 - i] === 'W' ? 3 : data.recent_form.away[5 - i] === 'D' ? 1 : 0
    }));

    return (
        <div className="match-analysis-page">
            {/* 헤더 */}
            <div className="analysis-header">
                <button className="back-btn" onClick={() => window.history.back()}>
                    ← 돌아가기
                </button>
                <div className="match-title">
                    <h1>
                        <span className="team home">{data.home_team}</span>
                        <span className="vs">vs</span>
                        <span className="team away">{data.away_team}</span>
                    </h1>
                    <p className="league-info">{data.league} • {new Date(data.match_time).toLocaleString('ko-KR')}</p>
                </div>
            </div>

            {/* AI 추천 요약 */}
            <Card title="🎯 AI 분석 요약" className="recommendation-summary">
                <div className="summary-grid">
                    <div className="summary-item">
                        <div className="label">추천 결과</div>
                        <div className="value large">{data.recommended_outcome}</div>
                    </div>
                    <div className="summary-item">
                        <div className="label">신뢰도</div>
                        <div className="value">{data.confidence_score}%</div>
                        <div className={`confidence-badge ${data.confidence_level.toLowerCase()}`}>
                            {data.confidence_level === 'HIGH' ? '높음' : data.confidence_level === 'MEDIUM' ? '중간' : '낮음'}
                        </div>
                    </div>
                    <div className="summary-item">
                        <div className="label">기댓값 (EV)</div>
                        <div className={`value ${data.ev_percentage > 0 ? 'positive' : 'negative'}`}>
                            {data.ev_percentage > 0 ? '+' : ''}{data.ev_percentage.toFixed(1)}%
                        </div>
                    </div>
                    <div className="summary-item">
                        <div className="label">AI 합의도</div>
                        <div className="value">{data.ai_opinions.length}/3 일치</div>
                    </div>
                </div>
            </Card>

            {/* 승률 예측 차트 */}
            <Card title="📊 승률 예측" icon="📈">
                <ResponsiveContainer width="100%" height={300}>
                    <BarChart data={probabilityData}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="name" />
                        <YAxis label={{ value: '확률 (%)', angle: -90, position: 'insideLeft' }} />
                        <Tooltip />
                        <Bar dataKey="probability" fill="#3b82f6" />
                    </BarChart>
                </ResponsiveContainer>
                <div className="probability-labels">
                    {probabilityData.map(item => (
                        <div key={item.name} className="prob-label">
                            <span className="dot" style={{ backgroundColor: item.fill }}></span>
                            <span className="name">{item.name}</span>
                            <span className="value">{item.probability.toFixed(1)}%</span>
                        </div>
                    ))}
                </div>
            </Card>

            {/* 주요 통계 비교 */}
            <Card title="⚖️ 주요 통계 비교" icon="📊">
                <div className="stats-comparison">
                    <div className="stats-table">
                        <div className="stat-row">
                            <div className="home-value">{data.team_stats.home.goals_avg.toFixed(1)}</div>
                            <div className="stat-name">평균 득점</div>
                            <div className="away-value">{data.team_stats.away.goals_avg.toFixed(1)}</div>
                        </div>
                        <div className="stat-row">
                            <div className="home-value">{data.team_stats.home.conceded_avg.toFixed(1)}</div>
                            <div className="stat-name">평균 실점</div>
                            <div className="away-value">{data.team_stats.away.conceded_avg.toFixed(1)}</div>
                        </div>
                        <div className="stat-row">
                            <div className="home-value">{data.team_stats.home.possession}%</div>
                            <div className="stat-name">점유율</div>
                            <div className="away-value">{data.team_stats.away.possession}%</div>
                        </div>
                        <div className="stat-row">
                            <div className="home-value">{data.team_stats.home.shots}</div>
                            <div className="stat-name">슈팅</div>
                            <div className="away-value">{data.team_stats.away.shots}</div>
                        </div>
                    </div>

                    <div className="radar-chart">
                        <ResponsiveContainer width="100%" height={350}>
                            <RadarChart data={statsComparisonData}>
                                <PolarGrid />
                                <PolarAngleAxis dataKey="stat" />
                                <PolarRadiusAxis angle={90} domain={[0, 100]} />
                                <Radar name={data.home_team} dataKey="home" stroke="#10b981" fill="#10b981" fillOpacity={0.5} />
                                <Radar name={data.away_team} dataKey="away" stroke="#ef4444" fill="#ef4444" fillOpacity={0.5} />
                                <Legend />
                            </RadarChart>
                        </ResponsiveContainer>
                    </div>
                </div>
            </Card>

            {/* 최근 폼 그래프 */}
            <Card title="📈 최근 5경기 폼" icon="⚡">
                <ResponsiveContainer width="100%" height={250}>
                    <LineChart data={formData}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="match" />
                        <YAxis domain={[0, 3]} ticks={[0, 1, 3]} tickFormatter={(value) => value === 3 ? '승' : value === 1 ? '무' : '패'} />
                        <Tooltip />
                        <Legend />
                        <Line type="monotone" dataKey="home" name={data.home_team} stroke="#10b981" strokeWidth={2} />
                        <Line type="monotone" dataKey="away" name={data.away_team} stroke="#ef4444" strokeWidth={2} />
                    </LineChart>
                </ResponsiveContainer>
                <div className="form-strings">
                    <div className="form-item">
                        <span className="team-name">{data.home_team}</span>
                        <div className="form-badges">
                            {data.recent_form.home.map((result, i) => (
                                <span key={i} className={`form-badge ${result.toLowerCase()}`}>{result}</span>
                            ))}
                        </div>
                    </div>
                    <div className="form-item">
                        <span className="team-name">{data.away_team}</span>
                        <div className="form-badges">
                            {data.recent_form.away.map((result, i) => (
                                <span key={i} className={`form-badge ${result.toLowerCase()}`}>{result}</span>
                            ))}
                        </div>
                    </div>
                </div>
            </Card>

            {/* 상대전적 */}
            <Card title="🔄 최근 상대전적" icon="📋">
                <div className="h2h-table">
                    {data.head_to_head.map((match, i) => (
                        <div key={i} className="h2h-row">
                            <div className="date">{new Date(match.date).toLocaleDateString('ko-KR')}</div>
                            <div className="score">
                                <span className={match.winner === 'home' ? 'winner' : ''}>{match.home_score}</span>
                                <span className="separator">-</span>
                                <span className={match.winner === 'away' ? 'winner' : ''}>{match.away_score}</span>
                            </div>
                            <div className={`result ${match.winner}`}>
                                {match.winner === 'home' ? data.home_team + ' 승' : match.winner === 'away' ? data.away_team + ' 승' : '무승부'}
                            </div>
                        </div>
                    ))}
                </div>
            </Card>

            {/* AI별 의견 */}
            <Card title="🤖 AI별 분석 의견" icon="💭">
                <div className="ai-opinions">
                    {data.ai_opinions.map((opinion, i) => (
                        <div key={i} className="opinion-card">
                            <div className="opinion-header">
                                <span className="provider">{opinion.provider}</span>
                                <span className="confidence">{opinion.confidence}%</span>
                            </div>
                            <div className="opinion-winner">
                                예측: <strong>{opinion.winner}</strong>
                            </div>
                            <div className="opinion-reasoning">{opinion.reasoning}</div>
                        </div>
                    ))}
                </div>
            </Card>

            {/* DeepSeek 심층 분석 */}
            <Card title="🧠 AI 심층 분석 (DeepSeek R1)" icon="✨">
                <div className="deep-analysis">
                    <p>{data.deepseek_analysis}</p>
                </div>
            </Card>

            {/* 배팅 추천 */}
            <Card title="💰 배팅 추천" icon="🎲">
                <div className="betting-recommendation">
                    <div className="rec-main">
                        <div className="rec-outcome">
                            <div className="label">추천 결과</div>
                            <div className="value">{data.recommended_outcome}</div>
                        </div>
                        <div className="rec-confidence">
                            <div className="label">신뢰도</div>
                            <div className="confidence-bar">
                                <div className="bar-fill" style={{ width: `${data.confidence_score}%` }}></div>
                            </div>
                            <div className="value">{data.confidence_score}%</div>
                        </div>
                    </div>
                    <div className="rec-footer">
                        <div className="ev-info">
                            <span className="label">기댓값 (EV):</span>
                            <span className={`value ${data.ev_percentage > 0 ? 'positive' : 'negative'}`}>
                                {data.ev_percentage > 0 ? '+' : ''}{data.ev_percentage.toFixed(1)}%
                            </span>
                        </div>
                        <button className="bet-btn">베트맨에서 배팅하기 →</button>
                    </div>
                </div>
            </Card>
        </div>
    );
}
