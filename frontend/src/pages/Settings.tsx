import { useSettingsStore } from '@/store';
import { Card, Button } from '@/components/common';
import './Settings.css';

export default function Settings() {
    const { theme, autoRefresh, refreshInterval, notifications, toggleTheme, setAutoRefresh, setRefreshInterval, setNotifications } = useSettingsStore();

    return (
        <div className="settings">
            <div className="page-header">
                <h1 className="page-title">
                    <span className="title-icon">⚙️</span>
                    설정
                </h1>
                <p className="page-subtitle">시스템 설정 및 환경 구성</p>
            </div>

            <Card title="테마 설정" icon="🎨">
                <div className="setting-row">
                    <div className="setting-info">
                        <span className="setting-label">다크/라이트 모드</span>
                        <span className="setting-desc">현재: {theme === 'dark' ? '다크 모드 🌙' : '라이트 모드 ☀️'}</span>
                    </div>
                    <Button variant={theme === 'dark' ? 'secondary' : 'primary'} onClick={toggleTheme}>
                        {theme === 'dark' ? '☀️ 라이트 모드로 전환' : '🌙 다크 모드로 전환'}
                    </Button>
                </div>
            </Card>

            <Card title="데이터 갱신 설정" icon="🔄">
                <div className="setting-row">
                    <div className="setting-info">
                        <span className="setting-label">자동 갱신</span>
                        <span className="setting-desc">경기 데이터를 자동으로 갱신합니다</span>
                    </div>
                    <label className="toggle-switch">
                        <input type="checkbox" checked={autoRefresh} onChange={(e) => setAutoRefresh(e.target.checked)} />
                        <span className="toggle-slider"></span>
                    </label>
                </div>

                {autoRefresh && (
                    <div className="setting-row">
                        <div className="setting-info">
                            <span className="setting-label">갱신 간격</span>
                            <span className="setting-desc">데이터를 갱신하는 주기</span>
                        </div>
                        <select className="setting-select" value={refreshInterval} onChange={(e) => setRefreshInterval(Number(e.target.value))}>
                            <option value={30}>30초</option>
                            <option value={60}>1분</option>
                            <option value={120}>2분</option>
                            <option value={300}>5분</option>
                        </select>
                    </div>
                )}
            </Card>

            <Card title="알림 설정" icon="🔔">
                <div className="setting-row">
                    <div className="setting-info">
                        <span className="setting-label">알림 활성화</span>
                        <span className="setting-desc">Value Bet 발견 시 알림을 받습니다</span>
                    </div>
                    <label className="toggle-switch">
                        <input type="checkbox" checked={notifications} onChange={(e) => setNotifications(e.target.checked)} />
                        <span className="toggle-slider"></span>
                    </label>
                </div>
            </Card>

            <Card title="API 연결 상태" icon="🔌">
                <div className="status-grid">
                    <div className="status-item online">
                        <span className="status-dot"></span>
                        <span className="status-label">백엔드 서버</span>
                        <span className="status-url">localhost:8000</span>
                    </div>
                </div>
            </Card>

            <Card title="시스템 정보" icon="ℹ️">
                <div className="info-list">
                    <div className="info-item">
                        <span className="info-label">버전</span>
                        <span className="info-value">1.0.0</span>
                    </div>
                    <div className="info-item">
                        <span className="info-label">프레임워크</span>
                        <span className="info-value">React + TypeScript + Vite</span>
                    </div>
                    <div className="info-item">
                        <span className="info-label">AI 모델</span>
                        <span className="info-value">GPT-4, Claude, Gemini, Kimi, DeepSeek</span>
                    </div>
                </div>
            </Card>
        </div>
    );
}
