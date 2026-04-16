"""
W13 overview 스타일을 W14~W17 모니터에 동일하게 반영.
- dailyReports(HTML 내장) + data/actual.json 병합
- Executive Summary + 6 KPI + 3 차트 + 일별 요약 + 단계별 누적
- rerenderOverview()도 W13 스타일로 맞춰 재작성
"""
import json, re, sys, pathlib

ROOT = pathlib.Path(__file__).parent
ACT = json.loads((ROOT / "data" / "actual.json").read_text(encoding="utf-8"))

DOW_KOR = ["월","화","수","목","금","토","일"]

# 단계 순서 (W13과 동일)
STAGE_ORDER = ["1110","1210","1220","1230","1240","1250","1310","1320","1330"]
STAGE_NAME  = {"1110":"준비기","1210":"초기1","1220":"초기2","1230":"중기",
               "1240":"후기","1250":"후기무른밥","1310":"영양밥","1320":"영양국","1330":"영양찬"}

def merge_actual(dr):
    """dailyReports 각 일자에 actual.json 데이터를 병합 (일/단계/채널/메뉴)"""
    for d in dr:
        date = d["date"]
        recs = ACT.get(date, [])
        if not recs:
            continue
        # 일 합계
        total = sum(r.get("qty",0) for r in recs)
        d["actual_total"] = total
        # 단계별 합계
        stage_act = {}
        stage_jasa = {}
        stage_oibu = {}
        for r in recs:
            sc = r.get("stage_code","")
            stage_act[sc] = stage_act.get(sc,0) + r.get("qty",0)
            stage_jasa[sc] = stage_jasa.get(sc,0) + r.get("jasa",0)
            stage_oibu[sc] = stage_oibu.get(sc,0) + r.get("oibu",0)
        for sh in d.get("stage_hits", []):
            a = stage_act.get(sh["stage_code"], 0)
            p = sh.get("planned",0)
            sh["actual"] = a
            if p > 0 and a > 0:
                sh["hit_rate"] = round(min(a/p, p/a)*100, 1)
            else:
                sh["hit_rate"] = 0.0
        # 채널별 합계
        total_jasa = sum(r.get("jasa",0) for r in recs)
        total_oibu = sum(r.get("oibu",0) for r in recs)
        for ch in d.get("channel_hits", []):
            if ch["channel"] == "자사몰":
                ch["actual"] = total_jasa
            elif ch["channel"] == "외부몰":
                ch["actual"] = total_oibu
            p, a = ch.get("planned",0), ch.get("actual",0)
            ch["hit_rate"] = round(min(a/p, p/a)*100, 1) if (p>0 and a>0) else 0.0
        # 메뉴별 실적 병합: 실적 기준으로 메뉴 재구성
        # 단계별 계획 합계 (예측에서)
        stage_plan = {}
        stage_plan_jasa = {}
        stage_plan_oibu = {}
        for sh in d.get("stage_hits", []):
            stage_plan[sh["stage_code"]] = sh.get("planned", 0)
        # 예측 메뉴에서 단계별 자사몰/외부몰 비율 계산
        for mh in d.get("menu_hits", []):
            sc = mh["stage_code"]
            stage_plan_jasa[sc] = stage_plan_jasa.get(sc, 0) + mh.get("planned_jasa", 0)
            stage_plan_oibu[sc] = stage_plan_oibu.get(sc, 0) + mh.get("planned_oibu", 0)
        # 실적 기준 메뉴 리스트 구성
        new_menu_hits = []
        # 단계별 실적 합계 (비례배분용)
        stage_actual_sum = {}
        for r in recs:
            sc = r.get("stage_code", "")
            stage_actual_sum[sc] = stage_actual_sum.get(sc, 0) + r.get("qty", 0)
        for r in recs:
            sc = r.get("stage_code", "")
            qty = r.get("qty", 0)
            jasa = r.get("jasa", 0)
            oibu = r.get("oibu", 0)
            # 단계 계획을 실적 비율로 비례배분
            s_plan = stage_plan.get(sc, 0)
            s_actual = stage_actual_sum.get(sc, 1)
            planned = round(s_plan * qty / s_actual) if s_actual > 0 else 0
            # 자사몰/외부몰 비례배분
            s_pj = stage_plan_jasa.get(sc, 0)
            s_po = stage_plan_oibu.get(sc, 0)
            s_pt = s_pj + s_po
            if s_pt > 0:
                planned_jasa = round(planned * s_pj / s_pt)
                planned_oibu = planned - planned_jasa
            else:
                planned_jasa = planned
                planned_oibu = 0
            # 적중률 계산
            if planned > 0 and qty > 0:
                hr = round(min(qty / planned, planned / qty) * 100, 1)
                ratio = round(qty / planned * 100, 1)
                if qty > planned:
                    status = "over"
                elif hr >= 90:
                    status = "normal"
                elif hr >= 70:
                    status = "under"
                else:
                    status = "fail"
            else:
                hr = 0.0
                ratio = 0.0
                status = "normal"
            new_menu_hits.append({
                "stage_code": sc,
                "stage": r.get("stage", ""),
                "product_code": r["product_code"],
                "product_name": r.get("product_name", ""),
                "label": "본",
                "planned": planned, "planned_jasa": planned_jasa, "planned_oibu": planned_oibu,
                "actual": qty, "actual_jasa": jasa, "actual_oibu": oibu,
                "hit_rate": hr, "ratio": ratio, "status": status
            })
        # 단계코드 → 계획 내림차순 정렬
        new_menu_hits.sort(key=lambda x: (x["stage_code"], -x["actual"]))
        d["menu_hits"] = new_menu_hits
        # 전체 적중률
        p_total = d.get("planned_total",0)
        if p_total > 0 and total > 0:
            d["total_hit_rate"] = round(min(total/p_total, p_total/total)*100, 1)
        else:
            d["total_hit_rate"] = 0.0
    return dr

def hr_class(hr):
    if hr >= 90: return "hr-excellent"
    if hr >= 70: return "hr-good"
    return "hr-poor"

def kpi_class(hr):
    if hr >= 90: return "kpi-green"
    if hr >= 70: return "kpi-yellow"
    return "kpi-red"

def build_overview_html(week_label, week_range_label, dr, today_iso="2026-04-15"):
    reported = [d for d in dr if d["actual_total"] > 0]
    n_days = len(dr)

    # 주간 누적 (보고된 일자만)
    wp = sum(d["planned_total"] for d in reported)
    wa = sum(d["actual_total"] for d in reported)
    wgap = wp - wa
    whr = round(min(wa/wp, wp/wa)*100,1) if (wp>0 and wa>0) else 0.0

    # 단계별 누적
    stage_agg = {sc: {"plan":0,"act":0} for sc in STAGE_ORDER}
    # 실적이 있으면 보고된 일자만 누적(W13 스타일), 없으면 전체 주의 계획을 누적
    days_for_stage = reported if reported else dr
    for d in days_for_stage:
        for sh in d.get("stage_hits",[]):
            sc = sh["stage_code"]
            if sc in stage_agg:
                stage_agg[sc]["plan"] += sh.get("planned",0)
                stage_agg[sc]["act"]  += sh.get("actual",0)

    # 이상 탐지 건수
    anomaly = 0
    for d in reported:
        for sh in d.get("stage_hits",[]):
            p = sh.get("planned",0); a = sh.get("actual",0)
            if p<=0: continue
            if a == 0:
                anomaly += 1; continue
            ratio = a/p
            hr = min(a/p, p/a)*100
            if ratio < 0.9 or ratio > 1.1:
                anomaly += 1

    # Executive Summary 문구
    if reported:
        status_msg = "전반적으로 예측 정확도가 양호합니다." if whr >= 90 else (
                     "단계별 편차가 있어 후속 보완이 필요합니다." if whr >= 70 else
                     "적중률이 낮아 긴급 점검이 필요합니다.")
        exec_text = (f"주간 누적 적중률 <b>{whr}%</b> "
                     f"(계획 {wp:,}병 vs 실적 {wa:,}병, {len(reported)}일/{n_days}일 집계). "
                     f"이상 탐지 {anomaly}건. {status_msg}")
    else:
        exec_text = (f"{week_label} 계획 총 {sum(d['planned_total'] for d in dr):,}병 배포 완료. "
                     f"실적 업로드 대기 중.")

    # KPI 색상
    hr_kpi_cls = kpi_class(whr) if reported else "kpi-blue"
    gap_kpi_cls = "kpi-red" if wgap > 0 else ("kpi-green" if wgap < 0 else "")
    anomaly_kpi_cls = "kpi-red" if anomaly > 10 else ("kpi-yellow" if anomaly > 0 else "kpi-green")

    # 일별 요약 행
    rows = []
    for d in dr:
        mmdd = d["date"][5:]
        dow = d["dow"]
        p = d["planned_total"]
        if d["actual_total"] > 0:
            a = d["actual_total"]
            gap = p - a
            hr = d["total_hit_rate"]
            gap_s = f"+{gap:,}" if gap > 0 else f"{gap:,}"
            status = '<span style="color:#2e7d32; font-weight:700;">확정</span>' if d["date"] <= today_iso else '<span style="color:#1565c0;">갱신 중</span>'
            rows.append(f'<tr><td>{mmdd}</td><td>{dow}</td><td class="num">{p:,}</td>'
                        f'<td class="num">{a:,}</td><td class="num">{gap_s}</td>'
                        f'<td class="{hr_class(hr)}">{hr}%</td><td>{status}</td></tr>')
        else:
            rows.append(f'<tr><td>{mmdd}</td><td>{dow}</td><td class="num">{p:,}</td>'
                        f'<td style="color:#bdbdbd;">-</td><td style="color:#bdbdbd;">-</td>'
                        f'<td style="color:#bdbdbd;">-</td><td style="color:#757575;">대기</td></tr>')
    # 합계행
    sumP = sum(d["planned_total"] for d in dr)
    sumA = sum(d["actual_total"] for d in dr)
    sumG = sumP - sumA
    sumGs = f"+{sumG:,}" if sumG > 0 else f"{sumG:,}"
    sumHR_s = f"{whr}%" if reported else "-"
    rows.append(f'<tr style="background:#e8eaf6; font-weight:700;"><td>합계</td><td></td>'
                f'<td class="num">{sumP:,}</td><td class="num">{sumA:,}</td><td class="num">{sumGs}</td>'
                f'<td style="color:#1a237e;">{sumHR_s}</td><td></td></tr>')
    daily_rows = "\n".join(rows)

    # 단계별 누적 행
    st_rows = []
    tp_total = sum(stage_agg[sc]["plan"] for sc in STAGE_ORDER)
    for sc in STAGE_ORDER:
        sp = stage_agg[sc]["plan"]; sa = stage_agg[sc]["act"]
        if reported:
            if sp == 0 and sa == 0:
                st_rows.append(f'<tr><td>{STAGE_NAME[sc]}</td><td class="num">-</td><td class="num">-</td><td class="num">-</td><td class="num">-</td></tr>')
                continue
            gap = sp - sa
            gap_s = f"+{gap:,}" if gap > 0 else f"{gap:,}"
            hr = round(min(sa/sp, sp/sa)*100,1) if (sp>0 and sa>0) else 0.0
            st_rows.append(f'<tr><td>{STAGE_NAME[sc]}</td><td class="num">{sp:,}</td>'
                           f'<td class="num">{sa:,}</td><td class="num">{gap_s}</td>'
                           f'<td class="{hr_class(hr)}">{hr}%</td></tr>')
        else:
            # 실적 대기: 계획 + 비중(%)
            share = round(sp / tp_total * 100, 1) if tp_total > 0 else 0.0
            st_rows.append(f'<tr><td>{STAGE_NAME[sc]}</td><td class="num">{sp:,}</td>'
                           f'<td class="num">{share}%</td></tr>')
    # 단계 합계
    tp = tp_total
    ta = sum(stage_agg[sc]["act"] for sc in STAGE_ORDER)
    tg = tp - ta
    tgs = f"+{tg:,}" if tg > 0 else f"{tg:,}"
    thr = round(min(ta/tp, tp/ta)*100,1) if (tp>0 and ta>0) else 0.0
    if reported:
        st_rows.append(f'<tr style="background:#e8eaf6; font-weight:700;"><td>합계</td>'
                       f'<td class="num">{tp:,}</td><td class="num">{ta:,}</td><td class="num">{tgs}</td>'
                       f'<td style="color:#1a237e;">{thr}%</td></tr>')
    else:
        st_rows.append(f'<tr style="background:#e8eaf6; font-weight:700;"><td>합계</td>'
                       f'<td class="num">{tp:,}</td><td style="color:#1a237e;">100.0%</td></tr>')
    stage_rows = "\n".join(st_rows)

    reported_days_label = f"{reported[0]['date'][5:]} ~ {reported[-1]['date'][5:]} ({len(reported)}일 확정)" if reported else f"계획 총 {sum(d['planned_total'] for d in dr):,}병 (실적 대기)"

    # KPI values
    wp_disp = f"{wp:,}" if reported else f"{sumP:,}"
    wa_disp = f"{wa:,}" if reported else "-"
    gap_disp = (f"+{wgap:,}" if wgap > 0 else f"{wgap:,}") if reported else "-"
    hr_disp = f"{whr}%" if reported else "-"

    html = f'''<div id="tab-overview" class="tab-content active">
<div class="exec">
  <div class="exec-title">{week_label} Executive Summary</div>
  <p>
    {exec_text}
  </p>
</div>

<div class="kpi-row">
  <div class="kpi-card">
    <div class="kpi-label">누적 적중률</div>
    <div class="kpi-value {hr_kpi_cls}">{hr_disp}</div>
    <div class="kpi-sub"></div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">계획 합계</div>
    <div class="kpi-value kpi-blue">{wp_disp}</div>
    <div class="kpi-sub">병</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">실적 합계</div>
    <div class="kpi-value kpi-blue">{wa_disp}</div>
    <div class="kpi-sub">병</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">Gap</div>
    <div class="kpi-value {gap_kpi_cls}">{gap_disp}</div>
    <div class="kpi-sub">계획 - 실적</div>
  </div>
  <div class="kpi-card has-tooltip">
    <div class="kpi-tooltip">
      <b>이상 탐지 기준</b><br>
      <span style="color:#ef9a9a;">&#9632;</span> 과소판매: 적중률 90% 미만<br>
      &nbsp;&nbsp;· high: 70% 미만 / medium: 70~90%<br>
      <span style="color:#ffcc80;">&#9632;</span> 과다판매: 적중률 110% 초과<br>
      &nbsp;&nbsp;· high: 130% 초과 / medium: 110~130%<br>
      <span style="color:#90caf9;">&#8505;</span> 미래 날짜는 과소판매 제외
    </div>
    <div class="kpi-label">이상 탐지</div>
    <div class="kpi-value {anomaly_kpi_cls}">{anomaly if reported else "-"}</div>
    <div class="kpi-sub">건</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">실적 현황</div>
    <div class="kpi-value kpi-blue">{len(reported)}<span style="font-size:14px; color:#999;">/{n_days}</span></div>
    <div class="kpi-sub">일</div>
  </div>
</div>

<div class="chart-row">
  <div class="chart-box" style="flex:1;"><div class="chart-title">일별 적중률 추이 (%)</div><canvas id="chartDailyHR" style="max-height:180px;"></canvas></div>
  <div class="chart-box" style="flex:1;"><div class="chart-title">일별 계획 vs 실적</div><canvas id="chartPlanActual" style="max-height:180px;"></canvas></div>
  <div class="chart-box" style="flex:1;"><div class="chart-title">단계별 누적 적중률</div><canvas id="chartStageHR" style="max-height:180px;"></canvas></div>
</div>

<h3 style="margin:16px 0 8px; color:#1a237e;">일별 요약</h3>
<table>
<thead><tr><th>날짜</th><th>요일</th><th>계획(병)</th><th>실적(병)</th><th>Gap</th><th>적중률</th><th>상태</th></tr></thead>
<tbody>
{daily_rows}
</tbody></table>
<h3 style="margin:16px 0 8px; color:#1a237e;">{("단계별 누적 적중률" if reported else "단계별 계획 수량")} <span style="font-size:11px; color:#666; font-weight:400;">{reported_days_label}</span></h3>
<table>
<thead><tr>{("<th>단계</th><th>계획(병)</th><th>실적(병)</th><th>Gap</th><th>적중률</th>" if reported else "<th>단계</th><th>계획(병)</th><th>비중</th>")}</tr></thead>
<tbody>
{stage_rows}
</tbody></table>
</div>'''
    return html


# W13 스타일 rerenderOverview (KPI 인덱스 [0,2,3,5], 3 차트 포함)
RERENDER_FN = r'''function rerenderOverview() {
  const tab = document.getElementById('tab-overview');
  if (!tab) return;

  const reported = dailyReports.filter(d => d.actual_total > 0);
  const stgPlan = reported.reduce((s,d) => s + (d.stage_hits||[]).reduce((ss,sh)=>ss+sh.planned,0), 0);
  const stgAct  = reported.reduce((s,d) => s + (d.stage_hits||[]).reduce((ss,sh)=>ss+sh.actual,0), 0);
  const stgHR = (stgPlan > 0 && stgAct > 0) ? Math.round(Math.min(stgAct/stgPlan, stgPlan/stgAct)*1000)/10 : 0;

  // 일별 요약 tbody 갱신 (첫 번째 table)
  const tbody = tab.querySelector('table tbody');
  if (tbody) {
    let rows = '';
    const today = new Date().toISOString().split('T')[0];
    dailyReports.forEach(dr => {
      if (dr.actual_total > 0) {
        const gap = dr.planned_total - dr.actual_total;
        const hrCls = dr.total_hit_rate >= 90 ? 'hr-excellent' : (dr.total_hit_rate >= 70 ? 'hr-good' : 'hr-poor');
        const statusH = dr.date <= today ? '<span style="color:#2e7d32; font-weight:700;">확정</span>' : '<span style="color:#1565c0;">갱신 중</span>';
        rows += '<tr><td>' + dr.date.substring(5) + '</td><td>' + dr.dow + '</td><td class="num">' + dr.planned_total.toLocaleString() + '</td>';
        rows += '<td class="num">' + dr.actual_total.toLocaleString() + '</td><td class="num">' + (gap>0?'+':'') + gap.toLocaleString() + '</td>';
        rows += '<td class="' + hrCls + '">' + dr.total_hit_rate + '%</td><td>' + statusH + '</td></tr>';
      } else {
        rows += '<tr><td>' + dr.date.substring(5) + '</td><td>' + dr.dow + '</td><td class="num">' + dr.planned_total.toLocaleString() + '</td>';
        rows += '<td style="color:#bdbdbd;">-</td><td style="color:#bdbdbd;">-</td><td style="color:#bdbdbd;">-</td><td style="color:#757575;">대기</td></tr>';
      }
    });
    const sumP = dailyReports.reduce((s,d)=>s+d.planned_total,0);
    const sumA = dailyReports.reduce((s,d)=>s+d.actual_total,0);
    const sumG = sumP - sumA;
    const sumHR = (reported.length > 0 && sumA > 0) ? Math.round(Math.min(sumA/sumP, sumP/sumA)*1000)/10 : 0;
    rows += '<tr style="background:#e8eaf6; font-weight:700;"><td>합계</td><td></td><td class="num">' + sumP.toLocaleString() + '</td>';
    rows += '<td class="num">' + sumA.toLocaleString() + '</td><td class="num">' + (sumG>0?'+':'') + sumG.toLocaleString() + '</td>';
    rows += '<td style="color:#1a237e;">' + (reported.length>0?sumHR+'%':'-') + '</td><td></td></tr>';
    tbody.innerHTML = rows;
  }

  // 단계별 표 전체 재구성 (두 번째 table) - 실적 여부에 따라 구조 변경
  const tables = tab.querySelectorAll('table');
  if (tables.length >= 2) {
    const stageOrder = ['1110','1210','1220','1230','1240','1250','1310','1320','1330'];
    const stageName = {'1110':'준비기','1210':'초기1','1220':'초기2','1230':'중기','1240':'후기','1250':'후기무른밥','1310':'영양밥','1320':'영양국','1330':'영양찬'};
    const agg = {};
    stageOrder.forEach(sc => agg[sc] = {plan:0, act:0});
    const stageSrc = reported.length > 0 ? reported : dailyReports;
    stageSrc.forEach(d => (d.stage_hits||[]).forEach(sh => {
      if (agg[sh.stage_code]) { agg[sh.stage_code].plan += sh.planned; agg[sh.stage_code].act += sh.actual; }
    }));
    const tp = stageOrder.reduce((s,sc)=>s+agg[sc].plan,0);
    const ta = stageOrder.reduce((s,sc)=>s+agg[sc].act,0);
    let theadHtml, srows = '';
    if (reported.length > 0) {
      theadHtml = '<tr><th>단계</th><th>계획(병)</th><th>실적(병)</th><th>Gap</th><th>적중률</th></tr>';
      stageOrder.forEach(sc => {
        const p = agg[sc].plan, a = agg[sc].act;
        if (p === 0 && a === 0) {
          srows += '<tr><td>' + stageName[sc] + '</td><td class="num">-</td><td class="num">-</td><td class="num">-</td><td class="num">-</td></tr>';
        } else {
          const gap = p - a;
          const hr = (p>0 && a>0) ? Math.round(Math.min(a/p, p/a)*1000)/10 : 0;
          const cls = hr >= 90 ? 'hr-excellent' : (hr >= 70 ? 'hr-good' : 'hr-poor');
          srows += '<tr><td>' + stageName[sc] + '</td><td class="num">' + p.toLocaleString() + '</td><td class="num">' + a.toLocaleString() + '</td><td class="num">' + (gap>0?'+':'') + gap.toLocaleString() + '</td><td class="' + cls + '">' + hr + '%</td></tr>';
        }
      });
      const tg = tp - ta;
      const thr = (tp>0 && ta>0) ? Math.round(Math.min(ta/tp, tp/ta)*1000)/10 : 0;
      srows += '<tr style="background:#e8eaf6; font-weight:700;"><td>합계</td><td class="num">' + tp.toLocaleString() + '</td><td class="num">' + ta.toLocaleString() + '</td><td class="num">' + (tg>0?'+':'') + tg.toLocaleString() + '</td><td style="color:#1a237e;">' + thr + '%</td></tr>';
    } else {
      theadHtml = '<tr><th>단계</th><th>계획(병)</th><th>비중</th></tr>';
      stageOrder.forEach(sc => {
        const p = agg[sc].plan;
        const share = tp > 0 ? Math.round(p / tp * 1000) / 10 : 0;
        srows += '<tr><td>' + stageName[sc] + '</td><td class="num">' + p.toLocaleString() + '</td><td class="num">' + share + '%</td></tr>';
      });
      srows += '<tr style="background:#e8eaf6; font-weight:700;"><td>합계</td><td class="num">' + tp.toLocaleString() + '</td><td style="color:#1a237e;">100.0%</td></tr>';
    }
    tables[1].innerHTML = '<thead>' + theadHtml + '</thead><tbody>' + srows + '</tbody>';
  }

  // 이상 탐지 건수
  let anomaly = 0;
  reported.forEach(d => (d.stage_hits||[]).forEach(sh => {
    if (!sh.planned) return;
    const ratio = sh.actual / sh.planned;
    if (sh.actual === 0) { anomaly++; return; }
    if (ratio < 0.9 || ratio > 1.1) anomaly++;
  }));

  // KPI 카드 갱신 (순서: 적중률, 계획, 실적, Gap, 이상 탐지, 실적 현황)
  const kpiCards = tab.querySelectorAll('.kpi-card');
  if (kpiCards.length >= 6) {
    const sumP = dailyReports.reduce((s,d)=>s+d.planned_total,0);
    const hrCls = stgHR >= 90 ? 'kpi-green' : (stgHR >= 70 ? 'kpi-yellow' : 'kpi-red');
    if (reported.length > 0) {
      kpiCards[0].querySelector('.kpi-value').className = 'kpi-value ' + hrCls;
      kpiCards[0].querySelector('.kpi-value').textContent = stgHR + '%';
      kpiCards[1].querySelector('.kpi-value').textContent = stgPlan.toLocaleString();
      kpiCards[2].querySelector('.kpi-value').textContent = stgAct.toLocaleString();
      const gap = stgPlan - stgAct;
      const gapCls = gap > 0 ? 'kpi-red' : (gap < 0 ? 'kpi-green' : '');
      kpiCards[3].querySelector('.kpi-value').className = 'kpi-value ' + gapCls;
      kpiCards[3].querySelector('.kpi-value').textContent = (gap>0?'+':'') + gap.toLocaleString();
      const aCls = anomaly > 10 ? 'kpi-red' : (anomaly > 0 ? 'kpi-yellow' : 'kpi-green');
      kpiCards[4].querySelector('.kpi-value').className = 'kpi-value ' + aCls;
      kpiCards[4].querySelector('.kpi-value').textContent = anomaly;
    } else {
      kpiCards[1].querySelector('.kpi-value').textContent = sumP.toLocaleString();
    }
    kpiCards[5].querySelector('.kpi-value').innerHTML = reported.length + '<span style="font-size:14px; color:#999;">/' + dailyReports.length + '</span>';
  }

  // 차트 재생성
  ['chartDailyHR','chartPlanActual','chartStageHR'].forEach(id => {
    const canvas = document.getElementById(id);
    if (canvas) {
      const existing = Chart.getChart(canvas);
      if (existing) existing.destroy();
    }
  });

  if (reported.length > 0) {
    new Chart(document.getElementById('chartDailyHR'), {
      type:'line',
      data:{
        labels:reported.map(d=>d.date.replace('2026-','')),
        datasets:[{
          label:'적중률(%)',data:reported.map(d=>d.total_hit_rate),
          borderColor:'#1a237e',backgroundColor:'rgba(26,35,126,0.1)',fill:true,tension:0.3,pointRadius:5
        },{label:'90',data:reported.map(()=>90),borderColor:'#e53935',borderWidth:1,borderDash:[4,4],pointRadius:0,fill:false}]
      },
      options:{scales:{y:{min:60,max:100,ticks:{stepSize:10}}},plugins:{legend:{display:false}}}
    });

    new Chart(document.getElementById('chartPlanActual'), {
      type:'bar',
      data:{
        labels:dailyReports.map(d=>d.date.replace('2026-','')+'('+d.dow+')'),
        datasets:[
          {label:'계획',data:dailyReports.map(d=>d.planned_total),backgroundColor:'#90caf9'},
          {label:'실적',data:dailyReports.map(d=>d.actual_total||null),backgroundColor:'#1a237e'}
        ]
      },
      options:{plugins:{legend:{position:'bottom'}}}
    });

    // 단계별 누적 적중률 bar chart
    const stageOrder = ['1110','1210','1220','1230','1240','1250','1310','1320','1330'];
    const stageName = {'1110':'준비기','1210':'초기1','1220':'초기2','1230':'중기','1240':'후기','1250':'후기무른밥','1310':'영양밥','1320':'영양국','1330':'영양찬'};
    const agg = {};
    stageOrder.forEach(sc => agg[sc] = {plan:0, act:0});
    reported.forEach(d => (d.stage_hits||[]).forEach(sh => {
      if (agg[sh.stage_code]) { agg[sh.stage_code].plan += sh.planned; agg[sh.stage_code].act += sh.actual; }
    }));
    const labels = stageOrder.map(sc => stageName[sc]);
    const hrs = stageOrder.map(sc => {
      const p = agg[sc].plan, a = agg[sc].act;
      return (p>0 && a>0) ? Math.round(Math.min(a/p, p/a)*1000)/10 : 0;
    });
    const colors = hrs.map(h => h>=90 ? '#43a047' : (h>=70 ? '#fdd835' : '#e53935'));
    new Chart(document.getElementById('chartStageHR'), {
      type:'bar',
      data:{labels:labels, datasets:[{label:'적중률(%)', data:hrs, backgroundColor:colors}]},
      options:{scales:{y:{min:0,max:110,ticks:{stepSize:20}}},plugins:{legend:{display:false}}}
    });
  }
}'''

# W13 Executive Summary 문구는 rerenderOverview()가 exec-title 아래 p를 갱신하도록 유도 — 단, W13은 exec를 갱신하지 않으므로
# 여기서도 exec는 갱신하지 않고 첫 렌더 스냅샷을 그대로 둠

def replace_overview(html, week_label, week_range, dr_merged):
    new_overview = build_overview_html(week_label, week_range, dr_merged)
    # 기존 overview 한 줄 교체: <div id="tab-overview" ... </div>\n (그 뒤가 <div id="tab-day_ 또는 <div id="tab-action")
    # 해당 div는 한 줄(단일 라인)에 있다고 가정
    pattern = re.compile(r'<div id="tab-overview"[\s\S]*?</div>\s*(?=<div id="tab-day_|<div id="tab-action)')
    # 위 패턴은 동작할 것이나 overview 내 중첩 </div>가 많아 신중해야 함.
    # 실제 구조 (W15 기준): 한 줄에 전체가 있고 끝이 </div>로 마무리된 직후 다음 div가 옴.
    # 따라서 탐욕이 아닌 '최초 일치'가 아니라 '다음 경계 직전'을 찾는 lookahead로 충분.
    m = pattern.search(html)
    if not m:
        raise RuntimeError("overview block not found")
    return html[:m.start()] + new_overview + "\n" + html[m.end():]

def replace_rerender(html):
    # 기존 rerenderOverview() 함수 전체를 W13 스타일로 교체
    # 함수 시작 'function rerenderOverview()' 부터 다음 'function ' 선언 직전까지
    m = re.search(r'function rerenderOverview\(\) \{', html)
    if not m:
        raise RuntimeError("rerenderOverview not found")
    # 중괄호 매칭으로 함수 끝 찾기
    start = m.start()
    i = m.end() - 1  # position of '{'
    depth = 0
    while i < len(html):
        if html[i] == '{': depth += 1
        elif html[i] == '}':
            depth -= 1
            if depth == 0:
                end = i + 1
                break
        i += 1
    else:
        raise RuntimeError("rerenderOverview close not found")
    return html[:start] + RERENDER_FN + html[end:]

WEEKS = {
    "w14": {"label":"W14","range":"03-30 ~ 04-04","file":"monitor_w14.html"},
    "w15": {"label":"W15","range":"04-06 ~ 04-11","file":"monitor_w15.html"},
    "w16": {"label":"W16","range":"04-13 ~ 04-18","file":"monitor_w16.html"},
    "w17": {"label":"W17","range":"04-20 ~ 04-25","file":"monitor_w17.html"},
}

def process(week_key):
    info = WEEKS[week_key]
    path = ROOT / info["file"]
    html = path.read_text(encoding="utf-8")
    m = re.search(r'const dailyReports = (\[.*?\]);', html, re.DOTALL)
    if not m:
        raise RuntimeError(f"dailyReports not found in {info['file']}")
    dr = json.loads(m.group(1))
    # merge
    dr_merged = merge_actual(dr)
    # dailyReports도 HTML에 갱신 (JS에서 쓰므로 최신 실적 반영)
    new_dr_json = json.dumps(dr_merged, ensure_ascii=False)
    html = html[:m.start()] + 'const dailyReports = ' + new_dr_json + ';' + html[m.end():]

    # overview 교체
    html = replace_overview(html, info["label"], info["range"], dr_merged)

    # rerenderOverview 교체
    html = replace_rerender(html)

    path.write_text(html, encoding="utf-8")
    print(f"[OK] {info['file']} 갱신 완료")

if __name__ == "__main__":
    targets = sys.argv[1:] if len(sys.argv) > 1 else list(WEEKS.keys())
    for t in targets:
        process(t)
