# -*- coding: utf-8 -*-
"""액션보드 디벨롭 — 모든 모니터(W12~W17)에 실질 데이터 기반 액션보드 탑재.

수요 드라이버 현황판(빈 탭)을 다음으로 교체:
  1) 주간 KPI 요약 (계획/실적/적중률/정상-경고-위험)
  2) 🔴 액션 필요 Top 10 (|Gap|, 적중률 기준 정렬)
  3) 📊 단계별 성과 (단계 누적 적중률 + 상태)
  4) ⚠️ 미예측 출고 메뉴 (예측 없었는데 출고된 건)
  5) 🎯 채널별 편차

각 모니터는 자신의 dailyReports 변수를 기반으로 렌더링.
"""
import re
from pathlib import Path

MONITORS = ['monitor_w12.html','monitor_w13.html','monitor_w14.html',
            'monitor_w15.html','monitor_w16.html','monitor_w17.html']

ACTION_TAB_HTML = '''<div id="tab-action" class="tab-content">
<h2 style="margin-bottom:14px; color:#1a237e;">🎯 액션 보드</h2>
<div id="actionBoardBody">
  <p style="color:#888; font-size:13px;">액션보드 로딩 중...</p>
</div>
</div>'''

ACTION_SCRIPT = r'''
// ═══════════════════════════════════════════════════
// 🎯 액션 보드 (dailyReports 기반 자동 생성)
// ═══════════════════════════════════════════════════
function renderActionBoard() {
  const body = document.getElementById('actionBoardBody');
  if (!body) return;

  const drs = (typeof dailyReports !== 'undefined') ? dailyReports : [];
  // 1) 주간 KPI 집계
  let totP = 0, totA = 0;
  let cntNormal = 0, cntWarn = 0, cntCrit = 0, cntTotal = 0;
  const stageAgg = {}; // {stage: {plan, actual}}
  const menuAgg = {};  // {code+name: {stage, name, plan, actual, dates:[]}}
  const unplanned = []; // 예측 없는데 실적 있음
  const chAgg = {}; // 채널별
  let hasActualDays = 0;

  drs.forEach(dr => {
    totP += dr.planned_total || 0;
    if ((dr.actual_total || 0) > 0) {
      hasActualDays++;
      totA += dr.actual_total || 0;
    }
    (dr.stage_hits || []).forEach(sh => {
      const key = sh.stage;
      stageAgg[key] = stageAgg[key] || { plan:0, actual:0 };
      stageAgg[key].plan += sh.planned || 0;
      stageAgg[key].actual += sh.actual || 0;
      if ((dr.actual_total || 0) > 0) {
        const hr = sh.hit_rate || 0;
        if (hr >= 90) cntNormal++;
        else if (hr >= 70) cntWarn++;
        else cntCrit++;
        cntTotal++;
      }
    });
    (dr.menu_hits || []).forEach(mh => {
      const key = mh.stage_code + '|' + mh.product_code + '|' + mh.product_name;
      menuAgg[key] = menuAgg[key] || { stage: mh.stage, code: mh.product_code, name: mh.product_name, plan:0, actual:0, days:0 };
      menuAgg[key].plan += mh.planned || 0;
      menuAgg[key].actual += mh.actual || 0;
      if ((mh.planned || 0) > 0 || (mh.actual || 0) > 0) menuAgg[key].days++;
      if ((mh.planned || 0) === 0 && (mh.actual || 0) > 0) {
        unplanned.push({ date: dr.date, stage: mh.stage, name: mh.product_name, code: mh.product_code, actual: mh.actual });
      }
    });
    (dr.channel_hits || []).forEach(ch => {
      chAgg[ch.channel] = chAgg[ch.channel] || { plan:0, actual:0 };
      chAgg[ch.channel].plan += ch.planned || 0;
      chAgg[ch.channel].actual += ch.actual || 0;
    });
  });

  const totHR = (totP > 0 && totA > 0) ? Math.round(Math.min(totA/totP, totP/totA) * 1000) / 10 : 0;
  const gap = totP - totA;

  let h = '';

  // ── 1) 주간 요약 KPI ──
  h += '<div class="kpi-row" style="margin-bottom:16px;">';
  h += '<div class="kpi-card"><div class="kpi-label">주간 누적 적중률</div><div class="kpi-value ' +
        (totHR >= 90 ? 'kpi-green' : (totHR >= 70 ? 'kpi-yellow' : 'kpi-red')) + '">' + totHR + '%</div><div class="kpi-sub">' + hasActualDays + '/' + drs.length + '일 확정</div></div>';
  h += '<div class="kpi-card"><div class="kpi-label">누적 계획</div><div class="kpi-value kpi-blue">' + totP.toLocaleString() + '</div><div class="kpi-sub">병</div></div>';
  h += '<div class="kpi-card"><div class="kpi-label">누적 실적</div><div class="kpi-value kpi-blue">' + totA.toLocaleString() + '</div><div class="kpi-sub">병</div></div>';
  h += '<div class="kpi-card"><div class="kpi-label">Gap</div><div class="kpi-value ' + (gap > 0 ? 'kpi-red' : 'kpi-green') + '">' +
        (gap > 0 ? '+' : '') + gap.toLocaleString() + '</div><div class="kpi-sub">병 (계획-실적)</div></div>';
  h += '<div class="kpi-card"><div class="kpi-label">단계 정상/경고/위험</div><div class="kpi-value">';
  h += '<span class="kpi-green">' + cntNormal + '</span> / <span class="kpi-yellow">' + cntWarn + '</span> / <span class="kpi-red">' + cntCrit + '</span>';
  h += '</div><div class="kpi-sub">일×단계 기준</div></div>';
  h += '</div>';

  // ── 2) 액션 필요 Top 10 메뉴 (|Gap| 기준) ──
  const menuArr = Object.values(menuAgg).map(m => {
    const hr = (m.plan > 0 && m.actual > 0) ? Math.round(Math.min(m.actual/m.plan, m.plan/m.actual) * 1000) / 10 : 0;
    const gapVal = m.plan - m.actual;
    return { ...m, hr, gap: gapVal, abs: Math.abs(gapVal) };
  }).filter(m => m.plan > 0 || m.actual > 0);
  const top = menuArr.sort((a,b) => b.abs - a.abs).slice(0, 10);

  h += '<h3 style="margin:16px 0 8px; color:#c62828;">🔴 액션 필요 Top 10 (|Gap| 기준)</h3>';
  h += '<div style="border:1px solid #ffcdd2; border-radius:8px; background:#fff8f7;">';
  h += '<table style="margin-bottom:0;"><thead><tr><th>순위</th><th>단계</th><th>상품</th><th>계획</th><th>실적</th><th>Gap</th><th>적중률</th><th>권장 액션</th></tr></thead><tbody>';
  if (top.length === 0) {
    h += '<tr><td colspan="8" style="color:#888; text-align:center;">데이터 없음</td></tr>';
  } else {
    top.forEach((m, i) => {
      let action, aColor;
      if (m.plan === 0 && m.actual > 0) { action = '예측 반영 필요 (미예측)'; aColor = '#757575'; }
      else if (m.gap > 0) { action = '계획 하향 검토 (과소 생산)'; aColor = '#c62828'; }
      else if (m.gap < 0) { action = '계획 상향 검토 (과다 수요)'; aColor = '#1565c0'; }
      else { action = '정상'; aColor = '#2e7d32'; }
      const hrCls = m.hr >= 90 ? 'hr-excellent' : (m.hr >= 70 ? 'hr-good' : 'hr-poor');
      h += '<tr><td>' + (i+1) + '</td><td>' + m.stage + '</td><td style="text-align:left;">' + (m.name || m.code) + '</td>';
      h += '<td class="num">' + m.plan.toLocaleString() + '</td><td class="num">' + m.actual.toLocaleString() + '</td>';
      h += '<td class="num" style="color:' + (m.gap > 0 ? '#c62828' : (m.gap < 0 ? '#1565c0' : '#333')) + '; font-weight:600;">' + (m.gap > 0 ? '+' : '') + m.gap.toLocaleString() + '</td>';
      h += '<td class="' + hrCls + '">' + m.hr + '%</td>';
      h += '<td style="text-align:left; color:' + aColor + '; font-weight:600; font-size:12px;">' + action + '</td></tr>';
    });
  }
  h += '</tbody></table></div>';

  // ── 3) 단계별 성과 체크리스트 ──
  h += '<h3 style="margin:16px 0 8px; color:#1a237e;">📊 단계별 누적 성과</h3>';
  h += '<div style="border:1px solid #c5cae9; border-radius:8px;">';
  h += '<table style="margin-bottom:0;"><thead><tr><th>단계</th><th>계획</th><th>실적</th><th>Gap</th><th>적중률</th><th>상태</th></tr></thead><tbody>';
  const stageOrder = ['준비기','초기1','초기2','중기','후기','후기무른밥','영양밥','영양국','영양찬'];
  stageOrder.forEach(stName => {
    const ag = stageAgg[stName];
    if (!ag) return;
    const hr = (ag.plan > 0 && ag.actual > 0) ? Math.round(Math.min(ag.actual/ag.plan, ag.plan/ag.actual) * 1000) / 10 : 0;
    const gp = ag.plan - ag.actual;
    const hrCls = hr >= 90 ? 'hr-excellent' : (hr >= 70 ? 'hr-good' : 'hr-poor');
    let status, sColor;
    if (hr >= 90) { status = '정상'; sColor = '#2e7d32'; }
    else if (gp > 0) { status = '과소 생산'; sColor = '#c62828'; }
    else { status = '과다 수요'; sColor = '#1565c0'; }
    h += '<tr><td>' + stName + '</td><td class="num">' + ag.plan.toLocaleString() + '</td><td class="num">' + ag.actual.toLocaleString() + '</td>';
    h += '<td class="num" style="color:' + (gp > 0 ? '#c62828' : (gp < 0 ? '#1565c0' : '#333')) + ';">' + (gp > 0 ? '+' : '') + gp.toLocaleString() + '</td>';
    h += '<td class="' + hrCls + '">' + hr + '%</td>';
    h += '<td style="color:' + sColor + '; font-weight:600;">' + status + '</td></tr>';
  });
  h += '</tbody></table></div>';

  // ── 4) 미예측 출고 메뉴 ──
  if (unplanned.length > 0) {
    h += '<h3 style="margin:16px 0 8px; color:#ef6c00;">⚠️ 미예측 출고 메뉴 (' + unplanned.length + '건)</h3>';
    h += '<div style="border:1px solid #ffe0b2; border-radius:8px; background:#fff8e1;">';
    h += '<table style="margin-bottom:0;"><thead><tr><th>일자</th><th>단계</th><th>상품</th><th>실적</th></tr></thead><tbody>';
    unplanned.slice(0, 30).forEach(u => {
      h += '<tr><td>' + u.date.substring(5) + '</td><td>' + u.stage + '</td><td style="text-align:left;">' + u.name + '</td><td class="num">' + u.actual.toLocaleString() + '</td></tr>';
    });
    if (unplanned.length > 30) {
      h += '<tr><td colspan="4" style="text-align:center; color:#888;">… 외 ' + (unplanned.length - 30) + '건</td></tr>';
    }
    h += '</tbody></table></div>';
  }

  // ── 5) 채널별 편차 ──
  const chNames = Object.keys(chAgg);
  if (chNames.length > 0) {
    h += '<h3 style="margin:16px 0 8px; color:#1a237e;">🎯 채널별 누적 편차</h3>';
    h += '<div class="kpi-row">';
    chNames.forEach(n => {
      const c = chAgg[n];
      const hr = (c.plan > 0 && c.actual > 0) ? Math.round(Math.min(c.actual/c.plan, c.plan/c.actual) * 1000) / 10 : 0;
      const gp = c.plan - c.actual;
      h += '<div class="kpi-card">';
      h += '<div class="kpi-label">' + n + '</div>';
      h += '<div class="kpi-value ' + (hr >= 90 ? 'kpi-green' : (hr >= 70 ? 'kpi-yellow' : 'kpi-red')) + '">' + hr + '%</div>';
      h += '<div class="kpi-sub">계획 ' + c.plan.toLocaleString() + ' / 실적 ' + c.actual.toLocaleString() + ' (Gap ' + (gp > 0 ? '+' : '') + gp.toLocaleString() + ')</div>';
      h += '</div>';
    });
    h += '</div>';
  }

  // ── 6) 요약 코멘트 ──
  let comment = '';
  if (hasActualDays === 0) comment = '이번 주차 실적이 아직 업로드되지 않았습니다. XLS 업로드 후 액션보드가 활성화됩니다.';
  else if (totHR >= 95) comment = '주간 적중률이 우수합니다. 현재 예측 전략을 유지하세요.';
  else if (totHR >= 90) comment = '주간 적중률은 안정적이나, Top 10 항목에 대한 미세 조정이 필요합니다.';
  else if (totHR >= 80) comment = '주간 적중률이 목표 대비 낮습니다. 과소/과다 메뉴를 집중 점검하세요.';
  else comment = '주간 적중률이 매우 낮습니다. 수요 패턴 변화 가능성을 검토하고 전반적인 예측 재조정이 필요합니다.';
  h += '<div style="margin-top:18px; padding:12px 16px; background:#e8eaf6; border-left:4px solid #1a237e; border-radius:4px; font-size:13px; color:#1a237e;">';
  h += '<strong>📌 요약:</strong> ' + comment + '</div>';

  body.innerHTML = h;
}
try { renderActionBoard(); } catch(e) { console.error('[액션보드] 렌더 실패:', e); }
'''


def patch_monitor(path: Path):
    t = path.read_text(encoding='utf-8')

    # 1) tab-action content 교체 (id="tab-action"부터 </div>까지)
    # 기존 블록 찾기
    m = re.search(r'<div id="tab-action" class="tab-content">.*?</div>\s*(?=<div id="tab-|<script>|</div>\s*<!--\s*tabs end|</body>)',
                  t, re.S)
    if not m:
        # fallback: until </div> closing tab-content
        m = re.search(r'<div id="tab-action" class="tab-content">.*?</script>\s*</div>', t, re.S)
    if not m:
        print(f'[SKIP] {path.name}: tab-action not found')
        return False

    t_new = t[:m.start()] + ACTION_TAB_HTML + t[m.end():]

    # 2) 액션보드 스크립트 삽입 — loadActualData().then 블록 이후에 renderActionBoard 호출 추가
    # loadActualData().then(() => { ... });  뒤에 renderActionBoard() 호출 추가
    # 먼저 renderActionBoard 함수 본문을 </script> 직전에 삽입
    # 마지막 </script> 찾기
    last_script_idx = t_new.rfind('</script>')
    if last_script_idx == -1:
        print(f'[SKIP] {path.name}: </script> not found')
        return False

    # 이미 renderActionBoard가 있으면 교체
    if 'function renderActionBoard()' in t_new:
        # 기존 renderActionBoard 블록 제거 (주석부터 "try { renderActionBoard" 라인까지)
        t_new = re.sub(
            r'\n// ═+\n// 🎯 액션 보드.*?try \{ renderActionBoard\(\); \} catch\(e\) \{[^}]*\}\s*',
            '\n',
            t_new,
            flags=re.S,
        )
        last_script_idx = t_new.rfind('</script>')

    t_new = t_new[:last_script_idx] + ACTION_SCRIPT + '\n' + t_new[last_script_idx:]

    # 3) 액션보드 자동 재렌더링 — loadActualData 이후에도 호출
    # "updateNavDots();" 뒤에 renderActionBoard 호출이 없으면 추가
    if 'renderActionBoard();\n});' not in t_new:
        # loadActualData().then 블록의 끝에서 재렌더링 호출
        t_new = re.sub(
            r'(loadActualData\(\)\.then\(\(\) => \{[\s\S]*?updateNavDots\(\);\s*)\}\);',
            lambda m: m.group(1) + '  try { renderActionBoard(); } catch(e) {}\n});',
            t_new,
            count=1,
        )

    path.write_text(t_new, encoding='utf-8')
    print(f'[OK] {path.name} patched')
    return True


if __name__ == '__main__':
    for fn in MONITORS:
        p = Path(fn)
        if p.exists():
            patch_monitor(p)
