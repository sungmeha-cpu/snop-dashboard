# -*- coding: utf-8 -*-
"""
Fix 1: W13 03-27 녹미단호박스프(12059) label → '본'
Fix 2: W14 04-02~04-04 메뉴별 실적 반영 (actual.json → menu_hits 매칭)
"""
import json, re
from pathlib import Path

# ═══════════════ Fix 1: W13 03-27 녹미단호박스프 label ═══════════════
print("=== Fix 1: W13 03-27 녹미단호박스프 label='본' ===")
w13 = Path('monitor_w13.html')
text13 = w13.read_text(encoding='utf-8')
m13 = re.search(r'^const dailyReports = (\[.*?\]);\s*$', text13, re.M | re.S)
daily13 = json.loads(m13.group(1))

d27 = next(d for d in daily13 if d['date'] == '2026-03-27')
for mh in d27['menu_hits']:
    if mh['product_code'] == '12059' and mh['stage_code'] == '1320':
        old_label = mh.get('label', '')
        mh['label'] = '본'
        print(f"  {mh['product_name']}: label '{old_label}' -> '본'")

new_json13 = json.dumps(daily13, ensure_ascii=False)
text13_new = text13.replace(m13.group(1), new_json13, 1)
w13.write_text(text13_new, encoding='utf-8')
print("[OK] monitor_w13.html 저장")

# ═══════════════ Fix 2: W14 메뉴별 실적 반영 ═══════════════
print("\n=== Fix 2: W14 메뉴별 실적 반영 (actual.json → menu_hits) ===")
w14 = Path('monitor_w14.html')
text14 = w14.read_text(encoding='utf-8')
m14 = re.search(r'^const dailyReports = (\[.*?\]);\s*$', text14, re.M | re.S)
daily14 = json.loads(m14.group(1))

actual = json.load(open('data/actual.json', encoding='utf-8'))
by_date14 = {d['date']: d for d in daily14}

# W14 범위: 03-30 ~ 04-04
w14_dates = ['2026-03-30','2026-03-31','2026-04-01','2026-04-02','2026-04-03','2026-04-04']

for dt in w14_dates:
    dr = by_date14.get(dt)
    if not dr:
        continue
    act_menus = actual.get(dt)
    if not act_menus:
        continue
    # 메뉴별 실적이 이미 있으면 스킵
    has_menu_actual = any((mh.get('actual') or 0) > 0 for mh in dr.get('menu_hits', []))
    if has_menu_actual:
        print(f"  {dt}: skip (menu actual exists)")
        continue

    print(f"  {dt}: 메뉴별 실적 매칭 중...")

    # 1) 기존 menu_hits → 예측 메뉴 (planned)
    planned_map = {}
    for mh in dr['menu_hits']:
        key = (mh['stage_code'], mh['product_code'])
        planned_map[key] = mh

    # 2) actual.json 메뉴로 실적 매칭
    matched = 0
    unmatched_actual = []
    total_actual = 0
    stage_actual = {}
    ch_actual = {'자사몰': 0, '외부몰': 0}

    for am in act_menus:
        key = (am['stage_code'], am['product_code'])
        total_actual += am['qty']
        stage_actual[am['stage_code']] = stage_actual.get(am['stage_code'], 0) + am['qty']
        ch_actual['자사몰'] += am.get('jasa', 0)
        ch_actual['외부몰'] += am.get('oibu', 0)

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
                mh['ratio'] = 0.0
                mh['status'] = 'unplanned'
            matched += 1
        else:
            # 미예측 메뉴 — menu_hits에 추가
            mh_new = {
                'stage_code': am['stage_code'],
                'stage': am['stage'],
                'product_code': am['product_code'],
                'product_name': am['product_name'],
                'label': '',
                'planned': 0,
                'planned_jasa': 0,
                'planned_oibu': 0,
                'actual': am['qty'],
                'actual_jasa': am.get('jasa', 0),
                'actual_oibu': am.get('oibu', 0),
                'hit_rate': 0.0,
                'ratio': 0.0,
                'status': 'unplanned',
            }
            dr['menu_hits'].append(mh_new)
            unmatched_actual.append(am['product_name'])

    # 3) 단계별 재집계
    for sh in dr['stage_hits']:
        sc = sh['stage_code']
        sh['actual'] = stage_actual.get(sc, 0)
        p, a = sh['planned'], sh['actual']
        if p > 0 and a > 0:
            sh['hit_rate'] = round(min(a/p, p/a) * 1000) / 10
            sh['ratio'] = round(a/p * 1000) / 10
            sh['status'] = 'normal' if sh['hit_rate'] >= 90 else ('over' if a > p else 'under')
        elif a == 0:
            sh['hit_rate'] = 0.0
            sh['status'] = 'under'
        else:
            sh['hit_rate'] = 0.0
            sh['status'] = 'over'

    # 4) 채널별
    for ch in dr['channel_hits']:
        ch['actual'] = ch_actual.get(ch['channel'], 0)
        p, a = ch['planned'], ch['actual']
        if p > 0 and a > 0:
            ch['hit_rate'] = round(min(a/p, p/a) * 1000) / 10
        else:
            ch['hit_rate'] = 0.0

    # 5) 전체 적중률
    dr['actual_total'] = total_actual
    p, a = dr['planned_total'], total_actual
    if p > 0 and a > 0:
        dr['total_hit_rate'] = round(min(a/p, p/a) * 1000) / 10
    else:
        dr['total_hit_rate'] = 0.0

    # 6) summary
    normal = sum(1 for sh in dr['stage_hits'] if sh['hit_rate'] >= 90)
    warning = sum(1 for sh in dr['stage_hits'] if 70 <= sh['hit_rate'] < 90)
    critical = sum(1 for sh in dr['stage_hits'] if sh['hit_rate'] < 70)
    dr['summary'] = {'normal': normal, 'warning': warning, 'critical': critical}

    print(f"    matched={matched}, unplanned={len(unmatched_actual)}, total_actual={total_actual}, hr={dr['total_hit_rate']}%")
    if unmatched_actual:
        print(f"    미예측: {', '.join(unmatched_actual[:5])}{'...' if len(unmatched_actual) > 5 else ''}")

new_json14 = json.dumps(daily14, ensure_ascii=False)
text14_new = text14.replace(m14.group(1), new_json14, 1)
w14.write_text(text14_new, encoding='utf-8')
print("[OK] monitor_w14.html 저장")

# ═══════════════ 검증 ═══════════════
print("\n=== 검증 ===")
for dt in w14_dates:
    dr = by_date14.get(dt)
    if not dr:
        continue
    mh_with_actual = sum(1 for mh in dr.get('menu_hits', []) if (mh.get('actual') or 0) > 0)
    print(f"  {dt}: actual_total={dr['actual_total']} menus_with_actual={mh_with_actual}/{len(dr['menu_hits'])} hr={dr['total_hit_rate']}%")
