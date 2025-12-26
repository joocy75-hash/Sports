"""
KSPO API로 실제 베트맨 데이터 수집 스크립트
"""
import asyncio
import sys
import os

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.services.kspo_api_client import KSPOApiClient
from src.core.logging import setup_logging

async def main():
    setup_logging()
    print("🚀 KSPO API 데이터 수집 시작...")

    client = KSPOApiClient()

    # 1. 프로토 승부식 경기 가져오기
    print("\n📊 프로토 승부식 경기 수집 중...")
    proto_matches = await client.get_proto_matches()
    print(f"   ✅ {len(proto_matches)}개의 프로토 경기 발견")

    if proto_matches:
        print("\n   첫 5개 경기 미리보기:")
        for i, match in enumerate(proto_matches[:5], 1):
            print(f"   {i}. {match.get('obj_prod_nm', 'N/A')} - {match.get('hteam_han_nm', 'N/A')} vs {match.get('ateam_han_nm', 'N/A')}")

    # 2. 승무패(축구토토) 경기 가져오기
    print("\n⚽ 승무패(축구토토) 경기 수집 중...")
    toto_matches = await client.get_toto_matches()
    print(f"   ✅ {len(toto_matches)}개의 승무패 경기 발견")

    if toto_matches:
        print("\n   첫 5개 경기 미리보기:")
        for i, match in enumerate(toto_matches[:5], 1):
            print(f"   {i}. {match.get('obj_prod_nm', 'N/A')} - {match.get('hteam_han_nm', 'N/A')} vs {match.get('ateam_han_nm', 'N/A')}")

    # 3. DB에 저장
    all_matches = proto_matches + toto_matches

    if all_matches:
        print(f"\n💾 총 {len(all_matches)}개 경기를 DB에 저장 중...")
        saved_count = await client.save_matches_to_db(all_matches)
        print(f"   ✅ {saved_count}개 경기 저장 완료!")
    else:
        print("\n⚠️  수집된 경기가 없습니다.")

    print("\n✅ 데이터 수집 완료!")

if __name__ == "__main__":
    asyncio.run(main())
