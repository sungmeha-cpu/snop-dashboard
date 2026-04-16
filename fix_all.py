# -*- coding: utf-8 -*-
"""
1) W13 03-27: 녹미단호박스프 순서를 한우송이탕 바로 다음으로 이동
2) 4/1~4/4 XLS 파싱 후 W14 + actual.json 반영
"""
import json, re, os, sys
from pathlib import Path
import pandas as pd

os.chdir(os.path.dirname(os.path.abspath(__file__)))

STAGE_MAP = {
    '1110':'준비기','1210':'초기1','1220':'초기2','1230':'중기',
    '1240':'후기','1250':'후기무른밥','1310':'영양밥','1320':'영양국','1330':'영양찬'
}
EXCLUDE = {'1410','1420','1430','1440'}

# ════════════════════════════════════════════
# Fix 1: W13 03-27 녹미단호박스프 위치 수정
# ════════════════════════════════════════════
print("=== Fix 1: W13 03-27 녹미단호박스프 위치 ===")
w13_path = Path('monitor_w13.html')
text13 = w13_path.read_text(encoding='utf-8')
m13 = re.search(r'^const dailyReports = (\[.*?\]);\s*$', text13, re.M | re.S)
daily13 = json.loads(m13.group(1))

d27 = next(d for d in daily13 if d['date'] == '2026-03-27')
menus = d27['menu_hits']

# 영양국(1320) 인덱스들 추출
yg_indices = [i for i, mh in enumerate(menus) if mh['stage_code'] == '1320']
yg_items = [menus[i] for i in yg_indices]

# 녹미단호박스프 찾기
nokmi = next((mh for mh in yg_items if mh['product_code'] == '12059'), None)
songitang = next((mh for mh in yg_items if mh['product_code'] == '10634'), None)

if nokmi and songitang:
    # 녹미단호박스프를 영양국 리스트에서 제거 후 한우송이탕 바로 뒤에 삽입
    yg_items.remove(nokmi)
    si = yg_items.index(songitang)
    yg_items.insert(si + 1, nokmi)
    # 전체 menu_hits에서 영양국 교체
    new_menus = []
    yg_idx = 0
    for i, mh in enumerate(menus):
        if mh['stage_code'] == '1320':
            new_menus.append(yg_items[yg_idx])
            yg_idx += 1
        else:
            new_menus.append(mh)
    d27['menu_hits'] = new_menus
    print("  한우송이탕 -> 녹미단호박스프 -> 대구살미역국 순서로 수정")

# 순서 확인
for mh in d27['menu_hits']:
    if mh['stage_code'] == '1320':
        print(f"    {mh['product_code']} {mh['product_name']} ({mh.get('label','')})")

new_json13 = json.dumps(daily13, ensure_ascii=False)
text13_new = text13.replace(m13.group(1), new_json13, 1)
w13_path.write_text(text13_new, encoding='utf-8')
print("[OK] monitor_w13.html")

# ════════════════════════════════════════════
# Fix 2: XLS 파싱 + W14 반영
# ════════════════════════════════════════════

def parse_direct_html(filepath, encoding='utf-8'):
    """직접 HTML 테이블 파싱 (4-2, 4-3, 4-4)"""
    tables = pd.read_html(filepath, encoding=encoding)
    if not tables:
        return []
    df = tables[0]
    # 컬럼명 정리
    cols = list(df.columns)
    result = []
    for _, row in df.iterrows():
        sc = str(row.iloc[1]).strip()
        if sc not in STAGE_MAP:
            continue
        if sc in EXCLUDE:
            continue
        def si(v):
            try: return int(re.sub(r'[,\s]', '', str(v)) or 0)
            except: return 0
        pcode = str(row.iloc[3]).strip().lstrip('0')
        pname = str(row.iloc[4]).strip()
        qty = si(row.iloc[6])
        dept = si(row.iloc[13]) if len(row) > 13 else 0
        online = qty - dept
        jasa = si(row.iloc[9]) + si(row.iloc[10])
        oibu = si(row.iloc[11]) + si(row.iloc[12])
        result.append({
            'stage_code': sc,
            'stage': STAGE_MAP[sc],
            'product_code': pcode,
            'product_name': pname,
            'qty': online,
            'jasa': jasa,
            'oibu': oibu,
        })
    return result

def parse_sheet001(filepath):
    """sheet001.htm 파싱 (frameset 4-1)"""
    from html.parser import HTMLParser

    class TP(HTMLParser):
        def __init__(self):
            super().__init__()
            self.rows, self.cr, self.cc = [], [], ''
            self.in_cell = False
            self.rs_tracker = {}
            self.ci, self.crs, self.ccs = 0, 1, 1
        def handle_starttag(self, tag, attrs):
            if tag == 'tr':
                self.cr, self.ci = [], 0
                while self.ci in self.rs_tracker and self.rs_tracker[self.ci]['r'] > 0:
                    self.cr.append(self.rs_tracker[self.ci]['v'])
                    self.rs_tracker[self.ci]['r'] -= 1
                    if self.rs_tracker[self.ci]['r'] <= 0: del self.rs_tracker[self.ci]
                    self.ci += 1
            elif tag in ('td','th'):
                self.in_cell, self.cc = True, ''
                ad = dict(attrs)
                self.crs = int(ad.get('rowspan', 1))
                self.ccs = int(ad.get('colspan', 1))
        def handle_data(self, data):
            if self.in_cell: self.cc += data.strip()
        def handle_endtag(self, tag):
            if tag in ('td','th') and self.in_cell:
                self.in_cell = False
                while self.ci in self.rs_tracker and self.rs_tracker[self.ci]['r'] > 0:
                    self.cr.append(self.rs_tracker[self.ci]['v'])
                    self.rs_tracker[self.ci]['r'] -= 1
                    if self.rs_tracker[self.ci]['r'] <= 0: del self.rs_tracker[self.ci]
                    self.ci += 1
                t = self.cc.replace('\xa0', ' ').strip()
                for _ in range(self.ccs):
                    self.cr.append(t)
                    if self.crs > 1: self.rs_tracker[self.ci] = {'v': t, 'r': self.crs - 1}
                    self.ci += 1
            elif tag == 'tr':
                while self.ci in self.rs_tracker and self.rs_tracker[self.ci]['r'] > 0:
                    self.cr.append(self.rs_tracker[self.ci]['v'])
                    self.rs_tracker[self.ci]['r'] -= 1
                    if self.rs_tracker[self.ci]['r'] <= 0: del self.rs_tracker[self.ci]
                    self.ci += 1
                if self.cr: self.rows.append(self.cr)

    with open(filepath, 'r', encoding='utf-8') as f:
        html = f.read()
    p = TP()
    p.feed(html)

    menus, hf, ls = [], False, ''
    for r in p.rows:
        if len(r) < 5: continue
        if not hf and ('단계' in str(r[0]) or '상품' in str(r[4]) or '상품' in str(r[2])):
            hf = True; continue
        if not hf: continue
        c1 = str(r[1] if len(r) > 1 else '').strip()
        isS = c1 in STAGE_MAP or c1 in EXCLUDE
        if isS: sc, ls, off = c1, c1, 0
        elif ls:
            sc = ls
            off = 0 if (not c1 and len(r) >= 14) else -2
        else: continue
        if sc in EXCLUDE or sc not in STAGE_MAP: continue
        def si(v):
            try: return int(re.sub(r'[,\s]', '', str(v)) or 0)
            except: return 0
        qty = si(r[6+off] if len(r) > 6+off else 0)
        dept = si(r[13+off] if len(r) > 13+off else 0)
        pcode = str(r[3+off] if len(r) > 3+off else '').strip().lstrip('0')
        pname = str(r[4+off] if len(r) > 4+off else '').strip()
        cj = si(r[9+off] if len(r) > 9+off else 0)
        tj = si(r[10+off] if len(r) > 10+off else 0)
        co = si(r[11+off] if len(r) > 11+off else 0)
        to2 = si(r[12+off] if len(r) > 12+off else 0)
        menus.append({
            'stage_code': sc, 'stage': STAGE_MAP[sc],
            'product_code': pcode, 'product_name': pname,
            'qty': qty - dept, 'jasa': cj + tj, 'oibu': co + to2,
        })
    return menus

# 파일 매핑
xls_files = {
    '2026-04-01': ('sheet001', 'd:/Users/muse23031801/Downloads/주문관리_생산수량표_20260416135535_foodcare.files/sheet001.htm'),
    '2026-04-02': ('direct', 'd:/Users/muse23031801/Downloads/4-2 출고수량.xls'),
    '2026-04-03': ('direct', 'd:/Users/muse23031801/Downloads/4-3 출고 수량..xls'),
    '2026-04-04': ('direct', 'd:/Users/muse23031801/Downloads/4-4 출고 수량..xls'),
}

parsed_data = {}
for dt, (fmt, fp) in xls_files.items():
    print(f"\n=== Parsing {dt} ({fmt}: {os.path.basename(fp)}) ===")
    if fmt == 'sheet001':
        menus = parse_sheet001(fp)
    else:
        menus = parse_direct_html(fp)

    # 빈 상품코드/상품명 처리 (사용자 지시: 파일 정보 입력)
    for m in menus:
        if not m['product_code'] or m['product_code'] in ('nan', 'None', ''):
            m['product_code'] = 'UNKNOWN'
        if not m['product_name'] or m['product_name'] in ('nan', 'None', ''):
            m['product_name'] = f"{m['stage']}_{m['product_code']}"

    total = sum(m['qty'] for m in menus)
    print(f"  {len(menus)} menus, total={total:,}")
    for m in menus[:3]:
        print(f"    {m['stage']}|{m['product_code']}|{m['product_name']}|{m['qty']}")
    parsed_data[dt] = menus

# actual.json 업데이트
print("\n=== Updating actual.json ===")
actual_path = Path('data/actual.json')
actual = json.load(actual_path.open(encoding='utf-8'))
for dt, menus in parsed_data.items():
    actual[dt] = menus
    print(f"  {dt}: {len(menus)} menus -> actual.json")
with open(actual_path, 'w', encoding='utf-8') as f:
    json.dump(actual, f, ensure_ascii=False, indent=2)
print("[OK] actual.json")

# W14 dailyReports 업데이트
print("\n=== Updating W14 dailyReports ===")
w14_path = Path('monitor_w14.html')
text14 = w14_path.read_text(encoding='utf-8')
m14 = re.search(r'^const dailyReports = (\[.*?\]);\s*$', text14, re.M | re.S)
daily14 = json.loads(m14.group(1))
by_date14 = {d['date']: d for d in daily14}

for dt, act_menus in parsed_data.items():
    dr = by_date14.get(dt)
    if not dr:
        print(f"  {dt}: not in W14 dailyReports - skip")
        continue

    # 메뉴 매칭
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
            # 미예측 메뉴 추가
            dr['menu_hits'].append({
                'stage_code': am['stage_code'], 'stage': am['stage'],
                'product_code': am['product_code'], 'product_name': am['product_name'],
                'label': '', 'planned': 0, 'planned_jasa': 0, 'planned_oibu': 0,
                'actual': am['qty'], 'actual_jasa': am.get('jasa', 0), 'actual_oibu': am.get('oibu', 0),
                'hit_rate': 0.0, 'ratio': 0.0, 'status': 'unplanned',
            })

    # 단계별
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

    # 채널별
    for ch in dr['channel_hits']:
        if ch['channel'] == '자사몰': ch['actual'] = ch_actual['jasa']
        elif ch['channel'] == '외부몰': ch['actual'] = ch_actual['oibu']
        p, a = ch['planned'], ch['actual']
        ch['hit_rate'] = round(min(a/p, p/a) * 1000) / 10 if (p > 0 and a > 0) else 0.0

    # 전체
    dr['actual_total'] = total_actual
    p, a = dr['planned_total'], total_actual
    dr['total_hit_rate'] = round(min(a/p, p/a) * 1000) / 10 if (p > 0 and a > 0) else 0.0

    # summary
    normal = sum(1 for sh in dr['stage_hits'] if sh['hit_rate'] >= 90)
    warning = sum(1 for sh in dr['stage_hits'] if 70 <= sh['hit_rate'] < 90)
    critical = sum(1 for sh in dr['stage_hits'] if sh['hit_rate'] < 70)
    dr['summary'] = {'normal': normal, 'warning': warning, 'critical': critical}

    mh_with_actual = sum(1 for mh in dr['menu_hits'] if (mh.get('actual') or 0) > 0)
    print(f"  {dt}: total={total_actual:,} menus_actual={mh_with_actual}/{len(dr['menu_hits'])} hr={dr['total_hit_rate']}%")

new_json14 = json.dumps(daily14, ensure_ascii=False)
text14_new = text14.replace(m14.group(1), new_json14, 1)
w14_path.write_text(text14_new, encoding='utf-8')
print("[OK] monitor_w14.html")
