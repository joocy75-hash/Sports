import './ConfidenceGauge.css';

interface ConfidenceGaugeProps {
    value: number; // 0-100
    label?: string;
    size?: 'sm' | 'md' | 'lg';
    showValue?: boolean;
}

export default function ConfidenceGauge({
    value,
    label = '신뢰도',
    size = 'md',
    showValue = true
}: ConfidenceGaugeProps) {
    // 값에 따른 색상 결정
    const getColor = (val: number) => {
        if (val >= 80) return 'var(--success-500)';
        if (val >= 60) return 'var(--primary-500)';
        if (val >= 40) return 'var(--warning-500)';
        return 'var(--danger-500)';
    };

    const color = getColor(value);
    const rotation = (value / 100) * 180 - 90; // -90 to 90 degrees

    const sizeMap = {
        sm: { width: 80, strokeWidth: 6, fontSize: 14 },
        md: { width: 120, strokeWidth: 8, fontSize: 20 },
        lg: { width: 160, strokeWidth: 10, fontSize: 28 }
    };

    const { width, strokeWidth, fontSize } = sizeMap[size];
    const radius = (width - strokeWidth) / 2;
    const circumference = Math.PI * radius;
    const progress = (value / 100) * circumference;

    return (
        <div className={`confidence-gauge ${size}`} style={{ width }}>
            <svg
                width={width}
                height={width / 2 + 10}
                viewBox={`0 0 ${width} ${width / 2 + 10}`}
            >
                {/* 배경 호 */}
                <path
                    d={`M ${strokeWidth / 2} ${width / 2} A ${radius} ${radius} 0 0 1 ${width - strokeWidth / 2} ${width / 2}`}
                    fill="none"
                    stroke="var(--gray-700)"
                    strokeWidth={strokeWidth}
                    strokeLinecap="round"
                />

                {/* 진행 호 */}
                <path
                    d={`M ${strokeWidth / 2} ${width / 2} A ${radius} ${radius} 0 0 1 ${width - strokeWidth / 2} ${width / 2}`}
                    fill="none"
                    stroke={color}
                    strokeWidth={strokeWidth}
                    strokeLinecap="round"
                    strokeDasharray={`${progress} ${circumference}`}
                    style={{
                        filter: `drop-shadow(0 0 8px ${color})`,
                        transition: 'stroke-dasharray 0.5s ease-out'
                    }}
                />

                {/* 값 표시 */}
                {showValue && (
                    <text
                        x={width / 2}
                        y={width / 2 - 5}
                        textAnchor="middle"
                        fill={color}
                        fontSize={fontSize}
                        fontWeight="700"
                    >
                        {value.toFixed(0)}%
                    </text>
                )}
            </svg>

            {label && (
                <div className="gauge-label" style={{ color: 'var(--gray-400)', fontSize: fontSize * 0.5, marginTop: 4 }}>
                    {label}
                </div>
            )}
        </div>
    );
}
