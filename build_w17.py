# -*- coding: utf-8 -*-
import json, re, datetime

# Load forecast
with open('w17_forecast.json', 'r', encoding='utf-8') as f:
    forecast = json.load(f)

# Read W16 template (which has correct structure)
with open('monitor_w16.html', 'r', encoding='utf-8') as f:
    template = f.read()

# Build dailyReports structure for W17
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

# Update week references: W16 -> W17
new_html = new_html.replace('W16', 'W17')
new_html = new_html.replace('04-13 ~ 04-18', '04-20 ~ 04-25')
new_html = new_html.replace('04-13~04-18', '04-20~04-25')
new_html = new_html.replace('monitor_w16.html', 'monitor_w17.html')

# Replace W16 dates with W17 dates
w16_dates = ['2026-04-13', '2026-04-14', '2026-04-15', '2026-04-16', '2026-04-17', '2026-04-18']
w17_dates = ['2026-04-20', '2026-04-21', '2026-04-22', '2026-04-23', '2026-04-24', '2026-04-25']
w16_short = ['04-13', '04-14', '04-15', '04-16', '04-17', '04-18']
w17_short = ['04-20', '04-21', '04-22', '04-23', '04-24', '04-25']
dows = ['월', '화', '수', '목', '금', '토']
for i in range(6):
    new_html = new_html.replace(w16_dates[i], w17_dates[i])
    new_html = new_html.replace(f'{w16_short[i]}({dows[i]})', f'{w17_short[i]}({dows[i]})')

# Update generation timestamp
now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
new_html = re.sub(r'생성: \d{4}-\d{2}-\d{2} \d{2}:\d{2}', f'생성: {now}', new_html)

# Fix dropdown: restore all week options correctly
# The blanket replace W16->W17 corrupts the dropdown, so fix it
# Find and replace the entire select options block
new_html = re.sub(
    r'(<select id="weekSelector"[^>]*>)\s*'
    r'<option value="w12"[^>]*>[^<]*</option>\s*'
    r'<option value="w13"[^>]*>[^<]*</option>\s*'
    r'<option value="w14"[^>]*>[^<]*</option>\s*'
    r'<option value="w15"[^>]*>[^<]*</option>\s*'
    r'<option value="w16"[^>]*>[^<]*</option>\s*'
    r'(<option value="compare"[^>]*>[^<]*</option>)',
    r'''\1
    <option value="w12" >W12 (03-16 ~ 03-21)</option>
    <option value="w13" >W13 (03-23 ~ 03-28)</option>
    <option value="w14" >W14 (03-30 ~ 04-04)</option>
    <option value="w15" >W15 (04-06 ~ 04-11)</option>
    <option value="w16" >W16 (04-13 ~ 04-18)</option>
    <option value="w17" selected>W17 (04-20 ~ 04-25)</option>
    \2''',
    new_html,
    flags=re.DOTALL
)

# If regex didn't match (no w17 option yet), try simpler approach
if 'value="w17"' not in new_html:
    # Manual fix
    new_html = new_html.replace(
        '<option value="compare"',
        '<option value="w17" selected>W17 (04-20 ~ 04-25)</option>\n    <option value="compare"'
    )

with open('monitor_w17.html', 'w', encoding='utf-8') as f:
    f.write(new_html)

print(f"monitor_w17.html 생성 완료!")
print(f"dailyReports 일수: {len(daily_reports)}")
print(f"파일 크기: {len(new_html):,} bytes")
for d in daily_reports:
    print(f"  {d['date']} ({d['dow']}): planned={d['planned_total']:,}")
