import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';

interface ProbabilityPieProps {
    homeProb: number;
    drawProb: number;
    awayProb: number;
    size?: number;
    showLabels?: boolean;
}

const COLORS = {
    home: '#3B82F6',
    draw: '#8B5CF6',
    away: '#F97316'
};

const LABELS = {
    home: '홈승',
    draw: '무',
    away: '원정승'
};

export default function ProbabilityPie({
    homeProb,
    drawProb,
    awayProb,
    size = 180,
    showLabels = true
}: ProbabilityPieProps) {
    const data = [
        { name: '홈승', key: 'home', value: homeProb, color: COLORS.home },
        { name: '무', key: 'draw', value: drawProb, color: COLORS.draw },
        { name: '원정승', key: 'away', value: awayProb, color: COLORS.away }
    ];

    // 가장 높은 확률 찾기
    const maxProb = Math.max(homeProb, drawProb, awayProb);
    const predicted = data.find(d => d.value === maxProb);

    return (
        <div className="probability-pie" style={{ width: size, height: size }}>
            <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                    <Pie
                        data={data}
                        cx="50%"
                        cy="50%"
                        innerRadius={size * 0.35}
                        outerRadius={size * 0.45}
                        paddingAngle={4}
                        dataKey="value"
                        stroke="none"
                    >
                        {data.map((entry, index) => (
                            <Cell
                                key={`cell-${index}`}
                                fill={entry.color}
                                style={{
                                    filter: entry.value === maxProb ? 'drop-shadow(0 0 8px ' + entry.color + ')' : 'none',
                                    opacity: entry.value === maxProb ? 1 : 0.7
                                }}
                            />
                        ))}
                    </Pie>
                    <Tooltip
                        contentStyle={{
                            background: 'rgba(17, 24, 39, 0.95)',
                            border: '1px solid rgba(75, 85, 99, 0.3)',
                            borderRadius: '8px',
                            color: '#F9FAFB'
                        }}
                        formatter={(value: unknown) => [`${Number(value).toFixed(1)}%`, '']}
                    />
                </PieChart>
            </ResponsiveContainer>

            {/* 중앙 텍스트 */}
            <div
                className="pie-center"
                style={{
                    position: 'absolute',
                    top: '50%',
                    left: '50%',
                    transform: 'translate(-50%, -50%)',
                    textAlign: 'center'
                }}
            >
                <div style={{
                    fontSize: size * 0.12,
                    fontWeight: 700,
                    color: predicted?.color
                }}>
                    {predicted?.value.toFixed(0)}%
                </div>
                <div style={{
                    fontSize: size * 0.08,
                    color: '#9CA3AF'
                }}>
                    {predicted?.name}
                </div>
            </div>

            {/* 범례 */}
            {showLabels && (
                <div
                    className="pie-legend"
                    style={{
                        display: 'flex',
                        justifyContent: 'center',
                        gap: '16px',
                        marginTop: '12px',
                        fontSize: '12px'
                    }}
                >
                    {data.map((item) => (
                        <div key={item.key} style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                            <div style={{
                                width: 8,
                                height: 8,
                                borderRadius: '50%',
                                background: item.color
                            }} />
                            <span style={{ color: '#9CA3AF' }}>{item.name}</span>
                            <span style={{ color: item.color, fontWeight: 600 }}>{item.value.toFixed(0)}%</span>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}
