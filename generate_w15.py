import json, re

# W12 기준 단계별 메뉴 수 (본 메뉴만)
STAGE_MENU_COUNTS = {
    '1110': 1, '1210': 2, '1220': 4, '1230': 5,
    '1240': 7, '1250': 7, '1310': 6, '1320': 6, '1330': 6
}

# W12 기준 단계별 구분 배분 (본/추가/케어)
STAGE_LABEL_SPLIT = {
    '1110': (1, 0, 0),   # 본1
    '1210': (1, 1, 0),   # 본1 + 추가1
    '1220': (2, 2, 0),   # 본2 + 추가2
    '1230': (2, 2, 1),   # 본2 + 추가2 + 케어1
    '1240': (3, 3, 1),   # 본3 + 추가3 + 케어1
    '1250': (3, 3, 1),   # 본3 + 추가3 + 케어1
    '1310': (3, 3, 0),   # 본3 + 추가3
    '1320': (3, 3, 0),   # 본3 + 추가3
    '1330': (3, 3, 0),   # 본3 + 추가3
}

def extract_reports(file):
    with open(file, 'r', encoding='utf-8') as f:
        html = f.read()
    match = re.search(r'const dailyReports = (\[.*?\]);', html, re.DOTALL)
    if not match:
        return []
    return json.loads(match.group(1))

w12 = extract_reports('monitor_w12.html')
w13 = extract_reports('monitor_w13.html')
w14 = extract_reports('monitor_w14.html')

# W12/W13에서 원본 label 매핑 구축 (W14는 label이 모두 '본'으로 잘못됨)
label_ref = {}
for week in [w12, w13]:
    for day in week:
        for m in day.get('menu_hits', []):
            key = (m['product_code'], m['stage_code'])
            lbl = m.get('label', '')
            if lbl and lbl != '본':
                label_ref[key] = lbl
            elif key not in label_ref:
                label_ref[key] = lbl or '본'

# Build per-DOW, per-menu actual data across weeks
weekly_by_dow = {}
for wi, week in enumerate([w12, w13, w14]):
    for day in week:
        dow = day['dow']
        if dow not in weekly_by_dow:
            weekly_by_dow[dow] = []
        menu_data = {}
        for m in day['menu_hits']:
            menu_data[m['product_code']] = m
        weekly_by_dow[dow].append({
            'week': f'W{12+wi}',
            'date': day['date'],
            'total_actual': day['actual_total'],
            'total_planned': day['planned_total'],
            'menus': menu_data
        })

dows = ['월','화','수','목','금','토']
w15_dates = ['2026-04-06','2026-04-07','2026-04-08','2026-04-09','2026-04-10','2026-04-11']

result = []

for di, dow in enumerate(dows):
    days = weekly_by_dow.get(dow, [])
    if not days:
        continue

    all_products = set()
    for d in days:
        all_products.update(d['menus'].keys())

    menu_forecasts = []

    for pc in all_products:
        actuals = [d['menus'][pc]['actual'] if pc in d['menus'] else 0 for d in days]
        actuals_jasa = [d['menus'][pc]['actual_jasa'] if pc in d['menus'] else 0 for d in days]
        actuals_oibu = [d['menus'][pc]['actual_oibu'] if pc in d['menus'] else 0 for d in days]
        planneds = [d['menus'][pc]['planned'] if pc in d['menus'] else 0 for d in days]

        # Get latest info
        info = None
        for i in range(len(days)-1, -1, -1):
            if pc in days[i]['menus']:
                info = days[i]['menus'][pc]
                break
        if not info:
            continue

        # Weighted average (recency bias: W12=1, W13=2, W14=3)
        weights = [i+1 for i in range(len(days))]
        total_weight = sum(weights)

        weighted_actual = round(sum(a*w for a,w in zip(actuals, weights)) / total_weight)
        weighted_jasa = round(sum(a*w for a,w in zip(actuals_jasa, weights)) / total_weight)
        weighted_oibu = round(sum(a*w for a,w in zip(actuals_oibu, weights)) / total_weight)

        # Trend analysis
        trend = 0
        if len(actuals) >= 2 and actuals[-2] > 0:
            trend = (actuals[-1] - actuals[-2]) / actuals[-2]

        # Also check plan-vs-actual bias to correct systematic over/under prediction
        valid_ratios = []
        for i in range(len(days)):
            if pc in days[i]['menus'] and planneds[i] > 0:
                valid_ratios.append(actuals[i] / planneds[i])
        avg_ratio = sum(valid_ratios) / len(valid_ratios) if valid_ratios else 1.0

        # Apply mild trend (cap at +/-10%)
        trend_factor = 1 + max(-0.1, min(0.1, trend * 0.3))

        forecast = max(1, round(weighted_actual * trend_factor))
        forecast_jasa = max(0, round(weighted_jasa * trend_factor))
        forecast_oibu = max(0, round(weighted_oibu * trend_factor))

        # Ensure total matches
        if forecast_jasa + forecast_oibu != forecast:
            forecast_oibu = forecast - forecast_jasa
            if forecast_oibu < 0:
                forecast_oibu = 0
                forecast_jasa = forecast

        # W12/W13 원본 label 참조 (W14는 label이 모두 '본'으로 잘못되어 있음)
        original_label = label_ref.get((info['product_code'], info['stage_code']), info.get('label', '본'))

        menu_forecasts.append({
            'stage_code': info['stage_code'],
            'stage': info['stage'],
            'product_code': info['product_code'],
            'product_name': info['product_name'],
            'label': original_label,
            'planned': forecast,
            'planned_jasa': forecast_jasa,
            'planned_oibu': forecast_oibu,
        })

    # W12 기준 단계별 메뉴 수로 제한: 상위 N개만 유지, 나머지 수량은 비례배분
    from collections import defaultdict
    stage_menus = defaultdict(list)
    for m in menu_forecasts:
        stage_menus[m['stage_code']].append(m)

    trimmed = []
    for sc, menus in stage_menus.items():
        max_count = STAGE_MENU_COUNTS.get(sc, len(menus))
        # planned 기준 내림차순 정렬 후 상위 N개 선택
        menus.sort(key=lambda x: -x['planned'])
        kept = menus[:max_count]
        dropped = menus[max_count:]

        if dropped and kept:
            # 제외 메뉴의 수량을 유지 메뉴에 비례배분
            extra_total = sum(d['planned'] for d in dropped)
            extra_jasa = sum(d['planned_jasa'] for d in dropped)
            extra_oibu = sum(d['planned_oibu'] for d in dropped)
            kept_total = sum(k['planned'] for k in kept)
            if kept_total > 0:
                for k in kept:
                    ratio = k['planned'] / kept_total
                    k['planned'] += round(extra_total * ratio)
                    k['planned_jasa'] += round(extra_jasa * ratio)
                    k['planned_oibu'] += round(extra_oibu * ratio)
                    # 합계 보정
                    if k['planned_jasa'] + k['planned_oibu'] != k['planned']:
                        k['planned_oibu'] = k['planned'] - k['planned_jasa']
                        if k['planned_oibu'] < 0:
                            k['planned_oibu'] = 0
                            k['planned_jasa'] = k['planned']

        # W12/W13 원본 label이 없는 경우 단계별 규칙으로 label 배분
        has_non_bon = any(k['label'] not in ('본', '') for k in kept)
        if not has_non_bon:
            bon_cnt, chuga_cnt, care_cnt = STAGE_LABEL_SPLIT.get(sc, (len(kept), 0, 0))
            for idx, k in enumerate(kept):  # already sorted by -planned
                if idx < bon_cnt:
                    k['label'] = '본'
                elif idx < bon_cnt + chuga_cnt:
                    k['label'] = '추가'
                else:
                    k['label'] = '케어'

        trimmed.extend(kept)

    menu_forecasts = trimmed

    # Sort
    menu_forecasts.sort(key=lambda m: (m['stage_code'], -m['planned']))

    # Stage totals
    stage_map = {}
    for m in menu_forecasts:
        sc = m['stage_code']
        if sc not in stage_map:
            stage_map[sc] = {'stage_code': sc, 'stage': m['stage'], 'planned': 0}
        stage_map[sc]['planned'] += m['planned']

    total_planned = sum(m['planned'] for m in menu_forecasts)
    total_jasa = sum(m['planned_jasa'] for m in menu_forecasts)
    total_oibu = sum(m['planned_oibu'] for m in menu_forecasts)

    # Channel hits
    channel_hits = [
        {'channel': '자사몰', 'planned': total_jasa},
        {'channel': '외부몰', 'planned': total_oibu}
    ]

    result.append({
        'date': w15_dates[di],
        'dow': dow,
        'planned_total': total_planned,
        'planned_jasa': total_jasa,
        'planned_oibu': total_oibu,
        'stages': sorted(stage_map.values(), key=lambda s: s['stage_code']),
        'channels': channel_hits,
        'menus': menu_forecasts
    })

with open('w15_forecast.json', 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print('=== W15 예측 요약 ===')
for d in result:
    print(f"{d['date']} ({d['dow']}): 총 {d['planned_total']:,}개 (자사몰: {d['planned_jasa']:,}, 외부몰: {d['planned_oibu']:,})")
    for s in d['stages']:
        print(f"  {s['stage']}: {s['planned']:,}")
    print()

print(f"메뉴 수: {[len(d['menus']) for d in result]}")

# Print some key accuracy analysis from W14
print("\n=== W14 예측 정확도 분석 (개선 참고) ===")
for day in w14:
    over = [m for m in day['menu_hits'] if m['status'] == 'over']
    under = [m for m in day['menu_hits'] if m['status'] == 'under']
    normal = [m for m in day['menu_hits'] if m['status'] == 'normal']
    print(f"{day['date']} ({day['dow']}): 적중 {len(normal)}, 과다 {len(over)}, 과소 {len(under)}, 적중률 {day['total_hit_rate']}%")
