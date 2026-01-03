#!/usr/bin/env python3
"""RoundManager 직접 테스트"""
import asyncio
import json
from src.services.round_manager import RoundManager


async def test_round_manager():
    """RoundManager 테스트"""
    manager = RoundManager()

    # 축구 승무패
    print("=" * 60)
    print("축구 승무패 테스트")
    print("=" * 60)
    round_info, games = await manager.get_soccer_wdl_round()

    print(f"\n회차 정보 타입: {type(round_info)}")
    print(f"회차 정보: {round_info}")

    print(f"\n경기 데이터 타입: {type(games)}")
    print(f"경기 수: {len(games)}")

    if games:
        print(f"\n첫 번째 경기 타입: {type(games[0])}")
        print(f"첫 번째 경기:")
        print(json.dumps(games[0], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(test_round_manager())
