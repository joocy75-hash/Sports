#!/usr/bin/env python3
"""
API 통합 테스트 스크립트 (T-01)
백엔드 API와 프론트엔드의 통합 테스트를 수행합니다.
"""

import asyncio
import sys
import json
from pathlib import Path
import aiohttp
import time

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

BASE_URL = "http://localhost:8000"


class APITester:
    """API 통합 테스트 클래스"""

    def __init__(self):
        self.session = None
        self.results = {"total": 0, "passed": 0, "failed": 0, "tests": []}

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    def log_test(self, name, success, message=None, response=None):
        """테스트 결과 기록"""
        self.results["total"] += 1
        if success:
            self.results["passed"] += 1
            status = "✅ PASS"
        else:
            self.results["failed"] += 1
            status = "❌ FAIL"

        test_result = {
            "name": name,
            "status": status,
            "message": message,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

        if response:
            test_result["response_status"] = response.status

        self.results["tests"].append(test_result)

        print(f"{status}: {name}")
        if message:
            print(f"   {message}")
        if response and response.status != 200:
            print(f"   Status: {response.status}")

    async def test_health_endpoint(self):
        """헬스체크 엔드포인트 테스트"""
        try:
            async with self.session.get(f"{BASE_URL}/health") as response:
                if response.status == 200:
                    data = await response.json()
                    self.log_test(
                        "Health Check",
                        True,
                        f"Status: {data.get('status', 'N/A')}, Services: {len(data.get('services', {}))}",
                    )
                else:
                    self.log_test(
                        "Health Check",
                        False,
                        f"Expected 200, got {response.status}",
                        response,
                    )
        except Exception as e:
            self.log_test("Health Check", False, f"Exception: {str(e)}")

    async def test_games_list_endpoint(self):
        """경기 목록 엔드포인트 테스트"""
        try:
            async with self.session.get(f"{BASE_URL}/api/v1/games/list") as response:
                if response.status == 200:
                    data = await response.json()
                    total_matches = data.get("total_matches", 0)
                    categories = data.get("categories", [])
                    self.log_test(
                        "Games List",
                        True,
                        f"Total matches: {total_matches}, Categories: {len(categories)}",
                    )
                else:
                    self.log_test(
                        "Games List",
                        False,
                        f"Expected 200, got {response.status}",
                        response,
                    )
        except Exception as e:
            self.log_test("Games List", False, f"Exception: {str(e)}")

    async def test_analysis_endpoint(self):
        """분석 엔드포인트 테스트"""
        try:
            # 먼저 경기 목록에서 첫 번째 경기 ID 가져오기
            async with self.session.get(f"{BASE_URL}/api/v1/games/list") as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("categories"):
                        matches = data["categories"][0].get("matches", [])
                        if matches:
                            match_id = matches[0]["id"]

                            # 분석 엔드포인트 테스트
                            async with self.session.get(
                                f"{BASE_URL}/api/v1/analysis/match/{match_id}"
                            ) as analysis_response:
                                if analysis_response.status == 200:
                                    analysis_data = await analysis_response.json()
                                    self.log_test(
                                        "Match Analysis",
                                        True,
                                        f"Match ID: {match_id}, Success: {analysis_data.get('success', False)}",
                                    )
                                else:
                                    self.log_test(
                                        "Match Analysis",
                                        False,
                                        f"Expected 200, got {analysis_response.status}",
                                        analysis_response,
                                    )
                        else:
                            self.log_test(
                                "Match Analysis", True, "No matches available (skipped)"
                            )
                    else:
                        self.log_test(
                            "Match Analysis", True, "No categories available (skipped)"
                        )
                else:
                    self.log_test(
                        "Match Analysis", False, "Could not fetch games list", response
                    )
        except Exception as e:
            self.log_test("Match Analysis", False, f"Exception: {str(e)}")

    async def test_ensemble_prediction(self):
        """앙상블 예측 엔드포인트 테스트"""
        try:
            payload = {
                "home_avg_goals": 1.5,
                "away_avg_goals": 1.3,
                "home_form": 0.6,
                "away_form": 0.4,
                "h2h_home_wins": 3,
                "h2h_away_wins": 2,
                "h2h_draws": 1,
            }

            async with self.session.post(
                f"{BASE_URL}/api/v1/predict/ensemble", json=payload
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    self.log_test(
                        "Ensemble Prediction",
                        True,
                        f"Prediction generated: {data.get('success', False)}",
                    )
                else:
                    self.log_test(
                        "Ensemble Prediction",
                        False,
                        f"Expected 200, got {response.status}",
                        response,
                    )
        except Exception as e:
            self.log_test("Ensemble Prediction", False, f"Exception: {str(e)}")

    async def test_h2h_endpoint(self):
        """상대전적 엔드포인트 테스트"""
        try:
            # 샘플 팀 ID로 테스트
            home_id = 1
            away_id = 2

            async with self.session.get(
                f"{BASE_URL}/api/v1/h2h/{home_id}/{away_id}",
                params={"home_team_name": "Liverpool", "away_team_name": "Chelsea"},
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    self.log_test(
                        "Head-to-Head",
                        True,
                        f"H2H data retrieved: {data.get('success', False)}",
                    )
                elif response.status == 404:
                    # 데이터가 없을 수 있음 (정상)
                    self.log_test(
                        "Head-to-Head",
                        True,
                        "No H2H data found (expected for sample IDs)",
                    )
                else:
                    self.log_test(
                        "Head-to-Head",
                        False,
                        f"Unexpected status: {response.status}",
                        response,
                    )
        except Exception as e:
            self.log_test("Head-to-Head", False, f"Exception: {str(e)}")

    async def test_toto_optimization(self):
        """토토 마킹 최적화 엔드포인트 테스트"""
        try:
            payload = {
                "matches": [
                    {"home_win_prob": 0.4, "draw_prob": 0.3, "away_win_prob": 0.3},
                    {"home_win_prob": 0.5, "draw_prob": 0.25, "away_win_prob": 0.25},
                    {"home_win_prob": 0.6, "draw_prob": 0.2, "away_win_prob": 0.2},
                ],
                "budget": 10000,
                "target_combinations": 5,
            }

            async with self.session.post(
                f"{BASE_URL}/api/v1/toto/optimize-marking", json=payload
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    self.log_test(
                        "Toto Optimization",
                        True,
                        f"Optimization completed: {data.get('success', False)}",
                    )
                else:
                    self.log_test(
                        "Toto Optimization",
                        False,
                        f"Expected 200, got {response.status}",
                        response,
                    )
        except Exception as e:
            self.log_test("Toto Optimization", False, f"Exception: {str(e)}")

    async def test_backtest_summary(self):
        """백테스트 요약 엔드포인트 테스트"""
        try:
            async with self.session.get(
                f"{BASE_URL}/api/v1/backtest/summary"
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    self.log_test(
                        "Backtest Summary",
                        True,
                        f"Backtest data retrieved: {data.get('success', False)}",
                    )
                else:
                    self.log_test(
                        "Backtest Summary",
                        False,
                        f"Expected 200, got {response.status}",
                        response,
                    )
        except Exception as e:
            self.log_test("Backtest Summary", False, f"Exception: {str(e)}")

    async def test_cache_stats(self):
        """캐시 통계 엔드포인트 테스트"""
        try:
            async with self.session.get(f"{BASE_URL}/api/v1/cache/stats") as response:
                if response.status == 200:
                    data = await response.json()
                    self.log_test(
                        "Cache Stats",
                        True,
                        f"Cache stats retrieved: {data.get('success', False)}",
                    )
                else:
                    self.log_test(
                        "Cache Stats",
                        False,
                        f"Expected 200, got {response.status}",
                        response,
                    )
        except Exception as e:
            self.log_test("Cache Stats", False, f"Exception: {str(e)}")

    async def run_all_tests(self):
        """모든 테스트 실행"""
        print("🔍 API 통합 테스트 시작")
        print("=" * 60)

        test_methods = [
            self.test_health_endpoint,
            self.test_games_list_endpoint,
            self.test_analysis_endpoint,
            self.test_ensemble_prediction,
            self.test_h2h_endpoint,
            self.test_toto_optimization,
            self.test_backtest_summary,
            self.test_cache_stats,
        ]

        for test_method in test_methods:
            await test_method()

        print("\n" + "=" * 60)
        print("📊 테스트 결과 요약")
        print(f"총 테스트: {self.results['total']}")
        print(f"통과: {self.results['passed']}")
        print(f"실패: {self.results['failed']}")

        if self.results["failed"] > 0:
            print("\n❌ 실패한 테스트:")
            for test in self.results["tests"]:
                if "FAIL" in test["status"]:
                    print(f"  - {test['name']}: {test.get('message', 'No message')}")

        # 결과를 JSON 파일로 저장
        results_file = Path(__file__).parent / "test_results.json"
        with open(results_file, "w", encoding="utf-8") as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)

        print(f"\n📁 테스트 결과 저장됨: {results_file}")

        if self.results["failed"] == 0:
            print("\n🎉 모든 테스트 통과!")
            return True
        else:
            print(f"\n⚠️  {self.results['failed']}개의 테스트가 실패했습니다.")
            return False


async def main():
    """메인 함수"""
    print("🚀 스포츠 AI 분석 시스템 - API 통합 테스트")
    print("=" * 60)
    print(f"백엔드 URL: {BASE_URL}")
    print("=" * 60)

    async with APITester() as tester:
        success = await tester.run_all_tests()

    if success:
        print("\n✅ T-01: API 통합 테스트 완료!")
        print("다음 단계: 프론트엔드-백엔드 연동 완성 (T-02)")
    else:
        print("\n❌ T-01: API 통합 테스트 실패!")
        print("문제를 해결한 후 다시 시도하세요.")

    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
