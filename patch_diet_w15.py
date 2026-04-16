# -*- coding: utf-8 -*-
"""
1) 식단시작일 조절 컬럼을 rerenderDayTab에 추가 (W12~W17)
2) W15 메뉴별 실적 반영
"""
import json, re
from pathlib import Path

MONITORS = ['monitor_w12.html','monitor_w13.html','monitor_w14.html',
            'monitor_w15.html','monitor_w16.html','monitor_w17.html']

# ═══════════════════════════════════════
# 1) rerenderDayTab 식단시작일 조절 패치
# ═══════════════════════════════════════
print("=== diet column patch ===")

# 정확한 대상 문자열 (JS 코드 내)
HDR_OLD = """html += '<th rowspan="2">적중률</th><th rowspan="2">상태</th></tr>';"""
HDR_NEW = """html += '<th rowspan="2">적중률</th><th rowspan="2">상태</th><th rowspan="2" style="min-width:130px;">식단시작일 조절</th></tr>';"""

ROW_OLD = """html += '<td class="' + hrCls + '">' + mh.hit_rate + '%</td>';
      html += '<td style="color:' + (statusColor[st]||'#333') + '; font-weight:600; font-size:12px;">' + (statusMap[st]||'') + '</td></tr>';"""
ROW_NEW = """html += '<td class="' + hrCls + '">' + mh.hit_rate + '%</td>';
      html += '<td style="color:' + (statusColor[st]||'#333') + '; font-weight:600; font-size:12px;">' + (statusMap[st]||'') + '</td>';
      html += '<td style="min-width:130px; padding:0; position:relative;"><div style="display:flex; align-items:center; justify-content:center; height:100%; padding:7px 6px;"><input type="checkbox" id="cb_' + dr.date + '_' + mh.product_code + '" class="diet-cb" onchange="saveCB(this)" style="position:absolute; left:50%; transform:translateX(-50%);"><span class="cb-ts" style="font-size:10px; color:#666; margin-left:calc(50% + 12px); white-space:nowrap;"></span></div></td></tr>';"""

SUM_OLD = """html += '<td style="color:#1a237e;">' + mSumHR + '%</td><td></td></tr>';"""
SUM_NEW = """html += '<td style="color:#1a237e;">' + mSumHR + '%</td><td></td><td></td></tr>';"""

RESTORE_AFTER = "try { renderActionBoard(); } catch(e) {}\n});"
RESTORE_NEW = "try { renderActionBoard(); } catch(e) {}\n  try { restoreCB(); } catch(e) {}\n});"

for fn in MONITORS:
    p = Path(fn)
    t = p.read_text(encoding='utf-8')
    changes = []

    if HDR_OLD in t and 'min-width:130px' not in t[t.find(HDR_OLD):t.find(HDR_OLD)+200]:
        t = t.replace(HDR_OLD, HDR_NEW, 1)
        changes.append('hdr')

    if ROW_OLD in t and 'diet-cb' not in t[t.find("statusMap[st]||''") + 50: t.find("statusMap[st]||''") + 500] if "statusMap[st]||''" in t else True:
        t = t.replace(ROW_OLD, ROW_NEW, 1)
        changes.append('row')

    if SUM_OLD in t:
        # Only patch if the sum row doesn't already have extra <td>
        idx = t.find(SUM_OLD)
        if idx >= 0:
            t = t.replace(SUM_OLD, SUM_NEW, 1)
            changes.append('sum')

    if RESTORE_AFTER in t and 'restoreCB' not in t[t.find(RESTORE_AFTER)-20:t.find(RESTORE_AFTER)+100]:
        t = t.replace(RESTORE_AFTER, RESTORE_NEW, 1)
        changes.append('restoreCB')

    if changes:
        p.write_text(t, encoding='utf-8')
        print(f"  [OK] {fn}: {', '.join(changes)}")
    else:
        print(f"  {fn}: already patched")

# Verify
print("\n=== Verify ===")
for fn in MONITORS:
    t = Path(fn).read_text(encoding='utf-8')
    s = t.find('function rerenderDayTab')
    if s < 0:
        print(f"  {fn}: no rerenderDayTab")
        continue
    sec = t[s:s+5000]
    has_hdr = '식단시작일 조절' in sec
    has_cb = 'diet-cb' in sec
    has_restore = 'restoreCB' in t[t.find('loadActualData'):] if 'loadActualData' in t else False
    print(f"  {fn}: hdr={has_hdr} cb={has_cb} restore={has_restore}")

# ═══════════════════════════════════════
# 2) W15 메뉴별 실적 반영
# ═══════════════════════════════════════
print("\n=== W15 menu actual fix ===")
w15_path = Path('monitor_w15.html')
text15 = w15_path.read_text(encoding='utf-8')
m15 = re.search(r'^const dailyReports = (\[.*?\]);\s*$', text15, re.M | re.S)
daily15 = json.loads(m15.group(1))
by_date15 = {d['date']: d for d in daily15}

actual = json.load(open('data/actual.json', encoding='utf-8'))

for dt in ['2026-04-06','2026-04-07','2026-04-08','2026-04-09','2026-04-10','2026-04-11']:
    dr = by_date15.get(dt)
    if not dr:
        continue
    act_menus = actual.get(dt)
    if not act_menus:
        print(f"  {dt}: no actual data")
        continue
    if any((mh.get('actual') or 0) > 0 for mh in dr.get('menu_hits', [])):
        print(f"  {dt}: skip")
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
            p, a = mh.get('planned', 0), am['qty']
            if p > 0 and a > 0:
                mh['hit_rate'] = round(min(a/p, p/a)*1000)/10
                mh['ratio'] = round(a/p*1000)/10
                mh['status'] = 'normal' if mh['hit_rate']>=90 else ('over' if a>p else 'under')
            elif p==0 and a>0:
                mh['hit_rate'] = 0.0; mh['status'] = 'unplanned'
        else:
            dr['menu_hits'].append({
                'stage_code':am['stage_code'],'stage':am['stage'],
                'product_code':am['product_code'],'product_name':am['product_name'],
                'label':'','planned':0,'planned_jasa':0,'planned_oibu':0,
                'actual':am['qty'],'actual_jasa':am.get('jasa',0),'actual_oibu':am.get('oibu',0),
                'hit_rate':0.0,'ratio':0.0,'status':'unplanned',
            })

    for sh in dr['stage_hits']:
        sh['actual'] = stage_actual.get(sh['stage_code'], 0)
        p, a = sh['planned'], sh['actual']
        if p>0 and a>0:
            sh['hit_rate'] = round(min(a/p,p/a)*1000)/10
            sh['status'] = 'normal' if sh['hit_rate']>=90 else ('over' if a>p else 'under')
        elif a==0: sh['hit_rate']=0.0; sh['status']='under'
        else: sh['hit_rate']=0.0; sh['status']='over'

    for ch in dr['channel_hits']:
        if ch['channel']=='자사몰': ch['actual']=ch_actual['jasa']
        elif ch['channel']=='외부몰': ch['actual']=ch_actual['oibu']
        p, a = ch['planned'], ch['actual']
        ch['hit_rate'] = round(min(a/p,p/a)*1000)/10 if (p>0 and a>0) else 0.0

    dr['actual_total'] = total_actual
    p, a = dr['planned_total'], total_actual
    dr['total_hit_rate'] = round(min(a/p,p/a)*1000)/10 if (p>0 and a>0) else 0.0
    dr['summary'] = {
        'normal': sum(1 for sh in dr['stage_hits'] if sh['hit_rate']>=90),
        'warning': sum(1 for sh in dr['stage_hits'] if 70<=sh['hit_rate']<90),
        'critical': sum(1 for sh in dr['stage_hits'] if sh['hit_rate']<70),
    }
    mh_act = sum(1 for mh in dr['menu_hits'] if (mh.get('actual') or 0)>0)
    print(f"  {dt}: total={total_actual:,} act={mh_act}/{len(dr['menu_hits'])} hr={dr['total_hit_rate']}%")

new_json15 = json.dumps(daily15, ensure_ascii=False)
text15_new = text15.replace(m15.group(1), new_json15, 1)
w15_path.write_text(text15_new, encoding='utf-8')
print("[OK] monitor_w15.html")
