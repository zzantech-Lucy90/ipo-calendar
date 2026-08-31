'use strict';

const $ = (s, r = document) => r.querySelector(s);
const el = (t, cls, txt) => { const n = document.createElement(t); if (cls) n.className = cls; if (txt != null) n.textContent = txt; return n; };
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

/* ------------------------------------------------------------ 포맷 */
const won = (v) => {
  if (v == null) return '—';
  if (v >= 1e12) return (v / 1e12).toFixed(v % 1e12 ? 1 : 0).replace(/\.0$/, '') + '조원';
  if (v >= 1e8) return Math.round(v / 1e8).toLocaleString('ko-KR') + '억원';
  if (v >= 1e4) return Math.round(v / 1e4).toLocaleString('ko-KR') + '만원';
  return v.toLocaleString('ko-KR') + '원';
};
const price = (v) => (v == null ? '—' : v.toLocaleString('ko-KR') + '원');
const shares = (v) => (v == null ? '—' : v.toLocaleString('ko-KR') + '주');
const pct = (v) => (v == null ? '—' : v + '%');
const ratio = (v) => (v == null ? '—' : v.toLocaleString('ko-KR') + ':1');
const md = (s) => (s ? s.slice(5).replace('-', '/') : '—');
const span = (a, b) => (!a ? '—' : a === b || !b ? md(a) : `${md(a)}~${md(b)}`);
// 스팩처럼 밴드 상·하단이 같으면 한 번만 적는다
const bandText = (r) => {
  if (!r.band_low) return null;
  return r.band_low === r.band_high
    ? price(r.band_low)
    : `${r.band_low.toLocaleString('ko-KR')}~${r.band_high.toLocaleString('ko-KR')}원`;
};

/* ------------------------------------------------------------ 날짜 기준 */
// 한국 증시 일정이므로 보는 사람의 시간대가 아니라 서울 기준 날짜로 판단한다.
const seoulToday = () => new Intl.DateTimeFormat('en-CA', {
  timeZone: 'Asia/Seoul', year: 'numeric', month: '2-digit', day: '2-digit',
}).format(new Date());

const daysUntil = (from, to) => {
  const [ay, am, ad] = from.split('-').map(Number);
  const [by, bm, bd] = to.split('-').map(Number);
  return Math.round((Date.UTC(by, bm - 1, bd) - Date.UTC(ay, am - 1, ad)) / 86400000);
};

// 수집 시점에 박아둔 status/dday 대신, 여는 순간을 기준으로 다시 계산한다.
// (collector/merge.py 의 status_of 와 같은 규칙)
function statusOf(r, today) {
  const { listing_date: L, bookbuilding_from: bF, bookbuilding_to: bT,
          subscription_from: sF, subscription_to: sT } = r;
  if (L && today >= L) return '상장완료';
  if (sF && sT && sF <= today && today <= sT) return '청약중';
  if (bF && bT && bF <= today && today <= bT) return '수요예측중';
  if (sT && today > sT) return '상장대기';
  if (sF && today < sF) return '청약예정';
  if (bF && today < bF) return '수요예측예정';
  return '일정미정';
}

function ddayOf(r, today) {
  for (const f of ['subscription_from', 'subscription_to', 'listing_date']) {
    if (r[f] && r[f] >= today) return daysUntil(today, r[f]);
  }
  return null;
}

const TODAY = seoulToday();

/* ------------------------------------------------------------ 상태 */
const TABS = [
  { id: '청약중', label: '청약중', match: (r) => r.status === '청약중' },
  { id: '청약예정', label: '청약예정', match: (r) => r.status === '청약예정' },
  { id: '수요예측', label: '수요예측', match: (r) => r.status === '수요예측중' || r.status === '수요예측예정' },
  { id: '상장대기', label: '상장대기', match: (r) => r.status === '상장대기' },
  { id: '완료', label: '상장완료', match: (r) => r.status === '상장완료' },
  { id: '전체', label: '전체', match: () => true },
];
const BADGE = { '청약중': 'b-live', '수요예측중': 'b-live', '청약예정': 'b-soon', '수요예측예정': 'b-soon', '상장대기': 'b-soon', '상장완료': 'b-done', '일정미정': 'b-done' };

let DATA = [], tab = '청약중', query = '';

/* ------------------------------------------------------------ 렌더 */
function visible() {
  const t = TABS.find((x) => x.id === tab);
  let rows = DATA.filter(t.match);
  if (query) {
    const q = query.toLowerCase();
    rows = rows.filter((r) =>
      (r.name || '').toLowerCase().includes(q) ||
      (r.industry || '').toLowerCase().includes(q) ||
      (r.underwriters || []).join(' ').toLowerCase().includes(q));
  }
  const past = tab === '완료';
  rows.sort((a, b) => {
    const ka = a.subscription_from || a.bookbuilding_from || '';
    const kb = b.subscription_from || b.bookbuilding_from || '';
    return past ? kb.localeCompare(ka) : ka.localeCompare(kb);
  });
  return rows;
}

function card(r) {
  const c = el('button', 'card');
  c.type = 'button';

  const h = el('div', 'card-h');
  h.append(el('span', 'name', r.name));
  if (r.market) h.append(el('span', 'badge b-mkt', r.market));
  h.append(el('span', `badge ${BADGE[r.status] || 'b-done'}`, r.status));
  if (r.dday != null && r.status !== '상장완료') {
    h.append(el('span', 'dday', r.dday === 0 ? 'D-DAY' : `D-${r.dday}`));
  }
  c.append(h);

  const bits = [`청약 ${span(r.subscription_from, r.subscription_to)}`];
  if (r.listing_date) bits.push(`상장 ${md(r.listing_date)}`);
  if (r.underwriters?.length) bits.push(r.underwriters.map((u) => u.replace(/\(주\)|주식회사/g, '').trim()).join(', '));
  c.append(el('div', 'meta', bits.join(' · ')));

  const figs = el('div', 'figs');
  const add = (label, value, hot) => {
    const f = el('div', 'fig' + (hot ? ' hot' : ''));
    f.append(el('span', null, label));
    f.append(el('b', null, value));
    figs.append(f);
  };
  add('공모가', r.offer_price ? price(r.offer_price) : bandText(r) || '—');
  add('공모금액', won(r.offer_amount));
  if (r.institutional_competition != null) add('기관경쟁률', ratio(r.institutional_competition), r.institutional_competition >= 800);
  if (r.lockup_ratio != null) add('의무확약', pct(r.lockup_ratio), r.lockup_ratio >= 15);
  if (r.subscription_competition != null) add('청약경쟁률', ratio(r.subscription_competition));
  c.append(figs);

  c.addEventListener('click', () => openSheet(r));
  return c;
}

function render() {
  const rows = visible();
  const list = $('#list');
  list.replaceChildren(...rows.map(card));
  $('#empty').hidden = rows.length > 0;

  $('#tabs').replaceChildren(...TABS.map((t) => {
    const n = DATA.filter(t.match).length;
    const b = el('button', 'tab', n ? `${t.label} ${n}` : t.label);
    b.type = 'button';
    b.setAttribute('role', 'tab');
    b.setAttribute('aria-selected', String(t.id === tab));
    b.addEventListener('click', () => { tab = t.id; render(); });
    return b;
  }));
}

/* ------------------------------------------------------------ 상세 */
function kv(pairs) {
  const d = el('dl', 'kv');
  for (const [k, v] of pairs) {
    if (v == null || v === '' || v === '—') continue;
    d.append(el('dt', null, k));
    const dd = el('dd');
    dd.innerHTML = v;
    d.append(dd);
  }
  return d.children.length ? d : null;
}

function section(title, node) {
  if (!node) return null;
  const f = document.createDocumentFragment();
  f.append(el('h3', null, title), node);
  return f;
}

function timeline(r) {
  const today = TODAY;
  const rows = [
    ['증권신고서', r.filed_date, r.filed_date],
    ['수요예측', r.bookbuilding_from, r.bookbuilding_to],
    ['공모청약', r.subscription_from, r.subscription_to],
    ['납입', r.payment_date, r.payment_date],
    ['환불', r.refund_date, r.refund_date],
    ['상장', r.listing_date, r.listing_date],
  ].filter(([, a]) => a);
  if (!rows.length) return null;
  const ul = el('ul', 'tl');
  for (const [label, a, b] of rows) {
    const li = el('li');
    if (a <= today && today <= (b || a)) li.className = 'now';
    li.append(el('span', 't', label));
    li.append(el('span', null, a === b || !b ? a : `${a} ~ ${b}`));
    ul.append(li);
  }
  return ul;
}

function distTable(rows) {
  if (!rows?.length) return null;
  const t = el('table', 'dist');
  t.innerHTML = '<thead><tr><th>가격대</th><th>건수</th><th>신청주식수</th><th>비중</th></tr></thead>';
  const tb = el('tbody');
  for (const d of rows) {
    const tr = el('tr');
    tr.innerHTML = `<td>${esc(d.band)}</td><td>${d.orders?.toLocaleString('ko-KR') ?? '—'}</td>` +
      `<td>${d.shares?.toLocaleString('ko-KR') ?? '—'}</td><td>${d.pct != null ? d.pct + '%' : '—'}</td>`;
    if (d.pct != null) {
      const bar = el('div', 'barwrap');
      bar.innerHTML = `<i style="width:${Math.min(100, d.pct)}%"></i>`;
      tr.lastElementChild.append(bar);
    }
    tb.append(tr);
  }
  t.append(tb);
  return t;
}

function lockupTable(b, ratioPct) {
  if (!b) return null;
  const labels = [['m6', '6개월'], ['m3', '3개월'], ['m1', '1개월'], ['d15', '15일']];
  const t = el('table', 'dist');
  t.innerHTML = '<thead><tr><th>확약기간</th><th>신청수량</th></tr></thead>';
  const tb = el('tbody');
  for (const [k, label] of labels) {
    if (b[k] == null) continue;
    const tr = el('tr');
    tr.innerHTML = `<td>${label}</td><td>${b[k].toLocaleString('ko-KR')}주</td>`;
    tb.append(tr);
  }
  if (b.total != null) {
    const tr = el('tr');
    tr.innerHTML = `<td><b>합계</b></td><td><b>${b.total.toLocaleString('ko-KR')}주</b></td>`;
    tb.append(tr);
  }
  t.append(tb);
  const f = document.createDocumentFragment();
  f.append(t);
  if (ratioPct != null) {
    f.append(el('p', 'note', `전체 수요예측 신청수량 대비 확약 비율 ${ratioPct}%. 확약 비율이 낮을수록 상장 직후 기관 물량이 풀릴 여지가 큽니다.`));
  }
  return f;
}

function proceedsTable(p) {
  if (!p?.items) return null;
  const entries = Object.entries(p.items).filter(([, v]) => v > 0);
  if (!entries.length) return null;
  const total = entries.reduce((s, [, v]) => s + v, 0);
  const t = el('table', 'dist');
  t.innerHTML = '<thead><tr><th>사용목적</th><th>금액</th><th>비중</th></tr></thead>';
  const tb = el('tbody');
  for (const [k, v] of entries.sort((a, b) => b[1] - a[1])) {
    const share = Math.round((v / total) * 1000) / 10;
    const tr = el('tr');
    tr.innerHTML = `<td>${esc(k)}</td><td>${won(v)}</td><td>${share}%</td>`;
    const bar = el('div', 'barwrap');
    bar.innerHTML = `<i style="width:${share}%"></i>`;
    tr.lastElementChild.append(bar);
    tb.append(tr);
  }
  t.append(tb);
  return t;
}

function openSheet(r) {
  const c = $('#sheet-content');
  c.replaceChildren();

  c.append(el('h2', null, r.name));
  const sub = [r.market, r.industry, r.status].filter(Boolean).join(' · ');
  c.append(el('p', 'note', sub));

  const band = bandText(r);
  const bandPos = r.band_position ? ` <b>(${esc(r.band_position.label)})</b>` : '';

  c.append(section('공모 개요', kv([
    ['희망공모가', band],
    ['확정공모가', r.offer_price ? price(r.offer_price) + bandPos : null],
    ['공모금액', r.offer_amount ? won(r.offer_amount) : null],
    ['총공모주식수', r.shares_offered ? shares(r.shares_offered) : null],
    ['공모 구성', r.offer_structure ? esc(r.offer_structure) : null],
    ['주관사', r.underwriters?.length ? esc(r.underwriters.join(', ')) : null],
  ])));

  c.append(section('일정', timeline(r)));

  const alloc = r.allocation || {};
  const allocRow = (o) => (o ? `${shares(o.shares)}${o.pct != null ? ` (${o.pct}%)` : ''}` : null);
  c.append(section('배정 물량', kv([
    ['기관투자자', allocRow(alloc.institutional)],
    ['일반청약자', allocRow(alloc.retail)],
    ['우리사주조합', allocRow(alloc.employee)],
  ])));

  c.append(section('수요예측 결과', kv([
    ['기관경쟁률', r.institutional_competition != null ? ratio(r.institutional_competition) : null],
    ['의무보유확약', r.lockup_ratio != null ? pct(r.lockup_ratio) : null],
  ])));
  c.append(distTable(r.price_distribution) || '');
  c.append(lockupTable(r.lockup_breakdown, r.lockup_ratio) || '');

  c.append(section('청약 결과', kv([
    ['청약경쟁률', r.subscription_competition != null ? ratio(r.subscription_competition) : null],
    ['비례경쟁률', r.proportional_competition != null ? ratio(r.proportional_competition) : null],
  ])));

  const proceeds = proceedsTable(r.use_of_proceeds);
  if (proceeds) {
    c.append(section('공모자금 사용목적', proceeds));
    c.append(el('p', 'note', '증권신고서 기재 기준이며, 정정신고로 변경될 수 있습니다.'));
  }

  c.append(section('회사 개요', kv([
    ['종목코드', r.code],
    ['대표자', r.ceo],
    ['업종', r.industry],
    ['기업구분', r.company_class],
    ['설립일', r.dart?.profile?.established],
    ['자본금', r.capital ? won(r.capital) : null],
    ['매출액', r.revenue != null ? won(r.revenue) : null],
    ['순이익', r.net_income != null ? (r.net_income < 0 ? '-' + won(-r.net_income) : won(r.net_income)) : null],
    ['본점소재지', r.address ? esc(r.address) : null],
    ['홈페이지', r.homepage ? `<a href="http://${esc(r.homepage.replace(/^https?:\/\//, ''))}" target="_blank" rel="noopener">${esc(r.homepage)}</a>` : null],
  ])));

  const src = el('div', 'src');
  const links = [['KIND 공모기업 현황', r.sources?.kind], ['DART 증권신고서', r.sources?.dart], ['38커뮤니케이션', r.sources?.ipo38]];
  for (const [label, url] of links) {
    if (!url) continue;
    const a = el('a', null, label);
    a.href = url; a.target = '_blank'; a.rel = 'noopener';
    src.append(a);
  }
  if (src.children.length) c.append(section('원문 확인', src));

  $('#sheet').hidden = false;
  document.body.style.overflow = 'hidden';
}

function closeSheet() {
  $('#sheet').hidden = true;
  document.body.style.overflow = '';
}

/* ------------------------------------------------------------ 부팅 */
async function boot() {
  let payload;
  try {
    const res = await fetch('data/ipos.json', { cache: 'no-cache' });
    payload = await res.json();
  } catch {
    $('#empty').hidden = false;
    $('#empty').textContent = '데이터를 불러오지 못했습니다. data/ipos.json 을 확인하세요.';
    return;
  }
  DATA = payload.items || [];
  for (const r of DATA) {
    r.status = statusOf(r, TODAY);
    r.dday = ddayOf(r, TODAY);
  }

  const gen = payload.generated_at;
  $('#gen').textContent = gen || '—';
  if (gen) {
    const age = daysUntil(gen, TODAY);
    if (age >= 2) {
      $('#gen').textContent = `${gen} (${age}일 전 — 자동 갱신이 멈췄는지 확인하세요)`;
      $('#gen').classList.add('stale');
    }
  }

  const n = (id) => DATA.filter(TABS.find((t) => t.id === id).match).length;
  const stats = $('#stats');
  stats.append(
    Object.assign(el('div', 'stat live'), { innerHTML: `청약중<b>${n('청약중')}</b>` }),
    Object.assign(el('div', 'stat soon'), { innerHTML: `청약예정<b>${n('청약예정')}</b>` }),
    Object.assign(el('div', 'stat'), { innerHTML: `수요예측<b>${n('수요예측')}</b>` }),
    Object.assign(el('div', 'stat'), { innerHTML: `전체<b>${DATA.length}</b>` }),
  );

  // 비어 있는 탭으로 시작하지 않도록
  tab = ['청약중', '청약예정', '수요예측', '전체'].find((id) => n(id) > 0) || '전체';

  $('#q').addEventListener('input', (e) => { query = e.target.value.trim(); render(); });
  $('#sheet').addEventListener('click', (e) => { if (e.target.hasAttribute('data-close')) closeSheet(); });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeSheet(); });

  render();
}

boot();
