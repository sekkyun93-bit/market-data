# market-data

아침 증시 브리핑용 시세 데이터 저장소입니다.

- GitHub Actions가 월~토 06:05·06:25(KST)에 Yahoo Finance에서 지수·선물 5분봉과 일봉을 받아 `data/latest.json`에 저장합니다.
- 브리핑은 `https://raw.githubusercontent.com/sekkyun93-bit/market-data/main/data/latest.json`을 읽어 차트를 그립니다.
- 수동 실행: Actions 탭 → Fetch market data → Run workflow.
