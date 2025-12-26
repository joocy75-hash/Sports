import './Card.css';
import { ReactNode } from 'react';

interface CardProps {
    children: ReactNode;
    className?: string;
    title?: string;
    icon?: string;
    action?: ReactNode;
    noPadding?: boolean;
}

export default function Card({
    children,
    className = '',
    title,
    icon,
    action,
    noPadding = false
}: CardProps) {
    return (
        <div className={`card-component ${className}`}>
            {(title || action) && (
                <div className="card-header">
                    <div className="card-title-wrapper">
                        {icon && <span className="card-icon">{icon}</span>}
                        {title && <h3 className="card-title">{title}</h3>}
                    </div>
                    {action && <div className="card-action">{action}</div>}
                </div>
            )}
            <div className={`card-body ${noPadding ? 'no-padding' : ''}`}>
                {children}
            </div>
        </div>
    );
}
