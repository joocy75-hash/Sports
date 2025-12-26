/**
 * 켈리 베팅 비율 계산
 */
export function calculateKellyFraction(
    probability: number,
    odds: number,
    fraction = 0.25 // 1/4 켈리 기본
): number {
    // 켈리 공식: (p * o - q) / o
    // p = 승리 확률, o = 배당률 - 1, q = 패배 확률
    const p = probability;
    const q = 1 - probability;
    const o = odds - 1;

    const fullKelly = (p * o - q) / o;

    // 음수면 0, fraction 적용
    return Math.max(0, fullKelly * fraction);
}

/**
 * 기대값 계산
 */
export function calculateExpectedValue(
    probability: number,
    odds: number
): number {
    // EV = (확률 * 배당) - 1
    return probability * odds - 1;
}

/**
 * Value 퍼센트 계산
 */
export function calculateValuePercent(
    calculatedOdds: number,
    officialOdds: number
): number {
    // Value = (공식 배당 / AI 배당 - 1) * 100
    return (officialOdds / calculatedOdds - 1) * 100;
}

/**
 * 확률을 배당률로 변환
 */
export function probabilityToOdds(probability: number, margin = 0.05): number {
    if (probability <= 0) return 999;
    if (probability >= 1) return 1;

    // 기본 공식: odds = 1 / probability
    // 마진 적용: odds = (1 / probability) * (1 - margin)
    return (1 / probability) * (1 - margin);
}

/**
 * 배당률을 확률로 변환
 */
export function oddsToProbability(odds: number): number {
    if (odds <= 1) return 1;
    return 1 / odds;
}

/**
 * 조합 총 배당률 계산
 */
export function calculateCombinedOdds(oddsList: number[]): number {
    return oddsList.reduce((acc, odds) => acc * odds, 1);
}

/**
 * 조합 승리 확률 계산
 */
export function calculateCombinedProbability(probabilities: number[]): number {
    return probabilities.reduce((acc, prob) => acc * prob, 1);
}

/**
 * 신뢰도에 따른 색상 반환
 */
export function getConfidenceColor(confidence: number): string {
    if (confidence >= 80) return 'var(--success-500)';
    if (confidence >= 60) return 'var(--primary-500)';
    if (confidence >= 40) return 'var(--warning-500)';
    return 'var(--danger-500)';
}

/**
 * Value에 따른 추천 등급 결정
 */
export function getValueRecommendation(valuePercent: number): string {
    if (valuePercent >= 10) return 'STRONG_BET';
    if (valuePercent >= 5) return 'BET';
    if (valuePercent >= 2) return 'CONSIDER';
    if (valuePercent >= 0) return 'SKIP';
    return 'AVOID';
}
