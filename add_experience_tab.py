import json, re

# Load signup data
with open('data/signups.json', 'r', encoding='utf-8') as f:
    signups = json.load(f)

# Week definitions
WEEKS = {
    'monitor_w12.html': {'dates': ['2026-03-16','2026-03-17','2026-03-18','2026-03-19','2026-03-20','2026-03-21'], 'prev_dates': []},
    'monitor_w13.html': {'dates': ['2026-03-23','2026-03-24','2026-03-25','2026-03-26','2026-03-27','2026-03-28'], 'prev_dates': ['2026-03-16','2026-03-17','2026-03-18','2026-03-19','2026-03-20','2026-03-21']},
    'monitor_w14.html': {'dates': ['2026-03-30','2026-03-31','2026-04-01','2026-04-02','2026-04-03','2026-04-04'], 'prev_dates': ['2026-03-23','2026-03-24','2026-03-25','2026-03-26','2026-03-27','2026-03-28']},
    'monitor_w15.html': {'dates': ['2026-04-06','2026-04-07','2026-04-08','2026-04-09','2026-04-10','2026-04-11'], 'prev_dates': ['2026-03-30','2026-03-31','2026-04-01','2026-04-02','2026-04-03','2026-04-04']},
    'monitor_w16.html': {'dates': ['2026-04-13','2026-04-14','2026-04-15','2026-04-16','2026-04-17','2026-04-18'], 'prev_dates': ['2026-04-06','2026-04-07','2026-04-08','2026-04-09','2026-04-10','2026-04-11']},
    'monitor_w17.html': {'dates': ['2026-04-20','2026-04-21','2026-04-22','2026-04-23','2026-04-24','2026-04-25'], 'prev_dates': ['2026-04-13','2026-04-14','2026-04-15','2026-04-16','2026-04-17','2026-04-18']},
}

RENDER_FN = r"""
function renderExperienceTab() {
  var tab = document.getElementById('tab-experience');
  if (!tab) return;

  var dows = ['일','월','화','수','목','금','토'];

  var rows = [];
  var totalSignup = 0, totalPrev = 0, totalExpected = 0, totalActual = 0;
  var validDays = 0;

  weekDates.forEach(function(d, i) {
    var s = signupData[d];
    var ps = prevWeekDates.length > i ? signupData[prevWeekDates[i]] : null;
    var expected = (s != null && s !== null) ? Math.round(s * EXPERIENCE_PACK_RATE) : null;
    var dt = new Date(d + 'T00:00:00');
    var dow = dows[dt.getDay()];

    var dr = dailyReports.find(function(r) { return r.date === d; });
    var act = dr ? dr.actual_total : 0;

    var change = (s != null && ps != null && ps > 0) ? Math.round((s - ps) / ps * 100) : null;

    rows.push({ date: d, dow: dow, signup: s, prev: ps, expected: expected, actual: act, change: change });
    if (s != null) { totalSignup += s; validDays++; }
    if (ps != null) totalPrev += ps;
    if (expected != null) totalExpected += expected;
    if (act > 0) totalActual += act;
  });

  var weekAvg = validDays > 0 ? Math.round(totalSignup / validDays) : 0;
  var totalChange = totalPrev > 0 ? Math.round((totalSignup - totalPrev) / totalPrev * 100) : null;

  var html = '<h2 style="margin-bottom:12px; color:#1a237e;">체험팩 추이 모니터링</h2>';
  html += '<p style="margin-bottom:16px; color:#555; font-size:13px;">회원가입자의 70%가 체험팩(본메뉴 1set)을 구매합니다. 가입자 수 기반으로 예상 체험팩 수요를 산출합니다.</p>';

  // KPI
  html += '<div class="kpi-row">';
  html += '<div class="kpi-card"><div class="kpi-label">금주 가입자</div><div class="kpi-value kpi-blue">' + totalSignup.toLocaleString() + '</div><div class="kpi-sub">명</div></div>';
  html += '<div class="kpi-card"><div class="kpi-label">예상 체험팩</div><div class="kpi-value kpi-green">' + totalExpected.toLocaleString() + '</div><div class="kpi-sub">건 (70%)</div></div>';
  html += '<div class="kpi-card"><div class="kpi-label">일평균 가입</div><div class="kpi-value kpi-blue">' + weekAvg.toLocaleString() + '</div><div class="kpi-sub">명/일</div></div>';
  if (totalChange !== null) {
    var chColor = totalChange >= 0 ? 'kpi-green' : 'kpi-red';
    html += '<div class="kpi-card"><div class="kpi-label">전주 대비</div><div class="kpi-value ' + chColor + '">' + (totalChange >= 0 ? '+' : '') + totalChange + '%</div></div>';
  }
  html += '</div>';

  // Chart
  html += '<div style="background:#fff; border-radius:8px; padding:16px; margin-bottom:16px; border:1px solid #e0e0e0;">';
  html += '<canvas id="experienceChart" height="80"></canvas></div>';

  // Table
  html += '<h3 style="margin:12px 0 6px; color:#1a237e;">일별 가입자 &amp; 예상 체험팩</h3>';
  html += '<table><thead><tr><th>날짜</th><th>요일</th><th>가입자(명)</th><th>예상 체험팩<br>(70%)</th><th>전주 가입자</th><th>전주 대비</th><th>실제 출고(건)</th></tr></thead><tbody>';

  rows.forEach(function(r) {
    var sStr = r.signup != null ? r.signup.toLocaleString() : '<span style="color:#999;">-</span>';
    var eStr = r.expected != null ? r.expected.toLocaleString() : '<span style="color:#999;">-</span>';
    var pStr = r.prev != null ? r.prev.toLocaleString() : '<span style="color:#999;">-</span>';
    var aStr = r.actual > 0 ? r.actual.toLocaleString() : '<span style="color:#999;">-</span>';
    var chStr = '-';
    if (r.change !== null) {
      var chColor = r.change >= 0 ? '#2e7d32' : '#c62828';
      chStr = '<span style="color:' + chColor + '; font-weight:600;">' + (r.change >= 0 ? '+' : '') + r.change + '%</span>';
    }
    html += '<tr><td>' + r.date.slice(5) + '</td><td>' + r.dow + '</td>';
    html += '<td class="num" style="font-weight:600;">' + sStr + '</td>';
    html += '<td class="num" style="color:#1565c0; font-weight:600;">' + eStr + '</td>';
    html += '<td class="num">' + pStr + '</td>';
    html += '<td style="text-align:center;">' + chStr + '</td>';
    html += '<td class="num">' + aStr + '</td></tr>';
  });

  // Total
  var totalChStr = totalChange !== null
    ? '<span style="color:' + (totalChange >= 0 ? '#2e7d32' : '#c62828') + '; font-weight:600;">' + (totalChange >= 0 ? '+' : '') + totalChange + '%</span>' : '';
  html += '<tr style="background:#e8eaf6; font-weight:700;"><td>합계</td><td></td>';
  html += '<td class="num">' + totalSignup.toLocaleString() + '</td>';
  html += '<td class="num" style="color:#1565c0;">' + totalExpected.toLocaleString() + '</td>';
  html += '<td class="num">' + totalPrev.toLocaleString() + '</td>';
  html += '<td style="text-align:center;">' + totalChStr + '</td>';
  html += '<td class="num">' + (totalActual > 0 ? totalActual.toLocaleString() : '-') + '</td></tr>';
  html += '</tbody></table>';

  tab.innerHTML = html;

  // Chart
  var ctx = document.getElementById('experienceChart');
  if (ctx && typeof Chart !== 'undefined') {
    var labels = rows.map(function(r) { return r.date.slice(5) + '(' + r.dow + ')'; });
    var signupVals = rows.map(function(r) { return r.signup; });
    var expectedVals = rows.map(function(r) { return r.expected; });
    var prevVals = rows.map(function(r) { return r.prev; });

    new Chart(ctx, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [
          { label: '가입자', data: signupVals, backgroundColor: 'rgba(25,118,210,0.7)', order: 2 },
          { label: '예상 체험팩(70%)', data: expectedVals, type: 'line', borderColor: '#e65100', backgroundColor: 'rgba(230,81,0,0.1)', borderWidth: 2, pointRadius: 4, fill: false, order: 1 },
          { label: '전주 가입자', data: prevVals, type: 'line', borderColor: '#9e9e9e', borderDash: [5,3], borderWidth: 1.5, pointRadius: 3, fill: false, order: 0 }
        ]
      },
      options: {
        responsive: true,
        plugins: { legend: { position: 'top' }, title: { display: true, text: '일별 회원가입자 & 예상 체험팩 추이' } },
        scales: { y: { beginAtZero: true, title: { display: true, text: '명/건' } } }
      }
    });
  }
}
"""

for monitor_file, info in WEEKS.items():
    with open(monitor_file, 'r', encoding='utf-8') as f:
        html = f.read()

    # Skip if already has experience tab
    if 'tab-experience' in html:
        print(f'{monitor_file}: already has experience tab, skipping')
        continue

    # Build signup data for this week + prev week
    all_dates = info['prev_dates'] + info['dates']
    signup_subset = {d: signups.get(d, None) for d in all_dates}

    # 1. Add nav button after last day button
    last_date = info['dates'][-1]
    nav_pattern = r'(<button class="nav-btn" draggable="true" data-tab="day_' + re.escape(last_date) + r'"[^<]*</button>)'
    nav_replacement = r'\1\n    <button class="nav-btn" draggable="true" data-tab="experience" onclick="showTab(\'experience\')">체험팩 추이</button>'
    html = re.sub(nav_pattern, nav_replacement, html)

    # 2. Add tab-experience div before <script>
    script_pos = html.find('\n<script>')
    if script_pos < 0:
        script_pos = html.find('<script>')
    if script_pos > 0:
        tab_div = '\n<div id="tab-experience" class="tab-content"></div>\n'
        html = html[:script_pos] + tab_div + html[script_pos:]

    # 3. Add signupData after dailyReports
    dr_match = re.search(r'const dailyReports = \[.*?\];', html, re.DOTALL)
    if dr_match:
        insert_pos = dr_match.end()
        signup_json = json.dumps(signup_subset, ensure_ascii=False)
        signup_const = f'\nconst signupData = {signup_json};\nconst EXPERIENCE_PACK_RATE = 0.70;\nconst weekDates = {json.dumps(info["dates"])};\nconst prevWeekDates = {json.dumps(info["prev_dates"])};\n'
        html = html[:insert_pos] + signup_const + html[insert_pos:]

    # 4. Add renderExperienceTab function + call before </script>
    close_script = html.rfind('</script>')
    html = html[:close_script] + RENDER_FN + '\nrenderExperienceTab();\n' + html[close_script:]

    # 5. Ensure Chart.js CDN is loaded
    if 'chart.js' not in html.lower():
        head_close = html.find('</head>')
        chart_cdn = '<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>\n'
        html = html[:head_close] + chart_cdn + html[head_close:]

    with open(monitor_file, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f'{monitor_file}: experience tab added')

print('\nDone!')
