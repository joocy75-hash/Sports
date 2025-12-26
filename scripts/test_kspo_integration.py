"""
KSPO API 연동 및 DB 저장 테스트 스크립트

테스트 항목:
1. KSPO TODZ API 호출 (체육진흥투표권 발매대상 경기정보)
2. KSPO SOSFO API 호출 (소셜포커스 경기관리)
3. 경기 데이터 DB 저장
4. DB에서 저장된 데이터 조회
"""

import asyncio
import os
import sys

# 프로젝트 루트를 PYTHONPATH에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.services.kspo_api_client import KSPOApiClient, KSPOSosfoApiClient
from src.db.session import get_session
from src.db.models import Match, Team, League
from sqlalchemy import select


async def test_kspo_todz_api():
    """KSPO TODZ API 테스트"""
    print("\n" + "=" * 60)
    print("1️⃣  KSPO TODZ API 테스트 (체육진흥투표권 발매대상 경기정보)")
    print("=" * 60)

    client = KSPOApiClient()

    # 프로토 경기 조회
    print("\n📋 프로토 경기 조회 중...")
    proto_matches = await client.get_proto_matches()

    print(f"✅ {len(proto_matches)}개의 프로토 경기 발견")

    if proto_matches:
        print("\n📊 첫 번째 경기 샘플:")
        first_match = proto_matches[0]
        print(f"  - row_num: {first_match.get('row_num')}")
        print(f"  - match_ymd: {first_match.get('match_ymd')}")
        print(f"  - 홈팀: {first_match.get('hteam_han_nm')}")
        print(f"  - 원정팀: {first_match.get('ateam_han_nm')}")
        print(f"  - 경기 결과: {first_match.get('match_end_val')}")
        print(f"  - 상품명: {first_match.get('obj_prod_nm')}")

    # DB 저장
    if proto_matches:
        print("\n💾 DB 저장 중...")
        saved_count = await client.save_matches_to_db(
            proto_matches[:5]
        )  # 처음 5개만 저장
        print(f"✅ {saved_count}개 경기 DB 저장 완료")

    return len(proto_matches)


async def test_kspo_sosfo_api():
    """KSPO SOSFO API 테스트"""
    print("\n" + "=" * 60)
    print("2️⃣  KSPO SOSFO API 테스트 (소셜포커스 경기관리)")
    print("=" * 60)

    client = KSPOSosfoApiClient()

    # 경기 정보 조회
    print("\n📋 SOSFO 경기 정보 조회 중...")
    matches = await client.get_match_info()

    print(f"✅ {len(matches)}개의 SOSFO 경기 발견")

    if matches:
        print("\n📊 첫 번째 경기 샘플:")
        first_match = matches[0]
        print(f"  - 응답 데이터: {first_match}")

    return len(matches)


async def test_db_query():
    """DB 저장된 데이터 조회 테스트"""
    print("\n" + "=" * 60)
    print("3️⃣  DB 저장 데이터 조회 테스트")
    print("=" * 60)

    async with get_session() as session:
        # 리그 조회
        league_result = await session.execute(select(League).where(League.id == 9999))
        league = league_result.scalar_one_or_none()

        if league:
            print(f"\n✅ KSPO 리그 발견: {league.name}")
        else:
            print("\n⚠️  KSPO 리그가 생성되지 않았습니다")
            return

        # 팀 조회
        team_result = await session.execute(select(Team).where(Team.league_id == 9999))
        teams = team_result.scalars().all()
        print(f"✅ {len(teams)}개 팀 발견")

        if teams:
            print("\n📊 팀 목록 (최대 5개):")
            for team in teams[:5]:
                print(f"  - {team.name} (ID: {team.id})")

        # 경기 조회
        match_result = await session.execute(
            select(Match).where(Match.league_id == 9999)
        )
        matches = match_result.scalars().all()
        print(f"\n✅ {len(matches)}개 경기 발견")

        if matches:
            print("\n📊 경기 목록 (최대 5개):")
            for match in matches[:5]:
                # 팀 정보 로드
                home_team_result = await session.execute(
                    select(Team).where(Team.id == match.home_team_id)
                )
                away_team_result = await session.execute(
                    select(Team).where(Team.id == match.away_team_id)
                )
                home_team = home_team_result.scalar_one_or_none()
                away_team = away_team_result.scalar_one_or_none()

                home_name = home_team.name if home_team else "Unknown"
                away_name = away_team.name if away_team else "Unknown"

                print(
                    f"  - {match.start_time.strftime('%Y-%m-%d')}: {home_name} vs {away_name} (상태: {match.status})"
                )


async def main():
    """메인 테스트 실행"""
    print("\n" + "🚀" * 30)
    print("KSPO API 연동 및 DB 저장 통합 테스트 시작")
    print("🚀" * 30)

    try:
        # 1. TODZ API 테스트
        todz_count = await test_kspo_todz_api()

        # 2. SOSFO API 테스트
        sosfo_count = await test_kspo_sosfo_api()

        # 3. DB 조회 테스트
        await test_db_query()

        # 결과 요약
        print("\n" + "=" * 60)
        print("✨ 테스트 결과 요약")
        print("=" * 60)
        print(f"✅ TODZ API: {todz_count}개 경기 조회 성공")
        print(f"✅ SOSFO API: {sosfo_count}개 경기 조회 성공")
        print("✅ DB 저장 및 조회: 성공")
        print("\n💡 다음 단계:")
        print("  1. 백엔드 서버가 실행 중인지 확인: http://localhost:8000/docs")
        print("  2. 전체 시스템 연동 테스트 진행")

    except Exception as e:
        print(f"\n❌ 테스트 중 에러 발생: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
