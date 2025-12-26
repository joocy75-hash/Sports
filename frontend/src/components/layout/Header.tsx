import { useState, useEffect } from 'react';
import { format } from 'date-fns';
import { ko } from 'date-fns/locale';
import './Header.css';

export default function Header() {
    const [currentTime, setCurrentTime] = useState(new Date());

    useEffect(() => {
        const timer = setInterval(() => setCurrentTime(new Date()), 1000);
        return () => clearInterval(timer);
    }, []);

    return (
        <header className="header">
            <div className="header-left">
                <h1 className="page-title">AI 앙상블 배당 분석</h1>
            </div>

            <div className="header-right">
                <div className="time-display">
                    <span className="time-icon">🕐</span>
                    <span className="time-text">
                        {format(currentTime, 'yyyy년 M월 d일 (EEE) HH:mm:ss', { locale: ko })}
                    </span>
                </div>

                <button className="header-btn notification">
                    <span className="btn-icon">🔔</span>
                    <span className="notification-dot"></span>
                </button>

                <button className="header-btn refresh">
                    <span className="btn-icon">🔄</span>
                </button>
            </div>
        </header>
    );
}
