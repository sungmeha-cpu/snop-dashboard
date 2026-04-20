# -*- coding: utf-8 -*-
"""
W18 (2026-04-27 ~ 2026-04-30) 예측 생성
W12~W16 실적 기반, 가중평균 + 성장률 50% 반영
5/1(금, 근로자의날) · 5/2(토) 휴무 → 대체배송 반영

대체배송 로직:
- 4/27(월): 정상 출고
- 4/28(화): 정상 + 금/토 대체분 30%
- 4/29(수): 정상 + 금/토 대체분 35%
- 4/30(목): 정상 + 금/토 대체분 35%
"""
import json, re, sys
from collections import defaultdict
sys.stdout.reconfigure(encoding='utf-8')

base = 'C:/Users/muse23031801/AppData/Local/Temp/snop-dashboard'

# ── monitor HTML에서 실적 추출 ──
def extract_reports(file):
    with open(f'{base}/{file}', 'r', encoding='utf-8') as f:
        html = f.read()
    m = re.search(r'const dailyReports = (\[.*?\]);', html, re.DOTALL)
    return json.loads(m.group(1)) if m else []

w12 = extract_reports('monitor_w12.html')
w13 = extract_reports('monitor_w13.html')
w14 = extract_reports('monitor_w14.html')
w15 = extract_reports('monitor_w15.html')
w16 = extract_reports('monitor_w16.html')
w17 = extract_reports('monitor_w17.html')

# ── W15 실적: parsed XLS ──
w15_parsed = {}
for fname, date in [
    ('parsed_0406.json','2026-04-06'), ('parsed_0407.json','2026-04-07'),
    ('parsed_0408.json','2026-04-08'), ('parsed_0409.json','2026-04-09'),
    ('parsed_0410.json','2026-04-10'), ('parsed_0411.json','2026-04-11'),
]:
    with open(f'{base}/{fname}', 'r', encoding='utf-8') as f:
        w15_parsed[date] = json.load(f)

# ── actual.json (W14, W16 등) ──
with open(f'{base}/data/actual.json', 'r', encoding='utf-8') as f:
    actual_data = json.load(f)

dows = ['월','화','수','목','금','토']
w18_dates = ['2026-04-27','2026-04-28','2026-04-29','2026-04-30']
w18_dows  = ['월','화','수','목']

# ── 요일별 주간 데이터 수집 ──
weekly_by_dow = defaultdict(list)

# W12/W13 from monitor
for wi, week in enumerate([w12, w13]):
    wk_name = f'W{12+wi}'
    for day in week:
        dow = day['dow']
        total_actual = day.get('actual_total', 0)
        if total_actual > 0:
            weekly_by_dow[dow].append({
                'week': wk_name, 'date': day['date'],
                'total_actual': total_actual,
            })

# W14 from monitor
for day in w14:
    dow = day['dow']
    total_actual = day.get('actual_total', 0)
    if total_actual > 0:
        weekly_by_dow[dow].append({
            'week': 'W14', 'date': day['date'],
            'total_actual': total_actual,
        })

# W15 from parsed XLS
w15_dow_map = {
    '2026-04-06':'월','2026-04-07':'화','2026-04-08':'수',
    '2026-04-09':'목','2026-04-10':'금','2026-04-11':'토',
}
for date, menus in w15_parsed.items():
    dow = w15_dow_map[date]
    total = sum(m['qty'] for m in menus)
    weekly_by_dow[dow].append({
        'week': 'W15', 'date': date,
        'total_actual': total,
    })

# W16 from actual.json
w16_date_range = ['2026-04-13','2026-04-14','2026-04-15','2026-04-16','2026-04-17','2026-04-18']
w16_dow_map = {
    '2026-04-13':'월','2026-04-14':'화','2026-04-15':'수',
    '2026-04-16':'목','2026-04-17':'금','2026-04-18':'토',
}
for date in w16_date_range:
    if date in actual_data and len(actual_data[date]) > 0:
        dow = w16_dow_map[date]
        total = sum(m['qty'] for m in actual_data[date])
        if total > 0:
            weekly_by_dow[dow].append({
                'week': 'W16', 'date': date,
                'total_actual': total,
            })

# W16 from monitor (if actual.json didn't have it)
for day in w16:
    dow = day['dow']
    total_actual = day.get('actual_total', 0)
    if total_actual > 0:
        existing_dates = [e['date'] for e in weekly_by_dow[dow]]
        if day['date'] not in existing_dates:
            weekly_by_dow[dow].append({
                'week': 'W16m', 'date': day['date'],
                'total_actual': total_actual,
            })

# W17 from monitor (if actual data uploaded)
for day in w17:
    dow = day['dow']
    total_actual = day.get('actual_total', 0)
    if total_actual > 0:
        weekly_by_dow[dow].append({
            'week': 'W17', 'date': day['date'],
            'total_actual': total_actual,
        })

print('=== 요일별 가용 데이터 ===')
for dow in dows:
    entries = weekly_by_dow[dow]
    info = ', '.join(f'{e["week"]}({e["date"]})={e["total_actual"]:,}' for e in entries)
    print(f'{dow}: {len(entries)}주 - {info}')

# ── 메뉴 템플릿: 가장 최근 실적의 메뉴 구성 사용 ──
def get_menu_template(dow):
    """해당 요일의 가장 최근 실적 메뉴 구성 반환"""
    # W17 monitor에서 planned 메뉴 사용 (실적이 없어도 메뉴 구성 참조)
    for day in w17:
        if day['dow'] == dow:
            menus = day.get('menu_hits', [])
            if menus:
                return [{'stage_code': m['stage_code'], 'stage': m['stage'],
                         'product_code': m['product_code'], 'product_name': m['product_name'],
                         'label': m.get('label','본'),
                         'qty': m.get('actual', 0) if m.get('actual', 0) > 0 else m.get('planned', 0),
                         'jasa': m.get('actual_jasa', 0) if m.get('actual_jasa', 0) > 0 else m.get('planned_jasa', 0),
                         'oibu': m.get('actual_oibu', 0) if m.get('actual_oibu', 0) > 0 else m.get('planned_oibu', 0)} for m in menus]
    # W16 actual.json
    for date, d in w16_dow_map.items():
        if d == dow and date in actual_data:
            menus = actual_data[date]
            return [{'stage_code': m['stage_code'], 'stage': m['stage'],
                     'product_code': m['product_code'], 'product_name': m['product_name'],
                     'label': m.get('label','본'), 'qty': m['qty'],
                     'jasa': m.get('jasa',0), 'oibu': m.get('oibu',0)} for m in menus]
    # W15 parsed
    for date, d in w15_dow_map.items():
        if d == dow and date in w15_parsed:
            return w15_parsed[date]
    return []

# ── W18 예측 ──
STAGE_MAP = {
    '1110':'준비기','1210':'초기1','1220':'초기2','1230':'중기',
    '1240':'후기','1250':'후기무른밥','1310':'영양밥','1320':'영양국','1330':'영양찬'
}
STAGE_MENU_COUNTS = {
    '1110': 1, '1210': 2, '1220': 4, '1230': 5,
    '1240': 7, '1250': 7, '1310': 6, '1320': 6, '1330': 6
}

# ── 먼저 월~토 정상 예측값 계산 ──
normal_forecast_by_dow = {}
for dow in dows:
    entries = weekly_by_dow[dow]
    if not entries:
        normal_forecast_by_dow[dow] = 0
        continue
    weights = list(range(1, len(entries) + 1))
    total_weight = sum(weights)
    forecast_total = round(sum(e['total_actual'] * w for e, w in zip(entries, weights)) / total_weight)
    if len(entries) >= 2:
        last = entries[-1]['total_actual']
        prev = entries[-2]['total_actual']
        if prev > 0:
            growth_rate = (last - prev) / prev
            forecast_total = round(forecast_total * (1 + growth_rate * 0.5))
    normal_forecast_by_dow[dow] = forecast_total

print('\n=== 요일별 정상 예측 (대체배송 적용 전) ===')
for dow in dows:
    print(f'  {dow}: {normal_forecast_by_dow[dow]:,}')

# ── 대체배송 물량 재분배 ──
# 5/1(금), 5/2(토) 휴무 → 금/토 출고량이 4/28~4/30으로 분산
# 배분 비율 (이미지 배송일정 기반):
#   4/28(화): 일반배송 월/수/금 3세트 + 화/목/금 5세트 → 대체분 30%
#   4/29(수): 클레 매일 2세트/월수금 3세트 + 일반 월/수/금 4세트 → 대체분 35%
#   4/30(목): 클레 매일 3세트/화목토 3세트 + 일반 화/목/금 4세트 → 대체분 35%

fri_sat_extra = normal_forecast_by_dow['금'] + normal_forecast_by_dow['토']
print(f'\n=== 대체배송 물량 ===')
print(f'  금요일 정상 예측: {normal_forecast_by_dow["금"]:,}')
print(f'  토요일 정상 예측: {normal_forecast_by_dow["토"]:,}')
print(f'  금+토 합계 (대체 대상): {fri_sat_extra:,}')

SUBSTITUTE_RATIOS = {
    '화': 0.30,  # 4/28: 30%
    '수': 0.35,  # 4/29: 35%
    '목': 0.35,  # 4/30: 35%
}

adjusted_forecast = {}
for dow in w18_dows:
    base_vol = normal_forecast_by_dow[dow]
    extra = round(fri_sat_extra * SUBSTITUTE_RATIOS.get(dow, 0))
    adjusted_forecast[dow] = base_vol + extra
    if extra > 0:
        print(f'  {dow}: {base_vol:,} + 대체 {extra:,} = {adjusted_forecast[dow]:,}')
    else:
        print(f'  {dow}: {base_vol:,} (정상)')

print(f'  W18 합계: {sum(adjusted_forecast.values()):,}')

# ── 일별 예측 생성 ──
result = []

for di, (dow, date) in enumerate(zip(w18_dows, w18_dates)):
    forecast_total = adjusted_forecast[dow]

    # 메뉴 템플릿
    menus_template = get_menu_template(dow)
    if not menus_template:
        print(f'  {date}: 메뉴 템플릿 없음!')
        continue

    # 단계별 메뉴 수 트리밍 (44개 표준)
    by_stage = defaultdict(list)
    for m in menus_template:
        by_stage[m['stage_code']].append(m)
    trimmed_template = []
    for sc, items in by_stage.items():
        max_count = STAGE_MENU_COUNTS.get(sc, len(items))
        items.sort(key=lambda x: -x['qty'])
        kept = items[:max_count]
        dropped = items[max_count:]
        if dropped and kept:
            extra_qty = sum(d['qty'] for d in dropped)
            kept_total = sum(k['qty'] for k in kept)
            if kept_total > 0:
                for k in kept:
                    ratio = k['qty'] / kept_total
                    k['qty'] += round(extra_qty * ratio)
                    k_total = k.get('jasa', 0) + k.get('oibu', 0)
                    if k_total > 0:
                        k['jasa'] += round(extra_qty * ratio * k.get('jasa', 0) / k_total)
                        k['oibu'] += round(extra_qty * ratio * k.get('oibu', 0) / k_total)
        trimmed_template.extend(kept)
    menus_template = trimmed_template

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
with open(f'{base}/w18_forecast.json', 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print('\n=== W18 예측 요약 (대체배송 반영) ===')
week_total = 0
for d in result:
    week_total += d['planned_total']
    substitute_note = ''
    if d['dow'] in SUBSTITUTE_RATIOS:
        substitute_note = f' ★대체배송 {SUBSTITUTE_RATIOS[d["dow"]]*100:.0f}% 포함'
    print(f"{d['date']} ({d['dow']}): 총 {d['planned_total']:,}개 (자사몰: {d['planned_jasa']:,}, 외부몰: {d['planned_oibu']:,}){substitute_note}")
    for s in d['stages']:
        print(f"  {s['stage']}: {s['planned']:,}")
    print()

print(f"W18 주간 합계: {week_total:,}개")
print(f"메뉴 수: {[len(d['menus']) for d in result]}")
print(f"\n참고: 5/1(금) 근로자의날, 5/2(토) 휴무로 금/토 출고분({fri_sat_extra:,}개)이 4/28~4/30에 분산됨")
