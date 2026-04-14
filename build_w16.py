# -*- coding: utf-8 -*-
import json, re, datetime

# Load forecast
with open('w16_forecast.json', 'r', encoding='utf-8') as f:
    forecast = json.load(f)

# Read W15 template (which has correct structure)
with open('monitor_w15.html', 'r', encoding='utf-8') as f:
    template = f.read()

# Build dailyReports structure for W16
daily_reports = []
for day in forecast:
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

    channel_hits = [
        {'channel': '자사몰', 'planned': day['planned_jasa'], 'actual': 0, 'hit_rate': 0.0},
        {'channel': '외부몰', 'planned': day['planned_oibu'], 'actual': 0, 'hit_rate': 0.0}
    ]

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

reports_json = json.dumps(daily_reports, ensure_ascii=False)

# Replace dailyReports in template
new_html = re.sub(
    r'const dailyReports = \[.*?\];',
    f'const dailyReports = {reports_json};',
    template,
    flags=re.DOTALL
)

# Update week references: W15 -> W16
new_html = new_html.replace('W15', 'W16')
new_html = new_html.replace('04-06 ~ 04-11', '04-13 ~ 04-18')
new_html = new_html.replace('04-06~04-11', '04-13~04-18')
new_html = new_html.replace('monitor_w15.html', 'monitor_w16.html')

# Replace W15 dates with W16 dates
w15_dates = ['2026-04-06', '2026-04-07', '2026-04-08', '2026-04-09', '2026-04-10', '2026-04-11']
w16_dates = ['2026-04-13', '2026-04-14', '2026-04-15', '2026-04-16', '2026-04-17', '2026-04-18']
w15_short = ['04-06', '04-07', '04-08', '04-09', '04-10', '04-11']
w16_short = ['04-13', '04-14', '04-15', '04-16', '04-17', '04-18']
dows = ['월', '화', '수', '목', '금', '토']
for i in range(6):
    new_html = new_html.replace(w15_dates[i], w16_dates[i])
    new_html = new_html.replace(f'{w15_short[i]}({dows[i]})', f'{w16_short[i]}({dows[i]})')

# Update generation timestamp
now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
new_html = re.sub(r'생성: \d{4}-\d{2}-\d{2} \d{2}:\d{2}', f'생성: {now}', new_html)

# Fix nav: restore W15 link (don't rename it to W16)
new_html = new_html.replace("'W16': 'monitor_w14.html'", "'W15': 'monitor_w15.html'")

with open('monitor_w16.html', 'w', encoding='utf-8') as f:
    f.write(new_html)

print(f"monitor_w16.html 생성 완료!")
print(f"dailyReports 일수: {len(daily_reports)}")
print(f"파일 크기: {len(new_html):,} bytes")
for d in daily_reports:
    print(f"  {d['date']} ({d['dow']}): planned={d['planned_total']:,}")
