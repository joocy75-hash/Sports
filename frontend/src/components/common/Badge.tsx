import './Badge.css';

interface BadgeProps {
    children: React.ReactNode;
    variant?: 'primary' | 'success' | 'warning' | 'danger' | 'info' | 'default';
    size?: 'sm' | 'md' | 'lg';
    icon?: string;
}

export default function Badge({
    children,
    variant = 'default',
    size = 'md',
    icon
}: BadgeProps) {
    return (
        <span className={`badge ${variant} ${size}`}>
            {icon && <span className="badge-icon">{icon}</span>}
            {children}
        </span>
    );
}
