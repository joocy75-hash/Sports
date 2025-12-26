#!/usr/bin/env python3
"""
데이터 검증 테스트 스크립트

사용법:
    python3 test_data_validation.py [--soccer] [--basketball] [--save-report]
"""

import asyncio
import argparse
import logging
import sys
from pathlib import Path

# 프로젝트 루트를 PYTHONPATH에 추가
sys.path.insert(0, str(Path(__file__).parent))

from src.services.data_validator import DataValidator


async def main():
    parser = argparse.ArgumentParser(description="데이터 검증 테스트")
    parser.add_argument("--soccer", action="store_true", help="축구 승무패만 검증")
    parser.add_argument("--basketball", action="store_true", help="농구 승5패만 검증")
    parser.add_argument("--save-report", action="store_true", help="보고서를 파일로 저장")
    parser.add_argument("--verbose", action="store_true", help="상세 로그 출력")

    args = parser.parse_args()

    # 로깅 설정
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    validator = DataValidator()

    # 검증할 게임 타입 결정
    game_types = []
    if args.soccer:
        game_types.append("soccer_wdl")
    if args.basketball:
        game_types.append("basketball_w5l")
    if not game_types:
        # 둘 다 선택 안하면 모두 검증
        game_types = ["soccer_wdl", "basketball_w5l"]

    # 검증 실행
    for game_type in game_types:
        game_type_name = "축구 승무패" if game_type == "soccer_wdl" else "농구 승5패"

        print("=" * 80)
        print(f"{'⚽' if game_type == 'soccer_wdl' else '🏀'} {game_type_name} 데이터 검증")
        print("=" * 80)
        print()

        try:
            # 보고서 생성
            report = await validator.generate_report(game_type, use_cache=False)
            print(report)
            print()

            # 요약 정보
            summary = await validator.get_validation_summary(game_type)
            print("=" * 80)
            print("검증 요약 (JSON)")
            print("=" * 80)
            import json
            print(json.dumps(summary, indent=2, ensure_ascii=False))
            print()

            # 보고서 저장
            if args.save_report:
                output_dir = Path(__file__).parent / ".state" / "validation_reports"
                output_dir.mkdir(exist_ok=True, parents=True)

                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                report_file = output_dir / f"{game_type}_{timestamp}.md"

                with open(report_file, "w", encoding="utf-8") as f:
                    f.write(report)

                print(f"보고서 저장됨: {report_file}")
                print()

        except Exception as e:
            print(f"오류 발생: {e}")
            import traceback
            traceback.print_exc()

    print("=" * 80)
    print("검증 완료")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
