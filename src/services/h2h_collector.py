"""
D-03: 상대전적 H2H 데이터 수집기
두 팀 간의 과거 상대전적을 수집하고 분석합니다.
"""

import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
import httpx


@dataclass
class H2HMatch:
    """상대전적 경기 정보"""
    match_id: int
    date: str
    competition: str
    home_team: str
    away_team: str
    home_score: int
    away_score: int
    venue: Optional[str] = None


@dataclass
class H2HStats:
    """상대전적 통계"""
    total_matches: int
    home_team_wins: int
    away_team_wins: int
    draws: int
    home_team_goals: int
    away_team_goals: int
    avg_goals_per_match: float
    avg_home_goals: float
    avg_away_goals: float
    both_teams_scored_pct: float
    over_2_5_pct: float
    home_team_name: str
    away_team_name: str


@dataclass
class H2HAnalysis:
    """상대전적 분석 결과"""
    stats: H2HStats
    recent_matches: List[H2HMatch]
    home_dominance: float  # -1 ~ 1 (음수면 원정팀 우세)
    trend: str  # "home_improving", "away_improving", "stable"
    venue_factor: float  # 홈 경기장에서의 추가 이점
    psychological_edge: str  # "home", "away", "neutral"
    key_insights: List[str]


class H2HCollector:
    """상대전적 데이터 수집기"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.base_url = "https://v3.football.api-sports.io"
        self.cache: Dict[str, Any] = {}
        self.cache_ttl = 86400  # 24시간 (H2H는 자주 안 바뀜)

    async def get_h2h(
        self,
        home_team_id: int,
        away_team_id: int,
        limit: int = 10
    ) -> List[H2HMatch]:
        """두 팀 간 상대전적 조회"""
        cache_key = f"h2h_{min(home_team_id, away_team_id)}_{max(home_team_id, away_team_id)}_{limit}"
        if cache_key in self.cache:
            cached = self.cache[cache_key]
            if datetime.now().timestamp() - cached["time"] < self.cache_ttl:
                return cached["data"]

        if not self.api_key:
            return self._generate_mock_h2h(home_team_id, away_team_id, limit)

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/fixtures/headtohead",
                    params={"h2h": f"{home_team_id}-{away_team_id}", "last": limit},
                    headers={"x-apisports-key": self.api_key},
                    timeout=30.0
                )

                if response.status_code == 200:
                    data = response.json()
                    matches = self._parse_h2h(data.get("response", []))
                    self.cache[cache_key] = {
                        "data": matches,
                        "time": datetime.now().timestamp()
                    }
                    return matches
        except Exception as e:
            print(f"[H2HCollector] API 오류: {e}")

        return self._generate_mock_h2h(home_team_id, away_team_id, limit)

    def _parse_h2h(self, fixtures: List[Dict]) -> List[H2HMatch]:
        """API 응답을 H2HMatch 객체로 변환"""
        matches = []
        for fixture in fixtures:
            teams = fixture.get("teams", {})
            goals = fixture.get("goals", {})
            league = fixture.get("league", {})
            venue = fixture.get("fixture", {}).get("venue", {})

            matches.append(H2HMatch(
                match_id=fixture.get("fixture", {}).get("id", 0),
                date=fixture.get("fixture", {}).get("date", "")[:10],
                competition=league.get("name", ""),
                home_team=teams.get("home", {}).get("name", ""),
                away_team=teams.get("away", {}).get("name", ""),
                home_score=goals.get("home", 0) or 0,
                away_score=goals.get("away", 0) or 0,
                venue=venue.get("name")
            ))

        return sorted(matches, key=lambda x: x.date, reverse=True)

    def _generate_mock_h2h(
        self,
        home_team_id: int,
        away_team_id: int,
        limit: int
    ) -> List[H2HMatch]:
        """목업 데이터 생성"""
        import random
        random.seed(home_team_id + away_team_id)

        teams = {
            40: "Liverpool", 33: "Manchester United",
            50: "Manchester City", 47: "Tottenham",
            42: "Arsenal", 49: "Chelsea"
        }

        home_name = teams.get(home_team_id, f"Team_{home_team_id}")
        away_name = teams.get(away_team_id, f"Team_{away_team_id}")

        matches = []
        from datetime import timedelta
        base_date = datetime.now()

        for i in range(limit):
            # 랜덤하게 홈/원정 결정 (상대전적이므로 양팀이 번갈아가며 홈)
            if i % 2 == 0:
                h_team, a_team = home_name, away_name
            else:
                h_team, a_team = away_name, home_name

            h_score = random.randint(0, 4)
            a_score = random.randint(0, 3)

            matches.append(H2HMatch(
                match_id=20000 + i,
                date=(base_date - timedelta(days=90 * (i + 1))).strftime("%Y-%m-%d"),
                competition="프리미어리그" if random.random() > 0.2 else "FA컵",
                home_team=h_team,
                away_team=a_team,
                home_score=h_score,
                away_score=a_score,
                venue=f"{h_team} Stadium"
            ))

        return matches

    def calculate_stats(
        self,
        matches: List[H2HMatch],
        team1_name: str,
        team2_name: str
    ) -> H2HStats:
        """상대전적 통계 계산"""
        if not matches:
            return H2HStats(
                total_matches=0,
                home_team_wins=0, away_team_wins=0, draws=0,
                home_team_goals=0, away_team_goals=0,
                avg_goals_per_match=0, avg_home_goals=0, avg_away_goals=0,
                both_teams_scored_pct=0, over_2_5_pct=0,
                home_team_name=team1_name, away_team_name=team2_name
            )

        team1_wins = 0
        team2_wins = 0
        draws = 0
        team1_goals = 0
        team2_goals = 0
        both_scored = 0
        over_2_5 = 0

        for m in matches:
            # team1이 이번 경기에서 홈인지 확인
            team1_is_home = m.home_team.lower() == team1_name.lower() or \
                           team1_name.lower() in m.home_team.lower()

            if team1_is_home:
                t1_score, t2_score = m.home_score, m.away_score
            else:
                t1_score, t2_score = m.away_score, m.home_score

            team1_goals += t1_score
            team2_goals += t2_score

            if t1_score > t2_score:
                team1_wins += 1
            elif t2_score > t1_score:
                team2_wins += 1
            else:
                draws += 1

            if t1_score > 0 and t2_score > 0:
                both_scored += 1

            if t1_score + t2_score > 2.5:
                over_2_5 += 1

        n = len(matches)
        return H2HStats(
            total_matches=n,
            home_team_wins=team1_wins,
            away_team_wins=team2_wins,
            draws=draws,
            home_team_goals=team1_goals,
            away_team_goals=team2_goals,
            avg_goals_per_match=round((team1_goals + team2_goals) / n, 2),
            avg_home_goals=round(team1_goals / n, 2),
            avg_away_goals=round(team2_goals / n, 2),
            both_teams_scored_pct=round(both_scored / n * 100, 1),
            over_2_5_pct=round(over_2_5 / n * 100, 1),
            home_team_name=team1_name,
            away_team_name=team2_name
        )

    def analyze_h2h(
        self,
        matches: List[H2HMatch],
        home_team: str,
        away_team: str
    ) -> H2HAnalysis:
        """상대전적 심층 분석"""
        stats = self.calculate_stats(matches, home_team, away_team)

        # 우세도 계산 (-1: 원정 완전 우세, 0: 균형, 1: 홈 완전 우세)
        if stats.total_matches > 0:
            dominance = (stats.home_team_wins - stats.away_team_wins) / stats.total_matches
        else:
            dominance = 0

        # 최근 트렌드 (최근 3경기 vs 이전 경기)
        if len(matches) >= 4:
            recent = matches[:3]
            older = matches[3:]

            recent_wins = sum(1 for m in recent if self._is_team_win(m, home_team))
            older_wins = sum(1 for m in older if self._is_team_win(m, home_team))

            recent_rate = recent_wins / 3
            older_rate = older_wins / len(older) if older else 0

            if recent_rate > older_rate + 0.2:
                trend = "home_improving"
            elif recent_rate < older_rate - 0.2:
                trend = "away_improving"
            else:
                trend = "stable"
        else:
            trend = "stable"

        # 홈 경기장 이점 계산
        home_venue_matches = [m for m in matches if home_team.lower() in m.home_team.lower()]
        if home_venue_matches:
            home_venue_wins = sum(1 for m in home_venue_matches if m.home_score > m.away_score)
            venue_factor = home_venue_wins / len(home_venue_matches)
        else:
            venue_factor = 0.5

        # 심리적 우위
        if dominance > 0.3:
            psychological_edge = "home"
        elif dominance < -0.3:
            psychological_edge = "away"
        else:
            psychological_edge = "neutral"

        # 핵심 인사이트 생성
        insights = self._generate_insights(stats, dominance, trend, venue_factor)

        return H2HAnalysis(
            stats=stats,
            recent_matches=matches[:5],  # 최근 5경기만
            home_dominance=round(dominance, 2),
            trend=trend,
            venue_factor=round(venue_factor, 2),
            psychological_edge=psychological_edge,
            key_insights=insights
        )

    def _is_team_win(self, match: H2HMatch, team_name: str) -> bool:
        """해당 팀이 이긴 경기인지 확인"""
        is_home = team_name.lower() in match.home_team.lower()
        if is_home:
            return match.home_score > match.away_score
        else:
            return match.away_score > match.home_score

    def _generate_insights(
        self,
        stats: H2HStats,
        dominance: float,
        trend: str,
        venue_factor: float
    ) -> List[str]:
        """핵심 인사이트 생성"""
        insights = []

        # 전적 우위
        if abs(dominance) > 0.3:
            winner = stats.home_team_name if dominance > 0 else stats.away_team_name
            insights.append(f"📊 {winner}이(가) 상대전적에서 우세합니다 ({stats.home_team_wins}승 {stats.draws}무 {stats.away_team_wins}패)")

        # 골 통계
        if stats.avg_goals_per_match > 2.5:
            insights.append(f"⚽ 평균 {stats.avg_goals_per_match}골의 다득점 경기 예상")
        elif stats.avg_goals_per_match < 2.0:
            insights.append(f"🛡️ 평균 {stats.avg_goals_per_match}골의 저득점 경기 예상")

        # 양팀 득점
        if stats.both_teams_scored_pct >= 70:
            insights.append(f"🎯 양팀 득점 확률 {stats.both_teams_scored_pct}% (BTTS Yes 유력)")

        # 오버/언더
        if stats.over_2_5_pct >= 60:
            insights.append(f"📈 오버 2.5 적중률 {stats.over_2_5_pct}%")
        elif stats.over_2_5_pct <= 40:
            insights.append(f"📉 언더 2.5 적중률 {100 - stats.over_2_5_pct}%")

        # 트렌드
        if trend == "home_improving":
            insights.append(f"📈 {stats.home_team_name}이(가) 최근 상대전적에서 상승세")
        elif trend == "away_improving":
            insights.append(f"📈 {stats.away_team_name}이(가) 최근 상대전적에서 상승세")

        # 홈 이점
        if venue_factor > 0.6:
            insights.append(f"🏟️ {stats.home_team_name} 홈에서 강한 상대전적 (승률 {int(venue_factor*100)}%)")

        return insights[:4]  # 최대 4개

    async def get_full_h2h_analysis(
        self,
        home_team_id: int,
        away_team_id: int,
        home_team_name: str,
        away_team_name: str,
        limit: int = 10
    ) -> Dict[str, Any]:
        """전체 상대전적 분석 결과 (API 응답용)"""
        matches = await self.get_h2h(home_team_id, away_team_id, limit)
        analysis = self.analyze_h2h(matches, home_team_name, away_team_name)

        return {
            "home_team": home_team_name,
            "away_team": away_team_name,
            "total_matches": analysis.stats.total_matches,
            "home_wins": analysis.stats.home_team_wins,
            "away_wins": analysis.stats.away_team_wins,
            "draws": analysis.stats.draws,
            "home_goals": analysis.stats.home_team_goals,
            "away_goals": analysis.stats.away_team_goals,
            "avg_goals": analysis.stats.avg_goals_per_match,
            "both_scored_pct": analysis.stats.both_teams_scored_pct,
            "over_2_5_pct": analysis.stats.over_2_5_pct,
            "dominance": analysis.home_dominance,
            "trend": analysis.trend,
            "venue_factor": analysis.venue_factor,
            "psychological_edge": analysis.psychological_edge,
            "insights": analysis.key_insights,
            "recent_matches": [
                {
                    "date": m.date,
                    "competition": m.competition,
                    "home_team": m.home_team,
                    "away_team": m.away_team,
                    "score": f"{m.home_score}-{m.away_score}"
                }
                for m in analysis.recent_matches
            ]
        }


# 싱글톤 인스턴스
_collector: Optional[H2HCollector] = None


def get_h2h_collector(api_key: Optional[str] = None) -> H2HCollector:
    """싱글톤 수집기 반환"""
    global _collector
    if _collector is None:
        _collector = H2HCollector(api_key)
    return _collector


# 테스트
if __name__ == "__main__":
    async def test():
        collector = H2HCollector()

        # Liverpool vs Man United
        matches = await collector.get_h2h(40, 33, limit=10)
        print("\n[상대전적 - Liverpool vs Manchester United]")
        for m in matches[:5]:
            print(f"  {m.date}: {m.home_team} {m.home_score}-{m.away_score} {m.away_team}")

        analysis = collector.analyze_h2h(matches, "Liverpool", "Manchester United")
        print(f"\n[분석 결과]")
        print(f"  전적: {analysis.stats.home_team_wins}승 {analysis.stats.draws}무 {analysis.stats.away_team_wins}패")
        print(f"  우세도: {analysis.home_dominance} ({'Liverpool' if analysis.home_dominance > 0 else 'Man Utd'} 우세)")
        print(f"  트렌드: {analysis.trend}")
        print(f"  심리전 우위: {analysis.psychological_edge}")

        print(f"\n[인사이트]")
        for insight in analysis.key_insights:
            print(f"  {insight}")

    asyncio.run(test())
