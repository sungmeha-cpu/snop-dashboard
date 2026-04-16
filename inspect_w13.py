# -*- coding: utf-8 -*-
import json, re
from pathlib import Path
text = Path('monitor_w13.html').read_text(encoding='utf-8')
m = re.search(r'^const dailyReports = (\[.*?\]);\s*$', text, re.M | re.S)
daily = json.loads(m.group(1))
for dr in daily:
    print(f"=== {dr['date']} ({dr['dow']}) planned={dr['planned_total']} actual={dr['actual_total']} hr={dr['total_hit_rate']}% ===")
    # 후기무른밥
    hg = [mh for mh in dr['menu_hits'] if mh['stage_code']=='1250']
    if hg:
        print('  후기무른밥:')
        for mh in hg:
            print(f"    {mh['product_code']} {mh['product_name']}: plan={mh['planned']} actual={mh['actual']} status={mh['status']}")
    # 영양찬
    yong = [mh for mh in dr['menu_hits'] if mh['stage_code']=='1330']
    print(f'  영양찬 ({len(yong)}종):')
    for mh in yong:
        print(f"    {mh['product_code']} {mh['product_name']}: plan={mh['planned']} actual={mh['actual']}")
    # 고구마죽 특이사항
    for mh in dr['menu_hits']:
        if mh.get('product_name') == '고구마죽':
            print(f"  [고구마죽] stage={mh['stage']}({mh['stage_code']}) plan={mh['planned']} actual={mh['actual']}")
