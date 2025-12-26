-- 샘플 데이터 삽입 SQL
-- 테스트용 리그, 팀, 경기, 예측 데이터

-- 1. 리그 삽입
INSERT INTO leagues (id, name, country, sport) VALUES
(39, 'Premier League', 'England', 'football'),
(140, 'La Liga', 'Spain', 'football'),
(78, 'Bundesliga', 'Germany', 'football'),
(135, 'Serie A', 'Italy', 'football')
ON CONFLICT (id) DO NOTHING;

-- 2. 팀 삽입
INSERT INTO teams (id, name, league_id, sport) VALUES
(50, 'Manchester City', 39, 'football'),
(40, 'Liverpool', 39, 'football'),
(33, 'Manchester United', 39, 'football'),
(42, 'Arsenal', 39, 'football'),
(49, 'Chelsea', 39, 'football'),
(541, 'Real Madrid', 140, 'football'),
(529, 'Barcelona', 140, 'football'),
(157, 'Bayern Munich', 78, 'football'),
(173, 'Borussia Dortmund', 78, 'football'),
(489, 'AC Milan', 135, 'football')
ON CONFLICT (id) DO NOTHING;

-- 3. 경기 삽입 (오늘과 내일)
INSERT INTO matches (id, league_id, season, sport, home_team_id, away_team_id, start_time, status, sharp_detected)
VALUES
(1001, 39, 2024, 'football', 50, 40, NOW() + INTERVAL '2 hours', 'scheduled', false),
(1002, 39, 2024, 'football', 42, 49, NOW() + INTERVAL '5 hours', 'scheduled', false),
(1003, 39, 2024, 'football', 33, 40, NOW() + INTERVAL '1 day', 'scheduled', false),
(1004, 140, 2024, 'football', 541, 529, NOW() + INTERVAL '1 day 3 hours', 'scheduled', false),
(1005, 78, 2024, 'football', 157, 173, NOW() + INTERVAL '2 days', 'scheduled', false)
ON CONFLICT (id) DO NOTHING;

-- 4. 배당 정보 삽입
INSERT INTO odds_history (match_id, bookmaker, odds_home, odds_draw, odds_away, market, captured_at)
VALUES
(1001, 'Bet365', 1.85, 3.75, 4.20, '1x2', NOW()),
(1002, 'Bet365', 2.10, 3.40, 3.50, '1x2', NOW()),
(1003, 'Bet365', 2.45, 3.20, 2.90, '1x2', NOW()),
(1004, 'Bet365', 2.20, 3.30, 3.40, '1x2', NOW()),
(1005, 'Bet365', 1.50, 4.50, 6.50, '1x2', NOW());

-- 5. AI 예측 삽입
INSERT INTO prediction_logs (match_id, prob_home, prob_draw, prob_away, expected_score_home, expected_score_away, value_home, value_draw, value_away, created_at)
VALUES
(1001, 0.58, 0.25, 0.17, 2.1, 1.3, 0.073, -0.067, -0.195, NOW()),
(1002, 0.45, 0.30, 0.25, 1.8, 1.5, -0.048, -0.118, -0.143, NOW()),
(1003, 0.42, 0.28, 0.30, 1.6, 1.7, 0.020, -0.107, 0.034, NOW()),
(1004, 0.48, 0.27, 0.25, 1.9, 1.6, 0.091, -0.111, -0.147, NOW()),
(1005, 0.72, 0.18, 0.10, 2.8, 0.9, 0.080, -0.222, -0.385, NOW());

-- 6. 팀 통계 삽입
INSERT INTO team_stats (team_id, season, xg, xga, momentum, updated_at)
VALUES
(50, 2024, 2.4, 1.1, 0.85, NOW()),
(40, 2024, 2.2, 0.9, 0.78, NOW()),
(42, 2024, 2.0, 1.0, 0.72, NOW()),
(49, 2024, 1.9, 1.2, 0.68, NOW()),
(33, 2024, 1.6, 1.3, 0.55, NOW())
ON CONFLICT DO NOTHING;
