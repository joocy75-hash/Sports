"""
D-04: 선수 부상/출장정지 정보 수집기
팀별 부상자, 출장정지 선수 정보를 수집하고 경기 영향도를 분석합니다.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
import httpx


class InjuryStatus(Enum):
    OUT = "out"  # 결장 확정
    DOUBTFUL = "doubtful"  # 출전 의심
    QUESTIONABLE = "questionable"  # 출전 불투명
    PROBABLE = "probable"  # 출전 유력
    SUSPENDED = "suspended"  # 출장정지


class PlayerPosition(Enum):
    GOALKEEPER = "GK"
    DEFENDER = "DF"
    MIDFIELDER = "MF"
    FORWARD = "FW"
    UNKNOWN = "UN"


@dataclass
class InjuredPlayer:
    """부상/출장정지 선수 정보"""
    player_id: int
    player_name: str
    team_id: int
    team_name: str
    position: PlayerPosition
    status: InjuryStatus
    reason: str  # "햄스트링 부상", "출장정지 1경기" 등
    expected_return: Optional[str] = None  # 예상 복귀일
    importance: float = 0.5  # 0-1, 팀 내 중요도
    games_missed: int = 0
    last_updated: str = ""


@dataclass
class TeamInjuryReport:
    """팀 부상 리포트"""
    team_id: int
    team_name: str
    injured_players: List[InjuredPlayer]
    total_out: int
    total_doubtful: int
    total_suspended: int
    impact_score: float  # 0-100, 부상이 팀에 미치는 영향
    key_absences: List[str]  # 주요 결장자 이름
    position_impact: Dict[str, int]  # 포지션별 결장 수


@dataclass
class MatchInjuryAnalysis:
    """경기 부상 영향 분석"""
    home_report: TeamInjuryReport
    away_report: TeamInjuryReport
    advantage: str  # "home", "away", "neutral"
    advantage_score: float  # -100 ~ 100 (양수면 홈 유리)
    key_factors: List[str]
    recommendation: str


class InjuryTracker:
    """선수 부상/출장정지 추적기"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.base_url = "https://v3.football.api-sports.io"
        self.cache: Dict[str, Any] = {}
        self.cache_ttl = 3600  # 1시간

        # 포지션별 중요도 가중치
        self.position_weights = {
            PlayerPosition.GOALKEEPER: 1.0,
            PlayerPosition.DEFENDER: 0.7,
            PlayerPosition.MIDFIELDER: 0.8,
            PlayerPosition.FORWARD: 0.9,
            PlayerPosition.UNKNOWN: 0.5,
        }

    async def get_team_injuries(
        self,
        team_id: int,
        team_name: str = ""
    ) -> List[InjuredPlayer]:
        """팀 부상자 목록 조회"""
        cache_key = f"injuries_{team_id}"
        if cache_key in self.cache:
            cached = self.cache[cache_key]
            if datetime.now().timestamp() - cached["time"] < self.cache_ttl:
                return cached["data"]

        if not self.api_key:
            return self._generate_mock_injuries(team_id, team_name)

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/injuries",
                    params={"team": team_id},
                    headers={"x-apisports-key": self.api_key},
                    timeout=30.0
                )

                if response.status_code == 200:
                    data = response.json()
                    injuries = self._parse_injuries(data.get("response", []), team_id, team_name)
                    self.cache[cache_key] = {
                        "data": injuries,
                        "time": datetime.now().timestamp()
                    }
                    return injuries
        except Exception as e:
            print(f"[InjuryTracker] API 오류: {e}")

        return self._generate_mock_injuries(team_id, team_name)

    def _parse_injuries(
        self,
        data: List[Dict],
        team_id: int,
        team_name: str
    ) -> List[InjuredPlayer]:
        """API 응답 파싱"""
        injuries = []
        for item in data:
            player = item.get("player", {})
            team = item.get("team", {})

            # 포지션 파싱
            pos_str = player.get("position", "").upper()
            if "GOAL" in pos_str:
                position = PlayerPosition.GOALKEEPER
            elif "DEF" in pos_str:
                position = PlayerPosition.DEFENDER
            elif "MID" in pos_str:
                position = PlayerPosition.MIDFIELDER
            elif "FOR" in pos_str or "ATT" in pos_str:
                position = PlayerPosition.FORWARD
            else:
                position = PlayerPosition.UNKNOWN

            # 상태 파싱
            reason = item.get("reason", "")
            if "suspen" in reason.lower():
                status = InjuryStatus.SUSPENDED
            elif "doubtful" in reason.lower():
                status = InjuryStatus.DOUBTFUL
            else:
                status = InjuryStatus.OUT

            injuries.append(InjuredPlayer(
                player_id=player.get("id", 0),
                player_name=player.get("name", "Unknown"),
                team_id=team.get("id", team_id),
                team_name=team.get("name", team_name),
                position=position,
                status=status,
                reason=reason,
                expected_return=None,
                importance=self._estimate_importance(position, player.get("name", "")),
                last_updated=datetime.now().isoformat()
            ))

        return injuries

    def _generate_mock_injuries(
        self,
        team_id: int,
        team_name: str
    ) -> List[InjuredPlayer]:
        """목업 데이터 생성"""
        import random
        random.seed(team_id)

        # 팀별 유명 선수 목업
        mock_players = {
            40: [  # Liverpool
                ("Mohamed Salah", PlayerPosition.FORWARD, 0.95),
                ("Virgil van Dijk", PlayerPosition.DEFENDER, 0.90),
                ("Trent Alexander-Arnold", PlayerPosition.DEFENDER, 0.85),
            ],
            33: [  # Man United
                ("Marcus Rashford", PlayerPosition.FORWARD, 0.85),
                ("Bruno Fernandes", PlayerPosition.MIDFIELDER, 0.90),
                ("Casemiro", PlayerPosition.MIDFIELDER, 0.80),
            ],
            50: [  # Man City
                ("Kevin De Bruyne", PlayerPosition.MIDFIELDER, 0.95),
                ("Erling Haaland", PlayerPosition.FORWARD, 0.95),
                ("John Stones", PlayerPosition.DEFENDER, 0.75),
            ],
        }

        players = mock_players.get(team_id, [
            ("Player A", PlayerPosition.FORWARD, 0.7),
            ("Player B", PlayerPosition.MIDFIELDER, 0.6),
            ("Player C", PlayerPosition.DEFENDER, 0.5),
        ])

        injuries = []
        reasons = [
            "햄스트링 부상", "무릎 부상", "발목 염좌",
            "근육 부상", "출장정지 1경기", "허벅지 부상"
        ]
        statuses = [InjuryStatus.OUT, InjuryStatus.DOUBTFUL, InjuryStatus.SUSPENDED]

        # 0-2명 부상자 생성
        num_injured = random.randint(0, min(2, len(players)))
        selected = random.sample(players, num_injured)

        for i, (name, position, importance) in enumerate(selected):
            injuries.append(InjuredPlayer(
                player_id=team_id * 100 + i,
                player_name=name,
                team_id=team_id,
                team_name=team_name or f"Team_{team_id}",
                position=position,
                status=random.choice(statuses),
                reason=random.choice(reasons),
                expected_return=(datetime.now() + timedelta(days=random.randint(7, 30))).strftime("%Y-%m-%d"),
                importance=importance,
                games_missed=random.randint(1, 5),
                last_updated=datetime.now().isoformat()
            ))

        return injuries

    def _estimate_importance(self, position: PlayerPosition, player_name: str) -> float:
        """선수 중요도 추정"""
        base = self.position_weights.get(position, 0.5)

        # 유명 선수 보너스 (실제로는 DB나 API에서 조회)
        star_players = [
            "Salah", "Haaland", "De Bruyne", "Mbappe", "Vinicius",
            "Son", "Kane", "Saka", "Bellingham", "Messi"
        ]
        for star in star_players:
            if star.lower() in player_name.lower():
                base = min(1.0, base + 0.2)
                break

        return round(base, 2)

    def analyze_team_injuries(
        self,
        injuries: List[InjuredPlayer],
        team_name: str = ""
    ) -> TeamInjuryReport:
        """팀 부상 리포트 생성"""
        if not injuries:
            return TeamInjuryReport(
                team_id=0,
                team_name=team_name,
                injured_players=[],
                total_out=0,
                total_doubtful=0,
                total_suspended=0,
                impact_score=0,
                key_absences=[],
                position_impact={}
            )

        team_id = injuries[0].team_id if injuries else 0

        total_out = sum(1 for p in injuries if p.status == InjuryStatus.OUT)
        total_doubtful = sum(1 for p in injuries if p.status == InjuryStatus.DOUBTFUL)
        total_suspended = sum(1 for p in injuries if p.status == InjuryStatus.SUSPENDED)

        # 포지션별 결장
        position_impact = {}
        for p in injuries:
            pos = p.position.value
            position_impact[pos] = position_impact.get(pos, 0) + 1

        # 영향도 점수 계산
        impact_score = sum(p.importance * 100 for p in injuries if p.status in [InjuryStatus.OUT, InjuryStatus.SUSPENDED])
        impact_score = min(100, impact_score)

        # 주요 결장자 (중요도 0.7 이상)
        key_absences = [
            p.player_name for p in injuries
            if p.importance >= 0.7 and p.status in [InjuryStatus.OUT, InjuryStatus.SUSPENDED]
        ]

        return TeamInjuryReport(
            team_id=team_id,
            team_name=team_name,
            injured_players=injuries,
            total_out=total_out,
            total_doubtful=total_doubtful,
            total_suspended=total_suspended,
            impact_score=round(impact_score, 1),
            key_absences=key_absences,
            position_impact=position_impact
        )

    async def analyze_match_injuries(
        self,
        home_team_id: int,
        away_team_id: int,
        home_team_name: str = "Home",
        away_team_name: str = "Away"
    ) -> MatchInjuryAnalysis:
        """경기 부상 영향 분석"""
        # 양 팀 부상 정보 조회
        home_injuries = await self.get_team_injuries(home_team_id, home_team_name)
        away_injuries = await self.get_team_injuries(away_team_id, away_team_name)

        home_report = self.analyze_team_injuries(home_injuries, home_team_name)
        away_report = self.analyze_team_injuries(away_injuries, away_team_name)

        # 유리/불리 계산
        advantage_score = away_report.impact_score - home_report.impact_score

        if advantage_score > 20:
            advantage = "home"
        elif advantage_score < -20:
            advantage = "away"
        else:
            advantage = "neutral"

        # 주요 팩터 생성
        key_factors = []

        if home_report.key_absences:
            key_factors.append(f"🏠 {home_team_name} 주요 결장: {', '.join(home_report.key_absences)}")
        if away_report.key_absences:
            key_factors.append(f"✈️ {away_team_name} 주요 결장: {', '.join(away_report.key_absences)}")

        if home_report.total_suspended > 0:
            key_factors.append(f"🟥 {home_team_name} 출장정지 {home_report.total_suspended}명")
        if away_report.total_suspended > 0:
            key_factors.append(f"🟥 {away_team_name} 출장정지 {away_report.total_suspended}명")

        # 포지션 영향
        for pos, count in home_report.position_impact.items():
            if count >= 2:
                key_factors.append(f"⚠️ {home_team_name} {pos} 포지션 {count}명 부재")

        for pos, count in away_report.position_impact.items():
            if count >= 2:
                key_factors.append(f"⚠️ {away_team_name} {pos} 포지션 {count}명 부재")

        # 추천
        if advantage == "home":
            recommendation = f"{home_team_name} 유리 - 상대팀 부상 영향 큼"
        elif advantage == "away":
            recommendation = f"{away_team_name} 유리 - 상대팀 부상 영향 큼"
        else:
            recommendation = "부상 영향 균형 - 다른 요소 고려 필요"

        return MatchInjuryAnalysis(
            home_report=home_report,
            away_report=away_report,
            advantage=advantage,
            advantage_score=round(advantage_score, 1),
            key_factors=key_factors,
            recommendation=recommendation
        )

    def to_dict(self, analysis: MatchInjuryAnalysis) -> Dict[str, Any]:
        """분석 결과를 딕셔너리로 변환"""
        return {
            "home_team": {
                "name": analysis.home_report.team_name,
                "total_out": analysis.home_report.total_out,
                "total_doubtful": analysis.home_report.total_doubtful,
                "total_suspended": analysis.home_report.total_suspended,
                "impact_score": analysis.home_report.impact_score,
                "key_absences": analysis.home_report.key_absences,
                "position_impact": analysis.home_report.position_impact,
                "injured_players": [
                    {
                        "name": p.player_name,
                        "position": p.position.value,
                        "status": p.status.value,
                        "reason": p.reason,
                        "importance": p.importance,
                    }
                    for p in analysis.home_report.injured_players
                ]
            },
            "away_team": {
                "name": analysis.away_report.team_name,
                "total_out": analysis.away_report.total_out,
                "total_doubtful": analysis.away_report.total_doubtful,
                "total_suspended": analysis.away_report.total_suspended,
                "impact_score": analysis.away_report.impact_score,
                "key_absences": analysis.away_report.key_absences,
                "position_impact": analysis.away_report.position_impact,
                "injured_players": [
                    {
                        "name": p.player_name,
                        "position": p.position.value,
                        "status": p.status.value,
                        "reason": p.reason,
                        "importance": p.importance,
                    }
                    for p in analysis.away_report.injured_players
                ]
            },
            "advantage": analysis.advantage,
            "advantage_score": analysis.advantage_score,
            "key_factors": analysis.key_factors,
            "recommendation": analysis.recommendation,
        }


# 싱글톤 인스턴스
_tracker: Optional[InjuryTracker] = None


def get_injury_tracker(api_key: Optional[str] = None) -> InjuryTracker:
    """싱글톤 트래커 반환"""
    global _tracker
    if _tracker is None:
        _tracker = InjuryTracker(api_key)
    return _tracker


# 테스트
if __name__ == "__main__":
    async def test():
        tracker = InjuryTracker()

        print("\n[Liverpool 부상자 조회]")
        injuries = await tracker.get_team_injuries(40, "Liverpool")
        for inj in injuries:
            print(f"  {inj.player_name} ({inj.position.value}): {inj.status.value} - {inj.reason}")

        print("\n[경기 부상 영향 분석]")
        analysis = await tracker.analyze_match_injuries(40, 33, "Liverpool", "Manchester United")
        print(f"  홈팀 영향도: {analysis.home_report.impact_score}")
        print(f"  원정팀 영향도: {analysis.away_report.impact_score}")
        print(f"  유리한 팀: {analysis.advantage} (점수: {analysis.advantage_score})")
        print(f"  추천: {analysis.recommendation}")

        if analysis.key_factors:
            print("\n[주요 팩터]")
            for factor in analysis.key_factors:
                print(f"  {factor}")

    asyncio.run(test())
