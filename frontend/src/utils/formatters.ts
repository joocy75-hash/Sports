import { format, formatDistanceToNow, parseISO, isValid } from 'date-fns';
import { ko } from 'date-fns/locale';

/**
 * 날짜를 한국어 형식으로 포맷
 */
export function formatDate(date: string | Date, formatStr = 'yyyy년 M월 d일'): string {
    const d = typeof date === 'string' ? parseISO(date) : date;
    if (!isValid(d)) return '-';
    return format(d, formatStr, { locale: ko });
}

/**
 * 날짜를 시간 포함하여 포맷
 */
export function formatDateTime(date: string | Date): string {
    return formatDate(date, 'yyyy년 M월 d일 (EEE) HH:mm');
}

/**
 * 시간만 포맷
 */
export function formatTime(date: string | Date): string {
    return formatDate(date, 'HH:mm');
}

/**
 * 상대 시간 표시 (예: 5분 전)
 */
export function formatRelativeTime(date: string | Date): string {
    const d = typeof date === 'string' ? parseISO(date) : date;
    if (!isValid(d)) return '-';
    return formatDistanceToNow(d, { addSuffix: true, locale: ko });
}

/**
 * 숫자를 퍼센트로 포맷
 */
export function formatPercent(value: number, decimals = 1): string {
    return `${(value * 100).toFixed(decimals)}%`;
}

/**
 * 숫자를 배당률 형식으로 포맷
 */
export function formatOdds(value: number): string {
    return value.toFixed(2);
}

/**
 * 숫자를 통화 형식으로 포맷 (한국 원화)
 */
export function formatCurrency(value: number): string {
    return new Intl.NumberFormat('ko-KR', {
        style: 'currency',
        currency: 'KRW',
        minimumFractionDigits: 0,
    }).format(value);
}

/**
 * 큰 숫자 축약 (K, M 형식)
 */
export function formatCompactNumber(value: number): string {
    return new Intl.NumberFormat('ko-KR', {
        notation: 'compact',
        compactDisplay: 'short',
    }).format(value);
}

/**
 * 예측 결과 레이블
 */
export function getPredictionLabel(prediction: string): string {
    const labels: Record<string, string> = {
        home: '홈승',
        draw: '무승부',
        away: '원정승'
    };
    return labels[prediction] || prediction;
}

/**
 * 리스크 레벨 레이블
 */
export function getRiskLabel(risk: string): string {
    const labels: Record<string, string> = {
        LOW: '낮음',
        MEDIUM: '보통',
        HIGH: '높음',
        VERY_HIGH: '매우 높음'
    };
    return labels[risk] || risk;
}
