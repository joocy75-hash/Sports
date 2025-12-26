"""
선발 라인업 모니터링 및 실시간 분석 시스템
경기 시작 1시간 전 라인업 발표 → 30분 전 분석 완료
"""

import asyncio
import aiohttp
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging
from dataclasses import dataclass
from enum import Enum


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MatchStatus(Enum):
    SCHEDULED = "scheduled"
    LINEUP_ANNOUNCED = "lineup_announced"
    ANALYZED = "analyzed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


@dataclass
class LineupData:
    """라인업 데이터"""
    match_id: int
    home_team: str
    away_team: str
    home_lineup: List[Dict]  # 선발 명단
    away_lineup: List[Dict]  # 선발 명단
    formation_home: str
    formation_away: str
    substitutes_home: List[str]
    substitutes_away: List[str]
    announced_at: datetime
    source: str  # 데이터 출처


@dataclass
class ScheduledMatch:
    """예정된 경기"""
    match_id: int
    home_team: str
    away_team: str
    league: str
    match_time: datetime
    status: MatchStatus
    lineup_data: Optional[LineupData] = None
    analysis_result: Optional[Dict] = None
    last_checked: Optional[datetime] = None


class LineupMonitor:
    """라인업 모니터링 시스템"""
    
    def __init__(self, check_interval: int = 300):  # 5분 간격
        self.check_interval = check_interval
        self.matches: Dict[int, ScheduledMatch] = {}
        self.lineup_sources = [
            "api_football",
            "flashscore",
            "sofascore",
            "premierleague"
        ]
        
    async def add_match(self, match: ScheduledMatch):
        """모니터링할 경기 추가"""
        self.matches[match.match_id] = match
        logger.info(f"경기 추가: {match.home_team} vs {match.away_team} ({match.match_time})")
    
    async def check_lineup_announcement(self, match: ScheduledMatch) -> Optional[LineupData]:
        """라인업 발표 확인"""
        
        # 경기 시작 1시간 10분 전부터 라인업 확인 시작
        time_until_match = match.match_time - datetime.now()
        if time_until_match > timedelta(hours=1, minutes=10):
            return None
        
        logger.info(f"라인업 확인 중: {match.home_team} vs {match.away_team}")
        
        # 실제 구현에서는 API 호출로 라인업 데이터 가져오기
        # 여기서는 모의 데이터 사용
        if time_until_match <= timedelta(hours=1, minutes=5):
            # 라인업 발표 시뮬레이션
            lineup_data = self._generate_mock_lineup(match)
            return lineup_data
        
        return None
    
    def _generate_mock_lineup(self, match: ScheduledMatch) -> LineupData:
        """테스트용 모의 라인업 데이터 생성"""
        return LineupData(
            match_id=match.match_id,
            home_team=match.home_team,
            away_team=match.away_team,
            home_lineup=[
                {"name": "Player 1", "position": "GK", "number": 1},
                {"name": "Player 2", "position": "DF", "number": 2},
                {"name": "Player 3", "position": "DF", "number": 3},
                {"name": "Player 4", "position": "DF", "number": 4},
                {"name": "Player 5", "position": "DF", "number": 5},
                {"name": "Player 6", "position": "MF", "number": 6},
                {"name": "Player 7", "position": "MF", "number": 7},
                {"name": "Player 8", "position": "MF", "number": 8},
                {"name": "Player 9", "position": "FW", "number": 9},
                {"name": "Player 10", "position": "FW", "number": 10},
                {"name": "Player 11", "position": "FW", "number": 11},
            ],
            away_lineup=[
                {"name": "Player 12", "position": "GK", "number": 1},
                {"name": "Player 13", "position": "DF", "number": 2},
                {"name": "Player 14", "position": "DF", "number": 3},
                {"name": "Player 15", "position": "DF", "number": 4},
                {"name": "Player 16", "position": "DF", "number": 5},
                {"name": "Player 17", "position": "MF", "number": 6},
                {"name": "Player 18", "position": "MF", "number": 7},
                {"name": "Player 19", "position": "MF", "number": 8},
                {"name": "Player 20", "position": "FW", "number": 9},
                {"name": "Player 21", "position": "FW", "number": 10},
                {"name": "Player 22", "position": "FW", "number": 11},
            ],
            formation_home="4-3-3",
            formation_away="4-4-2",
            substitutes_home=["Sub 1", "Sub 2", "Sub 3", "Sub 4", "Sub 5", "Sub 6", "Sub 7"],
            substitutes_away=["Sub 8", "Sub 9", "Sub 10", "Sub 11", "Sub 12", "Sub 13", "Sub 14"],
            announced_at=datetime.now(),
            source="mock_data"
        )
    
    async def analyze_with_lineup(self, match: ScheduledMatch, lineup_data: LineupData) -> Dict:
        """라인업 데이터로 분석 실행"""
        from .core_analyzer import AIOddsGenerator, MatchAnalysis, TeamAnalysis, LineupAnalysis, EnvironmentalFactors
        
        # 팀 분석 데이터 생성 (실제로는 DB에서 가져와야 함)
        home_team = TeamAnalysis(
            team_id=1,
            team_name=match.home_team,
            attack_strength=0.75,
            defense_strength=0.70,
            recent_form=0.65,
            home_advantage=0.15,
            key_players=["Player 9", "Player 10"],
            injuries=[],
            momentum=0.8
        )
        
        away_team = TeamAnalysis(
            team_id=2,
            team_name=match.away_team,
            attack_strength=0.70,
            defense_strength=0.75,
            recent_form=0.60,
            home_advantage=0.10,
            key_players=["Player 20", "Player 21"],
            injuries=[],
            momentum=0.7
        )
        
        # 라인업 분석
        lineup_analysis = LineupAnalysis(
            formation=lineup_data.formation_home,
            starting_xi=lineup_data.home_lineup,
            key_players_present=True,
            tactical_style="attacking",
            lineup_strength=0.85
        )
        
        # 환경 요인
        env_factors = EnvironmentalFactors(
            venue="Home Stadium",
            weather="Clear",
            temperature=20.5,
            humidity=65.0,
            travel_distance=0.0,
            rest_days=4
        )
        
        # 경기 분석 객체 생성
        match_analysis = MatchAnalysis(
            match_id=match.match_id,
            home_team=home_team,
            away_team=away_team,
            lineup_analysis=lineup_analysis,
            environmental_factors=env_factors,
            head_to_head={"home_win": 0.4, "draw": 0.3, "away_win": 0.3},
            predicted_probabilities={},
            own_odds={},
            confidence_score=0.0,
            analyzed_at=datetime.now(),
            match_time=match.match_time
        )
        
        # AI 분석 실행
        analyzer = AIOddsGenerator()
        result = analyzer.analyze_match(match_analysis)
        
        return {
            "match_id": match.match_id,
            "home_team": match.home_team,
            "away_team": match.away_team,
            "predicted_probabilities": {
                k.value: v for k, v in result.predicted_probabilities.items()
            },
            "own_odds": {
                k.value: round(v, 2) for k, v in result.own_odds.items()
            },
            "confidence_score": result.confidence_score,
            "analysis_time": result.analyzed_at.isoformat(),
            "lineup_used": True,
            "recommendation": self._generate_recommendation(result)
        }
    
    def _generate_recommendation(self, analysis_result) -> Dict:
        """분석 결과 기반 추천 생성"""
        probs = analysis_result.predicted_probabilities
        best_outcome = max(probs.items(), key=lambda x: x[1])
        
        recommendation = {
            "predicted_outcome": best_outcome[0].value,
            "probability": best_outcome[1],
            "recommended_odds": analysis_result.own_odds[best_outcome[0]],
            "confidence": analysis_result.confidence_score,
            "suggested_stake": self._calculate_stake(best_outcome[1], analysis_result.confidence_score),
            "analysis_summary": self._generate_summary(analysis_result)
        }
        
        return recommendation
    
    def _calculate_stake(self, probability: float, confidence: float) -> float:
        """권장 베팅 금액 계산 (Kelly Criterion 변형)"""
        # 단순화된 계산
        edge = probability - (1 / 2.5)  # 가정: 시장 배당 2.50
        if edge <= 0:
            return 0.0
        
        kelly_fraction = edge / 2.5  # 단순화된 Kelly
        adjusted = kelly_fraction * confidence
        
        # 최대 5% 제한
        return min(0.05, max(0.01, adjusted))
    
    def _generate_summary(self, analysis_result) -> str:
        """분석 요약 생성"""
        probs = analysis_result.predicted_probabilities
        home_prob = probs.get('home_win', 0) * 100
        draw_prob = probs.get('draw', 0) * 100
        away_prob = probs.get('away_win', 0) * 100
        
        return f"홈승 {home_prob:.1f}% / 무 {draw_prob:.1f}% / 원정승 {away_prob:.1f}%"
    
    async def monitor_matches(self):
        """경기 모니터링 메인 루프"""
        logger.info("라인업 모니터링 시작")
        
        while True:
            current_time = datetime.now()
            
            for match_id, match in list(self.matches.items()):
                try:
                    # 경기 상태 업데이트
                    if match.match_time <= current_time:
                        match.status = MatchStatus.COMPLETED
                        continue
                    
                    # 라인업 확인
                    if match.status == MatchStatus.SCHEDULED:
                        lineup_data = await self.check_lineup_announcement(match)
                        if lineup_data:
                            match.lineup_data = lineup_data
                            match.status = MatchStatus.LINEUP_ANNOUNCED
                            match.last_checked = current_time
                            logger.info(f"라인업 발표: {match.home_team} vs {match.away_team}")
                    
                    # 라인업 분석 실행 (발표 후 30분 이내)
                    if (match.status == MatchStatus.LINEUP_ANNOUNCED and 
                        match.lineup_data and
                        current_time - match.lineup_data.announced_at >= timedelta(minutes=5)):  # 테스트용 5분
                        
                        analysis_result = await self.analyze_with_lineup(match, match.lineup_data)
                        match.analysis_result = analysis_result
                        match.status = MatchStatus.ANALYZED
                        match.last_checked = current_time
                        
                        logger.info(f"분석 완료: {match.home_team} vs {match.away_team}")
                        logger.info(f"추천: {analysis_result['recommendation']}")
                    
                    # 분석 결과 전송 (경기 시작 30분 전)
                    if (match.status == MatchStatus.ANALYZED and
                        match.match_time - current_time <= timedelta(minutes=30)):
                        
                        # 여기서 실제로는 Telegram, Email 등으로 결과 전송
                        self._deliver_analysis(match)
                        match.status = MatchStatus.IN_PROGRESS
                
                except Exception as e:
                    logger.error(f"경기 {match_id} 모니터링 중 오류: {e}")
            
            # 완료된 경기 제거
            self.matches = {
                k: v for k, v in self.matches.items() 
                if v.status != MatchStatus.COMPLETED
            }
            
            # 대기
            await asyncio.sleep(self.check_interval)
    
    def _deliver_analysis(self, match: ScheduledMatch):
        """분석 결과 전송"""
        if not match.analysis_result:
            return
        
        result = match.analysis_result
        logger.info("=" * 50)
        logger.info(f"📊 최종 분석 결과 전송")
        logger.info(f"경기: {match.home_team} vs {match.away_team}")
        logger.info(f"리그: {match.league}")
        logger.info(f"경기 시간: {match.match_time}")
        logger.info(f"분석 시간: {result['analysis_time']}")
        logger.info("")
        
        # 확률 출력
        probs = result['predicted_probabilities']
        logger.info("📈 예측 확률:")
        for outcome, prob in probs.items():
            logger.info(f"  {outcome}: {prob*100:.1f}%")
        
        # 배당 출력
        odds = result['own_odds']
        logger.info("💰 자체 배당:")
        for outcome, odd in odds.items():
            logger.info(f"  {outcome}: {odd}")
        
        # 추천 출력
        rec = result['recommendation']
        logger.info("🎯 추천:")
        logger.info(f"  예측 결과: {rec['predicted_outcome']}")
        logger.info(f"  확률: {rec['probability']*100:.1f}%")
        logger.info(f"  권장 배당: {rec['recommended_odds']}")
        logger.info(f"  신뢰도: {rec['confidence']*100:.1f}%")
        logger.info(f"  권장 베팅금: {rec['suggested_stake']*100:.1f}%")
        logger.info(f"  요약: {rec['analysis_summary']}")
        logger.info("=" * 50)


# 테스트 실행
async def test_monitor():
    """모니터링 시스템 테스트"""
    monitor = LineupMonitor(check_interval=60)  # 1분 간격
    
    # 테스트 경기 추가 (1시간 30분 후 시작)
    test_match = ScheduledMatch(
        match_id=1,
        home_team="맨체스터 시티",
        away_team="리버풀",
        league="프리미어리그",
        match_time=datetime.now() + timedelta(hours=1, minutes=30),
        status=MatchStatus.SCHEDULED
    )
    
    await monitor.add_match(test_match)
    
    # 5분간 모니터링 실행
    logger.info("테스트 모니터링 시작 (5분간 실행)")
    monitor_task = asyncio.create_task(monitor.monitor_matches())
    
    await asyncio.sleep(300)  # 5분 대기
    monitor_task.cancel()
    
    try:
        await monitor_task
    except asyncio.CancelledError:
        logger.info("테스트 모니터링 종료")


if __name__ == "__main__":
    asyncio.run(test_monitor())