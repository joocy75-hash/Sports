import './StatCard.css';

interface StatCardProps {
    title: string;
    value: string | number;
    icon: string;
    subtitle?: string;
    trend?: {
        value: number;
        isPositive: boolean;
    };
    color?: 'primary' | 'success' | 'warning' | 'danger';
}

export default function StatCard({
    title,
    value,
    icon,
    subtitle,
    trend,
    color = 'primary'
}: StatCardProps) {
    return (
        <div className={`stat-card ${color}`}>
            <div className="stat-icon">{icon}</div>
            <div className="stat-content">
                <span className="stat-title">{title}</span>
                <span className="stat-value">{value}</span>
                {subtitle && <span className="stat-subtitle">{subtitle}</span>}
                {trend && (
                    <span className={`stat-trend ${trend.isPositive ? 'positive' : 'negative'}`}>
                        {trend.isPositive ? '↑' : '↓'} {Math.abs(trend.value)}%
                    </span>
                )}
            </div>
        </div>
    );
}
