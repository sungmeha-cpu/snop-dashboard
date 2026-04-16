from html.parser import HTMLParser
import json, re

class TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = []
        self.current_row = []
        self.current_cell = ''
        self.in_cell = False
        self.rowspan_tracker = {}
        self.col_idx = 0
        self.current_rowspan = 1
        self.current_colspan = 1

    def handle_starttag(self, tag, attrs):
        if tag == 'tr':
            self.current_row = []
            self.col_idx = 0
            while self.col_idx in self.rowspan_tracker and self.rowspan_tracker[self.col_idx]['remaining'] > 0:
                self.current_row.append(self.rowspan_tracker[self.col_idx]['value'])
                self.rowspan_tracker[self.col_idx]['remaining'] -= 1
                if self.rowspan_tracker[self.col_idx]['remaining'] <= 0:
                    del self.rowspan_tracker[self.col_idx]
                self.col_idx += 1
        elif tag in ('td', 'th'):
            self.in_cell = True
            self.current_cell = ''
            attrs_dict = dict(attrs)
            self.current_rowspan = int(attrs_dict.get('rowspan', 1))
            self.current_colspan = int(attrs_dict.get('colspan', 1))

    def handle_data(self, data):
        if self.in_cell:
            self.current_cell += data.strip()

    def handle_endtag(self, tag):
        if tag in ('td', 'th') and self.in_cell:
            self.in_cell = False
            while self.col_idx in self.rowspan_tracker and self.rowspan_tracker[self.col_idx]['remaining'] > 0:
                self.current_row.append(self.rowspan_tracker[self.col_idx]['value'])
                self.rowspan_tracker[self.col_idx]['remaining'] -= 1
                if self.rowspan_tracker[self.col_idx]['remaining'] <= 0:
                    del self.rowspan_tracker[self.col_idx]
                self.col_idx += 1
            text = self.current_cell.replace('\xa0', ' ').strip()
            for c in range(self.current_colspan):
                self.current_row.append(text)
                if self.current_rowspan > 1:
                    self.rowspan_tracker[self.col_idx] = {'value': text, 'remaining': self.current_rowspan - 1}
                self.col_idx += 1
        elif tag == 'tr':
            while self.col_idx in self.rowspan_tracker and self.rowspan_tracker[self.col_idx]['remaining'] > 0:
                self.current_row.append(self.rowspan_tracker[self.col_idx]['value'])
                self.rowspan_tracker[self.col_idx]['remaining'] -= 1
                if self.rowspan_tracker[self.col_idx]['remaining'] <= 0:
                    del self.rowspan_tracker[self.col_idx]
                self.col_idx += 1
            if self.current_row:
                self.rows.append(self.current_row)

import os
fpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sheet001_0325.htm')
with open(fpath, 'r', encoding='utf-8') as f:
    html = f.read()

parser = TableParser()
parser.feed(html)

STAGE_MAP = {'1110':'준비기','1210':'초기1','1220':'초기2','1230':'중기','1240':'후기','1250':'후기무른밥','1310':'영양밥','1320':'영양국','1330':'영양찬'}
EXCLUDE = {'1410','1420','1430','1440'}

menus = []
header_found = False
last_stage = ''

for i, r in enumerate(parser.rows):
    if len(r) < 5:
        continue
    if not header_found and ('단계' in str(r[0]) or '상품' in str(r[4]) or '상품' in str(r[2])):
        header_found = True
        continue
    if not header_found:
        continue

    col1 = str(r[1] if len(r) > 1 else '').strip()
    is_stage = col1 in STAGE_MAP or col1 in EXCLUDE

    if is_stage:
        stage_code = col1
        last_stage = stage_code
        off = 0
    elif last_stage:
        stage_code = last_stage
        if not col1 and len(r) >= 14:
            off = 0
        else:
            off = -2
    else:
        continue

    if stage_code in EXCLUDE or stage_code not in STAGE_MAP:
        continue

    def safe_int(val):
        try:
            return int(re.sub(r'[,\s]', '', str(val)) or 0)
        except:
            return 0

    total_qty = safe_int(r[6+off] if len(r) > 6+off else 0)
    dept = safe_int(r[13+off] if len(r) > 13+off else 0)
    online_qty = total_qty - dept
    cle_jasa = safe_int(r[9+off] if len(r) > 9+off else 0)
    tax_jasa = safe_int(r[10+off] if len(r) > 10+off else 0)
    cle_oibu = safe_int(r[11+off] if len(r) > 11+off else 0)
    tax_oibu = safe_int(r[12+off] if len(r) > 12+off else 0)

    pcode = str(r[3+off] if len(r) > 3+off else '').strip().lstrip('0')
    pname = str(r[4+off] if len(r) > 4+off else '').strip()

    menus.append({
        'stage_code': stage_code,
        'stage': STAGE_MAP[stage_code],
        'product_code': pcode,
        'product_name': pname,
        'qty': online_qty,
        'jasa': cle_jasa + tax_jasa,
        'oibu': cle_oibu + tax_oibu,
    })

total = sum(m['qty'] for m in menus)
print(f'파싱 완료: {len(menus)}개 상품, {total:,}병')
for m in menus[:5]:
    print(f"  {m['stage']} | {m['product_code']} | {m['product_name']} | {m['qty']}병")

outpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'parsed_0325.json')
with open(outpath, 'w', encoding='utf-8') as f:
    json.dump(menus, f, ensure_ascii=False, indent=2)
print('저장 완료: parsed_0325.json')
