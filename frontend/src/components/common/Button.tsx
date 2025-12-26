import './Button.css';
import { ReactNode, ButtonHTMLAttributes } from 'react';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
    children: ReactNode;
    variant?: 'primary' | 'secondary' | 'success' | 'danger' | 'ghost';
    size?: 'sm' | 'md' | 'lg';
    icon?: string;
    loading?: boolean;
    fullWidth?: boolean;
}

export default function Button({
    children,
    variant = 'primary',
    size = 'md',
    icon,
    loading = false,
    fullWidth = false,
    disabled,
    className = '',
    ...props
}: ButtonProps) {
    return (
        <button
            className={`btn-component ${variant} ${size} ${fullWidth ? 'full-width' : ''} ${loading ? 'loading' : ''} ${className}`}
            disabled={disabled || loading}
            {...props}
        >
            {loading ? (
                <span className="btn-spinner">⏳</span>
            ) : (
                <>
                    {icon && <span className="btn-icon">{icon}</span>}
                    <span className="btn-text">{children}</span>
                </>
            )}
        </button>
    );
}
