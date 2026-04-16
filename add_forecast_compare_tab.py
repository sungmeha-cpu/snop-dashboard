"""
예측 비교 탭: AI예측 vs 수기예측 vs 실적
각 monitor_wXX.html에 탭 추가
"""
import json, re

with open('data/manual_forecast.json', 'r', encoding='utf-8') as f:
    manual = json.load(f)

with open('data/actual.json', 'r', encoding='utf-8') as f:
    actual = json.load(f)

WEEKS = {
    'monitor_w12.html': ['2026-03-16','2026-03-17','2026-03-18','2026-03-19','2026-03-20','2026-03-21'],
    'monitor_w13.html': ['2026-03-23','2026-03-24','2026-03-25','2026-03-26','2026-03-27','2026-03-28'],
    'monitor_w14.html': ['2026-03-30','2026-03-31','2026-04-01','2026-04-02','2026-04-03','2026-04-04'],
    'monitor_w15.html': ['2026-04-06','2026-04-07','2026-04-08','2026-04-09','2026-04-10','2026-04-11'],
    'monitor_w16.html': ['2026-04-13','2026-04-14','2026-04-15','2026-04-16','2026-04-17','2026-04-18'],
    'monitor_w17.html': ['2026-04-20','2026-04-21','2026-04-22','2026-04-23','2026-04-24','2026-04-25'],
}

STAGE_ORDER = ['1110','1210','1220','1230','1240','1250','1310','1320','1330']
STAGE_NAME = {'1110':'준비기','1210':'초기1','1220':'초기2','1230':'중기',
              '1240':'후기','1250':'후기무른밥','1310':'영양밥','1320':'영양국','1330':'영양찬'}

def build_compare_data(dates):
    """Build per-date, per-stage comparison data"""
    compare = []
    for d in dates:
        # Manual forecast: aggregate by stage
        m_stages = {}
        for item in manual.get(d, []):
            sc = item['stage_code']
            if sc not in m_stages:
                m_stages[sc] = 0
            m_stages[sc] += item['manual_total']

        # Actual: aggregate by stage
        a_stages = {}
        a_total = 0
        for rec in actual.get(d, []):
            sc = rec['stage_code']
            a_stages[sc] = a_stages.get(sc, 0) + rec['qty']
            a_total += rec['qty']

        m_total = sum(m_stages.values())

        compare.append({
            'date': d,
            'manual_total': m_total,
            'actual_total': a_total,
            'manual_stages': m_stages,
            'actual_stages': a_stages,
        })
    return compare

RENDER_FN = r"""
function renderForecastCompare() {
  var tab = document.getElementById('tab-forecast-compare');
  if (!tab) return;

  var STAGE_ORDER = ['1110','1210','1220','1230','1240','1250','1310','1320','1330'];
  var STAGE_NAME = {'1110':'준비기','1210':'초기1','1220':'초기2','1230':'중기','1240':'후기','1250':'후기무른밥','1310':'영양밥','1320':'영양국','1330':'영양찬'};
  var dows = ['일','월','화','수','목','금','토'];

  function hitRate(plan, act) {
    if (plan <= 0 || act <= 0) return 0;
    return Math.round(Math.min(act/plan, plan/act) * 1000) / 10;
  }
  function hrCls(hr) { return hr >= 90 ? 'hr-excellent' : (hr >= 70 ? 'hr-good' : 'hr-poor'); }

  // Aggregate across all dates
  var totalAI = 0, totalManual = 0, totalActual = 0;
  var stageAI = {}, stageManual = {}, stageActual = {};
  var aiWins = 0, manualWins = 0, ties = 0;
  var dayRows = [];

  compareData.forEach(function(cd) {
    var dr = dailyReports.find(function(r) { return r.date === cd.date; });
    var aiPlan = dr ? dr.planned_total : 0;
    var manPlan = cd.manual_total;
    var act = cd.actual_total;
    var dt = new Date(cd.date + 'T00:00:00');
    var dow = dows[dt.getDay()];

    var aiHR = hitRate(aiPlan, act);
    var manHR = hitRate(manPlan, act);

    if (act > 0 && aiPlan > 0 && manPlan > 0) {
      totalAI += aiPlan; totalManual += manPlan; totalActual += act;
      if (aiHR > manHR) aiWins++;
      else if (manHR > aiHR) manualWins++;
      else ties++;
    }

    // Per-stage
    STAGE_ORDER.forEach(function(sc) {
      var aiS = 0;
      if (dr && dr.stage_hits) {
        var sh = dr.stage_hits.find(function(s) { return s.stage_code === sc; });
        if (sh) aiS = sh.planned;
      }
      var manS = cd.manual_stages[sc] || 0;
      var actS = cd.actual_stages[sc] || 0;
      stageAI[sc] = (stageAI[sc] || 0) + aiS;
      stageManual[sc] = (stageManual[sc] || 0) + manS;
      stageActual[sc] = (stageActual[sc] || 0) + actS;
    });

    dayRows.push({ date: cd.date, dow: dow, ai: aiPlan, manual: manPlan, actual: act, aiHR: aiHR, manHR: manHR });
  });

  var overallAiHR = hitRate(totalAI, totalActual);
  var overallManHR = hitRate(totalManual, totalActual);
  var winner = overallAiHR > overallManHR ? 'AI' : (overallManHR > overallAiHR ? '수기' : '동률');

  var html = '<h2 style="margin-bottom:12px; color:#1a237e;">예측 비교: AI vs 수기</h2>';
  html += '<p style="margin-bottom:16px; color:#555; font-size:13px;">AI 자동예측과 판매담당자 수기예측의 정확도를 실적 기준으로 비교합니다.</p>';

  // KPI
  html += '<div class="kpi-row">';
  html += '<div class="kpi-card"><div class="kpi-label">AI 적중률</div><div class="kpi-value ' + hrCls(overallAiHR) + '">' + overallAiHR + '%</div></div>';
  html += '<div class="kpi-card"><div class="kpi-label">수기 적중률</div><div class="kpi-value ' + hrCls(overallManHR) + '">' + overallManHR + '%</div></div>';
  var winColor = winner === 'AI' ? '#1565c0' : (winner === '수기' ? '#e65100' : '#333');
  html += '<div class="kpi-card"><div class="kpi-label">더 정확한 쪽</div><div class="kpi-value" style="color:' + winColor + ';">' + winner + '</div></div>';
  html += '<div class="kpi-card"><div class="kpi-label">일별 승패 (AI/수기/동률)</div><div class="kpi-value"><span style="color:#1565c0;">' + aiWins + '</span> / <span style="color:#e65100;">' + manualWins + '</span> / ' + ties + '</div></div>';
  html += '</div>';

  // Chart
  html += '<div style="background:#fff; border-radius:8px; padding:16px; margin-bottom:16px; border:1px solid #e0e0e0;">';
  html += '<canvas id="forecastCompareChart" height="80"></canvas></div>';

  // Daily table
  html += '<h3 style="margin:12px 0 6px; color:#1a237e;">일별 비교</h3>';
  html += '<table><thead><tr><th>날짜</th><th>요일</th><th style="color:#1565c0;">AI예측</th><th style="color:#e65100;">수기예측</th><th>실적</th><th style="color:#1565c0;">AI 적중률</th><th style="color:#e65100;">수기 적중률</th><th>승자</th></tr></thead><tbody>';

  dayRows.forEach(function(r) {
    var aiStr = r.ai > 0 ? r.ai.toLocaleString() : '-';
    var manStr = r.manual > 0 ? r.manual.toLocaleString() : '-';
    var actStr = r.actual > 0 ? r.actual.toLocaleString() : '-';
    var aiHRStr = r.actual > 0 && r.ai > 0 ? '<span class="' + hrCls(r.aiHR) + '">' + r.aiHR + '%</span>' : '-';
    var manHRStr = r.actual > 0 && r.manual > 0 ? '<span class="' + hrCls(r.manHR) + '">' + r.manHR + '%</span>' : '-';
    var w = '';
    if (r.actual > 0 && r.ai > 0 && r.manual > 0) {
      if (r.aiHR > r.manHR) w = '<span style="color:#1565c0; font-weight:700;">AI</span>';
      else if (r.manHR > r.aiHR) w = '<span style="color:#e65100; font-weight:700;">수기</span>';
      else w = '동률';
    }
    html += '<tr><td>' + r.date.slice(5) + '</td><td>' + r.dow + '</td>';
    html += '<td class="num">' + aiStr + '</td><td class="num">' + manStr + '</td><td class="num" style="font-weight:600;">' + actStr + '</td>';
    html += '<td style="text-align:center;">' + aiHRStr + '</td><td style="text-align:center;">' + manHRStr + '</td>';
    html += '<td style="text-align:center;">' + w + '</td></tr>';
  });
  html += '</tbody></table>';

  // Stage comparison
  html += '<h3 style="margin:16px 0 6px; color:#1a237e;">단계별 누적 비교</h3>';
  html += '<table><thead><tr><th>단계</th><th style="color:#1565c0;">AI예측</th><th style="color:#e65100;">수기예측</th><th>실적</th><th style="color:#1565c0;">AI 적중률</th><th style="color:#e65100;">수기 적중률</th><th>승자</th></tr></thead><tbody>';

  var stAiWins = 0, stManWins = 0;
  STAGE_ORDER.forEach(function(sc) {
    var ai = stageAI[sc] || 0, man = stageManual[sc] || 0, act = stageActual[sc] || 0;
    var aiHR = hitRate(ai, act), manHR = hitRate(man, act);
    var w = '';
    if (act > 0 && ai > 0 && man > 0) {
      if (aiHR > manHR) { w = '<span style="color:#1565c0; font-weight:700;">AI</span>'; stAiWins++; }
      else if (manHR > aiHR) { w = '<span style="color:#e65100; font-weight:700;">수기</span>'; stManWins++; }
      else w = '동률';
    }
    html += '<tr><td>' + (STAGE_NAME[sc]||sc) + '</td>';
    html += '<td class="num">' + ai.toLocaleString() + '</td><td class="num">' + man.toLocaleString() + '</td><td class="num" style="font-weight:600;">' + act.toLocaleString() + '</td>';
    html += '<td class="' + hrCls(aiHR) + '">' + aiHR + '%</td><td class="' + hrCls(manHR) + '">' + manHR + '%</td>';
    html += '<td style="text-align:center;">' + w + '</td></tr>';
  });
  // Total
  html += '<tr style="background:#e8eaf6; font-weight:700;"><td>합계</td>';
  html += '<td class="num">' + totalAI.toLocaleString() + '</td><td class="num">' + totalManual.toLocaleString() + '</td><td class="num">' + totalActual.toLocaleString() + '</td>';
  html += '<td class="' + hrCls(overallAiHR) + '">' + overallAiHR + '%</td><td class="' + hrCls(overallManHR) + '">' + overallManHR + '%</td>';
  html += '<td style="text-align:center;">' + (stAiWins > stManWins ? 'AI ' + stAiWins + ':' + stManWins : (stManWins > stAiWins ? '수기 ' + stManWins + ':' + stAiWins : '동률')) + '</td></tr>';
  html += '</tbody></table>';

  tab.innerHTML = html;

  // Chart
  var ctx = document.getElementById('forecastCompareChart');
  if (ctx && typeof Chart !== 'undefined') {
    var labels = dayRows.map(function(r) { return r.date.slice(5) + '(' + r.dow + ')'; });
    new Chart(ctx, {
      type: 'line',
      data: {
        labels: labels,
        datasets: [
          { label: 'AI예측', data: dayRows.map(function(r) { return r.aiHR || null; }), borderColor: '#1565c0', backgroundColor: 'rgba(21,101,192,0.1)', borderWidth: 2, pointRadius: 5, fill: false },
          { label: '수기예측', data: dayRows.map(function(r) { return r.manHR || null; }), borderColor: '#e65100', backgroundColor: 'rgba(230,81,0,0.1)', borderWidth: 2, pointRadius: 5, fill: false },
          { label: '90% 기준선', data: dayRows.map(function() { return 90; }), borderColor: '#ccc', borderDash: [5,3], borderWidth: 1, pointRadius: 0, fill: false }
        ]
      },
      options: {
        responsive: true,
        plugins: { legend: { position: 'top' }, title: { display: true, text: '일별 적중률 비교 (AI vs 수기)' } },
        scales: { y: { min: 0, max: 100, title: { display: true, text: '적중률 (%)' } } }
      }
    });
  }
}
"""

for monitor_file, dates in WEEKS.items():
    with open(monitor_file, 'r', encoding='utf-8') as f:
        html = f.read()

    if 'tab-forecast-compare' in html:
        print(f'{monitor_file}: already has forecast-compare tab, skipping')
        continue

    compare_data = build_compare_data(dates)

    # 1. Add nav button after experience tab button
    if 'data-tab="experience"' in html:
        exp_btn_end = html.find('체험팩 추이</button>') + len('체험팩 추이</button>')
        new_btn = '\n    <button class="nav-btn" draggable="true" data-tab="forecast-compare" onclick="showTab(\'forecast-compare\')">예측 비교</button>'
        html = html[:exp_btn_end] + new_btn + html[exp_btn_end:]
    else:
        # Find last nav button
        last_btn = html.rfind('</button>\n  </div>')
        if last_btn > 0:
            last_btn += len('</button>')
            new_btn = '\n    <button class="nav-btn" draggable="true" data-tab="forecast-compare" onclick="showTab(\'forecast-compare\')">예측 비교</button>'
            html = html[:last_btn] + new_btn + html[last_btn:]

    # 2. Add tab div before <script>
    exp_div = html.find('<div id="tab-experience"')
    if exp_div > 0:
        # Insert after experience tab div
        exp_div_end = html.find('</div>', exp_div) + len('</div>')
        tab_div = '\n<div id="tab-forecast-compare" class="tab-content"></div>\n'
        html = html[:exp_div_end] + tab_div + html[exp_div_end:]
    else:
        script_pos = html.find('<script>')
        tab_div = '\n<div id="tab-forecast-compare" class="tab-content"></div>\n'
        html = html[:script_pos] + tab_div + html[script_pos:]

    # 3. Add compareData after signupData (or after dailyReports)
    compare_json = json.dumps(compare_data, ensure_ascii=False)
    # Find insertion point
    if 'const signupData' in html:
        # Insert after the last signup-related const
        idx = html.find('const prevWeekDates')
        if idx > 0:
            line_end = html.find('\n', idx)
            insert_pos = line_end + 1
        else:
            idx = html.find('const signupData')
            line_end = html.find('\n', idx)
            insert_pos = line_end + 1
    else:
        dr_match = re.search(r'const dailyReports = \[.*?\];', html, re.DOTALL)
        insert_pos = dr_match.end() + 1 if dr_match else 0

    compare_const = f'const compareData = {compare_json};\n'
    html = html[:insert_pos] + compare_const + html[insert_pos:]

    # 4. Add render function + call before </script>
    close_script = html.rfind('</script>')
    html = html[:close_script] + RENDER_FN + '\nrenderForecastCompare();\n' + html[close_script:]

    with open(monitor_file, 'w', encoding='utf-8') as f:
        f.write(html)

    # Print summary
    has_actual = sum(1 for cd in compare_data if cd['actual_total'] > 0)
    print(f'{monitor_file}: forecast-compare tab added ({has_actual}/{len(dates)} days with actual)')

print('\nDone!')
