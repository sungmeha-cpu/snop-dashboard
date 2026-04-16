# -*- coding: utf-8 -*-
"""W13 데이터 보정 스크립트
- 03-23 후기무른밥 메뉴 교체(새우살청경채무른밥 → 대구살유부무른밥) + 실적 1245
- 03-23~28 영양찬 메뉴/실적 보정 (사용자 지시)
- 03-26 영양찬 점검 (가지수/고구마죽 노출)

dailyReports JSON만 수정하고, 페이지 로드 시 모든 날짜 탭을 rerender하도록
스크립트를 한 줄 추가한다.
"""
import json
import re
import sys
from pathlib import Path

HTML = Path('monitor_w13.html')
text = HTML.read_text(encoding='utf-8')

# --- dailyReports JSON 추출 ---
m = re.search(r'^const dailyReports = (\[.*?\]);\s*$', text, re.M | re.S)
if not m:
    print('[ERR] dailyReports not found')
    sys.exit(1)
json_raw = m.group(1)
daily = json.loads(json_raw)

by_date = {d['date']: d for d in daily}

def find_menu(dr, stage_code, product_code=None, product_name=None):
    for mh in dr['menu_hits']:
        if mh['stage_code'] != stage_code:
            continue
        if product_code and mh['product_code'] == product_code:
            return mh
        if product_name and mh['product_name'] == product_name:
            return mh
    return None

def find_menus_by_stage(dr, stage_code):
    return [mh for mh in dr['menu_hits'] if mh['stage_code'] == stage_code]

def set_actual_ratio(mh, actual):
    mh['actual'] = actual
    planned = mh['planned']
    if planned > 0 and actual > 0:
        mh['hit_rate'] = round(min(actual/planned, planned/actual) * 1000) / 10
        mh['ratio'] = round((actual/planned) * 1000) / 10
        if mh['hit_rate'] >= 90:
            mh['status'] = 'normal'
        elif actual > planned:
            mh['status'] = 'over'
        else:
            mh['status'] = 'under'
    elif actual == 0 and planned > 0:
        mh['hit_rate'] = 0.0
        mh['ratio'] = 0.0
        mh['status'] = 'under'
    elif planned == 0 and actual > 0:
        mh['hit_rate'] = 0.0
        mh['ratio'] = 0.0
        mh['status'] = 'over'
    else:
        mh['hit_rate'] = 0.0
        mh['ratio'] = 0.0
        mh['status'] = 'normal'

def recalc_actual_channel_split(mh):
    """자사몰/외부몰 비율을 예측 비율로 역산"""
    pj = mh.get('planned_jasa', 0) or 0
    po = mh.get('planned_oibu', 0) or 0
    total_p = pj + po
    a = mh.get('actual', 0) or 0
    if total_p > 0 and a > 0:
        aj = round(a * pj / total_p)
        mh['actual_jasa'] = aj
        mh['actual_oibu'] = a - aj
    elif a == 0:
        mh['actual_jasa'] = 0
        mh['actual_oibu'] = 0

def recalc_day(dr):
    # 단계별 재집계
    stage_actual = {}
    stage_planned = {}
    ch_actual = {'자사몰': 0, '외부몰': 0}
    ch_planned = {'자사몰': 0, '외부몰': 0}
    total_actual = 0
    total_planned = 0
    for mh in dr['menu_hits']:
        sc = mh['stage_code']
        stage_actual[sc] = stage_actual.get(sc, 0) + (mh.get('actual') or 0)
        stage_planned[sc] = stage_planned.get(sc, 0) + (mh.get('planned') or 0)
        ch_actual['자사몰'] += mh.get('actual_jasa', 0) or 0
        ch_actual['외부몰'] += mh.get('actual_oibu', 0) or 0
        ch_planned['자사몰'] += mh.get('planned_jasa', 0) or 0
        ch_planned['외부몰'] += mh.get('planned_oibu', 0) or 0
        total_actual += mh.get('actual', 0) or 0
        total_planned += mh.get('planned', 0) or 0
    for sh in dr['stage_hits']:
        sc = sh['stage_code']
        sh['actual'] = stage_actual.get(sc, 0)
        sh['planned'] = stage_planned.get(sc, sh['planned'])
        p, a = sh['planned'], sh['actual']
        if p > 0 and a > 0:
            sh['hit_rate'] = round(min(a/p, p/a) * 1000) / 10
            sh['ratio'] = round((a/p) * 1000) / 10
            if sh['hit_rate'] >= 90:
                sh['status'] = 'normal'
            elif a > p:
                sh['status'] = 'over'
            else:
                sh['status'] = 'under'
        else:
            sh['hit_rate'] = 0.0
            sh['ratio'] = 0.0
            sh['status'] = 'under' if a == 0 else 'over'
    for ch in dr['channel_hits']:
        name = ch['channel']
        ch['actual'] = ch_actual.get(name, 0)
        p, a = ch['planned'], ch['actual']
        if p > 0 and a > 0:
            ch['hit_rate'] = round(min(a/p, p/a) * 1000) / 10
        else:
            ch['hit_rate'] = 0.0
    dr['actual_total'] = total_actual
    dr['planned_total'] = total_planned
    if total_planned > 0 and total_actual > 0:
        dr['total_hit_rate'] = round(min(total_actual/total_planned, total_planned/total_actual) * 1000) / 10
    else:
        dr['total_hit_rate'] = 0.0
    # summary
    normal = sum(1 for sh in dr['stage_hits'] if sh['hit_rate'] >= 90)
    warning = sum(1 for sh in dr['stage_hits'] if 70 <= sh['hit_rate'] < 90)
    critical = sum(1 for sh in dr['stage_hits'] if sh['hit_rate'] < 70)
    dr['summary'] = {'normal': normal, 'warning': warning, 'critical': critical}

def replace_yongyang_menus(dr, menu_order_with_actuals):
    """영양찬(1330) 메뉴를 지정한 순서/실적으로 교체.
    기존 영양찬 menu_hits의 planned 값을 순서대로 승계(예측 합계 유지).
    - menu_order_with_actuals: [(product_name, actual), ...]
    """
    existing = find_menus_by_stage(dr, '1330')
    # 예측값은 높은 순서대로 (기존 기본 시드 로직이 높은→낮은으로 했음)
    existing_sorted = sorted(existing, key=lambda x: -x.get('planned', 0))
    # 기존 planned 목록
    planned_list = [mh['planned'] for mh in existing_sorted]
    planned_jasa_list = [mh.get('planned_jasa', 0) for mh in existing_sorted]
    planned_oibu_list = [mh.get('planned_oibu', 0) for mh in existing_sorted]
    # 기존 product_code 목록 (재사용)
    code_list = [mh['product_code'] for mh in existing_sorted]

    # 기존 영양찬 제거
    dr['menu_hits'] = [mh for mh in dr['menu_hits'] if mh['stage_code'] != '1330']

    # 새 영양찬 삽입
    n = len(menu_order_with_actuals)
    # 예측 항목 수와 새 항목 수가 다를 수 있음 — 부족분은 마지막 planned 값을 사용
    for i, (pname, actual) in enumerate(menu_order_with_actuals):
        if i < len(planned_list):
            p = planned_list[i]
            pj = planned_jasa_list[i]
            po = planned_oibu_list[i]
            pcode = code_list[i]
        else:
            # 추가 메뉴는 planned=0 (신규)
            p = 0
            pj = 0
            po = 0
            pcode = f'Y{i:04d}'
        mh = {
            'stage_code': '1330',
            'stage': '영양찬',
            'product_code': pcode,
            'product_name': pname,
            'label': '본',
            'planned': p,
            'planned_jasa': pj,
            'planned_oibu': po,
            'actual': 0,
            'actual_jasa': 0,
            'actual_oibu': 0,
            'hit_rate': 0.0,
            'ratio': 0.0,
            'status': 'normal',
        }
        set_actual_ratio(mh, actual)
        recalc_actual_channel_split(mh)
        dr['menu_hits'].append(mh)

# ============ 03-23 ============
dr = by_date['2026-03-23']
# 후기무른밥 교체 — 새우살청경채무른밥 → 대구살유부무른밥, 실적 1245
# 단, 대구살유부무른밥(10228)이 이미 존재하면 합치지 말고 새우살청경채(10246) 제거
# 03-23은 대구살유부무른밥이 이미 존재. 새우살청경채무른밥은 예측 1536, 실적 1346.
# 사용자 지시는 "새우살청경채무른밥을 대구살유부무른밥으로 변경 후 실적 1245" → 새우살청경채 행을 삭제하고 그 예측 1536 을 대구살유부무른밥에 병합?
# 해석: 03-23에 배포된 새우살청경채 = 사실 대구살유부였음. 따라서 새우살청경채 행의 값을 대구살유부로 보내고 (병합), 병합 후 대구살유부 실적을 1245로 설정.
daegu = find_menu(dr, '1250', product_name='대구살유부무른밥')
saewoo = find_menu(dr, '1250', product_name='새우살청경채무른밥')
if daegu and saewoo:
    # planned / planned_jasa / planned_oibu 합산
    daegu['planned'] += saewoo['planned']
    daegu['planned_jasa'] = daegu.get('planned_jasa', 0) + saewoo.get('planned_jasa', 0)
    daegu['planned_oibu'] = daegu.get('planned_oibu', 0) + saewoo.get('planned_oibu', 0)
    # 새우살 제거
    dr['menu_hits'] = [mh for mh in dr['menu_hits'] if mh is not saewoo]
# 실적 1245 세팅
if daegu:
    set_actual_ratio(daegu, 1245)
    recalc_actual_channel_split(daegu)

# 영양찬 교체
replace_yongyang_menus(dr, [
    ('한우적채조림', 614),
    ('새우살느타리볶음', 614),
    ('닭가슴살배추볶음', 444),
    ('한우부추잡채', 170),
    ('가지닭살조림', 170),
    ('두부조림', 129),
])
recalc_day(dr)

# ============ 03-24 ============
dr = by_date['2026-03-24']
replace_yongyang_menus(dr, [
    ('한우부추잡채', 428),
    ('가지닭살조림', 425),
    ('두부조림', 321),
    ('한우적채조림', 97),
    ('새우살느타리볶음', 94),
    ('닭가슴살배추볶음', 73),
])
recalc_day(dr)

# ============ 03-25 ============
dr = by_date['2026-03-25']
replace_yongyang_menus(dr, [
    ('찹스테이크', 485),
    ('닭가슴살고구마조림', 467),
    ('토마토흰콩조림', 316),
    ('한우단호박찜', 124),
    ('시금치병아리콩볶음', 124),
    ('닭가슴살치즈스튜', 90),
])
recalc_day(dr)

# ============ 03-26 ============ 영양찬 점검: 실적 6종 유지 + 고구마죽 노출 정리
dr = by_date['2026-03-26']
# 1) 고구마죽: 초기1(1210)에 있는 10002 고구마죽의 자사/외부 값을 dailyReports 기준으로 정리
#    (stage는 유지 — 10002 고구마죽은 초기1이 맞음. 기존 정적 HTML이 잘못 렌더링된 케이스)
gogu = find_menu(dr, '1210', product_code='10002')
if gogu:
    # planned/actual 기준 자사-외부 비율 재계산
    recalc_actual_channel_split(gogu)
    # planned_jasa/oibu 없으면 planned을 자사에 몰아줌
    if gogu.get('planned_jasa', 0) + gogu.get('planned_oibu', 0) == 0 and gogu.get('planned', 0) > 0:
        gogu['planned_jasa'] = gogu['planned']
        gogu['planned_oibu'] = 0

# 2) 영양찬 가지수 정리: 실적 6종만 유지, 예측 6종의 합계를 실적 메뉴에 승계
yong = [mh for mh in dr['menu_hits'] if mh['stage_code'] == '1330']
with_actual = [mh for mh in yong if (mh.get('actual', 0) or 0) > 0]
# 실적 내림차순으로 정렬 유지
with_actual_sorted = sorted(with_actual, key=lambda x: -(x.get('actual', 0) or 0))[:6]
replace_yongyang_menus(dr, [(mh['product_name'], mh['actual']) for mh in with_actual_sorted])
recalc_day(dr)

# ============ 03-27 ============
dr = by_date['2026-03-27']
replace_yongyang_menus(dr, [
    ('한우표고잡채', 624),
    ('청경채두부볶음', 621),
    ('새우컬리볶음', 430),
    ('한우양배추볶음', 232),
    ('버섯불고기', 229),
    ('닭가슴살들깨영양찜', 173),
])
recalc_day(dr)

# ============ 03-28 ============
dr = by_date['2026-03-28']
replace_yongyang_menus(dr, [
    ('한우양배추볶음', 376),
    ('버섯불고기', 380),
    ('닭가슴살들깨영양찜', 272),
    ('한우감자치즈조림', 123),
    ('닭가슴살깻잎볶음', 123),
    ('오트밀짜장', 80),
])
recalc_day(dr)

# ---- JSON 직렬화 & 파일 교체 ----
new_json = json.dumps(daily, ensure_ascii=False)
new_text = text.replace(json_raw, new_json, 1)

# ---- 모든 day 탭을 rerender 하도록 스크립트 패치 ----
# loadActualData().then(() => { rerenderOverview(); updateNavDots(); });
# 뒤에 dailyReports.forEach(dr => rerenderDayTab(dr));  추가
if 'dailyReports.forEach(dr => rerenderDayTab(dr))' not in new_text:
    new_text = new_text.replace(
        "loadActualData().then(() => {\n  rerenderOverview();\n  updateNavDots();\n});",
        "loadActualData().then(() => {\n  dailyReports.forEach(dr => {\n    const normal = (dr.stage_hits||[]).filter(s=>s.hit_rate>=90).length;\n    const warning = (dr.stage_hits||[]).filter(s=>s.hit_rate>=70 && s.hit_rate<90).length;\n    const critical = (dr.stage_hits||[]).filter(s=>s.hit_rate<70).length;\n    dr.summary = dr.summary || { normal, warning, critical };\n    rerenderDayTab(dr);\n  });\n  rerenderOverview();\n  updateNavDots();\n});",
        1,
    )

HTML.write_text(new_text, encoding='utf-8')
print('[OK] monitor_w13.html updated')

# 검증 요약
for dstr in ['2026-03-23','2026-03-24','2026-03-25','2026-03-26','2026-03-27','2026-03-28']:
    dr = by_date[dstr]
    yong = [mh for mh in dr['menu_hits'] if mh['stage_code']=='1330']
    print(f"\n{dstr} 영양찬 {len(yong)}종 (total_hit={dr['total_hit_rate']}%):")
    for mh in yong:
        print(f"  - {mh['product_name']}: plan {mh['planned']} / actual {mh['actual']} ({mh['hit_rate']}%)")
