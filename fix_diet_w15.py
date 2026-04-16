# -*- coding: utf-8 -*-
"""
1) 모든 모니터(W12~W17) rerenderDayTab에 식단시작일 조절 컬럼 추가
2) W15 04-06~04-11 메뉴별 실적 반영 (actual.json -> menu_hits 매칭)
"""
import json, re
from pathlib import Path

MONITORS = ['monitor_w12.html','monitor_w13.html','monitor_w14.html',
            'monitor_w15.html','monitor_w16.html','monitor_w17.html']

# ═══════════════════════════════════════
# 1) rerenderDayTab에 식단시작일 조절 추가
# ═══════════════════════════════════════
print("=== 식단시작일 조절 컬럼 패치 ===")

# 패치 대상: rerenderDayTab의 메뉴 테이블 헤더와 각 행에 체크박스 컬럼 추가
# 헤더: <th rowspan="2">상태</th> 뒤에 <th rowspan="2" style="min-width:130px;">식단시작일 조절</th>
# 행: </td></tr> 전에 체크박스 셀 추가

for fn in MONITORS:
    p = Path(fn)
    t = p.read_text(encoding='utf-8')
    changed = False

    # (A) 헤더에 식단시작일 컬럼이 없으면 추가
    # rerenderDayTab 내 메뉴 헤더: '<th rowspan="2">적중률</th><th rowspan="2">상태</th></tr>';
    old_hdr = "'<th rowspan=\"2\">적중률</th><th rowspan=\"2\">상태</th></tr>';"
    new_hdr = """'<th rowspan="2">적중률</th><th rowspan="2">상태</th><th rowspan="2" style="min-width:130px;">식단시작일 조절</th></tr>';"""
    if old_hdr in t and '식단시작일 조절</th></tr>' not in t.split('function rerenderDayTab')[1].split('function ')[0] if 'function rerenderDayTab' in t else True:
        # Check if already patched in rerenderDayTab
        if 'function rerenderDayTab' in t:
            # Find the rerenderDayTab function
            rdt_start = t.index('function rerenderDayTab')
            # Find next function or end of script
            rdt_section = t[rdt_start:rdt_start+5000]
            if '식단시작일 조절' not in rdt_section:
                t = t[:rdt_start] + rdt_section.replace(old_hdr, new_hdr, 1) + t[rdt_start+5000:]
                changed = True
                print(f"  {fn}: 헤더 패치")

    # (B) 메뉴 행 끝에 체크박스 컬럼 추가
    # 현재: + (statusMap[st]||'') + '</td></tr>';
    old_row_end = """+ (statusMap[st]||'') + '</td></tr>';"""
    new_row_end = """+ (statusMap[st]||'') + '</td>' + '<td style="min-width:130px; padding:0; position:relative;"><div style="display:flex; align-items:center; justify-content:center; height:100%; padding:7px 6px;"><input type="checkbox" id="cb_' + dr.date + '_' + mh.product_code + '" class="diet-cb" onchange="saveCB(this)" style="position:absolute; left:50%; transform:translateX(-50%);"><span class="cb-ts" style="font-size:10px; color:#666; margin-left:calc(50% + 12px); white-space:nowrap;"></span></div></td></tr>';"""
    if 'function rerenderDayTab' in t:
        rdt_start = t.index('function rerenderDayTab')
        rdt_section = t[rdt_start:rdt_start+5000]
        if 'diet-cb' not in rdt_section and old_row_end in rdt_section:
            rdt_section = rdt_section.replace(old_row_end, new_row_end, 1)
            t = t[:rdt_start] + rdt_section + t[rdt_start+5000:]
            changed = True
            print(f"  {fn}: 행 체크박스 패치")

    # (C) 합계행에도 빈 셀 추가
    # 현재 합계행 끝: + mSumHR + '%</td><td></td></tr>';
    old_sum_end = """+ mSumHR + '%</td><td></td></tr>';"""
    new_sum_end = """+ mSumHR + '%</td><td></td><td></td></tr>';"""
    if 'function rerenderDayTab' in t:
        rdt_start = t.index('function rerenderDayTab')
        rdt_section = t[rdt_start:rdt_start+5000]
        if old_sum_end in rdt_section and new_sum_end not in rdt_section:
            rdt_section = rdt_section.replace(old_sum_end, new_sum_end, 1)
            t = t[:rdt_start] + rdt_section + t[rdt_start+5000:]
            changed = True
            print(f"  {fn}: 합계행 패치")

    # (D) restoreCB 호출 추가 — rerenderDayTab 루프 후 restoreCB() 호출
    # loadActualData().then 블록 내에 restoreCB 호출 확인
    if 'restoreCB()' not in t.split('loadActualData')[1][:500] if 'loadActualData' in t else True:
        # updateNavDots(); 뒤에 restoreCB(); 추가
        if 'loadActualData' in t:
            after_load = t.split('loadActualData')[1][:500]
            if 'restoreCB()' not in after_load:
                t = t.replace(
                    'try { renderActionBoard(); } catch(e) {}\n});',
                    'try { renderActionBoard(); } catch(e) {}\n  try { restoreCB(); } catch(e) {}\n});',
                    1,
                )
                changed = True
                print(f"  {fn}: restoreCB 호출 추가")

    if changed:
        p.write_text(t, encoding='utf-8')
        print(f"  [OK] {fn}")
    else:
        print(f"  {fn}: no changes needed or already patched")

# ═══════════════════════════════════════
# 2) W15 메뉴별 실적 반영
# ═══════════════════════════════════════
print("\n=== W15 메뉴별 실적 반영 ===")
w15_path = Path('monitor_w15.html')
text15 = w15_path.read_text(encoding='utf-8')
m15 = re.search(r'^const dailyReports = (\[.*?\]);\s*$', text15, re.M | re.S)
daily15 = json.loads(m15.group(1))
by_date15 = {d['date']: d for d in daily15}

actual = json.load(open('data/actual.json', encoding='utf-8'))

w15_dates = ['2026-04-06','2026-04-07','2026-04-08','2026-04-09','2026-04-10','2026-04-11']

for dt in w15_dates:
    dr = by_date15.get(dt)
    if not dr:
        continue
    act_menus = actual.get(dt)
    if not act_menus:
        print(f"  {dt}: no actual data in actual.json")
        continue

    has_menu_actual = any((mh.get('actual') or 0) > 0 for mh in dr.get('menu_hits', []))
    if has_menu_actual:
        print(f"  {dt}: skip (already has menu actuals)")
        continue

    planned_map = {(mh['stage_code'], mh['product_code']): mh for mh in dr['menu_hits']}
    total_actual = 0
    stage_actual = {}
    ch_actual = {'jasa': 0, 'oibu': 0}

    for am in act_menus:
        key = (am['stage_code'], am['product_code'])
        total_actual += am['qty']
        stage_actual[am['stage_code']] = stage_actual.get(am['stage_code'], 0) + am['qty']
        ch_actual['jasa'] += am.get('jasa', 0)
        ch_actual['oibu'] += am.get('oibu', 0)

        if key in planned_map:
            mh = planned_map[key]
            mh['actual'] = am['qty']
            mh['actual_jasa'] = am.get('jasa', 0)
            mh['actual_oibu'] = am.get('oibu', 0)
            p = mh.get('planned', 0)
            a = am['qty']
            if p > 0 and a > 0:
                mh['hit_rate'] = round(min(a/p, p/a) * 1000) / 10
                mh['ratio'] = round(a/p * 1000) / 10
                mh['status'] = 'normal' if mh['hit_rate'] >= 90 else ('over' if a > p else 'under')
            elif p == 0 and a > 0:
                mh['hit_rate'] = 0.0
                mh['status'] = 'unplanned'
        else:
            dr['menu_hits'].append({
                'stage_code': am['stage_code'], 'stage': am['stage'],
                'product_code': am['product_code'], 'product_name': am['product_name'],
                'label': '', 'planned': 0, 'planned_jasa': 0, 'planned_oibu': 0,
                'actual': am['qty'], 'actual_jasa': am.get('jasa', 0), 'actual_oibu': am.get('oibu', 0),
                'hit_rate': 0.0, 'ratio': 0.0, 'status': 'unplanned',
            })

    for sh in dr['stage_hits']:
        sh['actual'] = stage_actual.get(sh['stage_code'], 0)
        p, a = sh['planned'], sh['actual']
        if p > 0 and a > 0:
            sh['hit_rate'] = round(min(a/p, p/a) * 1000) / 10
            sh['status'] = 'normal' if sh['hit_rate'] >= 90 else ('over' if a > p else 'under')
        elif a == 0:
            sh['hit_rate'] = 0.0; sh['status'] = 'under'
        else:
            sh['hit_rate'] = 0.0; sh['status'] = 'over'

    for ch in dr['channel_hits']:
        if ch['channel'] == '자사몰': ch['actual'] = ch_actual['jasa']
        elif ch['channel'] == '외부몰': ch['actual'] = ch_actual['oibu']
        p, a = ch['planned'], ch['actual']
        ch['hit_rate'] = round(min(a/p, p/a) * 1000) / 10 if (p > 0 and a > 0) else 0.0

    dr['actual_total'] = total_actual
    p, a = dr['planned_total'], total_actual
    dr['total_hit_rate'] = round(min(a/p, p/a) * 1000) / 10 if (p > 0 and a > 0) else 0.0

    normal = sum(1 for sh in dr['stage_hits'] if sh['hit_rate'] >= 90)
    warning = sum(1 for sh in dr['stage_hits'] if 70 <= sh['hit_rate'] < 90)
    critical = sum(1 for sh in dr['stage_hits'] if sh['hit_rate'] < 70)
    dr['summary'] = {'normal': normal, 'warning': warning, 'critical': critical}

    mh_act = sum(1 for mh in dr['menu_hits'] if (mh.get('actual') or 0) > 0)
    print(f"  {dt}: total={total_actual:,} menus_act={mh_act}/{len(dr['menu_hits'])} hr={dr['total_hit_rate']}%")

new_json15 = json.dumps(daily15, ensure_ascii=False)
text15_new = text15.replace(m15.group(1), new_json15, 1)
w15_path.write_text(text15_new, encoding='utf-8')
print("[OK] monitor_w15.html")
