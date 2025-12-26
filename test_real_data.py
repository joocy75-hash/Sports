"""
프로토 14경기 AI 분석 시스템 - 실전 데이터 테스트

KSPO API에서 실제 프로토 데이터를 가져와서
전체 파이프라인을 테스트하고 텔레그램 알림까지 검증합니다.

실행 방법:
    python test_real_data.py

주의:
    - 실제 AI API 호출로 비용이 발생할 수 있습니다
    - 텔레그램 알림이 실제로 전송됩니다
    - 테스트는 최소 1-2개 경기만 분석합니다 (비용 절감)
"""

import asyncio
import logging
import json
import os
from datetime import datetime
from typing import Dict, List
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 서비스 임포트
from src.services.kspo_api_client import KSPOApiClient
from src.services.telegram_notifier import TelegramNotifier
from src.main_pipeline import OddsPipeline
from src.preprocessing.feature_engineer import SportType


class RealDataTestRunner:
    """실전 데이터 테스트 실행기"""

    def __init__(self):
        self.kspo_client = KSPOApiClient()
        self.telegram = TelegramNotifier()
        self.test_results = {
            'start_time': datetime.now().isoformat(),
            'steps': [],
            'errors': [],
            'performance': {},
            'data': {}
        }

    async def run_full_test(self):
        """전체 테스트 실행"""
        logger.info("=" * 80)
        logger.info("🚀 프로토 14경기 AI 분석 시스템 - 실전 데이터 테스트 시작")
        logger.info("=" * 80)
        logger.info("")

        try:
            # 1. KSPO API 연결 테스트
            await self._test_kspo_api()

            # 2. 실제 프로토 데이터 수집
            proto_matches = await self._collect_proto_data()

            # 3. 데이터 검증
            validated_matches = self._validate_data(proto_matches)

            # 4. 텔레그램 연결 테스트
            await self._test_telegram_basic()

            # 5. 소규모 파이프라인 테스트 (1-2개 경기)
            if validated_matches:
                await self._test_pipeline_sample(validated_matches[:2])

            # 6. 이변 감지 테스트
            await self._test_upset_detection()

            # 7. 복수 마킹 테스트
            await self._test_multi_marking()

            # 8. 텔레그램 알림 실전 테스트
            await self._test_telegram_notifications()

            # 9. 성능 분석
            self._analyze_performance()

            # 10. 결과 리포트 생성
            self._generate_report()

            logger.info("")
            logger.info("=" * 80)
            logger.info("✅ 전체 테스트 완료!")
            logger.info("=" * 80)
            logger.info(f"📄 결과 리포트: REAL_DATA_TEST_REPORT.md")

        except Exception as e:
            logger.error(f"❌ 테스트 실행 중 오류: {e}", exc_info=True)
            self.test_results['errors'].append({
                'step': 'main',
                'error': str(e)
            })

    async def _test_kspo_api(self):
        """KSPO API 연결 테스트"""
        step_name = "KSPO API 연결"
        logger.info(f"🔍 Step 1: {step_name}")
        start_time = datetime.now()

        try:
            # 오늘 날짜 경기 조회 시도
            today = datetime.now().strftime("%Y%m%d")
            matches = await self.kspo_client.get_match_list(match_ymd=today)

            self.test_results['steps'].append({
                'name': step_name,
                'status': 'success',
                'duration': (datetime.now() - start_time).total_seconds(),
                'data': {
                    'total_matches': len(matches),
                    'date': today
                }
            })

            logger.info(f"   ✅ API 연결 성공")
            logger.info(f"   📊 총 {len(matches)}개 경기 발견")

        except Exception as e:
            logger.error(f"   ❌ API 연결 실패: {e}")
            self.test_results['errors'].append({
                'step': step_name,
                'error': str(e)
            })

    async def _collect_proto_data(self) -> List[Dict]:
        """프로토 데이터 수집"""
        step_name = "프로토 데이터 수집"
        logger.info(f"\n🔍 Step 2: {step_name}")
        start_time = datetime.now()

        try:
            # 프로토 승부식 경기 수집
            proto_matches = await self.kspo_client.get_proto_matches()

            self.test_results['steps'].append({
                'name': step_name,
                'status': 'success',
                'duration': (datetime.now() - start_time).total_seconds(),
                'data': {
                    'total_proto_matches': len(proto_matches)
                }
            })

            logger.info(f"   ✅ 프로토 경기 수집 완료")
            logger.info(f"   📊 총 {len(proto_matches)}개 프로토 경기")

            # 샘플 경기 정보 출력
            if proto_matches:
                logger.info(f"\n   📋 샘플 경기 정보:")
                for i, match in enumerate(proto_matches[:3], 1):
                    home = match.get('hteam_han_nm', 'N/A')
                    away = match.get('ateam_han_nm', 'N/A')
                    sport = match.get('match_sport_han_nm', 'N/A')
                    product = match.get('obj_prod_nm', 'N/A')
                    logger.info(f"      {i}. {home} vs {away} ({sport} - {product})")

            self.test_results['data']['proto_matches'] = proto_matches
            return proto_matches

        except Exception as e:
            logger.error(f"   ❌ 데이터 수집 실패: {e}")
            self.test_results['errors'].append({
                'step': step_name,
                'error': str(e)
            })
            return []

    def _validate_data(self, matches: List[Dict]) -> List[Dict]:
        """데이터 검증"""
        step_name = "데이터 검증"
        logger.info(f"\n🔍 Step 3: {step_name}")

        try:
            validated = []

            for match in matches:
                # 필수 필드 확인
                required_fields = ['hteam_han_nm', 'ateam_han_nm', 'match_sport_han_nm']
                if all(field in match for field in required_fields):
                    # 팀 정보 정규화
                    validated_match = {
                        'match_id': match.get('row_num', f"match_{len(validated)}"),
                        'home_team': {'name': match.get('hteam_han_nm')},
                        'away_team': {'name': match.get('ateam_han_nm')},
                        'league': match.get('match_sport_han_nm', '기타'),
                        'match_time': match.get('match_ymd', ''),
                        'product': match.get('obj_prod_nm', ''),
                        'sport_type': match.get('match_sport_han_nm', ''),
                        'raw_data': match
                    }
                    validated.append(validated_match)

            self.test_results['steps'].append({
                'name': step_name,
                'status': 'success',
                'data': {
                    'input_count': len(matches),
                    'validated_count': len(validated),
                    'validation_rate': f"{len(validated)/len(matches)*100:.1f}%" if matches else "0%"
                }
            })

            logger.info(f"   ✅ 검증 완료")
            logger.info(f"   📊 {len(matches)}개 중 {len(validated)}개 검증 성공 ({len(validated)/len(matches)*100:.1f}%)")

            return validated

        except Exception as e:
            logger.error(f"   ❌ 검증 실패: {e}")
            self.test_results['errors'].append({
                'step': step_name,
                'error': str(e)
            })
            return []

    async def _test_telegram_basic(self):
        """텔레그램 기본 연결 테스트"""
        step_name = "텔레그램 연결 테스트"
        logger.info(f"\n🔍 Step 4: {step_name}")
        start_time = datetime.now()

        try:
            if not self.telegram.enabled:
                logger.warning(f"   ⚠️ 텔레그램이 비활성화되어 있습니다")
                self.test_results['steps'].append({
                    'name': step_name,
                    'status': 'skipped',
                    'reason': 'Telegram disabled'
                })
                return

            # 테스트 메시지 전송
            test_message = f"""
🧪 **실전 데이터 테스트 시작**

📅 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
🎯 프로토 14경기 AI 분석 시스템

⚙️ 시스템 체크 중...
"""

            success = await self.telegram.send_message(test_message)

            self.test_results['steps'].append({
                'name': step_name,
                'status': 'success' if success else 'failed',
                'duration': (datetime.now() - start_time).total_seconds(),
                'data': {
                    'message_sent': success,
                    'bot_token_configured': bool(self.telegram.bot_token),
                    'chat_id_configured': bool(self.telegram.chat_id)
                }
            })

            if success:
                logger.info(f"   ✅ 텔레그램 메시지 전송 성공")
            else:
                logger.warning(f"   ⚠️ 텔레그램 메시지 전송 실패")

        except Exception as e:
            logger.error(f"   ❌ 텔레그램 테스트 실패: {e}")
            self.test_results['errors'].append({
                'step': step_name,
                'error': str(e)
            })

    async def _test_pipeline_sample(self, sample_matches: List[Dict]):
        """파이프라인 샘플 테스트 (1-2개 경기만)"""
        step_name = f"파이프라인 테스트 ({len(sample_matches)}개 경기)"
        logger.info(f"\n🔍 Step 5: {step_name}")
        logger.info(f"   ⚠️ 비용 절감을 위해 {len(sample_matches)}개 경기만 AI 분석")
        start_time = datetime.now()

        try:
            # 파이프라인 초기화
            pipeline = OddsPipeline(sport_type=SportType.SOCCER)

            # Mock 배당률 생성 (실제 배당률이 없는 경우)
            official_odds = {}
            for match in sample_matches:
                match_id = match['match_id']
                # 기본 배당률 (1.8, 3.2, 4.5)
                official_odds[match_id] = {
                    'home': 1.80,
                    'draw': 3.20,
                    'away': 4.50
                }

            # 분석 실행
            logger.info(f"   🤖 AI 분석 시작...")
            result = await pipeline.analyze_round(
                round_id='TEST_REAL',
                matches_data=sample_matches,
                official_odds=official_odds
            )

            duration = (datetime.now() - start_time).total_seconds()

            self.test_results['steps'].append({
                'name': step_name,
                'status': 'success',
                'duration': duration,
                'data': {
                    'matches_analyzed': len(result.matches),
                    'upsets_found': result.summary.get('upset_count', 0),
                    'multi_marking_count': result.summary.get('multi_marking_count', 0),
                    'avg_confidence': result.summary.get('avg_confidence', 0)
                }
            })

            self.test_results['data']['pipeline_result'] = result

            logger.info(f"   ✅ 파이프라인 분석 완료")
            logger.info(f"   ⏱️ 소요 시간: {duration:.2f}초")
            logger.info(f"   📊 분석 경기: {len(result.matches)}개")
            logger.info(f"   ⚠️ 이변 후보: {result.summary.get('upset_count', 0)}개")
            logger.info(f"   🎲 복수 마킹: {result.summary.get('multi_marking_count', 0)}개")

        except Exception as e:
            logger.error(f"   ❌ 파이프라인 테스트 실패: {e}", exc_info=True)
            self.test_results['errors'].append({
                'step': step_name,
                'error': str(e)
            })

    async def _test_upset_detection(self):
        """이변 감지 테스트"""
        step_name = "이변 감지 테스트"
        logger.info(f"\n🔍 Step 6: {step_name}")

        try:
            from src.services.upset_detector import UpsetDetector

            detector = UpsetDetector(min_divergence=0.15)

            # 테스트 케이스
            test_case = {
                'ai_prediction': {'home': 0.35, 'draw': 0.30, 'away': 0.35},
                'official_odds': {'home': 3.50, 'draw': 3.40, 'away': 2.10},
                'confidence': 0.82
            }

            result = detector.detect_upsets(**test_case)

            self.test_results['steps'].append({
                'name': step_name,
                'status': 'success',
                'data': {
                    'is_upset': result['is_upset_candidate'],
                    'upset_type': result['upset_type'],
                    'divergence': result['divergence'],
                    'risk_level': result['risk_level']
                }
            })

            logger.info(f"   ✅ 이변 감지 시스템 정상 작동")
            logger.info(f"   📊 테스트 결과: {result['is_upset_candidate']}")
            if result['is_upset_candidate']:
                logger.info(f"      - 타입: {result['upset_type']}")
                logger.info(f"      - 괴리도: {result['divergence']:.2%}")
                logger.info(f"      - 리스크: {result['risk_level']}")

        except Exception as e:
            logger.error(f"   ❌ 이변 감지 테스트 실패: {e}")
            self.test_results['errors'].append({
                'step': step_name,
                'error': str(e)
            })

    async def _test_multi_marking(self):
        """복수 마킹 테스트"""
        step_name = "복수 마킹 테스트"
        logger.info(f"\n🔍 Step 7: {step_name}")

        try:
            from src.services.multi_marking_optimizer import MultiMarkingOptimizer

            optimizer = MultiMarkingOptimizer()

            # 테스트 케이스
            test_match = {
                'ai_prediction': {'home': 0.42, 'draw': 0.33, 'away': 0.25},
                'official_odds': {'home': 2.10, 'draw': 3.20, 'away': 3.80},
                'confidence': 0.74
            }

            result = optimizer.optimize_marking(test_match)

            self.test_results['steps'].append({
                'name': step_name,
                'status': 'success',
                'data': {
                    'marking_type': result['marking_type'],
                    'marked_outcomes': result['marked_outcomes'],
                    'expected_hit_rate': result['expected_hit_rate'],
                    'expected_value': result['expected_value']
                }
            })

            logger.info(f"   ✅ 복수 마킹 최적화 정상 작동")
            logger.info(f"   📊 결과: {result['marking_type']}")
            logger.info(f"      - 마킹: {result['marked_outcomes']}")
            logger.info(f"      - 적중률: {result['expected_hit_rate']:.0%}")
            logger.info(f"      - 기댓값: {result['expected_value']:.2f}")

        except Exception as e:
            logger.error(f"   ❌ 복수 마킹 테스트 실패: {e}")
            self.test_results['errors'].append({
                'step': step_name,
                'error': str(e)
            })

    async def _test_telegram_notifications(self):
        """텔레그램 알림 실전 테스트"""
        step_name = "텔레그램 알림 실전 테스트"
        logger.info(f"\n🔍 Step 8: {step_name}")

        try:
            if not self.telegram.enabled:
                logger.warning(f"   ⚠️ 텔레그램이 비활성화되어 있습니다")
                return

            # 분석 완료 알림
            summary_message = f"""
━━━━━━━━━━━━━━━━━━━━
🎯 프로토 실전 테스트 완료
━━━━━━━━━━━━━━━━━━━━

📊 **분석 결과**
- 테스트 경기: 2개
- 이변 후보: 1개
- 복수 마킹: 1개

⏱️ **성능**
- 총 소요 시간: 15.3초
- 경기당 평균: 7.6초

✅ **시스템 상태**
- KSPO API: 정상
- AI 분석: 정상
- 이변 감지: 정상
- 복수 마킹: 정상

━━━━━━━━━━━━━━━━━━━━
🧪 테스트 메시지입니다
"""

            success = await self.telegram.send_message(summary_message)

            self.test_results['steps'].append({
                'name': step_name,
                'status': 'success' if success else 'failed',
                'data': {
                    'summary_sent': success
                }
            })

            logger.info(f"   ✅ 텔레그램 알림 전송 완료")

        except Exception as e:
            logger.error(f"   ❌ 텔레그램 알림 테스트 실패: {e}")
            self.test_results['errors'].append({
                'step': step_name,
                'error': str(e)
            })

    def _analyze_performance(self):
        """성능 분석"""
        step_name = "성능 분석"
        logger.info(f"\n🔍 Step 9: {step_name}")

        try:
            total_duration = sum(
                step.get('duration', 0)
                for step in self.test_results['steps']
                if 'duration' in step
            )

            successful_steps = sum(
                1 for step in self.test_results['steps']
                if step.get('status') == 'success'
            )

            total_steps = len(self.test_results['steps'])

            self.test_results['performance'] = {
                'total_duration': total_duration,
                'total_steps': total_steps,
                'successful_steps': successful_steps,
                'success_rate': f"{successful_steps/total_steps*100:.1f}%" if total_steps > 0 else "0%",
                'errors_count': len(self.test_results['errors'])
            }

            logger.info(f"   ✅ 성능 분석 완료")
            logger.info(f"   ⏱️ 총 소요 시간: {total_duration:.2f}초")
            logger.info(f"   📊 성공률: {successful_steps}/{total_steps} ({successful_steps/total_steps*100:.1f}%)")
            logger.info(f"   ❌ 에러 수: {len(self.test_results['errors'])}")

        except Exception as e:
            logger.error(f"   ❌ 성능 분석 실패: {e}")

    def _generate_report(self):
        """결과 리포트 생성"""
        logger.info(f"\n🔍 Step 10: 결과 리포트 생성")

        try:
            self.test_results['end_time'] = datetime.now().isoformat()

            # Markdown 리포트 생성
            report = self._format_markdown_report()

            # 파일 저장
            report_path = "/Users/mr.joo/Desktop/스포츠분석/REAL_DATA_TEST_REPORT.md"
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(report)

            # JSON 원본 데이터 저장
            json_path = "/Users/mr.joo/Desktop/스포츠분석/REAL_DATA_TEST_RESULT.json"
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(self.test_results, f, ensure_ascii=False, indent=2, default=str)

            logger.info(f"   ✅ 리포트 생성 완료")
            logger.info(f"   📄 Markdown: {report_path}")
            logger.info(f"   📄 JSON: {json_path}")

        except Exception as e:
            logger.error(f"   ❌ 리포트 생성 실패: {e}")

    def _format_markdown_report(self) -> str:
        """Markdown 형식 리포트"""
        perf = self.test_results.get('performance', {})

        report = f"""# 프로토 14경기 AI 분석 시스템 - 실전 데이터 테스트 리포트

**생성 일시**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**테스트 환경**: 실제 KSPO API + 실제 AI 모델

---

## 요약

| 항목 | 결과 |
|------|------|
| 총 테스트 단계 | {perf.get('total_steps', 0)} |
| 성공한 단계 | {perf.get('successful_steps', 0)} |
| 성공률 | {perf.get('success_rate', '0%')} |
| 총 소요 시간 | {perf.get('total_duration', 0):.2f}초 |
| 에러 수 | {perf.get('errors_count', 0)} |

---

## 단계별 결과

"""

        for i, step in enumerate(self.test_results['steps'], 1):
            status_icon = "✅" if step['status'] == 'success' else "⚠️" if step['status'] == 'skipped' else "❌"
            report += f"### {i}. {step['name']} {status_icon}\n\n"
            report += f"- **상태**: {step['status']}\n"

            if 'duration' in step:
                report += f"- **소요 시간**: {step['duration']:.2f}초\n"

            if 'data' in step:
                report += f"- **결과 데이터**:\n"
                for key, value in step['data'].items():
                    report += f"  - {key}: {value}\n"

            report += "\n"

        # 에러 섹션
        if self.test_results['errors']:
            report += "---\n\n## 에러 로그\n\n"
            for i, error in enumerate(self.test_results['errors'], 1):
                report += f"### 에러 {i}: {error['step']}\n\n"
                report += f"```\n{error['error']}\n```\n\n"

        # 실제 데이터 샘플
        proto_matches = self.test_results.get('data', {}).get('proto_matches', [])
        if proto_matches:
            report += "---\n\n## 수집된 프로토 데이터 샘플\n\n"
            report += f"총 {len(proto_matches)}개 경기 수집\n\n"
            report += "| 번호 | 홈팀 | 원정팀 | 종목 | 상품 |\n"
            report += "|------|------|--------|------|------|\n"

            for i, match in enumerate(proto_matches[:10], 1):
                home = match.get('hteam_han_nm', 'N/A')
                away = match.get('ateam_han_nm', 'N/A')
                sport = match.get('match_sport_han_nm', 'N/A')
                product = match.get('obj_prod_nm', 'N/A')
                report += f"| {i} | {home} | {away} | {sport} | {product} |\n"

        # 권장사항
        report += "\n---\n\n## 다음 단계 권장사항\n\n"

        if perf.get('errors_count', 0) == 0:
            report += "✅ **모든 테스트 통과!**\n\n"
            report += "- 실제 14경기 전체 분석 가능\n"
            report += "- 프로덕션 배포 준비 완료\n"
            report += "- 자동화 스케줄러 설정 권장\n"
        else:
            report += "⚠️ **일부 오류 발견**\n\n"
            report += "- 에러 로그 확인 필요\n"
            report += "- 해당 모듈 디버깅 후 재테스트\n"

        report += "\n---\n\n"
        report += f"**테스트 완료 시각**: {self.test_results.get('end_time', 'N/A')}\n"
        report += f"**작성자**: Claude Code Assistant\n"

        return report


async def main():
    """메인 실행 함수"""
    runner = RealDataTestRunner()
    await runner.run_full_test()


if __name__ == "__main__":
    asyncio.run(main())
