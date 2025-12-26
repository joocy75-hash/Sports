import { NavLink } from 'react-router-dom';
import './Sidebar.css';

const navItems = [
    { path: '/', label: '대시보드', icon: '🏠' },
    { path: '/rounds', label: '회차 분석', icon: '📊' },
    { path: '/value-bets', label: 'Value Bet', icon: '💰' },
    { path: '/combinations', label: '조합 최적화', icon: '🎲' },
    { path: '/ai-insights', label: 'AI 인사이트', icon: '🤖' },
    { path: '/settings', label: '설정', icon: '⚙️' },
];

export default function Sidebar() {
    return (
        <aside className="sidebar">
            <div className="sidebar-header">
                <div className="logo">
                    <span className="logo-icon">🎯</span>
                    <span className="logo-text">AI 배당 분석</span>
                </div>
                <span className="version-badge">v1.0</span>
            </div>

            <nav className="sidebar-nav">
                {navItems.map((item) => (
                    <NavLink
                        key={item.path}
                        to={item.path}
                        className={({ isActive }) =>
                            `nav-item ${isActive ? 'active' : ''}`
                        }
                    >
                        <span className="nav-icon">{item.icon}</span>
                        <span className="nav-label">{item.label}</span>
                    </NavLink>
                ))}
            </nav>

            <div className="sidebar-footer">
                <div className="status-indicator">
                    <span className="status-dot online"></span>
                    <span className="status-text">서버 연결됨</span>
                </div>
            </div>
        </aside>
    );
}
