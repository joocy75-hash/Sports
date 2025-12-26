"""
D-02: 최근 경기 결과 수집기
팀별 최근 N경기 결과를 수집하고 폼(Form) 데이터를 분석합니다.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
from enum import Enum
import httpx


class MatchResult(Enum):
    WIN = "W"
    DRAW = "D"
    LOSS = "L"


@dataclass
class RecentMatch:
    """최근 경기 정보"""
    match_id: int
    date: str
    home_team: str
    away_team: str
    home_score: int
    away_score: int
    is_home: bool  # 조회 팀이 홈이었는지
    result: MatchResult
    opponent: str
    league: str
    points: int  # 승=3, 무=1, 패=0


@dataclass
class TeamForm:
    """팀 폼 분석 결과"""
    team_name: str
    matches: List[RecentMatch]
    form_string: str  # "WWDLW" 형태
    points: int  # 최근 5경기 총 승점
    wins: int
    draws: int
    losses: int
    goals_scored: int
    goals_conceded: int
    goal_difference: int
    avg_goals_scored: float
    avg_goals_conceded: float
    clean_sheets: int  # 무실점 경기 수
    failed_to_score: int  # 무득점 경기 수
    home_form: str  # 홈 경기만
    away_form: str  # 원정 경기만
    trend: str  # "improving", "declining", "stable"


class RecentMatchesCollector:
    """최근 경기 결과 수집기"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.base_url = "https://v3.football.api-sports.io"
        self.cache: Dict[str, Any] = {}
        self.cache_ttl = 3600  # 1시간

    async def get_team_recent_matches(
        self,
        team_id: int,
        count: int = 5,
        league_id: Optional[int] = None
    ) -> List[RecentMatch]:
        """팀의 최근 경기 결과 조회"""
        cache_key = f"recent_{team_id}_{count}_{league_id}"
        if cache_key in self.cache:
            cached = self.cache[cache_key]
            if datetime.now().timestamp() - cached["time"] < self.cache_ttl:
                return cached["data"]

        if not self.api_key:
            return self._generate_mock_matches(team_id, count)

        try:
            async with httpx.AsyncClient() as client:
                params = {"team": team_id, "last": count}
                if league_id:
                    params["league"] = league_id

                response = await client.get(
                    f"{self.base_url}/fixtures",
                    params=params,
                    headers={"x-apisports-key": self.api_key},
                    timeout=30.0
                )

                if response.status_code == 200:
                    data = response.json()
                    matches = self._parse_matches(data.get("response", []), team_id)
                    self.cache[cache_key] = {
                        "data": matches,
                        "time": datetime.now().timestamp()
                    }
                    return matches
        except Exception as e:
            print(f"[RecentMatchesCollector] API 오류: {e}")

        return self._generate_mock_matches(team_id, count)

    def _parse_matches(self, fixtures: List[Dict], team_id: int) -> List[RecentMatch]:
        """API 응답을 RecentMatch 객체로 변환"""
        matches = []
        for fixture in fixtures:
            teams = fixture.get("teams", {})
            goals = fixture.get("goals", {})
            league = fixture.get("league", {})

            home_team = teams.get("home", {}).get("name", "")
            away_team = teams.get("away", {}).get("name", "")
            home_id = teams.get("home", {}).get("id", 0)
            home_score = goals.get("home", 0) or 0
            away_score = goals.get("away", 0) or 0

            is_home = home_id == team_id
            team_score = home_score if is_home else away_score
            opponent_score = away_score if is_home else home_score

            if team_score > opponent_score:
                result = MatchResult.WIN
                points = 3
            elif team_score == opponent_score:
                result = MatchResult.DRAW
                points = 1
            else:
                result = MatchResult.LOSS
                points = 0

            matches.append(RecentMatch(
                match_id=fixture.get("fixture", {}).get("id", 0),
                date=fixture.get("fixture", {}).get("date", "")[:10],
                home_team=home_team,
                away_team=away_team,
                home_score=home_score,
                away_score=away_score,
                is_home=is_home,
                result=result,
                opponent=away_team if is_home else home_team,
                league=league.get("name", ""),
                points=points
            ))

        return matches

    def _generate_mock_matches(self, team_id: int, count: int) -> List[RecentMatch]:
        """목업 데이터 생성 (API 없을 때)"""
        import random
        random.seed(team_id)

        opponents = [
            "맨체스터 유나이티드", "첼시", "아스널", "토트넘",
            "맨체스터 시티", "뉴캐슬", "브라이튼", "아스톤 빌라"
        ]
        results_pool = [MatchResult.WIN, MatchResult.WIN, MatchResult.DRAW,
                       MatchResult.LOSS, MatchResult.WIN]

        matches = []
        base_date = datetime.now()

        for i in range(count):
            is_home = random.choice([True, False])
            result = random.choice(results_pool)

            if result == MatchResult.WIN:
                team_score = random.randint(1, 4)
                opp_score = random.randint(0, team_score - 1)
                points = 3
            elif result == MatchResult.DRAW:
                team_score = random.randint(0, 2)
                opp_score = team_score
                points = 1
            else:
                opp_score = random.randint(1, 3)
                team_score = random.randint(0, opp_score - 1)
                points = 0

            home_score = team_score if is_home else opp_score
            away_score = opp_score if is_home else team_score
            opponent = random.choice(opponents)

            matches.append(RecentMatch(
                match_id=10000 + i,
                date=(base_date - timedelta(days=7 * (i + 1))).strftime("%Y-%m-%d"),
                home_team="조회팀" if is_home else opponent,
                away_team=opponent if is_home else "조회팀",
                home_score=home_score,
                away_score=away_score,
                is_home=is_home,
                result=result,
                opponent=opponent,
                league="프리미어리그",
                points=points
            ))

        return matches

    def analyze_form(self, matches: List[RecentMatch], team_name: str = "") -> TeamForm:
        """경기 결과로 폼 분석"""
        if not matches:
            return TeamForm(
                team_name=team_name,
                matches=[],
                form_string="",
                points=0,
                wins=0, draws=0, losses=0,
                goals_scored=0, goals_conceded=0, goal_difference=0,
                avg_goals_scored=0.0, avg_goals_conceded=0.0,
                clean_sheets=0, failed_to_score=0,
                home_form="", away_form="",
                trend="stable"
            )

        form_string = "".join([m.result.value for m in matches])
        home_form = "".join([m.result.value for m in matches if m.is_home])
        away_form = "".join([m.result.value for m in matches if not m.is_home])

        wins = sum(1 for m in matches if m.result == MatchResult.WIN)
        draws = sum(1 for m in matches if m.result == MatchResult.DRAW)
        losses = sum(1 for m in matches if m.result == MatchResult.LOSS)
        points = wins * 3 + draws

        goals_scored = sum(
            m.home_score if m.is_home else m.away_score for m in matches
        )
        goals_conceded = sum(
            m.away_score if m.is_home else m.home_score for m in matches
        )

        clean_sheets = sum(
            1 for m in matches
            if (m.away_score if m.is_home else m.home_score) == 0
        )
        failed_to_score = sum(
            1 for m in matches
            if (m.home_score if m.is_home else m.away_score) == 0
        )

        # 트렌드 분석 (최근 2경기 vs 이전 경기)
        if len(matches) >= 3:
            recent_points = sum(m.points for m in matches[:2])
            older_points = sum(m.points for m in matches[2:])
            older_avg = older_points / len(matches[2:]) if matches[2:] else 0
            recent_avg = recent_points / 2

            if recent_avg > older_avg + 0.5:
                trend = "improving"
            elif recent_avg < older_avg - 0.5:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "stable"

        n = len(matches)
        return TeamForm(
            team_name=team_name,
            matches=matches,
            form_string=form_string,
            points=points,
            wins=wins,
            draws=draws,
            losses=losses,
            goals_scored=goals_scored,
            goals_conceded=goals_conceded,
            goal_difference=goals_scored - goals_conceded,
            avg_goals_scored=round(goals_scored / n, 2) if n else 0,
            avg_goals_conceded=round(goals_conceded / n, 2) if n else 0,
            clean_sheets=clean_sheets,
            failed_to_score=failed_to_score,
            home_form=home_form,
            away_form=away_form,
            trend=trend
        )

    async def get_team_form(
        self,
        team_id: int,
        team_name: str = "",
        count: int = 5
    ) -> TeamForm:
        """팀 폼 분석 결과 조회"""
        matches = await self.get_team_recent_matches(team_id, count)
        return self.analyze_form(matches, team_name)

    def compare_forms(
        self,
        home_form: TeamForm,
        away_form: TeamForm
    ) -> Dict[str, Any]:
        """두 팀의 폼 비교 분석"""
        home_ppg = home_form.points / len(home_form.matches) if home_form.matches else 0
        away_ppg = away_form.points / len(away_form.matches) if away_form.matches else 0

        # 폼 점수 계산 (0-100)
        home_form_score = min(100, int(home_ppg * 33.3))
        away_form_score = min(100, int(away_ppg * 33.3))

        # 공격력/수비력 비교
        home_attack = home_form.avg_goals_scored
        away_attack = away_form.avg_goals_scored
        home_defense = 3 - home_form.avg_goals_conceded  # 낮을수록 좋음
        away_defense = 3 - away_form.avg_goals_conceded

        return {
            "home_form_score": home_form_score,
            "away_form_score": away_form_score,
            "form_advantage": "home" if home_form_score > away_form_score + 10 else (
                "away" if away_form_score > home_form_score + 10 else "neutral"
            ),
            "home_trend": home_form.trend,
            "away_trend": away_form.trend,
            "attack_comparison": {
                "home": round(home_attack, 2),
                "away": round(away_attack, 2),
                "advantage": "home" if home_attack > away_attack else "away"
            },
            "defense_comparison": {
                "home": round(home_form.avg_goals_conceded, 2),
                "away": round(away_form.avg_goals_conceded, 2),
                "advantage": "home" if home_form.avg_goals_conceded < away_form.avg_goals_conceded else "away"
            },
            "expected_goals": {
                "home": round((home_attack + (3 - away_defense)) / 2, 2),
                "away": round((away_attack + (3 - home_defense)) / 2, 2)
            },
            "home_form_string": home_form.form_string,
            "away_form_string": away_form.form_string
        }

    def to_chart_data(self, form: TeamForm) -> List[Dict[str, Any]]:
        """차트용 데이터 변환 (FormChart 컴포넌트용)"""
        return [
            {
                "date": m.date,
                "result": m.result.value,
                "points": m.points
            }
            for m in form.matches
        ]


# 싱글톤 인스턴스
_collector: Optional[RecentMatchesCollector] = None


def get_recent_matches_collector(api_key: Optional[str] = None) -> RecentMatchesCollector:
    """싱글톤 수집기 반환"""
    global _collector
    if _collector is None:
        _collector = RecentMatchesCollector(api_key)
    return _collector


# 테스트
if __name__ == "__main__":
    async def test():
        collector = RecentMatchesCollector()

        # 목업 데이터로 테스트
        matches = await collector.get_team_recent_matches(team_id=40, count=5)
        print("\n[최근 5경기]")
        for m in matches:
            print(f"  {m.date}: {m.home_team} {m.home_score}-{m.away_score} {m.away_team} ({m.result.value})")

        form = collector.analyze_form(matches, "Liverpool")
        print(f"\n[폼 분석]")
        print(f"  폼 스트링: {form.form_string}")
        print(f"  승점: {form.points}점 ({form.wins}승 {form.draws}무 {form.losses}패)")
        print(f"  득실: {form.goals_scored}득점 {form.goals_conceded}실점")
        print(f"  트렌드: {form.trend}")

        print(f"\n[차트 데이터]")
        chart_data = collector.to_chart_data(form)
        print(chart_data)

    asyncio.run(test())
