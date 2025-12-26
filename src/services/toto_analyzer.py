import logging
from typing import List, Dict
import re
from sqlalchemy import select
from src.db.session import get_session
from src.db.models import Team, TeamStats
from src.services.predictor import AdvancedStatisticalPredictor
from src.services.gpt_analyzer import GPTAnalyzer

logger = logging.getLogger(__name__)


class TotoAnalyzer:
    """
    스포츠토토 승무패(14경기) 전용 분석기
    - 배당 독립적 AI 확률 계산
    - 최적의 마킹 조합(단통/투마킹/쓰리마킹) 추천
    """

    def __init__(self):
        self.stat_model = AdvancedStatisticalPredictor()
        self.gpt_analyzer = GPTAnalyzer()

    async def analyze_batch(self, matches_data: List[Dict]) -> List[Dict]:
        """
        다수의 경기 데이터를 받아 일괄 분석 수행
        matches_data: [{'home': 'TeamA', 'away': 'TeamB', 'row_num': '1'}, ...]
        """
        results = []
        async with get_session() as session:
            # 1. 1차 통계 분석 (전체 경기)
            for match in matches_data:
                home_name = match.get("home") or match.get("hteam_han_nm")
                away_name = match.get("away") or match.get("ateam_han_nm")

                if not home_name or not away_name:
                    continue

                # DB에서 팀 찾기
                home_team = await self._find_team(session, home_name)
                away_team = await self._find_team(session, away_name)

                if not home_team or not away_team:
                    results.append(
                        {"id": match.get("row_num"), "error": "Team not found"}
                    )
                    continue

                # 통계 분석 실행
                analysis = await self._analyze_single_match(
                    session, home_team, away_team
                )

                results.append(
                    {
                        "id": match.get("row_num"),
                        "home": home_team.name,
                        "away": away_team.name,
                        "analysis": analysis,
                        "match_info": f"{home_team.name} vs {away_team.name}",
                    }
                )

        # 2. Top 3 선정 (승률 기준)
        # analysis['probs']['home'] 등 최대값 기준 정렬
        def get_max_prob(item):
            if "analysis" not in item or "probs" not in item["analysis"]:
                return 0
            probs = item["analysis"]["probs"]
            return max(probs.get("home", 0), probs.get("draw", 0), probs.get("away", 0))

        sorted_results = sorted(results, key=get_max_prob, reverse=True)
        top_picks = sorted_results[:3]

        # 3. Top 3에 대해 GPT 정밀 분석 수행 (병렬 처리 가능하지만 여기선 순차)
        for item in top_picks:
            if "analysis" in item:
                # 통계 데이터 문자열화
                home_stats_str = f"Attack: {item['analysis'].get('home_att', 0)}, Defense: {item['analysis'].get('home_def', 0)}"
                away_stats_str = f"Attack: {item['analysis'].get('away_att', 0)}, Defense: {item['analysis'].get('away_def', 0)}"

                gpt_result = await self.gpt_analyzer.analyze_match(
                    item["match_info"], home_stats_str, away_stats_str
                )

                # 결과 병합 (GPT 의견을 우선하거나 보조로 사용)
                item["analysis"]["gpt_opinion"] = gpt_result
                # 추천 마크를 GPT 것으로 덮어쓸 수도 있음 (선택 사항)
                # item['analysis']['recommendation'] = gpt_result['recommendation']

        return results

    async def analyze_14_games(self, raw_text: str) -> str:
        """
        사용자가 입력한 14경기 텍스트를 파싱하고 분석하여 리포트 생성
        """
        # 1. 텍스트 파싱 (팀 이름 추출)
        matches_input = self._parse_input(raw_text)
        if not matches_input:
            return "❌ 경기 목록을 인식하지 못했습니다. '홈팀 vs 원정팀' 형식으로 입력해주세요."

        report = "📊 **제 12회차 승무패 AI 독자 분석**\n"
        report += "💡 *배당 무시 / 순수 경기력 기반*\n\n"

        # 2. 각 경기 분석
        results = []
        async with get_session() as session:
            for idx, (home_name, away_name) in enumerate(matches_input, 1):
                # DB에서 팀 찾기 (이름 매칭)
                home_team = await self._find_team(session, home_name)
                away_team = await self._find_team(session, away_name)

                if not home_team or not away_team:
                    results.append(
                        f"{idx}. ⚠️ 팀 인식 실패 ({home_name} vs {away_name})"
                    )
                    continue

                # AI 분석 실행
                analysis = await self._analyze_single_match(
                    session, home_team, away_team
                )
                results.append(
                    self._format_match_result(
                        idx, home_team.name, away_team.name, analysis
                    )
                )

        report += "\n".join(results)
        report += "\n\nℹ️ **범례**:\n🔒 단통 | 🛡️ 투마킹 | 💣 지우개(쓰리마킹)"
        return report

    def _parse_input(self, text: str) -> List[tuple]:
        """
        입력 텍스트에서 '팀A vs 팀B' 또는 '팀A 팀B' 패턴 추출
        """
        lines = text.strip().split("\n")
        matches = []
        for line in lines:
            # 제거: 숫자, 점, 특수문자
            clean_line = re.sub(r"^\d+[\.\)]\s*", "", line).strip()

            # 분리: vs, -, 또는 공백
            parts = re.split(r"\s+(?:vs|VS|-)\s+|\s{2,}", clean_line)

            if len(parts) >= 2:
                matches.append((parts[0].strip(), parts[1].strip()))

        return matches

    async def _find_team(self, session, name: str) -> Team:
        """
        팀 이름으로 DB 검색 (한글 -> 영어 매핑 포함)
        """
        # 1. 한글 이름 매핑 확인
        english_name = self._map_korean_to_english(name)

        # 2. 정확히 일치 (영어 이름)
        stmt = select(Team).where(Team.name.ilike(english_name))
        team = await session.scalar(stmt)
        if team:
            return team

        # 3. 부분 일치 (Like 검색)
        stmt = select(Team).where(Team.name.ilike(f"%{english_name}%"))
        team = await session.scalar(stmt)
        if team:
            return team

        # 4. 원래 이름으로도 시도 (혹시 DB에 한글로 저장된 경우)
        stmt = select(Team).where(Team.name.ilike(f"%{name}%"))
        team = await session.scalar(stmt)
        return team

    def _map_korean_to_english(self, name: str) -> str:
        """
        한글 팀명을 영문 팀명으로 변환
        """
        mapping = {
            # EPL
            "뉴캐슬": "Newcastle",
            "첼시": "Chelsea",
            "본머스": "Bournemouth",
            "번리": "Burnley",
            "브라이턴": "Brighton",
            "선덜랜드": "Sunderland",
            "울버햄프턴": "Wolverhampton",
            "울버햄튼": "Wolverhampton",
            "브렌트퍼드": "Brentford",
            "토트넘": "Tottenham",
            "리버풀": "Liverpool",
            "에버턴": "Everton",
            "아스널": "Arsenal",
            "아스톤 빌라": "Aston Villa",
            "맨체스터 유나이티드": "Manchester United",
            "맨유": "Manchester United",
            "맨체스터 시티": "Manchester City",
            "맨시티": "Manchester City",
            "리즈": "Leeds",
            "크리스탈 팰리스": "Crystal Palace",
            "노팅엄": "Nottingham",
            "풀럼": "Fulham",
            "웨스트햄": "West Ham",
            # Serie A
            "라치오": "Lazio",
            "파르마": "Parma",
            "유벤투스": "Juventus",
            "AS 로마": "AS Roma",
            "로마": "AS Roma",
            "칼리아리": "Cagliari",
            "피사": "Pisa",
            "사수올로": "Sassuolo",
            "토리노": "Torino",
            "인터밀란": "Inter",
            "AC밀란": "AC Milan",
            "나폴리": "Napoli",
            "아탈란타": "Atalanta",
            "볼로냐": "Bologna",
            "피오렌티나": "Fiorentina",
            "베로나": "Verona",
            "우디네세": "Udinese",
            "제노아": "Genoa",
            "몬차": "Monza",
            "레체": "Lecce",
            "엠폴리": "Empoli",
            "살레르니타나": "Salernitana",
            "프로시노네": "Frosinone",
        }

        # 공백 제거 및 정규화
        clean_name = name.replace("FC", "").replace("유나이티드", "").strip()

        return mapping.get(clean_name, mapping.get(name, name))

    async def _analyze_single_match(self, session, home: Team, away: Team) -> Dict:
        """
        단일 경기 AI 분석 (DB의 TeamStats 기반)
        """
        # 1. DB에서 최신 팀 스탯 조회
        stmt_home = (
            select(TeamStats)
            .where(TeamStats.team_id == home.id)
            .order_by(TeamStats.updated_at.desc())
            .limit(1)
        )
        stmt_away = (
            select(TeamStats)
            .where(TeamStats.team_id == away.id)
            .order_by(TeamStats.updated_at.desc())
            .limit(1)
        )

        home_stats = await session.scalar(stmt_home)
        away_stats = await session.scalar(stmt_away)

        # 2. 스탯이 없으면 기본값 사용 (추후 Match 테이블에서 계산 로직 추가 가능)
        # xG(기대 득점)를 공격력으로, xGA(기대 실점)를 수비력으로 사용
        h_att = home_stats.xg if home_stats and home_stats.xg else 1.4
        h_def = home_stats.xga if home_stats and home_stats.xga else 1.1

        a_att = away_stats.xg if away_stats and away_stats.xg else 1.2
        a_def = away_stats.xga if away_stats and away_stats.xga else 1.3

        # 3. 모멘텀(최근 분위기) 반영
        h_mom = home_stats.momentum if home_stats and home_stats.momentum else 0.5
        a_mom = away_stats.momentum if away_stats and away_stats.momentum else 0.5

        # 모멘텀이 높으면 공격력 소폭 상향
        if h_mom > 0.7:
            h_att *= 1.1
        if a_mom > 0.7:
            a_att *= 1.1

        # 4. 포아송 분포 기반 확률 계산
        probs = self.stat_model.predict_match_probabilities(h_att, h_def, a_att, a_def)

        # 5. AI Fair Odds 계산 (마진 0%)
        ai_odds = {
            "home": 1 / probs["home"] if probs["home"] > 0 else 0,
            "draw": 1 / probs["draw"] if probs["draw"] > 0 else 0,
            "away": 1 / probs["away"] if probs["away"] > 0 else 0,
        }

        # 6. 전략 추천 로직
        recommendation = self._get_strategy(probs)

        return {
            "probs": probs,
            "ai_odds": ai_odds,
            "recommendation": recommendation,
            "stats": {"h_att": h_att, "h_def": h_def, "a_att": a_att, "a_def": a_def},
        }

    def _get_strategy(self, probs: Dict) -> Dict:
        """
        확률 기반 마킹 전략 수립
        """
        p_home = probs["home"]
        p_draw = probs["draw"]
        p_away = probs["away"]

        max_prob = max(p_home, p_draw, p_away)

        # 1. 단통 (Banker)
        if max_prob >= 0.60:
            if p_home == max_prob:
                return {"type": "Single", "mark": "[승]", "icon": "🔒"}
            if p_away == max_prob:
                return {"type": "Single", "mark": "[패]", "icon": "🔒"}

        # 2. 투마킹 (Insurance)
        # 승무 / 무패 / 승패
        if p_home + p_draw >= 0.75 and p_away < 0.25:
            return {"type": "Double", "mark": "[승/무]", "icon": "🛡️"}
        if p_away + p_draw >= 0.75 and p_home < 0.25:
            return {"type": "Double", "mark": "[무/패]", "icon": "🛡️"}
        if p_home + p_away >= 0.80 and p_draw < 0.20:  # 남자의 승부
            return {"type": "Double", "mark": "[승/패]", "icon": "⚔️"}

        # 3. 지우개 (Eraser)
        return {"type": "Triple", "mark": "[승/무/패]", "icon": "💣"}

    def _format_match_result(
        self, idx: int, home: str, away: str, analysis: Dict
    ) -> str:
        rec = analysis["recommendation"]
        probs = analysis["probs"]

        # ai_odds_str = f"AI배당: {analysis['ai_odds']['home']:.2f} {analysis['ai_odds']['draw']:.2f} {analysis['ai_odds']['away']:.2f}"

        line1 = f"{idx}. **{home}** vs **{away}**"
        line2 = f"   {rec['icon']} **{rec['mark']}** (승 {probs['home'] * 100:.0f}% 무 {probs['draw'] * 100:.0f}% 패 {probs['away'] * 100:.0f}%)"
        # line3 = f"   └ AI 배당: {analysis['ai_odds']['home']:.2f} {analysis['ai_odds']['draw']:.2f} {analysis['ai_odds']['away']:.2f}"

        return f"{line1}\n{line2}"
