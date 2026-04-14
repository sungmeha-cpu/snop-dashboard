import json, re

# Load forecast
with open('w15_forecast.json', 'r', encoding='utf-8') as f:
    forecast = json.load(f)

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
