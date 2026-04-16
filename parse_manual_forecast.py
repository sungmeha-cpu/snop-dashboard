import xlrd, json, re

wb = xlrd.open_workbook('d:/Users/muse23031801/Downloads/수기예측파일.xls')

STAGE_CODE = {
    '준비기': '1110', '초기1': '1210', '초기2': '1220', '중기': '1230',
    '후기': '1240', '후기무른밥': '1250', '후기 무른밥': '1250', '무른밥': '1250',
    '영양밥': '1310', '영양국': '1320', '영양찬': '1330'
}

# Date mapping from sheet names
DATE_MAP = {
    '3-16': '2026-03-16', '3-17': '2026-03-17', '3-18': '2026-03-18',
    '3-19': '2026-03-19', '3-20': '2026-03-20', '3-21': '2026-03-21',
    '3-23': '2026-03-23', '3-24': '2026-03-24', '3-25': '2026-03-25',
    '3-26': '2026-03-26', '3-27': '2026-03-27', '3-28': '2026-03-28',
    '3-30': '2026-03-30', '3-31': '2026-03-31',
    '4-1': '2026-04-01', '4-2': '2026-04-02', '4-3': '2026-04-03', '4-4': '2026-04-04',
    '4-6': '2026-04-06', '4-7': '2026-04-07', '4-8': '2026-04-08',
    '4-9': '2026-04-09', '4-10': '2026-04-10', '4-11': '2026-04-11',
    '4-13': '2026-04-13', '4-14': '2026-04-14', '4-15': '2026-04-15', '4-16': '2026-04-16',
}

result = {}

for sname in wb.sheet_names():
    ws = wb.sheet_by_name(sname)

    # Extract date from sheet name (e.g., "3-16(월)" -> "3-16")
    date_key = re.match(r'([\d]+-[\d]+)', sname)
    if not date_key:
        continue
    date_key = date_key.group(1)
    date_iso = DATE_MAP.get(date_key)
    if not date_iso:
        continue

    stages = []
    current_stage = ''
    for r in range(3, ws.nrows):
        stage_raw = ws.cell_value(r, 0)
        if stage_raw and str(stage_raw).strip():
            current_stage = str(stage_raw).strip()

        label = str(ws.cell_value(r, 1)).strip() if ws.cell_value(r, 1) else ''
        if not label or label in ('', '\u3000'):
            continue

        # 예측(A): col 2 = 자사몰, col 3 = 외부몰, col 4 = 합계
        try:
            jasa = float(ws.cell_value(r, 2) or 0)
            oibu = float(ws.cell_value(r, 3) or 0)
            total = float(ws.cell_value(r, 4) or 0)
        except:
            continue

        if total == 0 and jasa == 0:
            continue

        sc = STAGE_CODE.get(current_stage, '')
        if not sc:
            continue

        stages.append({
            'stage_code': sc,
            'stage': current_stage,
            'label': label,
            'manual_jasa': round(jasa),
            'manual_oibu': round(oibu),
            'manual_total': round(total)
        })

    if stages:
        result[date_iso] = stages

with open('data/manual_forecast.json', 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print(f'Saved {len(result)} dates')
for d in sorted(result.keys()):
    total = sum(s['manual_total'] for s in result[d])
    stages = len(result[d])
    print(f'  {d}: {stages} rows, total={total:,}')
