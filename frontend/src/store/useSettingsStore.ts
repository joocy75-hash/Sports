import { create } from 'zustand';
import { persist } from 'zustand/middleware';

type Theme = 'dark' | 'light';

interface SettingsState {
    theme: Theme;
    autoRefresh: boolean;
    refreshInterval: number; // seconds
    notifications: boolean;

    // Actions
    setTheme: (theme: Theme) => void;
    toggleTheme: () => void;
    setAutoRefresh: (enabled: boolean) => void;
    setRefreshInterval: (seconds: number) => void;
    setNotifications: (enabled: boolean) => void;
}

export const useSettingsStore = create<SettingsState>()(
    persist(
        (set, get) => ({
            theme: 'dark',
            autoRefresh: true,
            refreshInterval: 60,
            notifications: true,

            setTheme: (theme) => {
                document.documentElement.setAttribute('data-theme', theme);
                set({ theme });
            },

            toggleTheme: () => {
                const newTheme = get().theme === 'dark' ? 'light' : 'dark';
                document.documentElement.setAttribute('data-theme', newTheme);
                set({ theme: newTheme });
            },

            setAutoRefresh: (enabled) => set({ autoRefresh: enabled }),
            setRefreshInterval: (seconds) => set({ refreshInterval: seconds }),
            setNotifications: (enabled) => set({ notifications: enabled }),
        }),
        {
            name: 'app-settings',
            onRehydrateStorage: () => (state) => {
                // 저장된 테마 적용
                if (state?.theme) {
                    document.documentElement.setAttribute('data-theme', state.theme);
                }
            },
        }
    )
);

export default useSettingsStore;
