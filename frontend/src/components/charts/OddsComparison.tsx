import { BarChart, Bar, XAxis, YAxis, Cell, ResponsiveContainer, Tooltip } from 'recharts';

interface OddsComparisonProps {
    calculatedOdds: {
        home: number;
        draw: number;
        away: number;
    };
    officialOdds?: {
        home: number;
        draw: number;
        away: number;
    };
    height?: number;
}

const COLORS = {
    home: '#3B82F6',
    draw: '#8B5CF6',
    away: '#F97316'
};

const LABELS: Record<string, string> = {
    home: '홈승',
    draw: '무',
    away: '원정승'
};

export default function OddsComparison({
    calculatedOdds,
    officialOdds,
    height = 200
}: OddsComparisonProps) {
    const data = [
        {
            name: '홈승',
            key: 'home',
            calculated: calculatedOdds.home,
            official: officialOdds?.home,
            color: COLORS.home
        },
        {
            name: '무',
            key: 'draw',
            calculated: calculatedOdds.draw,
            official: officialOdds?.draw,
            color: COLORS.draw
        },
        {
            name: '원정승',
            key: 'away',
            calculated: calculatedOdds.away,
            official: officialOdds?.away,
            color: COLORS.away
        }
    ];

    return (
        <div className="odds-comparison">
            <ResponsiveContainer width="100%" height={height}>
                <BarChart
                    data={data}
                    layout="vertical"
                    margin={{ top: 10, right: 30, left: 60, bottom: 10 }}
                    barGap={4}
                >
                    <XAxis
                        type="number"
                        domain={[1, 'auto']}
                        tick={{ fill: '#9CA3AF', fontSize: 12 }}
                        axisLine={{ stroke: '#374151' }}
                        tickLine={{ stroke: '#374151' }}
                    />
                    <YAxis
                        dataKey="name"
                        type="category"
                        tick={{ fill: '#9CA3AF', fontSize: 12 }}
                        axisLine={{ stroke: '#374151' }}
                        tickLine={false}
                        width={50}
                    />
                    <Tooltip
                        contentStyle={{
                            background: 'rgba(17, 24, 39, 0.95)',
                            border: '1px solid rgba(75, 85, 99, 0.3)',
                            borderRadius: '8px',
                            color: '#F9FAFB'
                        }}
                        formatter={(value: unknown, name: unknown) => [
                            Number(value).toFixed(2),
                            name === 'calculated' ? 'AI 배당' : '공식 배당'
                        ]}
                    />
                    <Bar
                        dataKey="calculated"
                        name="AI 배당"
                        radius={[0, 4, 4, 0]}
                    >
                        {data.map((entry, index) => (
                            <Cell key={`cell-${index}`} fill={entry.color} fillOpacity={0.8} />
                        ))}
                    </Bar>
                    {officialOdds && (
                        <Bar
                            dataKey="official"
                            name="공식 배당"
                            radius={[0, 4, 4, 0]}
                            fillOpacity={0.4}
                        >
                            {data.map((entry, index) => (
                                <Cell key={`cell-${index}`} fill={entry.color} fillOpacity={0.4} />
                            ))}
                        </Bar>
                    )}
                </BarChart>
            </ResponsiveContainer>

            {/* 범례 */}
            <div style={{
                display: 'flex',
                justifyContent: 'center',
                gap: '24px',
                marginTop: '8px',
                fontSize: '12px'
            }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <div style={{
                        width: 12,
                        height: 12,
                        background: 'linear-gradient(90deg, #3B82F6, #8B5CF6)',
                        borderRadius: 2
                    }} />
                    <span style={{ color: '#9CA3AF' }}>AI 산출 배당</span>
                </div>
                {officialOdds && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <div style={{
                            width: 12,
                            height: 12,
                            background: 'rgba(156, 163, 175, 0.4)',
                            borderRadius: 2
                        }} />
                        <span style={{ color: '#9CA3AF' }}>공식 배당</span>
                    </div>
                )}
            </div>
        </div>
    );
}
