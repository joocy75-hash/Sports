"""
복수 마킹 최적화 시스템
- 14경기 중 복수 대상 선정
- 2개/3개/4개 복수 조합 최적화
"""

from typing import Dict, List, Tuple
import numpy as np
from itertools import combinations


class MultiMarkingOptimizer:
    """복수 마킹 최적화기"""

    def __init__(self):
        self.outcomes = ['home', 'draw', 'away']

    def optimize_marking(
        self,
        match: Dict
    ) -> Dict:
        """
        단일 경기 최적 마킹 결정

        Args:
            match: {
                'ai_prediction': {'home': 0.42, 'draw': 0.33, 'away': 0.25},
                'official_odds': {'home': 2.10, 'draw': 3.20, 'away': 3.80},
                'confidence': 0.74,
                'consensus': 0.60  # AI 합의도 (5개 중 3개 동의 = 60%)
            }

        Returns:
            {
                'marking_type': 'single' | 'double' | 'triple' | 'all',
                'marked_outcomes': ['home', 'draw'],
                'expected_hit_rate': 0.75,
                'expected_value': 1.15,
                'reasoning': "확률 분산이 크고..."
            }
        """
        probs = match.get('ai_prediction', {})
        odds = match.get('official_odds', {})
        confidence = match.get('confidence', 0)

        # 기본값 설정
        if not probs:
            probs = {'home': 0.33, 'draw': 0.34, 'away': 0.33}
        if not odds:
            odds = {'home': 2.5, 'draw': 3.0, 'away': 3.0}

        # 1. 확률 분산도 계산
        prob_values = list(probs.values())
        prob_std = np.std(prob_values)
        prob_entropy = -sum(p * np.log2(p) if p > 0 else 0 for p in prob_values)

        # 2. 복수 대상 여부 판단
        should_multi = self._should_use_multi_marking(
            probs, confidence, prob_std, prob_entropy
        )

        if not should_multi:
            # 단식: 가장 높은 확률
            best_outcome = max(probs, key=probs.get)
            return {
                'marking_type': 'single',
                'marked_outcomes': [best_outcome],
                'expected_hit_rate': probs[best_outcome],
                'expected_value': probs[best_outcome] * odds.get(best_outcome, 1.0),
                'reasoning': f"신뢰도 {confidence:.0%}, {best_outcome} 확률 {probs[best_outcome]:.0%}"
            }

        # 3. 복수 조합 시뮬레이션
        best_combo = self._find_best_combo(probs, odds, confidence)

        return best_combo

    def _should_use_multi_marking(
        self,
        probs: Dict[str, float],
        confidence: float,
        prob_std: float,
        entropy: float
    ) -> bool:
        """복수 마킹 사용 여부 결정"""

        # 조건 1: 최고 확률이 60% 미만
        max_prob = max(probs.values()) if probs else 0
        if max_prob < 0.60:
            return True

        # 조건 2: 확률 분산이 큼 (표준편차 > 0.08)
        if prob_std > 0.08:
            return True

        # 조건 3: 신뢰도가 낮음 (< 75%)
        if confidence < 0.75:
            return True

        # 조건 4: 엔트로피가 높음 (불확실성)
        if entropy > 1.3:
            return True

        return False

    def _find_best_combo(
        self,
        probs: Dict[str, float],
        odds: Dict[str, float],
        confidence: float
    ) -> Dict:
        """최적 복수 조합 찾기"""

        candidates = []

        # 2개 복수 조합
        for combo in combinations(self.outcomes, 2):
            hit_rate = sum(probs.get(o, 0) for o in combo)
            # 2개 복수는 배당이 낮아짐 (평균의 70%)
            avg_odds = np.mean([odds.get(o, 1.0) for o in combo]) * 0.7
            ev = hit_rate * avg_odds

            candidates.append({
                'marking_type': 'double',
                'marked_outcomes': list(combo),
                'expected_hit_rate': hit_rate,
                'expected_value': ev,
                'reasoning': f"2개 복수 (적중률 {hit_rate:.0%})"
            })

        # 3개 복수 (전체)
        hit_rate_all = 1.0
        avg_odds_all = np.mean(list(odds.values())) * 0.5
        ev_all = hit_rate_all * avg_odds_all

        candidates.append({
            'marking_type': 'triple',
            'marked_outcomes': self.outcomes,
            'expected_hit_rate': hit_rate_all,
            'expected_value': ev_all,
            'reasoning': "3개 복수 (전체, 확실 적중)"
        })

        # 기댓값 최대화 선택
        best = max(candidates, key=lambda x: x['expected_value'])

        return best

    def optimize_round(
        self,
        matches: List[Dict]
    ) -> Dict:
        """
        14경기 전체 최적화

        Args:
            matches: 경기 리스트
                [
                    {
                        'id': '001',
                        'home_team': 'Arsenal',
                        'away_team': 'Liverpool',
                        'ai_prediction': {'home': 0.45, 'draw': 0.28, 'away': 0.27},
                        'official_odds': {'home': 1.80, 'draw': 3.50, 'away': 4.50},
                        'confidence': 0.85,
                        'consensus': 0.80
                    },
                    ...
                ]

        Returns:
            {
                'markings': [
                    {
                        'match_id': '001',
                        'match_name': 'Arsenal vs Liverpool',
                        'marking_type': 'single',
                        'marked_outcomes': ['home'],
                        'expected_hit_rate': 0.45,
                        'expected_value': 0.81,
                        'reasoning': '...'
                    },
                    ...
                ],
                'summary': {
                    'single_count': 6,
                    'double_count': 5,
                    'triple_count': 3,
                    'expected_hit_rate': 0.68,
                    'average_odds': 2.1,
                    'expected_payout': 1.43
                }
            }
        """
        results = []

        for match in matches:
            marking = self.optimize_marking(match)
            results.append({
                'match_id': match.get('id', ''),
                'match_name': f"{match.get('home_team', '')} vs {match.get('away_team', '')}",
                **marking
            })

        # 통계
        single_count = sum(1 for r in results if r['marking_type'] == 'single')
        double_count = sum(1 for r in results if r['marking_type'] == 'double')
        triple_count = sum(1 for r in results if r['marking_type'] == 'triple')

        # 전체 적중률 (독립 사건의 곱)
        total_hit_rate = np.prod([r['expected_hit_rate'] for r in results])
        avg_odds = np.mean([r['expected_value'] for r in results])

        return {
            'markings': results,
            'summary': {
                'single_count': single_count,
                'double_count': double_count,
                'triple_count': triple_count,
                'expected_hit_rate': total_hit_rate,
                'average_odds': avg_odds,
                'expected_payout': total_hit_rate * avg_odds
            }
        }

    def get_multi_marking_stats(self, markings: List[Dict]) -> Dict:
        """
        복수 마킹 통계 요약

        Args:
            markings: optimize_round()의 'markings' 결과

        Returns:
            {
                'total_games': int,
                'single_games': int,
                'multi_games': int,
                'avg_multi_outcomes': float,
                'high_confidence_singles': int,
                'uncertain_multis': int
            }
        """
        if not markings:
            return {
                'total_games': 0,
                'single_games': 0,
                'multi_games': 0,
                'avg_multi_outcomes': 0.0,
                'high_confidence_singles': 0,
                'uncertain_multis': 0
            }

        total_games = len(markings)
        single_games = sum(1 for m in markings if m['marking_type'] == 'single')
        multi_games = total_games - single_games

        # 복수 마킹 평균 결과 개수
        multi_outcome_counts = [
            len(m['marked_outcomes']) for m in markings
            if m['marking_type'] != 'single'
        ]
        avg_multi_outcomes = np.mean(multi_outcome_counts) if multi_outcome_counts else 0.0

        # 고신뢰도 단식 (expected_hit_rate > 0.7)
        high_confidence_singles = sum(
            1 for m in markings
            if m['marking_type'] == 'single' and m['expected_hit_rate'] > 0.7
        )

        # 불확실 복수 (expected_hit_rate < 0.8)
        uncertain_multis = sum(
            1 for m in markings
            if m['marking_type'] != 'single' and m['expected_hit_rate'] < 0.8
        )

        return {
            'total_games': total_games,
            'single_games': single_games,
            'multi_games': multi_games,
            'avg_multi_outcomes': float(avg_multi_outcomes),
            'high_confidence_singles': high_confidence_singles,
            'uncertain_multis': uncertain_multis
        }
