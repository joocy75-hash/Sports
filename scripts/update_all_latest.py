import asyncio
from datetime import datetime, timedelta
from src.db.session import get_session
from src.db.models import Match, Team, PredictionLog, BetRecord, OddsHistory
from sqlalchemy import delete, select


async def update_all_latest():
    async with get_session() as session:
        league_id = 9999

        # 0. 기존 관련 데이터 정리
        await session.execute(delete(PredictionLog))
        await session.execute(delete(BetRecord))
        await session.execute(delete(OddsHistory))
        await session.execute(delete(Match))
        await session.flush()

        # 1. 축구 승무패 83회차
        soccer_83_matches = [
            ("뉴캐슬", "첼시"),
            ("본머스", "번리"),
            ("브라이턴", "선덜랜드"),
            ("울버햄튼", "브렌트포드"),
            ("라치오", "크레모네세"),
            ("토트넘", "리버풀"),
            ("유벤투스", "AS로마"),
            ("에버턴", "아스널"),
            ("리즈", "크리스탈"),
            ("칼리아리", "피사"),
            ("사수올로", "토리노"),
            ("아스톤빌라", "맨체스터U"),
            ("볼로냐", "몬차"),
            ("베로나", "엠폴리"),
        ]
        for i, (h, a) in enumerate(soccer_83_matches):
            await add_match(
                session,
                h,
                a,
                "축구 승무패",
                83,
                "축구",
                "축구토토 승무패",
                i,
                league_id,
            )

        # 2. 프로토 승부식 149회차
        proto_149_matches = [
            ("아스널", "크리스털팰리스", "축구"),
            ("PSG", "플라멩고", "축구"),
            ("울산모비스", "안양정관", "농구"),
            ("BNK썸", "하나은행", "농구"),
            ("OK금융그룹", "우리카드", "배구"),
            ("현대건설", "흥국생명", "배구"),
            ("골든스테이트", "LA레이커스", "농구"),
            ("레알마드리드", "세비야", "축구"),
        ]
        for i, (h, a, sport) in enumerate(proto_149_matches):
            await add_match(
                session,
                h,
                a,
                "프로토 승부식",
                149,
                sport,
                "프로토 승부식",
                i,
                league_id,
            )

        # 2-1. 프로토 기록식 103회차
        proto_103_matches = [
            ("맨체스터C", "토트넘", "축구"),
            ("바르셀로나", "레알마드리드", "축구"),
        ]
        for i, (h, a, sport) in enumerate(proto_103_matches):
            await add_match(
                session,
                h,
                a,
                "프로토 기록식",
                103,
                sport,
                "프로토 기록식",
                i,
                league_id,
            )

        # 3. 농구 승5패 45회차
        basketball_45_matches = [
            ("원주DB", "서울SK"),
            ("창원LG", "수원KT"),
            ("대구한국가스공사", "부산KCC"),
            ("서울삼성", "고양소노"),
            ("안양정관", "울산모비스"),
            ("하나은행", "KB스타즈"),
            ("우리은행", "BNK썸"),
            ("골든스테이트", "새크라멘토"),
            ("LA클리퍼스", "피닉스선즈"),
            ("보스턴셀틱스", "뉴욕닉스"),
            ("밀워키벅스", "클리블랜드"),
            ("덴버너기츠", "댈러스매버릭스"),
            ("미네소타", "오클라호마"),
            ("필라델피아", "마이애미"),
        ]
        for i, (h, a) in enumerate(basketball_45_matches):
            await add_match(
                session, h, a, "농구 승5패", 45, "농구", "농구토토 승5패", i, league_id
            )

        # 4. 추가 토토 게임 (이미지 반영)
        toto_extra = [
            ("농구", "스페셜 트리플", 42, "농구토토 스페셜 트리플"),
            ("농구", "스페셜 더블", 42, "농구토토 스페셜 더블"),
            ("농구", "스페셜N 트리플", 134, "농구토토 스페셜N 트리플"),
            ("농구", "스페셜N 더블", 134, "농구토토 스페셜N 더블"),
            ("농구", "스페셜N 트리플", 135, "농구토토 스페셜N 트리플"),
            ("농구", "스페셜N 더블", 135, "농구토토 스페셜N 더블"),
            ("농구", "매치", 125, "농구토토 매치"),
            ("농구", "W매치", 83, "농구토토 W매치"),
            ("농구", "W매치", 84, "농구토토 W매치"),
        ]
        for i, (sport, name, rnd, prod) in enumerate(toto_extra):
            await add_match(
                session,
                "홈팀",
                "어웨이팀",
                f"{sport} {name}",
                rnd,
                sport,
                prod,
                i,
                league_id,
            )

        await session.commit()
        print(
            "Successfully updated all categories to ACTUAL latest rounds (Soccer 83, Proto 149, Basketball 45)."
        )


async def add_match(session, h_name, a_name, cat, rnd, sport, prod, idx, league_id):
    h_id = await get_team_id(session, h_name, sport, league_id)
    a_id = await get_team_id(session, a_name, sport, league_id)

    # 카테고리별 고유 오프셋 생성 (중복 방지)
    cat_offset = hash(cat) % 10000

    match = Match(
        id=9000000 + (rnd * 10000) + cat_offset + idx,
        league_id=league_id,
        season=2025,
        sport=map_sport(sport),
        start_time=datetime.now() + timedelta(days=1, hours=idx),
        status="예정",
        home_team_id=h_id,
        away_team_id=a_id,
        product_name=prod,
        category_name=cat,
        round_number=rnd,
        sport_type=sport,
        odds_home=2.0,
        odds_draw=3.0,
        odds_away=3.0,
    )
    session.add(match)


async def get_team_id(session, name, sport, league_id):
    mapped_s = map_sport(sport)
    res = await session.execute(
        select(Team).where(Team.name == name, Team.sport == mapped_s)
    )
    team = res.scalars().first()
    if not team:
        team = Team(
            id=hash(f"{name}_{sport}") % 1000000,
            name=name,
            league_id=league_id,
            sport=mapped_s,
        )
        session.add(team)
        await session.flush()
    return team.id


def map_sport(s):
    m = {
        "축구": "football",
        "농구": "basketball",
        "배구": "volleyball",
        "야구": "baseball",
    }
    return m.get(s, "other")


if __name__ == "__main__":
    asyncio.run(update_all_latest())
