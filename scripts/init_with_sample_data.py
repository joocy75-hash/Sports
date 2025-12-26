#!/usr/bin/env python3
"""
데이터베이스 초기화 및 샘플 데이터 생성 스크립트
"""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db.session import init_db, get_session
from src.db.models import League, Team, Match, OddsHistory, TeamStats, PredictionLog


async def create_sample_data():
    """샘플 데이터 생성"""
    print("📊 샘플 데이터 생성 중...")
    
    async with get_session() as session:
        # 1. 리그 생성
        print("   - 리그 생성 중...")
        premier_league = League(
            id=1,
            name="Premier League",
            country="England",
   ㄴ      
       sport="football"
        )
         
        la_liga = League(
            id=2,
            name="La Liga",
            country="Spain",
            sport="football"
        )
        
        session.add_all([premier_league, la_liga])
        await session.flush()  # ID를 얻기 위해 flush
        
        # 2. 팀 생성
        print("   - 팀 생성 중...")
        teams = [
            # Premier League 팀들
            Team(id=1, name="Manchester City", league_id=1, sport="football"),
            Team(id=2, name="Liverpool", league_id=1, sport="football"),
            Team(id=3, name="Arsenal", league_id=1, sport="football"),
            Team(id=4, name="Chelsea", league_id=1, sport="football"),
            
            # La Liga 팀들
            Team(id=5, name="Real Madrid", league_id=2, sport="football"),
            Team(id=6, name="Barcelona", league_id=2, sport="football"),
            Team(id=7, name="Atletico Madrid", league_id=2, sport="football"),
            Team(id=8, name="Sevilla", league_id=2, sport="football"),
        ]
        
        session.add_all(teams)
        await session.flush()
        
        # 3. 팀 통계 생성
        print("   - 팀 통계 생성 중...")
        team_stats = []
        for team in teams:
            stats = TeamStats(
                team_id=team.id,
                season=2024,
                xg=1.8 if team.id % 2 == 0 else 1.5,  # 짝수 ID 팀은 공격력 좋음
                xga=1.2 if team.id % 2 == 0 else 1.5,  # 짝수 ID 팀은 수비력 좋음
                momentum=1.1 if team.id % 2 == 0 else 0.9,  # 짝수 ID 팀은 모멘텀 좋음
                updated_at=datetime.utcnow()
            )
            team_stats.append(stats)
        
        session.add_all(team_stats)
        await session.flush()
        
        # 4. 경기 생성 (오늘과 내일)
        print("   - 경기 생성 중...")
        now = datetime.utcnow()
        matches = []
        
        # 오늘 경기
        match1 = Match(
            id=1001,
            league_id=1,
            season=2024,
            sport="football",
            start_time=now + timedelta(hours=2),  # 2시간 후
            status="scheduled",
            home_team_id=1,  # Man City
            away_team_id=2,  # Liverpool
            odds_home=1.80,
            odds_draw=3.50,
            odds_away=4.20,
            recommendation="VALUE",
            recommended_stake_pct=0.02
        )
        
        match2 = Match(
            id=1002,
            league_id=1,
            season=2024,
            sport="football",
            start_time=now + timedelta(hours=4),  # 4시간 후
            status="scheduled",
            home_team_id=3,  # Arsenal
            away_team_id=4,  # Chelsea
            odds_home=2.10,
            odds_draw=3.20,
            odds_away=3.40,
            recommendation="STRONG_VALUE",
            recommended_stake_pct=0.03
        )
        
        # 내일 경기
        match3 = Match(
            id=1003,
            league_id=2,
            season=2024,
            sport="football",
            start_time=now + timedelta(days=1, hours=3),  # 내일 3시간 후
            status="scheduled",
            home_team_id=5,  # Real Madrid
            away_team_id=6,  # Barcelona
            odds_home=2.30,
            odds_draw=3.40,
            odds_away=2.90
        )
        
        matches.extend([match1, match2, match3])
        session.add_all(matches)
        await session.flush()
        
        # 5. 배당 히스토리 생성
        print("   - 배당 히스토리 생성 중...")
        odds_history = []
        for match in matches:
            for i in range(3):  # 3개의 히스토리 기록
                odds = OddsHistory(
                    match_id=match.id,
                    bookmaker="Pinnacle",
                    captured_at=now - timedelta(hours=i*2),
                    odds_home=match.odds_home + (i * 0.05),  # 시간에 따라 변화
                    odds_draw=match.odds_draw - (i * 0.02),
                    odds_away=match.odds_away - (i * 0.03),
                    market="1x2",
                    payload={"source": "sample_data"}
                )
                odds_history.append(odds)
        
        session.add_all(odds_history)
        await session.flush()
        
        # 6. 예측 로그 생성
        print("   - 예측 로그 생성 중...")
        prediction_logs = []
        for match in matches:
            log = PredictionLog(
                match_id=match.id,
                created_at=now,
                prob_home=0.45 if match.id == 1001 else 0.40,
                prob_draw=0.25 if match.id == 1001 else 0.30,
                prob_away=0.30 if match.id == 1001 else 0.30,
                expected_score_home=1.8,
                expected_score_away=1.2,
                value_home=0.05 if match.id == 1001 else 0.03,
                value_draw=0.02,
                value_away=0.01,
                meta={"model": "sample", "version": "1.0"}
            )
            prediction_logs.append(log)
        
        session.add_all(prediction_logs)
        
        await session.commit()
        
        print(f"✅ 샘플 데이터 생성 완료:")
        print(f"   - 리그: {len([premier_league, la_liga])}개")
        print(f"   - 팀: {len(teams)}개")
        print(f"   - 팀 통계: {len(team_stats)}개")
        print(f"   - 경기: {len(matches)}개")
        print(f"   - 배당 히스토리: {len(odds_history)}개")
        print(f"   - 예측 로그: {len(prediction_logs)}개")


async def main():
    """메인 함수"""
    print("🚀 데이터베이스 초기화 및 샘플 데이터 생성")
    
    try:
        # 1. 데이터베이스 초기화
        print("📦 데이터베이스 초기화 중...")
        await init_db()
        print("✅ 데이터베이스 초기화 완료")
        
        # 2. 샘플 데이터 생성
        await create_sample_data()
        
        print("\n🎉 모든 작업 완료!")
        print("\n다음 명령어로 테스트해보세요:")
        print("1. python main_enhanced.py --test")
        print("2. python main_enhanced.py --mode full")
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())