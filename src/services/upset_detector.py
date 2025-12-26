"""
이변 감지 시스템
- AI 예측 vs 공식 배당 괴리도 분석
- 저평가/과대평가 팀 식별
"""

from typing import Dict, List, Optional
import numpy as np


class UpsetDetector:
    """이변 가능성 감지기"""

    def __init__(self, min_divergence: float = 0.15):
        """
        Args:
            min_divergence: 최소 괴리도 (15%p 이상)
        """
        self.min_divergence = min_divergence

    def detect_upsets(
        self,
        ai_prediction: Dict[str, float],
        official_odds: Dict[str, float],
        confidence: float
    ) -> Dict:
        """
        이변 가능성 분석

        Args:
            ai_prediction: {'home': 0.45, 'draw': 0.28, 'away': 0.27}
            official_odds: {'home': 1.80, 'draw': 3.50, 'away': 4.50}
            confidence: AI 신뢰도 (0-1)

        Returns:
            {
                'is_upset_candidate': bool,
                'upset_type': 'underdog' | 'overdog' | None,
                'divergence': float,
                'recommended_bet': str,
                'risk_level': 'low' | 'medium' | 'high'
            }
        """
        # 1. 배당 → 내재확률 변환
        implied_probs = self._odds_to_probability(official_odds)

        # 2. 괴리도 계산
        divergences = {
            outcome: ai_prediction.get(outcome, 0) - implied_probs.get(outcome, 0)
            for outcome in ['home', 'draw', 'away']
        }

        # 3. 가장 큰 괴리도 찾기
        max_divergence_outcome = max(divergences, key=lambda k: abs(divergences[k]))
        max_divergence = divergences[max_divergence_outcome]

        # 4. 이변 판정
        is_upset = (
            abs(max_divergence) >= self.min_divergence and
            confidence >= 0.70
        )

        # 5. 이변 타입
        upset_type: Optional[str] = None
        recommended_bet: Optional[str] = None

        if is_upset:
            if max_divergence > 0:
                # AI가 더 높은 확률 → 시장이 저평가 (언더독)
                upset_type = 'underdog'
                recommended_bet = max_divergence_outcome
            else:
                # AI가 더 낮은 확률 → 시장이 과대평가 (오버독)
                upset_type = 'overdog'
                # 반대편에 베팅
                if max_divergence_outcome == 'home':
                    recommended_bet = 'away'
                elif max_divergence_outcome == 'away':
                    recommended_bet = 'home'
                else:
                    recommended_bet = 'draw'

        # 6. 리스크 레벨
        risk_level = self._calculate_risk(
            abs(max_divergence),
            confidence
        )

        return {
            'is_upset_candidate': is_upset,
            'upset_type': upset_type,
            'divergence': max_divergence,
            'divergence_outcome': max_divergence_outcome,
            'recommended_bet': recommended_bet,
            'risk_level': risk_level,
            'ai_probs': ai_prediction,
            'market_probs': implied_probs,
            'divergence_all': divergences
        }

    def _odds_to_probability(self, odds: Dict[str, float]) -> Dict[str, float]:
        """
        배당률 → 내재확률 (마진 제거)

        Args:
            odds: {'home': 1.80, 'draw': 3.50, 'away': 4.50}

        Returns:
            {'home': 0.52, 'draw': 0.27, 'away': 0.21}
        """
        if not odds:
            return {'home': 0.33, 'draw': 0.34, 'away': 0.33}

        raw_probs = {k: 1/v if v > 0 else 0 for k, v in odds.items()}
        total = sum(raw_probs.values())
        # 마진 제거 (정규화)
        if total > 0:
            return {k: v/total for k, v in raw_probs.items()}
        return {'home': 0.33, 'draw': 0.34, 'away': 0.33}

    def _calculate_risk(self, divergence: float, confidence: float) -> str:
        """
        리스크 레벨 계산

        Args:
            divergence: 괴리도 (절댓값)
            confidence: AI 신뢰도 (0-1)

        Returns:
            'low' | 'medium' | 'high'
        """
        # 괴리도가 크고 신뢰도가 높을수록 리스크 낮음
        risk_score = (divergence * 2) + (confidence * 0.5)

        if risk_score >= 0.60:
            return 'low'
        elif risk_score >= 0.35:
            return 'medium'
        else:
            return 'high'

    def find_all_upsets(
        self,
        matches: List[Dict]
    ) -> List[Dict]:
        """
        14경기 전체에서 이변 후보 찾기

        Args:
            matches: 경기 리스트
                [
                    {
                        'id': '001',
                        'home_team': 'Arsenal',
                        'away_team': 'Liverpool',
                        'ai_prediction': {'home': 0.45, 'draw': 0.28, 'away': 0.27},
                        'official_odds': {'home': 1.80, 'draw': 3.50, 'away': 4.50},
                        'confidence': 0.85
                    },
                    ...
                ]

        Returns:
            이변 후보 리스트 (괴리도 순 정렬)
        """
        upsets = []

        for match in matches:
            upset_analysis = self.detect_upsets(
                ai_prediction=match.get('ai_prediction', {}),
                official_odds=match.get('official_odds', {}),
                confidence=match.get('confidence', 0)
            )

            if upset_analysis['is_upset_candidate']:
                upsets.append({
                    'match_id': match.get('id', ''),
                    'match_name': f"{match.get('home_team', '')} vs {match.get('away_team', '')}",
                    **upset_analysis
                })

        # 괴리도 순 정렬
        upsets.sort(key=lambda x: abs(x['divergence']), reverse=True)

        return upsets

    def get_upset_summary(self, upsets: List[Dict]) -> Dict:
        """
        이변 후보 요약 통계

        Args:
            upsets: find_all_upsets() 결과

        Returns:
            {
                'total_upsets': int,
                'underdog_count': int,
                'overdog_count': int,
                'risk_breakdown': {'low': 3, 'medium': 2, 'high': 1},
                'avg_divergence': float
            }
        """
        if not upsets:
            return {
                'total_upsets': 0,
                'underdog_count': 0,
                'overdog_count': 0,
                'risk_breakdown': {'low': 0, 'medium': 0, 'high': 0},
                'avg_divergence': 0.0
            }

        underdog_count = sum(1 for u in upsets if u.get('upset_type') == 'underdog')
        overdog_count = sum(1 for u in upsets if u.get('upset_type') == 'overdog')

        risk_breakdown = {
            'low': sum(1 for u in upsets if u.get('risk_level') == 'low'),
            'medium': sum(1 for u in upsets if u.get('risk_level') == 'medium'),
            'high': sum(1 for u in upsets if u.get('risk_level') == 'high')
        }

        avg_divergence = np.mean([abs(u.get('divergence', 0)) for u in upsets])

        return {
            'total_upsets': len(upsets),
            'underdog_count': underdog_count,
            'overdog_count': overdog_count,
            'risk_breakdown': risk_breakdown,
            'avg_divergence': float(avg_divergence)
        }
