import './Loading.css';

interface LoadingProps {
    size?: 'sm' | 'md' | 'lg';
    text?: string;
    fullScreen?: boolean;
}

export default function Loading({
    size = 'md',
    text = '로딩 중...',
    fullScreen = false
}: LoadingProps) {
    const content = (
        <div className={`loading ${size}`}>
            <div className="loading-spinner">
                <div className="spinner-ring"></div>
                <div className="spinner-ring"></div>
                <div className="spinner-ring"></div>
                <div className="spinner-center">🎯</div>
            </div>
            {text && <span className="loading-text">{text}</span>}
        </div>
    );

    if (fullScreen) {
        return <div className="loading-overlay">{content}</div>;
    }

    return content;
}

// 스켈레톤 로더
export function Skeleton({
    width = '100%',
    height = '20px',
    borderRadius = 'var(--radius-md)'
}: {
    width?: string;
    height?: string;
    borderRadius?: string;
}) {
    return (
        <div
            className="skeleton"
            style={{ width, height, borderRadius }}
        />
    );
}

// 카드 스켈레톤
export function CardSkeleton() {
    return (
        <div className="card-skeleton">
            <Skeleton height="24px" width="60%" />
            <Skeleton height="48px" width="40%" />
            <Skeleton height="16px" width="80%" />
        </div>
    );
}
