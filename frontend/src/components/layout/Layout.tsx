import { ReactNode } from 'react';
import Sidebar from './Sidebar';
import Header from './Header';
import './Layout.css';

interface LayoutProps {
    children: ReactNode;
}

export default function Layout({ children }: LayoutProps) {
    return (
        <div className="app-layout">
            <Sidebar />
            <div className="main-wrapper">
                <Header />
                <main className="page-content">
                    {children}
                </main>
            </div>
        </div>
    );
}
