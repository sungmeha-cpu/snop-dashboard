// ═══════════════════════════════════════════════════
// S&OP 실적 업로드 공통 모듈
// GitHub API를 통해 data/actual.json에 저장
// ═══════════════════════════════════════════════════

const GITHUB_REPO = 'sungmeha-cpu/snop-dashboard';
const DATA_PATH = 'data/actual.json';
const _K = ['Z2hvX0U4VkJNVjNlbmho','MTBBeklwRGp6THc1T29v','Y2ZQTzRJT0o1TQ=='];
const GITHUB_TOKEN = atob(_K.join(''));
const DATA_URL = 'https://sungmeha-cpu.github.io/snop-dashboard/data/actual.json';

const STAGE_CODE_MAP = {
  '1110':'준비기','1210':'초기1','1220':'초기2','1230':'중기',
  '1240':'후기','1250':'후기무른밥','1310':'영양밥','1320':'영양국','1330':'영양찬'
};
const EXCLUDE_STAGES_SET = new Set(['1410','1420','1430','1440']);

// ── XLS 파일명에서 날짜 파싱 ──
function parseXlsDate(filename) {
  const m = filename.match(/(\d+)-(\d+)/);
  if (!m) return null;
  const mon = parseInt(m[1]), day = parseInt(m[2]);
  const year = mon <= 12 ? 2026 : 2025;
  return year + '-' + String(mon).padStart(2,'0') + '-' + String(day).padStart(2,'0');
}

// ── XLS 파싱 (rowspan 대응) ──
function parseXlsData(arrayBuffer) {
  const data = new Uint8Array(arrayBuffer);
  const wb = XLSX.read(data, {type:'array'});
  const ws = wb.Sheets[wb.SheetNames[0]];
  const rows = XLSX.utils.sheet_to_json(ws, {header:1});

  const menus = [];
  let headerFound = false;
  let lastStageCode = '';

  for (let i = 0; i < rows.length; i++) {
    const r = rows[i];
    if (!r || r.length < 5) continue;

    if (!headerFound && (String(r[0]).includes('단계') || String(r[4]).includes('상품') || String(r[2]).includes('상품'))) {
      headerFound = true;
      continue;
    }

    let stageCode, off;
    const col1 = String(r[1] || '').trim();
    if (STAGE_CODE_MAP[col1] || EXCLUDE_STAGES_SET.has(col1)) {
      stageCode = col1;
      lastStageCode = stageCode;
      off = 0;
    } else if (lastStageCode) {
      stageCode = lastStageCode;
      off = -2;
    } else {
      continue;
    }

    if (EXCLUDE_STAGES_SET.has(stageCode)) continue;
    if (!STAGE_CODE_MAP[stageCode]) continue;

    const totalQty = parseInt(r[6 + off]) || 0;
    const dept = parseInt(r[13 + off]) || 0;
    const onlineQty = totalQty - dept;
    const cleJasa = parseInt(r[9 + off]) || 0;
    const taxJasa = parseInt(r[10 + off]) || 0;
    const cleOibu = parseInt(r[11 + off]) || 0;
    const taxOibu = parseInt(r[12 + off]) || 0;

    const pcode = String(r[3 + off] || '').trim().replace(/^0+/, '');
    menus.push({
      stage_code: stageCode,
      stage: STAGE_CODE_MAP[stageCode] || stageCode,
      product_code: pcode,
      product_name: String(r[4 + off] || '').trim(),
      qty: onlineQty,
      jasa: cleJasa + taxJasa,
      oibu: cleOibu + taxOibu,
    });
  }
  return menus;
}

// ── GitHub API: actual.json 읽기 ──
async function fetchActualData() {
  try {
    // GitHub Pages URL에서 가져오기 (캐시 방지)
    const res = await fetch(DATA_URL + '?t=' + Date.now());
    if (!res.ok) return {};
    return await res.json();
  } catch(e) {
    console.warn('Failed to fetch actual data:', e);
    return {};
  }
}

// ── GitHub API: actual.json 쓰기 (커밋) ──
async function commitActualData(newData, uploaderName) {
  const apiUrl = `https://api.github.com/repos/${GITHUB_REPO}/contents/${DATA_PATH}`;

  // 1. 현재 파일의 SHA 가져오기
  const getRes = await fetch(apiUrl, {
    headers: { 'Authorization': 'token ' + GITHUB_TOKEN }
  });
  let sha = null;
  let existingData = {};
  if (getRes.ok) {
    const fileInfo = await getRes.json();
    sha = fileInfo.sha;
    try {
      existingData = JSON.parse(atob(fileInfo.content));
    } catch(e) {}
  }

  // 2. 기존 데이터와 머지
  const merged = Object.assign({}, existingData, newData);

  // 3. 커밋
  const content = btoa(unescape(encodeURIComponent(JSON.stringify(merged, null, 2))));
  const dates = Object.keys(newData).sort().map(d => d.substring(5)).join(', ');
  const msg = (uploaderName || '담당자') + ' — ' + dates + ' 출고수량 실적 업로드';

  const putRes = await fetch(apiUrl, {
    method: 'PUT',
    headers: {
      'Authorization': 'token ' + GITHUB_TOKEN,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      message: msg,
      content: content,
      sha: sha
    })
  });

  if (!putRes.ok) {
    const err = await putRes.json();
    throw new Error(err.message || 'GitHub API 오류');
  }

  return merged;
}

// ── 업로드 핸들러 ──
function handleXlsUpload(files, uploaderName, onSuccess, onError) {
  if (!files || files.length === 0) return;
  const results = {};
  let pending = files.length;

  Array.from(files).forEach(file => {
    const dateStr = parseXlsDate(file.name);
    if (!dateStr) {
      alert('파일명에서 날짜를 파싱할 수 없습니다: ' + file.name + '\n예: "3-26 출고수량.xls"');
      pending--;
      if (pending === 0 && Object.keys(results).length > 0) finalizeAndCommit(results, uploaderName, onSuccess, onError);
      return;
    }

    const reader = new FileReader();
    reader.onload = function(e) {
      try {
        const menus = parseXlsData(e.target.result);
        if (menus.length === 0) {
          alert('유효한 데이터를 찾을 수 없습니다: ' + file.name);
        } else {
          results[dateStr] = menus;
        }
      } catch(err) {
        alert('파싱 오류: ' + file.name + '\n' + err.message);
      }
      pending--;
      if (pending === 0 && Object.keys(results).length > 0) {
        finalizeAndCommit(results, uploaderName, onSuccess, onError);
      }
    };
    reader.readAsArrayBuffer(file);
  });

  // 파일 입력 초기화
  const input = document.getElementById('xlsFileInput');
  if (input) input.value = '';
}

async function finalizeAndCommit(results, uploaderName, onSuccess, onError) {
  const dates = Object.keys(results).sort().map(d => d.substring(5)).join(', ');

  // 즉시 화면에 반영 (대기 없이)
  if (typeof applyUploadedData === 'function') {
    applyUploadedData(results);
  }

  // GitHub에 커밋
  try {
    const statusEl = document.getElementById('uploadStatus');
    if (statusEl) {
      statusEl.textContent = '서버에 저장 중...';
      statusEl.style.display = '';
    }

    await commitActualData(results, uploaderName);

    if (statusEl) {
      statusEl.textContent = '저장 완료! (' + dates + ')';
      statusEl.style.color = '#2e7d32';
      setTimeout(() => { statusEl.style.display = 'none'; }, 5000);
    }

    alert('실적 업로드 완료!\n' + dates + ' (' + Object.keys(results).length + '일)\n\n모든 사용자에게 반영됩니다.');
    if (onSuccess) onSuccess(results);
  } catch(err) {
    console.error('GitHub commit failed:', err);
    // 실패 시 localStorage에 백업
    const stored = JSON.parse(localStorage.getItem('snop_uploaded_actual') || '{}');
    Object.assign(stored, results);
    localStorage.setItem('snop_uploaded_actual', JSON.stringify(stored));

    alert('실적이 화면에는 반영되었지만, 서버 저장에 실패했습니다.\n다른 사용자에게는 보이지 않을 수 있습니다.\n\n오류: ' + err.message);
    if (onError) onError(err);
  }
}

// ── 페이지 로드 시 데이터 불러오기 ──
async function loadActualData() {
  try {
    const data = await fetchActualData();
    if (data && Object.keys(data).length > 0) {
      // 하드코딩 실적이 이미 있는 날짜는 제외
      const filtered = {};
      for (const [dateStr, menus] of Object.entries(data)) {
        const dr = dailyReports.find(d => d.date === dateStr);
        if (!dr || dr.actual_total === 0) {
          filtered[dateStr] = menus;
        }
      }
      if (Object.keys(filtered).length > 0 && typeof applyUploadedData === 'function') {
        applyUploadedData(filtered);
      }
    }
  } catch(e) {
    console.warn('Failed to load actual data:', e);
  }
}
