# -*- coding: utf-8 -*-
"""
W16 (2026-04-13 ~ 2026-04-18) 예측 생성
W12~W15 실적 기반, 가중평균(최근 주차 가중치 높게)
W14 목/금/토는 실적=0이므로 해당 요일은 W12/W13/W15만 사용
"""
import json, re, sys, os
from collections import defaultdict
sys.stdout.reconfigure(encoding='utf-8')

base = 'C:/Users/muse23031801/AppData/Local/Temp/snop-dashboard'

# ── W12/W13/W14 monitor에서 실적 추출 ──
def extract_reports(file):
    with open(f'{base}/{file}', 'r', encoding='utf-8') as f:
        html = f.read()
    m = re.search(r'const dailyReports = (\[.*?\]);', html, re.DOTALL)
    return json.loads(m.group(1)) if m else []

w12 = extract_reports('monitor_w12.html')
w13 = extract_reports('monitor_w13.html')
w14 = extract_reports('monitor_w14.html')

# ── W15 실적은 parsed XLS에서 ──
w15_parsed = {}
for fname, date in [
    ('parsed_0406.json','2026-04-06'), ('parsed_0407.json','2026-04-07'),
    ('parsed_0408.json','2026-04-08'), ('parsed_0409.json','2026-04-09'),
    ('parsed_0410.json','2026-04-10'), ('parsed_0411.json','2026-04-11'),
]:
    with open(f'{base}/{fname}', 'r', encoding='utf-8') as f:
        w15_parsed[date] = json.load(f)

dows = ['월','화','수','목','금','토']
w16_dates = ['2026-04-13','2026-04-14','2026-04-15','2026-04-16','2026-04-17','2026-04-18']

# ── 요일별 주간 데이터 수집 ──
weekly_by_dow = defaultdict(list)

# W12/W13 (always have full data)
for wi, week in enumerate([w12, w13]):
    wk_name = f'W{12+wi}'
    for day in week:
        dow = day['dow']
        menu_data = {}
        for m in day['menu_hits']:
            menu_data[m['product_code']] = {
                'actual': m.get('actual', 0),
                'actual_jasa': m.get('actual_jasa', 0),
                'actual_oibu': m.get('actual_oibu', 0),
            }
        total_actual = day.get('actual_total', 0)
        if total_actual > 0:
            weekly_by_dow[dow].append({
                'week': wk_name, 'date': day['date'],
                'total_actual': total_actual,
            })

# W14 (only mon/tue/wed have data)
for day in w14:
    dow = day['dow']
    total_actual = day.get('actual_total', 0)
    if total_actual > 0:
        weekly_by_dow[dow].append({
            'week': 'W14', 'date': day['date'],
            'total_actual': total_actual,
        })

# W15 from parsed XLS
dow_map = {
    '2026-04-06':'월','2026-04-07':'화','2026-04-08':'수',
    '2026-04-09':'목','2026-04-10':'금','2026-04-11':'토',
}
for date, menus in w15_parsed.items():
    dow = dow_map[date]
    total = sum(m['qty'] for m in menus)
    weekly_by_dow[dow].append({
        'week': 'W15', 'date': date,
        'total_actual': total,
    })

print('=== 요일별 가용 데이터 ===')
for dow in dows:
    entries = weekly_by_dow[dow]
    info = ', '.join(f'{e["week"]}({e["date"]})={e["total_actual"]:,}' for e in entries)
    print(f'{dow}: {len(entries)}주 - {info}')

# ── W16 예측: 요일별 총량을 가중평균으로 산출 ──
result = []

for di, (dow, date) in enumerate(zip(dows, w16_dates)):
    entries = weekly_by_dow[dow]
    if not entries:
        print(f'{date} ({dow}): 데이터 없음, skip')
        continue

    # Weighted average: 오래된 주→낮은 가중치, 최근→높은 가중치
    weights = list(range(1, len(entries) + 1))
    total_weight = sum(weights)
    forecast_total = round(sum(e['total_actual'] * w for e, w in zip(entries, weights)) / total_weight)

    # W15 메뉴 구성을 사용 (가장 최근 해당 요일의 메뉴)
    w15_date = list(dow_map.keys())[list(dow_map.values()).index(dow)]
    menus_template = w15_parsed[w15_date]
    template_total = sum(m['qty'] for m in menus_template)

    # 메뉴별 비율로 배분
    new_menus = []
    stage_totals = defaultdict(int)

    for m in menus_template:
        if template_total > 0:
            ratio = m['qty'] / template_total
        else:
            ratio = 1.0 / len(menus_template)

        menu_planned = max(1, round(forecast_total * ratio))
        total_jo = m.get('jasa', 0) + m.get('oibu', 0)
        if total_jo > 0:
            jasa_ratio = m.get('jasa', 0) / total_jo
        else:
            jasa_ratio = 0.9

        menu_jasa = round(menu_planned * jasa_ratio)
        menu_oibu = menu_planned - menu_jasa

        new_menus.append({
            'stage_code': m['stage_code'],
            'stage': m['stage'],
            'product_code': m['product_code'],
            'product_name': m['product_name'],
            'label': m.get('label', '본'),
            'planned': menu_planned,
            'planned_jasa': menu_jasa,
            'planned_oibu': menu_oibu,
        })
        stage_totals[m['stage_code']] += menu_planned

    total_planned = sum(m['planned'] for m in new_menus)
    total_jasa = sum(m['planned_jasa'] for m in new_menus)
    total_oibu = sum(m['planned_oibu'] for m in new_menus)

    stages = []
    STAGE_MAP = {'1110':'준비기','1210':'초기1','1220':'초기2','1230':'중기','1240':'후기','1250':'후기무른밥','1310':'영양밥','1320':'영양국','1330':'영양찬'}
    for sc in sorted(stage_totals.keys()):
        stages.append({
            'stage_code': sc,
            'stage': STAGE_MAP.get(sc, sc),
            'planned': stage_totals[sc]
        })

    result.append({
        'date': date,
        'dow': dow,
        'planned_total': total_planned,
        'planned_jasa': total_jasa,
        'planned_oibu': total_oibu,
        'stages': stages,
        'channels': [
            {'channel': '자사몰', 'planned': total_jasa},
            {'channel': '외부몰', 'planned': total_oibu}
        ],
        'menus': new_menus
    })

# Save
with open(f'{base}/w16_forecast.json', 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print('\n=== W16 예측 요약 ===')
for d in result:
    print(f"{d['date']} ({d['dow']}): 총 {d['planned_total']:,}개 (자사몰: {d['planned_jasa']:,}, 외부몰: {d['planned_oibu']:,})")
    for s in d['stages']:
        print(f"  {s['stage']}: {s['planned']:,}")
    print()

print(f"메뉴 수: {[len(d['menus']) for d in result]}")
