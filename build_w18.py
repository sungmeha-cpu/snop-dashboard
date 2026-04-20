# -*- coding: utf-8 -*-
"""
W18 (2026-04-27 ~ 2026-04-30) 모니터 HTML 빌드
5/1(금)·5/2(토) 휴무, 대체배송 반영 4일 구성
"""
import json, re, datetime

base = 'C:/Users/muse23031801/AppData/Local/Temp/snop-dashboard'

# Load forecast
with open(f'{base}/w18_forecast.json', 'r', encoding='utf-8') as f:
    forecast = json.load(f)

# Read W17 template
with open(f'{base}/monitor_w17.html', 'r', encoding='utf-8') as f:
    template = f.read()

# Build dailyReports structure for W18
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

# ── Update week references: W17 -> W18 ──
new_html = new_html.replace('W17 Executive Summary', 'W18 Executive Summary')
new_html = new_html.replace('W17 계획 총 107,901병 배포 완료. 실적 업로드 대기 중.',
                            'W18 계획 총 {:,}병 배포 완료 (대체배송 반영). 5/1(금)·5/2(토) 휴무로 금/토분이 4/28~4/30에 분산.'.format(
                                sum(d['planned_total'] for d in forecast)))

# Title
new_html = new_html.replace(
    'S&OP 적중률 모니터링 — W17 2026-04-20 ~ 2026-04-25',
    'S&OP 적중률 모니터링 — W18 2026-04-27 ~ 2026-04-30'
)

# ── Replace W17 dates with W18 dates ──
w17_dates = ['2026-04-20','2026-04-21','2026-04-22','2026-04-23','2026-04-24','2026-04-25']
w18_dates = ['2026-04-27','2026-04-28','2026-04-29','2026-04-30']
w17_short = ['04-20','04-21','04-22','04-23','04-24','04-25']
w18_short = ['04-27','04-28','04-29','04-30']
w17_dows = ['월','화','수','목','금','토']
w18_dows = ['월','화','수','목']

for i in range(6):
    if i < 4:
        new_html = new_html.replace(w17_dates[i], w18_dates[i])
        new_html = new_html.replace(f'{w17_short[i]}({w17_dows[i]})', f'{w18_short[i]}({w18_dows[i]})')
    else:
        # Remove W17 금/토 date references (tabs, table rows for unused days)
        new_html = new_html.replace(w17_dates[i], '')
        new_html = new_html.replace(f'{w17_short[i]}({w17_dows[i]})', '')

# ── Remove Friday/Saturday daily tab buttons ──
# Remove nav buttons for 금/토 (days 5, 6 of W17 which don't exist in W18)
new_html = re.sub(
    r'<button class="nav-btn"\s+onclick="showTab\(\'day_\'\)">[\s]*\([금토]\)</button>\s*',
    '',
    new_html
)

# ── Remove tab content divs for removed days ──
new_html = re.sub(
    r'<div id="tab-day_" class="tab-content">\s*</div>\s*',
    '',
    new_html
)

# ── Update Overview daily summary table ──
# Remove rows for 금/토 in the overview table
# Replace planned total KPI
total_planned = sum(d['planned_total'] for d in forecast)
# Find and replace the total in KPI card
new_html = re.sub(
    r'(<div class="kpi-label">계획 합계</div>\s*<div class="kpi-value kpi-blue">)[^<]*(</div>)',
    rf'\g<1>{total_planned:,}\2',
    new_html
)

# ── Rebuild the daily summary table in overview ──
daily_table_rows = ''
for d in forecast:
    daily_table_rows += f'''<tr>
            <td>{d["date"][5:]}</td><td>{d["dow"]}</td><td class="num">{d["planned_total"]:,}</td>
            <td style="color:#bdbdbd;">-</td><td style="color:#bdbdbd;">-</td>
            <td style="color:#bdbdbd;">-</td><td style="color:#757575;">대기</td>
          </tr>
'''

# Replace old daily summary table body
new_html = re.sub(
    r'(일별 적중률 요약.*?<tbody>)\s*(.*?)(</tbody>)',
    lambda m: m.group(1) + '\n' + daily_table_rows + m.group(3),
    new_html,
    flags=re.DOTALL,
    count=1
)

# ── Rebuild stage distribution table ──
stage_totals = {}
for d in forecast:
    for s in d['stages']:
        stage_totals[s['stage_code']] = stage_totals.get(s['stage_code'], 0) + s['planned']

stage_table_rows = ''
for sc in sorted(stage_totals.keys()):
    stage_name = {'1110':'준비기','1210':'초기1','1220':'초기2','1230':'중기',
                  '1240':'후기','1250':'후기무른밥','1310':'영양밥','1320':'영양국','1330':'영양찬'}.get(sc, sc)
    pct = stage_totals[sc] / total_planned * 100 if total_planned > 0 else 0
    stage_table_rows += f'<tr><td>{stage_name}</td><td class="num">{stage_totals[sc]:,}</td><td class="num">{pct:.1f}%</td></tr>\n'

new_html = re.sub(
    r'(단계별 분포.*?<tbody>)\s*(.*?)(</tbody>)',
    lambda m: m.group(1) + '\n' + stage_table_rows + m.group(3),
    new_html,
    flags=re.DOTALL,
    count=1
)

# ── Fix dropdown: restore all week options with W18 ──
dropdown_html = '''<select id="weekSelector" onchange="var w=this.value;if(w==='w18')return;parent.postMessage({week:w},'*');">
    <option value="w12" >W12 (03-16 ~ 03-21)</option>
    <option value="w13" >W13 (03-23 ~ 03-28)</option>
    <option value="w14" >W14 (03-30 ~ 04-04)</option>
    <option value="w15" >W15 (04-06 ~ 04-11)</option>
    <option value="w16" >W16 (04-13 ~ 04-18)</option>
    <option value="w17" >W17 (04-20 ~ 04-25)</option>
    <option value="w18" selected>W18 (04-27 ~ 04-30) ★대체배송</option>
    <option value="compare">주차별 비교</option>
    </select>'''

new_html = re.sub(
    r'<select id="weekSelector"[^>]*>.*?</select>',
    dropdown_html,
    new_html,
    flags=re.DOTALL
)

# ── Update generation timestamp ──
now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
new_html = re.sub(r'생성: \d{4}-\d{2}-\d{2} \d{2}:\d{2}', f'생성: {now}', new_html)

# ── Add holiday notice banner ──
holiday_notice = '''<div style="background:#fff3cd;border:1px solid #ffc107;border-radius:8px;padding:12px 16px;margin:8px 0;font-size:13px;color:#856404;">
      ⚠️ <b>5월 휴무 안내</b>: 5/1(금) 근로자의날, 5/2(토) 휴무로 금·토 출고분이 4/28~4/30에 대체배송됩니다.
    </div>'''

# Insert notice after the exec summary
new_html = new_html.replace(
    '</div>\n    <!-- KPI',
    f'</div>\n    {holiday_notice}\n    <!-- KPI',
    1
)

# If the above didn't match, try alternative insertion point
if '5월 휴무 안내' not in new_html:
    new_html = new_html.replace(
        '<div class="kpi-row">',
        f'{holiday_notice}\n    <div class="kpi-row">',
        1
    )

# Save
with open(f'{base}/monitor_w18.html', 'w', encoding='utf-8') as f:
    f.write(new_html)

print(f"monitor_w18.html 생성 완료!")
print(f"dailyReports 일수: {len(daily_reports)}")
print(f"파일 크기: {len(new_html):,} bytes")
for d in daily_reports:
    extra = ''
    if d['dow'] in ('화','수','목'):
        extra = ' ★대체배송'
    print(f"  {d['date']} ({d['dow']}): planned={d['planned_total']:,}{extra}")
print(f"  합계: {sum(d['planned_total'] for d in daily_reports):,}")
