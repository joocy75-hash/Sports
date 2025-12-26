#!/usr/bin/env python3
"""베트맨 웹사이트 구조 디버깅 스크립트"""

import asyncio
from playwright.async_api import async_playwright


async def debug_betman():
    """베트맨 페이지 구조 확인"""
    async with async_playwright() as p:
        # 헤드리스 False로 브라우저 열기
        browser = await p.chromium.launch(headless=False, slow_mo=500)
        page = await browser.new_page()

        # 베트맨 페이지 로딩
        url = "https://www.betman.co.kr/main/mainPage/gamebuy/buyableGameList.do"
        print(f"페이지 로딩: {url}")
        await page.goto(url, wait_until="networkidle")

        await asyncio.sleep(3)

        # 승무패 탭 클릭
        try:
            await page.click("text=승무패", timeout=5000)
            print("승무패 탭 클릭 성공")
        except Exception as e:
            print(f"승무패 탭 클릭 실패: {e}")

        await asyncio.sleep(3)

        # 페이지 HTML 전체 가져오기
        html_content = await page.content()

        # HTML 파일로 저장
        with open("/Users/mr.joo/Desktop/스포츠분석/.state/betman_page.html", "w", encoding="utf-8") as f:
            f.write(html_content)
        print("HTML 저장 완료: .state/betman_page.html")

        # JavaScript로 경기 데이터 추출 시도
        games_data = await page.evaluate("""
            () => {
                // 모든 테이블 찾기
                const tables = document.querySelectorAll('table');
                console.log('테이블 개수:', tables.length);

                const result = {
                    tables: [],
                    allText: document.body.innerText.substring(0, 5000)
                };

                tables.forEach((table, idx) => {
                    const rows = table.querySelectorAll('tr');
                    const tableData = {
                        index: idx,
                        rows: []
                    };

                    rows.forEach((row, rowIdx) => {
                        const cells = row.querySelectorAll('td, th');
                        const rowData = [];
                        cells.forEach(cell => {
                            rowData.push(cell.textContent.trim());
                        });
                        if (rowData.length > 0) {
                            tableData.rows.push({
                                index: rowIdx,
                                cells: rowData
                            });
                        }
                    });

                    if (tableData.rows.length > 0) {
                        result.tables.push(tableData);
                    }
                });

                return result;
            }
        """)

        print("\n=== 테이블 구조 분석 ===")
        print(f"테이블 개수: {len(games_data['tables'])}")

        for table in games_data['tables'][:3]:  # 처음 3개 테이블만
            print(f"\n테이블 {table['index']}:")
            for row in table['rows'][:5]:  # 처음 5행만
                print(f"  행 {row['index']}: {row['cells']}")

        # 30초 대기 (수동으로 페이지 확인 가능)
        print("\n30초 대기 중... (수동으로 페이지를 확인하세요)")
        await asyncio.sleep(30)

        await browser.close()


if __name__ == "__main__":
    asyncio.run(debug_betman())
