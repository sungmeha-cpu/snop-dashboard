import json, re

# Load forecast
with open('w15_forecast.json', 'r', encoding='utf-8') as f:
    forecast = json.load(f)

# Load actual data
with open('data/actual.json', 'r', encoding='utf-8') as f:
    actual_data = json.load(f)

# Read W14 template
with open('monitor_w14.html', 'r', encoding='utf-8') as f:
    template = f.read()

# Build dailyReports structure for W15
daily_reports = []
for day in forecast:
    # Build stage_hits (no actuals yet, so actual=0)
    stage_hits = []
    for s in day['stages']:
        stage_hits.append({
            'stage_code': s['stage_code'],
            'stage': s['stage'],
            'planned': s['planned'],
            'actual': 0,
            'hit_rate': 0.0,
            'ratio': 0.0,
            'status': 'normal'
        })

    # Build channel_hits
    channel_hits = [
        {'channel': '자사몰', 'planned': day['planned_jasa'], 'actual': 0, 'hit_rate': 0.0},
        {'channel': '외부몰', 'planned': day['planned_oibu'], 'actual': 0, 'hit_rate': 0.0}
    ]

    # Build menu_hits
    menu_hits = []
    for m in day['menus']:
        menu_hits.append({
            'stage_code': m['stage_code'],
            'stage': m['stage'],
            'product_code': m['product_code'],
            'product_name': m['product_name'],
            'label': m['label'],
            'planned': m['planned'],
            'planned_jasa': m['planned_jasa'],
            'planned_oibu': m['planned_oibu'],
            'actual': 0,
            'actual_jasa': 0,
            'actual_oibu': 0,
            'hit_rate': 0.0,
            'ratio': 0.0,
            'status': 'normal'
        })

    daily_reports.append({
        'date': day['date'],
        'dow': day['dow'],
        'planned_total': day['planned_total'],
        'actual_total': 0,
        'total_hit_rate': 0.0,
        'stage_hits': stage_hits,
        'channel_hits': channel_hits,
        'menu_hits': menu_hits
    })

# Merge actual data from actual.json
for dr in daily_reports:
    date_str = dr['date']
    if date_str not in actual_data:
        continue
    menus = actual_data[date_str]

    # 실적 집계
    total_actual = 0
    stage_actual = {}
    ch_jasa = 0
    ch_oibu = 0
    for m in menus:
        total_actual += m['qty']
        stage_actual[m['stage']] = stage_actual.get(m['stage'], 0) + m['qty']
        ch_jasa += m.get('jasa', 0)
        ch_oibu += m.get('oibu', 0)

    dr['actual_total'] = total_actual

    # 메뉴별 매칭
    matched = set()
    for mh in dr['menu_hits']:
        match = next((m for m in menus if m['stage_code'] == mh['stage_code'] and m['product_code'] == mh['product_code']), None)
        if match:
            mh['actual'] = match['qty']
            mh['actual_jasa'] = match.get('jasa', 0)
            mh['actual_oibu'] = match.get('oibu', 0)
            matched.add(match['product_code'] + '_' + match['stage_code'])
        else:
            mh['actual'] = 0
            mh['actual_jasa'] = 0
            mh['actual_oibu'] = 0
        if mh['planned'] > 0:
            mh['hit_rate'] = round(min(mh['actual'] / mh['planned'], mh['planned'] / max(mh['actual'], 1)) * 1000) / 10
        else:
            mh['hit_rate'] = 0.0
        if mh['actual'] == 0:
            mh['status'] = 'fail'
        elif mh['actual'] > mh['planned']:
            mh['status'] = 'over'
        elif mh['hit_rate'] >= 90:
            mh['status'] = 'normal'
        elif mh['hit_rate'] >= 70:
            mh['status'] = 'under'
        else:
            mh['status'] = 'fail'

    # 계획에 없는 실적 상품 추가
    for m in menus:
        key = m['product_code'] + '_' + m['stage_code']
        if key not in matched:
            dr['menu_hits'].append({
                'stage_code': m['stage_code'], 'stage': m['stage'],
                'product_code': m['product_code'], 'product_name': m['product_name'],
                'label': m.get('label', ''), 'planned': 0, 'planned_jasa': 0, 'planned_oibu': 0,
                'actual': m['qty'], 'actual_jasa': m.get('jasa', 0), 'actual_oibu': m.get('oibu', 0),
                'hit_rate': 0.0, 'ratio': 999.9, 'status': 'over'
            })

    # 단계별
    for sh in dr['stage_hits']:
        sh['actual'] = stage_actual.get(sh['stage'], 0)
        if sh['planned'] > 0:
            sh['hit_rate'] = round(min(sh['actual'] / sh['planned'], sh['planned'] / max(sh['actual'], 1)) * 1000) / 10
        else:
            sh['hit_rate'] = 0.0
        if sh['actual'] == 0:
            sh['status'] = 'fail'
        elif sh['actual'] > sh['planned']:
            sh['status'] = 'over'
        elif sh['hit_rate'] >= 90:
            sh['status'] = 'normal'
        elif sh['hit_rate'] >= 70:
            sh['status'] = 'under'
        else:
            sh['status'] = 'fail'

    # 채널별
    for ch in dr['channel_hits']:
        if ch['channel'] == '자사몰':
            ch['actual'] = ch_jasa
        elif ch['channel'] == '외부몰':
            ch['actual'] = ch_oibu
        if ch['planned'] > 0:
            ch['hit_rate'] = round(min(ch['actual'] / ch['planned'], ch['planned'] / max(ch['actual'], 1)) * 1000) / 10
        else:
            ch['hit_rate'] = 0.0

    # 전체 적중률
    if dr['planned_total'] > 0:
        dr['total_hit_rate'] = round(min(total_actual / dr['planned_total'], dr['planned_total'] / max(total_actual, 1)) * 1000) / 10
    else:
        dr['total_hit_rate'] = 0.0

# Convert to JSON string
reports_json = json.dumps(daily_reports, ensure_ascii=False)

# Replace dailyReports in template
new_html = re.sub(
    r'const dailyReports = \[.*?\];',
    f'const dailyReports = {reports_json};',
    template,
    flags=re.DOTALL
)

# Update week title references: W14 -> W15, date range
new_html = new_html.replace('W14', 'W15')
new_html = new_html.replace('03-30 ~ 04-04', '04-06 ~ 04-11')
new_html = new_html.replace('03-30~04-04', '04-06~04-11')
new_html = new_html.replace('monitor_w14.html', 'monitor_w15.html')

# W14 날짜 → W15 날짜 치환 (탭 버튼, tab-div id 등)
w14_dates = ['2026-03-30', '2026-03-31', '2026-04-01', '2026-04-02', '2026-04-03', '2026-04-04']
w15_dates = ['2026-04-06', '2026-04-07', '2026-04-08', '2026-04-09', '2026-04-10', '2026-04-11']
w14_short = ['03-30', '03-31', '04-01', '04-02', '04-03', '04-04']
w15_short = ['04-06', '04-07', '04-08', '04-09', '04-10', '04-11']
dows = ['월', '화', '수', '목', '금', '토']
for i in range(6):
    new_html = new_html.replace(w14_dates[i], w15_dates[i])
    new_html = new_html.replace(f'{w14_short[i]}({dows[i]})', f'{w15_short[i]}({dows[i]})')

# 생성 시각 업데이트
import datetime
now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
new_html = re.sub(r'생성: \d{4}-\d{2}-\d{2} \d{2}:\d{2}', f'생성: {now}', new_html)

# Fix any navigation references
# Don't change the nav links to other weeks
new_html = new_html.replace("'W15': 'monitor_w13.html'", "'W14': 'monitor_w14.html'")

with open('monitor_w15.html', 'w', encoding='utf-8') as f:
    f.write(new_html)

print(f"monitor_w15.html 생성 완료!")
print(f"dailyReports 일수: {len(daily_reports)}")
print(f"파일 크기: {len(new_html):,} bytes")

# Verify dates
for d in daily_reports:
    print(f"  {d['date']} ({d['dow']}): planned={d['planned_total']:,}")
