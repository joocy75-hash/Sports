#!/usr/bin/env python3
"""
농구 승5패 분석기 (Basketball Win-5-Lose Analyzer)

승5패 게임 규칙:
- 승(W): 홈팀이 6점 이상 차이로 승리
- 5: 점수 차이가 5점 이내 (접전)
- 패(L): 원정팀이 6점 이상 차이로 승리 (홈팀 대패)

이변 가능성 분석:
- 배당률 대비 실제 확률이 과소평가된 결과를 찾음
- 접전(5) 확률이 높은 경기, 약팀의 승리 가능성 분석
"""

import asyncio
import math
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
from datetime import datetime
from scipy import stats
import numpy as np

from dotenv import load_dotenv
load_dotenv()


@dataclass
class TeamStats:
    """팀 통계 데이터"""
    name: str
    league: str  # "NBA" or "KBL"

    # 공격/수비 레이팅 (100 포제션당 득점)
    off_rating: float = 110.0
    def_rating: float = 110.0

    # 최근 성적
    recent_wins: int = 5
    recent_losses: int = 5

    # 홈/원정 성적
    home_record: Tuple[int, int] = (10, 10)  # (wins, losses)
    away_record: Tuple[int, int] = (10, 10)

    # 점수 차이 관련 통계
    avg_margin: float = 0.0  # 평균 점수 차이 (양수=승리 마진)
    margin_std: float = 12.0  # 점수 차이 표준편차

    # 접전 경기 비율
    close_game_pct: float = 0.25  # 5점 이내 경기 비율


@dataclass
class W5LPrediction:
    """승5패 예측 결과"""
    game_number: int
    home_team: str
    away_team: str
    match_time: str
    league: str

    # 승/5/패 확률
    prob_win: float      # 홈팀 6점↑ 승리
    prob_5: float        # 5점 이내 접전
    prob_lose: float     # 원정팀 6점↑ 승리

    # 예상 점수
    expected_home_score: float
    expected_away_score: float
    expected_margin: float  # 홈팀 기준 (+면 홈 우세)

    # 추천
    recommended: str     # "승", "5", "패"
    confidence: float    # 최고 확률

    # 이변 가능성 (배당 대비)
    upset_value: float = 0.0  # 양수면 이변 가치 있음
    upset_type: Optional[str] = None  # "underdog_win", "close_game", "blowout"

    # 분석 근거
    analysis: str = ""


@dataclass
class W5LCombination:
    """복식 조합"""
    games: List[W5LPrediction]
    selections: List[str]  # ["승", "5", "패", ...]

    # 조합 확률
    combined_prob: float

    # 이변 가치
    upset_score: float

    # 설명
    description: str = ""


# NBA/KBL 팀 기본 통계 (2024-25 시즌 기준 추정치)
NBA_TEAM_STATS = {
    # 동부 컨퍼런스 강팀
    "클리블랜드캐벌리어스": TeamStats("클리블랜드캐벌리어스", "NBA", 117.5, 108.0, 8, 2, (12, 3), (10, 4), 8.5, 11.0, 0.22),
    "보스턴셀틱스": TeamStats("보스턴셀틱스", "NBA", 118.0, 109.5, 7, 3, (11, 4), (9, 5), 7.2, 11.5, 0.24),
    "뉴욕닉스": TeamStats("뉴욕닉스", "NBA", 114.5, 110.0, 6, 4, (10, 5), (8, 6), 4.5, 10.5, 0.28),
    "밀워키벅스": TeamStats("밀워키벅스", "NBA", 115.0, 112.5, 5, 5, (8, 6), (7, 7), 2.5, 12.0, 0.26),
    "인디애나페이서스": TeamStats("인디애나페이서스", "NBA", 116.0, 114.0, 5, 5, (8, 6), (6, 8), 2.0, 13.0, 0.25),
    "마이애미히트": TeamStats("마이애미히트", "NBA", 110.5, 111.0, 5, 5, (7, 7), (6, 8), -0.5, 11.0, 0.30),
    "올랜도매직": TeamStats("올랜도매직", "NBA", 109.0, 107.5, 6, 4, (9, 5), (7, 7), 1.5, 10.0, 0.27),
    "애틀랜타호크스": TeamStats("애틀랜타호크스", "NBA", 113.5, 115.0, 5, 5, (7, 7), (6, 8), -1.5, 12.5, 0.24),
    "시카고불스": TeamStats("시카고불스", "NBA", 111.0, 114.0, 4, 6, (6, 8), (5, 9), -3.0, 11.5, 0.26),
    "필라델피아76s": TeamStats("필라델피아76s", "NBA", 108.0, 112.0, 3, 7, (5, 9), (4, 10), -4.0, 13.0, 0.23),
    "토론토랩터스": TeamStats("토론토랩터스", "NBA", 107.5, 116.0, 2, 8, (4, 10), (3, 11), -8.5, 12.0, 0.20),
    "브루클린네츠": TeamStats("브루클린네츠", "NBA", 108.5, 117.0, 2, 8, (3, 11), (3, 11), -8.5, 13.5, 0.18),
    "샬럿호네츠": TeamStats("샬럿호네츠", "NBA", 106.0, 118.0, 2, 8, (3, 11), (2, 12), -12.0, 14.0, 0.16),
    "워싱턴위저즈": TeamStats("워싱턴위저즈", "NBA", 105.0, 120.0, 1, 9, (2, 12), (1, 13), -15.0, 15.0, 0.14),

    # 서부 컨퍼런스 강팀
    "오클라호마시티썬더": TeamStats("오클라호마시티썬더", "NBA", 117.0, 107.0, 9, 1, (13, 2), (11, 4), 10.0, 10.5, 0.20),
    "휴스턴로케츠": TeamStats("휴스턴로케츠", "NBA", 113.0, 109.0, 7, 3, (10, 5), (9, 6), 4.0, 11.0, 0.26),
    "멤피스그리즐리스": TeamStats("멤피스그리즐리스", "NBA", 114.0, 111.0, 6, 4, (9, 5), (8, 7), 3.0, 12.5, 0.24),
    "댈러스매버릭스": TeamStats("댈러스매버릭스", "NBA", 115.5, 112.5, 6, 4, (9, 5), (7, 7), 3.0, 12.0, 0.25),
    "덴버너게츠": TeamStats("덴버너게츠", "NBA", 114.5, 113.0, 5, 5, (8, 6), (6, 8), 1.5, 11.5, 0.27),
    "LA레이커스": TeamStats("LA레이커스", "NBA", 113.0, 112.0, 5, 5, (8, 6), (6, 8), 1.0, 12.0, 0.28),
    "LA클리퍼스": TeamStats("LA클리퍼스", "NBA", 111.0, 111.5, 5, 5, (7, 7), (6, 8), -0.5, 11.0, 0.30),
    "미네소타팀버울브스": TeamStats("미네소타팀버울브스", "NBA", 110.0, 109.0, 5, 5, (8, 6), (6, 8), 1.0, 10.5, 0.29),
    "피닉스선즈": TeamStats("피닉스선즈", "NBA", 112.5, 113.5, 5, 5, (7, 7), (6, 8), -1.0, 12.5, 0.26),
    "골든스테이트워리어스": TeamStats("골든스테이트워리어스", "NBA", 111.5, 112.5, 4, 6, (7, 7), (5, 9), -1.0, 11.5, 0.28),
    "새크라멘토킹스": TeamStats("새크라멘토킹스", "NBA", 113.0, 114.5, 4, 6, (6, 8), (5, 9), -1.5, 13.0, 0.24),
    "샌안토니오스퍼스": TeamStats("샌안토니오스퍼스", "NBA", 110.5, 115.0, 4, 6, (6, 8), (4, 10), -4.5, 13.5, 0.22),
    "포틀랜드트레일블레이저스": TeamStats("포틀랜드트레일블레이저스", "NBA", 108.0, 116.5, 3, 7, (5, 9), (3, 11), -8.5, 14.0, 0.19),
    "유타재즈": TeamStats("유타재즈", "NBA", 107.0, 118.0, 2, 8, (3, 11), (2, 12), -11.0, 14.5, 0.17),
    "뉴올리언스펠리컨스": TeamStats("뉴올리언스펠리컨스", "NBA", 109.5, 115.5, 3, 7, (4, 10), (3, 11), -6.0, 13.0, 0.21),
    "디트로이트피스톤스": TeamStats("디트로이트피스톤스", "NBA", 109.0, 116.0, 3, 7, (4, 10), (3, 11), -7.0, 13.5, 0.20),
}

KBL_TEAM_STATS = {
    # KBL 2024-25 시즌 (추정치)
    "울산현대모비스피버스": TeamStats("울산현대모비스피버스", "KBL", 82.0, 78.0, 7, 3, (8, 4), (6, 5), 4.0, 9.0, 0.30),
    "서울SK나이츠": TeamStats("서울SK나이츠", "KBL", 81.0, 79.0, 6, 4, (7, 5), (6, 5), 2.0, 8.5, 0.32),
    "안양정관장레드부스터스": TeamStats("안양정관장레드부스터스", "KBL", 80.5, 79.5, 6, 4, (7, 5), (5, 6), 1.0, 9.0, 0.30),
    "수원KT소닉붐": TeamStats("수원KT소닉붐", "KBL", 79.5, 80.0, 5, 5, (6, 6), (5, 6), -0.5, 8.0, 0.33),
    "서울삼성썬더스": TeamStats("서울삼성썬더스", "KBL", 79.0, 80.5, 5, 5, (6, 6), (4, 7), -1.5, 9.5, 0.28),
    "부산KCC이지스": TeamStats("부산KCC이지스", "KBL", 80.0, 79.0, 5, 5, (6, 6), (5, 6), 1.0, 8.5, 0.31),
    "원주DB프로미": TeamStats("원주DB프로미", "KBL", 78.5, 81.0, 4, 6, (5, 7), (4, 7), -2.5, 9.0, 0.29),
    "창원LG세이커스": TeamStats("창원LG세이커스", "KBL", 78.0, 81.5, 4, 6, (4, 8), (4, 7), -3.5, 10.0, 0.26),
    "대구한국가스공사페가수스": TeamStats("대구한국가스공사페가수스", "KBL", 77.5, 82.0, 3, 7, (4, 8), (3, 8), -4.5, 10.5, 0.24),
    "고양소노스카이거너스": TeamStats("고양소노스카이거너스", "KBL", 77.0, 82.5, 3, 7, (3, 9), (3, 8), -5.5, 11.0, 0.22),

    # WKBL (여자프로농구)
    "우리은행우리WON": TeamStats("우리은행우리WON", "WKBL", 72.0, 68.0, 8, 2, (9, 2), (7, 3), 4.0, 8.0, 0.28),
    "삼성생명블루밍스": TeamStats("삼성생명블루밍스", "WKBL", 70.0, 70.0, 5, 5, (6, 5), (5, 6), 0.0, 8.5, 0.32),
    "하나은행": TeamStats("하나은행", "WKBL", 69.5, 71.0, 5, 5, (5, 6), (5, 6), -1.5, 9.0, 0.30),
    "신한은행에스버드": TeamStats("신한은행에스버드", "WKBL", 68.5, 72.0, 4, 6, (5, 6), (4, 7), -3.5, 9.5, 0.26),
    "KB스타즈": TeamStats("KB스타즈", "WKBL", 68.0, 72.5, 3, 7, (4, 7), (3, 8), -4.5, 10.0, 0.24),
    "BNK썸": TeamStats("BNK썸", "WKBL", 67.0, 73.0, 3, 7, (3, 8), (3, 8), -6.0, 10.5, 0.22),
}

ALL_TEAM_STATS = {**NBA_TEAM_STATS, **KBL_TEAM_STATS}


class BasketballW5LAnalyzer:
    """농구 승5패 분석기"""

    def __init__(self):
        self.team_stats = ALL_TEAM_STATS
        # 홈 어드밴티지 (NBA: 약 3점, KBL: 약 4점)
        self.home_advantage = {"NBA": 3.0, "KBL": 4.0, "WKBL": 3.5}

    def get_team_stats(self, team_name: str) -> TeamStats:
        """팀 통계 조회 (없으면 기본값 반환)"""
        if team_name in self.team_stats:
            return self.team_stats[team_name]

        # 리그 추정
        if any(x in team_name for x in ["이지스", "SK", "KT", "DB", "LG", "가스공사", "소노", "삼성썬더스", "피버스", "레드부스터스"]):
            return TeamStats(team_name, "KBL", 79.0, 80.0, 5, 5)
        elif any(x in team_name for x in ["우리은행", "삼성생명", "하나은행", "신한은행", "KB스타즈", "BNK"]):
            return TeamStats(team_name, "WKBL", 69.0, 71.0, 5, 5)
        else:
            return TeamStats(team_name, "NBA", 111.0, 112.0, 5, 5)

    def predict_margin(
        self,
        home_team: str,
        away_team: str,
        is_home: bool = True
    ) -> Tuple[float, float]:
        """
        예상 점수 차이 및 표준편차 계산

        Returns:
            (expected_margin, std_dev): 홈팀 기준 예상 점수 차이와 표준편차
        """
        home_stats = self.get_team_stats(home_team)
        away_stats = self.get_team_stats(away_team)

        # 리그 결정
        league = home_stats.league
        home_adv = self.home_advantage.get(league, 3.0)

        # 예상 득점 계산 (레이팅 기반)
        # 홈팀 득점 = (홈 공격력 + 리그 평균 - 원정 수비력) / 2
        league_avg = 110.0 if league == "NBA" else (80.0 if league == "KBL" else 70.0)

        home_score = (home_stats.off_rating + league_avg - away_stats.def_rating) / 2
        away_score = (away_stats.off_rating + league_avg - home_stats.def_rating) / 2

        # 홈 어드밴티지 적용
        home_score += home_adv / 2
        away_score -= home_adv / 2

        # 최근 폼 반영 (10%)
        home_form = (home_stats.recent_wins - home_stats.recent_losses) / 10
        away_form = (away_stats.recent_wins - away_stats.recent_losses) / 10

        home_score += home_form * 1.5
        away_score += away_form * 1.5

        # 예상 마진 (홈팀 기준)
        expected_margin = home_score - away_score

        # 표준편차 (두 팀의 변동성 합성)
        combined_std = math.sqrt(home_stats.margin_std**2 + away_stats.margin_std**2) / math.sqrt(2)

        return expected_margin, combined_std

    def calculate_w5l_probabilities(
        self,
        expected_margin: float,
        std_dev: float
    ) -> Tuple[float, float, float]:
        """
        승/5/패 확률 계산 (정규분포 기반)

        승(W): 홈팀이 6점 이상 차이로 승리 → margin >= 6
        5: 점수 차이가 5점 이내 → -5 <= margin <= 5
        패(L): 원정팀이 6점 이상 차이로 승리 → margin <= -6
        """
        # 정규분포 CDF 사용
        norm = stats.norm(loc=expected_margin, scale=std_dev)

        # P(margin >= 6) = 1 - P(margin < 6)
        prob_win = 1 - norm.cdf(5.5)  # 5.5 초과 = 6 이상

        # P(-5.5 < margin < 5.5) = P(margin < 5.5) - P(margin <= -5.5)
        prob_5 = norm.cdf(5.5) - norm.cdf(-5.5)

        # P(margin <= -6) = P(margin < -5.5)
        prob_lose = norm.cdf(-5.5)

        return prob_win, prob_5, prob_lose

    def analyze_game(
        self,
        game_number: int,
        home_team: str,
        away_team: str,
        match_time: str,
        home_odds: float = 2.0,
        draw_odds: float = 3.5,
        away_odds: float = 2.5
    ) -> W5LPrediction:
        """단일 경기 분석"""

        # 팀 통계 가져오기
        home_stats = self.get_team_stats(home_team)
        away_stats = self.get_team_stats(away_team)
        league = home_stats.league

        # 예상 점수 차이 계산
        expected_margin, std_dev = self.predict_margin(home_team, away_team)

        # 승/5/패 확률 계산
        prob_win, prob_5, prob_lose = self.calculate_w5l_probabilities(expected_margin, std_dev)

        # 예상 점수 (레이팅 기반)
        league_avg = 110.0 if league == "NBA" else (80.0 if league == "KBL" else 70.0)
        home_score = league_avg + expected_margin / 2
        away_score = league_avg - expected_margin / 2

        # 추천 결정
        probs = {"승": prob_win, "5": prob_5, "패": prob_lose}
        recommended = max(probs, key=probs.get)
        confidence = probs[recommended]

        # 이변 가능성 분석
        upset_value, upset_type = self._analyze_upset_potential(
            prob_win, prob_5, prob_lose,
            home_odds, draw_odds, away_odds,
            home_stats, away_stats
        )

        # 분석 근거 생성
        analysis = self._generate_analysis(
            home_team, away_team, expected_margin, std_dev,
            prob_win, prob_5, prob_lose, upset_type
        )

        return W5LPrediction(
            game_number=game_number,
            home_team=home_team,
            away_team=away_team,
            match_time=match_time,
            league=league,
            prob_win=round(prob_win, 4),
            prob_5=round(prob_5, 4),
            prob_lose=round(prob_lose, 4),
            expected_home_score=round(home_score, 1),
            expected_away_score=round(away_score, 1),
            expected_margin=round(expected_margin, 1),
            recommended=recommended,
            confidence=round(confidence, 4),
            upset_value=round(upset_value, 3),
            upset_type=upset_type,
            analysis=analysis
        )

    def _analyze_upset_potential(
        self,
        prob_win: float,
        prob_5: float,
        prob_lose: float,
        home_odds: float,
        draw_odds: float,
        away_odds: float,
        home_stats: TeamStats,
        away_stats: TeamStats
    ) -> Tuple[float, Optional[str]]:
        """이변 가능성 분석"""

        # 배당률에서 내재 확률 계산 (마진 제거)
        total_implied = (1/home_odds) + (1/draw_odds) + (1/away_odds)
        implied_win = (1/home_odds) / total_implied
        implied_5 = (1/draw_odds) / total_implied
        implied_lose = (1/away_odds) / total_implied

        # 가치 계산 (실제 확률 - 내재 확률)
        value_win = prob_win - implied_win
        value_5 = prob_5 - implied_5
        value_lose = prob_lose - implied_lose

        # 이변 유형 및 가치 결정
        upset_value = 0.0
        upset_type = None

        # 1. 약팀의 대승 가능성 (패 선택 가치)
        if value_lose > 0.05 and prob_lose > 0.15:
            upset_value = value_lose
            upset_type = "underdog_win"

        # 2. 접전 가능성 과소평가 (5 선택 가치)
        elif value_5 > 0.05 and prob_5 > 0.20:
            upset_value = value_5
            upset_type = "close_game"

        # 3. 강팀의 대승 가능성 과소평가
        elif value_win > 0.08 and prob_win > 0.40:
            upset_value = value_win
            upset_type = "blowout"

        return upset_value, upset_type

    def _generate_analysis(
        self,
        home_team: str,
        away_team: str,
        expected_margin: float,
        std_dev: float,
        prob_win: float,
        prob_5: float,
        prob_lose: float,
        upset_type: Optional[str]
    ) -> str:
        """분석 근거 생성"""
        parts = []

        if expected_margin > 8:
            parts.append(f"{home_team} 대승 예상")
        elif expected_margin > 3:
            parts.append(f"{home_team} 우세")
        elif expected_margin > -3:
            parts.append("접전 예상")
        elif expected_margin > -8:
            parts.append(f"{away_team} 우세")
        else:
            parts.append(f"{away_team} 대승 예상")

        if std_dev > 13:
            parts.append("변동성 높음")
        elif std_dev < 10:
            parts.append("변동성 낮음")

        if upset_type == "underdog_win":
            parts.append("약팀 이변 가능성")
        elif upset_type == "close_game":
            parts.append("5점 이내 접전 가능성")
        elif upset_type == "blowout":
            parts.append("예상 외 대승 가능성")

        return ", ".join(parts)

    def find_upset_combinations(
        self,
        predictions: List[W5LPrediction],
        max_complex: int = 4
    ) -> List[W5LCombination]:
        """이변 가능성 높은 복식 조합 찾기"""

        # 이변 가치가 있는 경기만 필터링
        upset_games = [p for p in predictions if p.upset_value > 0.03]

        if len(upset_games) < 2:
            # 이변 경기가 부족하면 5점 접전 확률 높은 경기 추가
            close_games = sorted(predictions, key=lambda x: x.prob_5, reverse=True)
            upset_games = close_games[:6]

        combinations = []

        # 1. 고신뢰 + 이변 조합 (안정성 + 수익)
        high_conf_games = sorted(predictions, key=lambda x: x.confidence, reverse=True)[:5]

        for upset in upset_games[:3]:
            if upset.upset_type:
                combo_games = [
                    g for g in high_conf_games[:3]
                    if g.game_number != upset.game_number
                ][:2]
                combo_games.append(upset)

                selections = [g.recommended for g in combo_games]
                # 이변 경기는 이변 선택으로 변경
                if upset.upset_type == "close_game":
                    selections[-1] = "5"
                elif upset.upset_type == "underdog_win":
                    selections[-1] = "패"

                combined_prob = 1.0
                for i, g in enumerate(combo_games):
                    if selections[i] == "승":
                        combined_prob *= g.prob_win
                    elif selections[i] == "5":
                        combined_prob *= g.prob_5
                    else:
                        combined_prob *= g.prob_lose

                combinations.append(W5LCombination(
                    games=combo_games,
                    selections=selections,
                    combined_prob=combined_prob,
                    upset_score=upset.upset_value,
                    description=f"이변 조합: {upset.home_team} vs {upset.away_team} - {upset.upset_type}"
                ))

        # 2. 접전(5) 집중 조합
        close_games = sorted(predictions, key=lambda x: x.prob_5, reverse=True)[:4]
        if len(close_games) >= 3:
            selections = ["5"] * len(close_games[:3])
            combined_prob = 1.0
            for g in close_games[:3]:
                combined_prob *= g.prob_5

            combinations.append(W5LCombination(
                games=close_games[:3],
                selections=selections,
                combined_prob=combined_prob,
                upset_score=sum(g.prob_5 for g in close_games[:3]) / 3,
                description="접전(5) 집중 조합 - 5점 이내 경기 예상"
            ))

        # 3. 약팀 이변 조합
        underdog_games = [p for p in predictions if p.prob_lose > 0.20]
        if len(underdog_games) >= 2:
            underdog_games = sorted(underdog_games, key=lambda x: x.prob_lose, reverse=True)[:3]
            selections = ["패"] * len(underdog_games[:2])
            combined_prob = 1.0
            for g in underdog_games[:2]:
                combined_prob *= g.prob_lose

            combinations.append(W5LCombination(
                games=underdog_games[:2],
                selections=selections,
                combined_prob=combined_prob,
                upset_score=sum(g.prob_lose for g in underdog_games[:2]) / 2,
                description="약팀 이변 조합 - 원정팀 대승 예상"
            ))

        # 이변 가치 순으로 정렬
        combinations.sort(key=lambda x: x.upset_score, reverse=True)

        return combinations[:max_complex]


def format_analysis_result(
    predictions: List[W5LPrediction],
    combinations: List[W5LCombination]
) -> str:
    """분석 결과 포맷팅"""

    lines = []
    lines.append("=" * 60)
    lines.append("🏀 농구 승5패 분석 결과")
    lines.append(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("=" * 60)
    lines.append("")

    # 경기별 분석
    lines.append("📊 경기별 분석")
    lines.append("-" * 50)

    for pred in predictions:
        # 추천에 따른 아이콘
        if pred.recommended == "승":
            icon = "🏠"
        elif pred.recommended == "5":
            icon = "🤝"
        else:
            icon = "✈️"

        lines.append(f"\n[{pred.game_number:02d}] {pred.home_team} vs {pred.away_team}")
        lines.append(f"    ⏰ {pred.match_time} | {pred.league}")
        lines.append(f"    📈 예상: {pred.expected_home_score:.0f} - {pred.expected_away_score:.0f} (차이: {pred.expected_margin:+.1f})")
        lines.append(f"    🎯 확률: 승 {pred.prob_win*100:.1f}% | 5 {pred.prob_5*100:.1f}% | 패 {pred.prob_lose*100:.1f}%")
        lines.append(f"    {icon} 추천: [{pred.recommended}] ({pred.confidence*100:.1f}%)")

        if pred.upset_type:
            lines.append(f"    ⚡ 이변: {pred.upset_type} (가치: {pred.upset_value:.1%})")

        lines.append(f"    💡 {pred.analysis}")

    # 복식 조합 추천
    lines.append("")
    lines.append("=" * 60)
    lines.append("🎰 이변 가능성 높은 복식 조합 (최대 4개)")
    lines.append("=" * 60)

    for i, combo in enumerate(combinations, 1):
        lines.append(f"\n📌 조합 {i}: {combo.description}")
        lines.append(f"    확률: {combo.combined_prob*100:.2f}% | 이변가치: {combo.upset_score:.2%}")
        lines.append("    경기:")

        for j, (game, sel) in enumerate(zip(combo.games, combo.selections)):
            lines.append(f"      [{game.game_number:02d}] {game.home_team} vs {game.away_team} → [{sel}]")

    lines.append("")
    lines.append("=" * 60)
    lines.append("⚠️ 주의: 이변 조합은 고위험-고수익 전략입니다.")
    lines.append("   안정적인 베팅을 원하시면 고신뢰도 경기 위주로 선택하세요.")
    lines.append("=" * 60)

    return "\n".join(lines)


async def main():
    """메인 실행"""
    from collect_and_notify import BetmanDataCollector

    print("🏀 농구 승5패 분석 시작...")
    print()

    # 1. 베트맨에서 경기 데이터 수집
    collector = BetmanDataCollector()
    categorized = await collector.collect_all_games(days_ahead=3)
    basketball_games = categorized.get("basketball_5", [])

    if not basketball_games:
        print("❌ 수집된 농구 경기가 없습니다.")
        return

    # 오늘 경기만 필터링 (또는 가장 가까운 경기)
    today = datetime.now().strftime("%Y%m%d")
    today_games = [g for g in basketball_games if str(g.get("match_ymd")) == today]

    if not today_games:
        # 오늘 경기가 없으면 가장 가까운 날짜 사용
        dates = sorted(set(str(g.get("match_ymd")) for g in basketball_games))
        if dates:
            target_date = dates[0]
            today_games = [g for g in basketball_games if str(g.get("match_ymd")) == target_date]

    print(f"📊 분석 대상: {len(today_games)}경기")
    print()

    # 2. 승5패 분석
    analyzer = BasketballW5LAnalyzer()
    predictions = []

    for game in today_games[:14]:  # 최대 14경기
        game_num = game.get("row_num", 0)
        home = game.get("hteam_han_nm", "")
        away = game.get("ateam_han_nm", "")
        match_tm = str(game.get("match_tm", "0000")).zfill(4)
        match_time = f"{match_tm[:2]}:{match_tm[2:]}"

        pred = analyzer.analyze_game(
            game_number=game_num,
            home_team=home,
            away_team=away,
            match_time=match_time
        )
        predictions.append(pred)

    # 3. 이변 복식 조합 찾기
    combinations = analyzer.find_upset_combinations(predictions, max_complex=4)

    # 4. 결과 출력
    result = format_analysis_result(predictions, combinations)
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
