"""
AI 기반 자체 배당 생성 및 경기 분석 엔진
북메이커 배당에 의존하지 않는 순수 AI 분석 시스템
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import numpy as np
from dataclasses import dataclass
from enum import Enum


class MatchOutcome(Enum):
    HOME_WIN = "home_win"
    DRAW = "draw"
    AWAY_WIN = "away_win"


@dataclass
class TeamAnalysis:
    """팀 분석 결과"""
    team_id: int
    team_name: str
    attack_strength: float  # 0.0 ~ 1.0
    defense_strength: float  # 0.0 ~ 1.0
    recent_form: float  # 최근 5경기 평균 (승=1.0, 무=0.5, 패=0.0)
    home_advantage: float  # 홈 경기 승률 보정치
    key_players: List[str]  # 주전 선수 목록
    injuries: List[str]  # 부상 선수 목록
    momentum: float  # 모멘텀 (최근 성적 추이)


@dataclass
class LineupAnalysis:
    """선발 라인업 분석"""
    formation: str  # 포메이션 (4-3-3 등)
    starting_xi: List[Dict]  # 선발 명단
    key_players_present: bool  # 핵심 선수 출전 여부
    tactical_style: str  # 공격/수비/밸런스
    lineup_strength: float  # 라인업 강도 (0.0 ~ 1.0)


@dataclass
class EnvironmentalFactors:
    """환경적 요인"""
    venue: str  # 경기장
    weather: str  # 날씨
    temperature: float  # 기온
    humidity: float  # 습도
    travel_distance: float  # 이동 거리 (km)
    rest_days: int  # 휴식일 수


@dataclass
class MatchAnalysis:
    """경기 분석 결과"""
    match_id: int
    home_team: TeamAnalysis
    away_team: TeamAnalysis
    lineup_analysis: Optional[LineupAnalysis]  # 라인업 분석 (있을 경우)
    environmental_factors: EnvironmentalFactors
    head_to_head: Dict[str, float]  # 상대 전적 (홈승/무/원정승 비율)
    
    # AI 예측 확률
    predicted_probabilities: Dict[MatchOutcome, float]
    
    # 자체 배당 (1/확률 * 마진)
    own_odds: Dict[MatchOutcome, float]
    
    # 신뢰도 점수
    confidence_score: float  # 0.0 ~ 1.0
    
    # 분석 시간
    analyzed_at: datetime
    match_time: datetime


class AIOddsGenerator:
    """AI 기반 자체 배당 생성기"""
    
    def __init__(self):
        self.margin = 0.05  # 5% 마진 (자체 수익률)
        
    def calculate_base_probabilities(self, analysis: MatchAnalysis) -> Dict[MatchOutcome, float]:
        """기본 확률 계산 (라인업 없는 경우)"""
        
        # 1. 팀 기본 능력치 (40%)
        home_strength = (
            analysis.home_team.attack_strength * 0.6 +
            analysis.home_team.defense_strength * 0.4
        )
        away_strength = (
            analysis.away_team.attack_strength * 0.6 +
            analysis.away_team.defense_strength * 0.4
        )
        
        # 2. 최근 폼 (30%)
        form_factor = analysis.home_team.recent_form - analysis.away_team.recent_form
        
        # 3. 홈 어드밴티지 (15%)
        home_advantage = analysis.home_team.home_advantage
        
        # 4. 상대 전적 (15%)
        h2h_home = analysis.head_to_head.get('home_win', 0.4)
        h2h_away = analysis.head_to_head.get('away_win', 0.3)
        h2h_draw = analysis.head_to_head.get('draw', 0.3)
        
        # 종합 점수 계산
        home_score = (
            home_strength * 0.4 +
            (0.5 + form_factor * 0.5) * 0.3 +
            (0.5 + home_advantage * 0.5) * 0.15 +
            h2h_home * 0.15
        )
        
        away_score = (
            away_strength * 0.4 +
            (0.5 - form_factor * 0.5) * 0.3 +
            (0.5 - home_advantage * 0.5) * 0.15 +
            h2h_away * 0.15
        )
        
        # 확률 정규화
        total = home_score + away_score + h2h_draw
        return {
            MatchOutcome.HOME_WIN: home_score / total,
            MatchOutcome.DRAW: h2h_draw / total,
            MatchOutcome.AWAY_WIN: away_score / total
        }
    
    def calculate_lineup_adjusted_probabilities(self, analysis: MatchAnalysis) -> Dict[MatchOutcome, float]:
        """라인업 반영 확률 계산"""
        base_probs = self.calculate_base_probabilities(analysis)
        
        if not analysis.lineup_analysis:
            return base_probs
        
        # 라인업 영향력 계산
        lineup_impact = analysis.lineup_analysis.lineup_strength
        
        # 홈팀 라인업 영향 (라인업이 강할수록 홈승 확률 증가)
        home_lineup_boost = lineup_impact * 0.2  # 최대 20% 보정
        
        # 핵심 선수 출전 여부
        if analysis.lineup_analysis.key_players_present:
            home_lineup_boost += 0.1
        
        # 확률 조정
        adjusted_probs = base_probs.copy()
        adjusted_probs[MatchOutcome.HOME_WIN] *= (1 + home_lineup_boost)
        adjusted_probs[MatchOutcome.AWAY_WIN] *= (1 - home_lineup_boost * 0.5)
        
        # 정규화
        total = sum(adjusted_probs.values())
        return {k: v / total for k, v in adjusted_probs.items()}
    
    def generate_own_odds(self, probabilities: Dict[MatchOutcome, float]) -> Dict[MatchOutcome, float]:
        """자체 배당 생성 (마진 포함)"""
        odds = {}
        for outcome, prob in probabilities.items():
            # 1/확률 * (1 + 마진)
            odds[outcome] = round(1.0 / prob * (1 + self.margin), 2)
        return odds
    
    def analyze_match(self, analysis: MatchAnalysis) -> MatchAnalysis:
        """경기 분석 실행"""
        
        # 라인업 여부에 따라 다른 확률 계산
        if analysis.lineup_analysis:
            probabilities = self.calculate_lineup_adjusted_probabilities(analysis)
            confidence = min(0.9, analysis.lineup_analysis.lineup_strength * 0.8 + 0.3)
        else:
            probabilities = self.calculate_base_probabilities(analysis)
            confidence = 0.7  # 라인업 없을 때 기본 신뢰도
        
        # 자체 배당 생성
        own_odds = self.generate_own_odds(probabilities)
        
        # 분석 결과 업데이트
        analysis.predicted_probabilities = probabilities
        analysis.own_odds = own_odds
        analysis.confidence_score = confidence
        analysis.analyzed_at = datetime.now()
        
        return analysis


class ProtoAnalyzer:
    """프로토 승무패 14경기 분석기"""
    
    def __init__(self):
        self.combination_cache = {}
        
    def analyze_proto_matches(self, matches: List[MatchAnalysis]) -> Dict:
        """14경기 프로토 분석"""
        
        if len(matches) != 14:
            raise ValueError("프로토 분석은 정확히 14경기가 필요합니다")
        
        # 각 경기별 확률 계산
        match_probs = []
        for match in matches:
            analyzer = AIOddsGenerator()
            analyzed = analyzer.analyze_match(match)
            match_probs.append({
                'match_id': match.match_id,
                'home_team': match.home_team.team_name,
                'away_team': match.away_team.team_name,
                'probabilities': analyzed.predicted_probabilities,
                'confidence': analyzed.confidence_score
            })
        
        # 최적의 단일식 조합 찾기
        best_single = self.find_best_single_combination(match_probs)
        
        # 최적의 복수식 조합 찾기 (상위 3개)
        best_multiple = self.find_best_multiple_combinations(match_probs, top_n=3)
        
        return {
            'analysis_time': datetime.now(),
            'total_matches': 14,
            'match_analyses': match_probs,
            'best_single_combination': best_single,
            'best_multiple_combinations': best_multiple,
            'recommendation': self.generate_recommendation(best_single, best_multiple)
        }
    
    def find_best_single_combination(self, match_probs: List[Dict]) -> Dict:
        """최고 확률의 단일식 조합 찾기"""
        combination = []
        total_prob = 1.0
        total_confidence = 0.0
        
        for match in match_probs:
            # 각 경기별 가장 높은 확률의 결과 선택
            probs = match['probabilities']
            best_outcome = max(probs.items(), key=lambda x: x[1])
            
            combination.append({
                'match_id': match['match_id'],
                'prediction': best_outcome[0].value,
                'probability': best_outcome[1],
                'confidence': match['confidence']
            })
            
            total_prob *= best_outcome[1]
            total_confidence += match['confidence']
        
        avg_confidence = total_confidence / len(match_probs)
        
        return {
            'combination': combination,
            'total_probability': total_prob,
            'expected_value': total_prob * 100,  # 단일식 당첨금 기준
            'confidence': avg_confidence,
            'risk_level': self.calculate_risk_level(total_prob)
        }
    
    def find_best_multiple_combinations(self, match_probs: List[Dict], top_n: int = 3) -> List[Dict]:
        """최고의 복수식 조합 찾기 (상위 N개)"""
        # 복잡한 조합 탐색 알고리즘 (간소화 버전)
        # 실제로는 3^14 조합을 모두 탐색할 수 없으므로 휴리스틱 사용
        
        combinations = []
        
        # 각 경기별 상위 2개 선택지 고려
        for i in range(top_n):
            combination = []
            total_prob = 1.0
            
            for match in match_probs:
                probs = list(match['probabilities'].items())
                probs.sort(key=lambda x: x[1], reverse=True)
                
                # i번째로 좋은 선택지 선택 (다양성 위해)
                selected_idx = min(i, len(probs) - 1)
                selected = probs[selected_idx]
                
                combination.append({
                    'match_id': match['match_id'],
                    'prediction': selected[0].value,
                    'probability': selected[1]
                })
                
                total_prob *= selected[1]
            
            combinations.append({
                'combination': combination,
                'total_probability': total_prob,
                'expected_value': total_prob * 50,  # 복수식 당첨금 기준
                'combination_type': f'variant_{i+1}'
            })
        
        # 확률 기준 정렬
        combinations.sort(key=lambda x: x['total_probability'], reverse=True)
        return combinations[:top_n]
    
    def calculate_risk_level(self, probability: float) -> str:
        """리스크 레벨 계산"""
        if probability > 0.0001:  # 0.01%
            return "매우 높음"
        elif probability > 0.00001:  # 0.001%
            return "높음"
        elif probability > 0.000001:  # 0.0001%
            return "중간"
        else:
            return "매우 낮음"
    
    def generate_recommendation(self, single: Dict, multiple: List[Dict]) -> Dict:
        """베팅 추천 생성"""
        single_ev = single['expected_value']
        best_multiple_ev = multiple[0]['expected_value'] if multiple else 0
        
        if single_ev > best_multiple_ev * 2:  # 단일식 기대값이 2배 이상 높을 때
            recommendation = "단일식 추천"
            reasoning = "단일식의 기대값이 복수식보다 현저히 높습니다"
        else:
            recommendation = "복수식 추천 (분산 투자)"
            reasoning = "복수식을 통해 리스크를 분산하는 것이 유리합니다"
        
        return {
            'recommendation': recommendation,
            'reasoning': reasoning,
            'suggested_budget_allocation': {
                'single': 0.3 if recommendation == "복수식 추천 (분산 투자)" else 0.7,
                'multiple': 0.7 if recommendation == "복수식 추천 (분산 투자)" else 0.3
            },
            'expected_return': max(single_ev, best_multiple_ev)
        }


# 사용 예시
async def main():
    """테스트 실행"""
    analyzer = AIOddsGenerator()
    proto_analyzer = ProtoAnalyzer()
    
    print("✅ AI 배당 생성기 및 프로토 분석기 초기화 완료")
    print("1. 자체 배당 생성 시스템")
    print("2. 프로토 14경기 분석 시스템")
    print("3. 라인업 기반 실시간 분석")
    
    return analyzer, proto_analyzer


if __name__ == "__main__":
    asyncio.run(main())