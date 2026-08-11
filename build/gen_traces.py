"""Task & trace explorer. Data is captured oracle rollouts — every step and
every verifier check is real output from replaying the world."""
import json
import pathlib

T = json.loads(pathlib.Path("/tmp/demo/traces.json").read_text())
W = json.loads(pathlib.Path("world/world.json").read_text())

TOTAL_STEPS = sum(len(t["steps"]) for t in T)
TOTAL_CHECKS = sum(len(t["verdict"]["assertions"]) for t in T)

CSS = """
:root{
  --ground:#EEF1F4; --surface:#FFFFFF; --surface-2:#F7F9FA; --sunk:#0F1B2A;
  --text:#14212F; --muted:#5D6E80; --faint:#8496A6; --line:#D5DEE6; --line-2:#E7EDF2;
  --accent:#0E7C86; --accent-soft:#DCEFF0; --accent-ink:#0A5A62;
  --ok:#2E7D4F; --ok-soft:#DFF0E6; --warn:#B7791F; --warn-soft:#F8ECD5;
  --crit:#C0392B; --crit-soft:#F8DFDC;
  --code-bg:#0F1B2A; --code-fg:#C9DAE8; --code-line:#1E3047;
  --mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,"Liberation Mono",monospace;
  --sans:system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
}
@media (prefers-color-scheme:dark){
  :root:not([data-theme="light"]){
    --ground:#0A1119; --surface:#111E2E; --surface-2:#16263A; --sunk:#070D15;
    --text:#DCE6F0; --muted:#93A6B8; --faint:#6C7F91; --line:#22374F; --line-2:#1A2C41;
    --accent:#3FB3BC; --accent-soft:#0F3238; --accent-ink:#7FD3D9;
    --ok:#5FBF87; --ok-soft:#11301F; --warn:#D9A441; --warn-soft:#2E2310;
    --crit:#E4695C; --crit-soft:#331512;
    --code-bg:#070D15; --code-fg:#BCD1E2; --code-line:#1B2C40;
  }
}
:root[data-theme="dark"]{
  --ground:#0A1119; --surface:#111E2E; --surface-2:#16263A; --sunk:#070D15;
  --text:#DCE6F0; --muted:#93A6B8; --faint:#6C7F91; --line:#22374F; --line-2:#1A2C41;
  --accent:#3FB3BC; --accent-soft:#0F3238; --accent-ink:#7FD3D9;
  --ok:#5FBF87; --ok-soft:#11301F; --warn:#D9A441; --warn-soft:#2E2310;
  --crit:#E4695C; --crit-soft:#331512;
  --code-bg:#070D15; --code-fg:#BCD1E2; --code-line:#1B2C40;
}
*{box-sizing:border-box}
html,body{height:100%}
body{margin:0;background:var(--ground);color:var(--text);font-family:var(--sans);
  font-size:15.5px;line-height:1.55;-webkit-font-smoothing:antialiased}
h1,h2,h3{margin:0;letter-spacing:-.02em;font-weight:750;text-wrap:balance}
p{margin:0}
code{font-family:var(--mono)}
/* ---------- masthead ---------- */
header{background:var(--sunk);color:#DCE6F0;padding:20px 22px 16px;
  border-bottom:1px solid var(--code-line);
  background-image:linear-gradient(transparent 95%,rgba(63,179,188,.09) 95%),
    linear-gradient(90deg,transparent 95%,rgba(63,179,188,.09) 95%);background-size:32px 32px}
header .in{max-width:1500px;margin:0 auto;display:flex;flex-wrap:wrap;gap:16px;
  align-items:baseline;justify-content:space-between}
header h1{color:#F2F7FB;font-size:1.3rem}
header .sub{color:#9DB4C8;font-size:.85rem;font-family:var(--mono)}
header .sub b{color:#8FE3EA;font-weight:600}
/* ---------- toolbar ---------- */
.toolbar{position:sticky;top:0;z-index:30;background:var(--surface);
  border-bottom:1px solid var(--line);padding:9px 22px}
.toolbar .in{max-width:1500px;margin:0 auto;display:flex;flex-wrap:wrap;gap:7px;align-items:center}
.f{font-family:var(--mono);font-size:.71rem;letter-spacing:.03em;padding:4px 9px;border-radius:3px;
  border:1px solid var(--line);background:var(--surface-2);color:var(--muted);cursor:pointer;
  white-space:nowrap}
.f:hover{color:var(--text);border-color:var(--faint)}
.f[aria-pressed="true"]{background:var(--accent-soft);color:var(--accent-ink);
  border-color:var(--accent);font-weight:600}
.f:focus-visible{outline:2px solid var(--accent);outline-offset:1px}
input[type=search]{font-family:var(--mono);font-size:.75rem;padding:5px 9px;border-radius:3px;
  border:1px solid var(--line);background:var(--surface-2);color:var(--text);min-width:190px}
input[type=search]:focus-visible{outline:2px solid var(--accent);outline-offset:1px}
.sep{width:1px;height:19px;background:var(--line)}
.count{font-family:var(--mono);font-size:.71rem;color:var(--faint);margin-left:auto}
/* ---------- layout ---------- */
main{max-width:1500px;margin:0 auto;display:grid;grid-template-columns:334px 1fr;
  gap:0;align-items:start}
.list{border-right:1px solid var(--line);background:var(--surface);
  max-height:calc(100vh - 108px);overflow-y:auto;position:sticky;top:47px}
.catlab{font-family:var(--mono);font-size:.63rem;letter-spacing:.13em;text-transform:uppercase;
  color:var(--faint);padding:11px 14px 5px;background:var(--surface);position:sticky;top:0;
  border-bottom:1px solid var(--line-2)}
.row{display:block;width:100%;text-align:left;border:0;border-bottom:1px solid var(--line-2);
  background:transparent;padding:8px 14px;cursor:pointer;font:inherit;color:inherit}
.row:hover{background:var(--surface-2)}
.row[aria-current="true"]{background:var(--accent-soft);
  box-shadow:inset 3px 0 0 var(--accent)}
.row .id{font-family:var(--mono);font-size:.755rem;font-weight:600;display:block;
  word-break:break-all}
.row .mt{font-family:var(--mono);font-size:.66rem;color:var(--faint);margin-top:2px;
  display:flex;gap:7px;flex-wrap:wrap}
.detail{padding:22px 26px 60px;min-width:0}
.dhead{display:flex;flex-wrap:wrap;gap:9px;align-items:baseline;margin-bottom:5px}
.dhead h2{font-family:var(--mono);font-size:1.06rem;word-break:break-all}
/* ---------- chips ---------- */
.chip{display:inline-block;font-family:var(--mono);font-size:.66rem;padding:2px 7px;
  border-radius:3px;background:var(--surface-2);color:var(--muted);
  border:1px solid var(--line-2);white-space:nowrap}
.chip.ok{background:var(--ok-soft);color:var(--ok);border-color:transparent}
.chip.warn{background:var(--warn-soft);color:var(--warn);border-color:transparent}
.chip.crit{background:var(--crit-soft);color:var(--crit);border-color:transparent}
.chip.acc{background:var(--accent-soft);color:var(--accent-ink);border-color:transparent}
/* ---------- panels ---------- */
.panel{background:var(--surface);border:1px solid var(--line);border-radius:4px;
  overflow:hidden;margin-top:16px}
.ph{display:flex;align-items:center;justify-content:space-between;gap:9px;padding:8px 13px;
  border-bottom:1px solid var(--line-2);background:var(--surface-2)}
.ph .t{font-family:var(--mono);font-size:.75rem;font-weight:600}
.ph .s{font-family:var(--mono);font-size:.68rem;color:var(--faint)}
.pb{padding:13px}
.instr p{margin:0 0 .5em;color:var(--muted);font-size:.89rem;max-width:78ch}
.instr p:last-child{margin-bottom:0}
/* ---------- scorecard ---------- */
.dims{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:0;
  border-top:0}
.dimcol{border-right:1px solid var(--line-2)}
.dimcol:last-child{border-right:0}
.dimh{display:flex;justify-content:space-between;align-items:baseline;gap:7px;padding:8px 12px;
  border-bottom:1px solid var(--line-2)}
.dimh .n{font-weight:700;font-size:.83rem}
.dimh .w{font-family:var(--mono);font-size:.66rem;color:var(--faint)}
.chk{display:flex;gap:7px;align-items:baseline;padding:4px 12px;font-family:var(--mono);
  font-size:.71rem;color:var(--muted)}
.chk .mk{color:var(--ok)}
.chk.bad .mk{color:var(--crit)}
/* ---------- trace ---------- */
.step{display:grid;grid-template-columns:27px 1fr;gap:10px;padding:5px 0;position:relative}
.step::before{content:"";position:absolute;left:13px;top:0;bottom:0;width:1px;background:var(--line)}
.step:first-child::before{top:15px}
.step:last-child::before{bottom:calc(100% - 15px)}
.dot{width:26px;height:26px;border-radius:50%;background:var(--surface);
  border:1px solid var(--line);display:grid;place-items:center;font-family:var(--mono);
  font-size:.65rem;color:var(--muted);position:relative;z-index:1;font-variant-numeric:tabular-nums}
.dot.w{border-color:var(--accent);color:var(--accent-ink);background:var(--accent-soft);
  font-weight:600}
.fn{font-family:var(--mono);font-size:.77rem;font-weight:600}
.ar{font-family:var(--mono);font-size:.7rem;color:var(--faint);word-break:break-word}
.res{font-family:var(--mono);font-size:.7rem;color:var(--muted);margin-top:2px;
  white-space:pre-wrap;word-break:break-word}
.res.err{color:var(--crit)}
.empty{padding:60px 20px;text-align:center;color:var(--faint);font-family:var(--mono);
  font-size:.8rem}
@media (max-width:900px){
  main{grid-template-columns:1fr}
  .list{position:static;max-height:340px;border-right:0;border-bottom:1px solid var(--line)}
}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}
"""

JS = """
const DATA = JSON.parse(document.getElementById('data').textContent);
const state = {cat:new Set(), diff:new Set(), split:new Set(), q:''};
const el = s => document.querySelector(s);
const esc = s => String(s).replace(/[&<>"]/g, c =>
  ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const WRITE = new Set(['open_pull_request','run_ci','merge_pull_request','deploy_service',
  'assess_canary','promote_canary','rollback_deployment','set_feature_flag',
  'shift_endpoint_traffic','apply_migration','acknowledge_alert','resolve_alert',
  'resolve_error_event','create_incident','update_incident','post_message','create_ticket',
  'update_ticket','publish_status_update','submit_diagnosis']);
const DIFF_TONE = {easy:'', medium:'', hard:'warn', expert:'crit'};

function visible(){
  return DATA.filter(t =>
    (!state.cat.size  || state.cat.has(t.category)) &&
    (!state.diff.size || state.diff.has(t.difficulty)) &&
    (!state.split.size|| state.split.has(t.split)) &&
    (!state.q || (t.id + ' ' + t.instruction + ' ' +
                  t.steps.map(s=>s.tool).join(' ')).toLowerCase().includes(state.q)));
}

function renderList(sel){
  const rows = visible();
  el('#count').textContent = rows.length + ' / ' + DATA.length + ' tasks · ' +
    rows.reduce((a,t)=>a+t.steps.length,0) + ' steps';
  let html = '', cat = null;
  for (const t of rows){
    if (t.category !== cat){
      cat = t.category;
      html += '<div class="catlab">' + esc(cat.replace(/_/g,' ')) + '</div>';
    }
    html += '<button class="row" data-id="' + esc(t.id) + '"' +
      (t.id===sel ? ' aria-current="true"' : '') + '>' +
      '<span class="id">' + esc(t.id) + '</span><span class="mt">' +
      '<span>' + esc(t.difficulty) + '</span><span>' + esc(t.split) + '</span>' +
      '<span>' + t.steps.length + ' steps</span></span></button>';
  }
  el('#list').innerHTML = html || '<div class="empty">no tasks match</div>';
  el('#list').querySelectorAll('.row').forEach(b =>
    b.onclick = () => select(b.dataset.id));
}

function renderDetail(id){
  const t = DATA.find(x => x.id === id);
  if (!t){ el('#detail').innerHTML = '<div class="empty">select a task</div>'; return; }
  const v = t.verdict;
  const dims = {correctness:[], deployment:[], quality:[]};
  v.assertions.forEach(a => (dims[a.dimension] = dims[a.dimension] || []).push(a));

  let h = '<div class="dhead"><h2>' + esc(t.id) + '</h2>' +
    '<span class="chip acc">' + esc(t.category.replace(/_/g,' ')) + '</span>' +
    '<span class="chip ' + (DIFF_TONE[t.difficulty]||'') + '">' + esc(t.difficulty) + '</span>' +
    '<span class="chip">' + esc(t.split) + '</span>' +
    '<span class="chip ' + (v.passed?'ok':'crit') + '">PF ' + (v.passed?'pass':'fail') + '</span>' +
    '<span class="chip">PC ' + (v.score ?? 0).toFixed(2) + '</span></div>';

  h += '<div class="panel"><div class="ph"><span class="t">assignment</span>' +
    '<span class="s">' + t.required_tools.length + ' tools required</span></div>' +
    '<div class="pb instr">' +
    t.instruction.split('\\n').filter(p=>p.trim()).map(p=>'<p>'+esc(p)+'</p>').join('') +
    '</div></div>';

  h += '<div class="panel"><div class="ph"><span class="t">verifier</span>' +
    '<span class="s">' + v.assertions.length + ' executable checks</span></div><div class="dims">';
  for (const [d, w] of [['correctness','60%'],['deployment','30%'],['quality','10%']]){
    const items = dims[d] || [];
    if (!items.length) continue;
    const ok = items.filter(a=>a.passed).length;
    h += '<div class="dimcol"><div class="dimh"><span class="n">' + d + '</span>' +
      '<span class="w">' + w + ' · ' + ok + '/' + items.length + '</span></div>';
    for (const a of items)
      h += '<div class="chk' + (a.passed?'':' bad') + '"><span class="mk">' +
        (a.passed?'✓':'✕') + '</span><span>' + esc(a.name) + '</span></div>';
    h += '</div>';
  }
  h += '</div></div>';

  h += '<div class="panel"><div class="ph"><span class="t">oracle trace</span>' +
    '<span class="s">' + t.steps.length + ' tool calls</span></div><div class="pb">';
  t.steps.forEach((s, i) => {
    const args = JSON.stringify(s.args).slice(1,-1);
    let res = JSON.stringify(s.result, null, 0);
    if (res.length > 340) res = res.slice(0,340) + ' …';
    const bad = s.result && s.result.ok === false;
    h += '<div class="step"><div class="dot' + (WRITE.has(s.tool)?' w':'') + '">' + (i+1) +
      '</div><div><div><span class="fn">' + esc(s.tool) + '</span> ' +
      '<span class="ar">' + esc(args.slice(0,220)) + '</span></div>' +
      '<div class="res' + (bad?' err':'') + '">→ ' + esc(res) + '</div></div></div>';
  });
  h += '</div></div>';
  el('#detail').innerHTML = h;
}

function select(id){
  history.replaceState(null,'','#'+id);
  renderList(id); renderDetail(id);
  if (window.innerWidth <= 900) el('#detail').scrollIntoView({behavior:'smooth'});
}

function chipRow(){
  document.querySelectorAll('.f').forEach(b => b.onclick = () => {
    const k = b.dataset.k, val = b.dataset.v;
    if (state[k].has(val)) state[k].delete(val); else state[k].add(val);
    b.setAttribute('aria-pressed', state[k].has(val));
    const cur = el('.row[aria-current="true"]');
    renderList(cur ? cur.dataset.id : null);
  });
  el('#q').oninput = e => {
    state.q = e.target.value.toLowerCase();
    const cur = el('.row[aria-current="true"]');
    renderList(cur ? cur.dataset.id : null);
  };
}

chipRow();
const start = location.hash.slice(1) || DATA[0].id;
select(DATA.some(t=>t.id===start) ? start : DATA[0].id);
"""


def build():
    cats = sorted({t["category"] for t in T})
    diffs = ["easy", "medium", "hard", "expert"]
    o = []
    A = o.append
    A("<title>Tasks &amp; traces — NovaCart engineering world</title>")
    A("<style>%s</style>" % CSS)
    A('<header><div class="in"><div><h1>Tasks &amp; traces</h1>'
      '<div class="sub">every task in the world, with its full oracle rollout and the '
      "executable checks that grade it</div></div>"
      '<div class="sub"><b>%d</b> tasks · <b>%d</b> oracle steps · <b>%d</b> checks · '
      "all pass</div></div></header>" % (len(T), TOTAL_STEPS, TOTAL_CHECKS))

    A('<div class="toolbar"><div class="in">')
    for c in cats:
        A('<button class="f" data-k="cat" data-v="%s" aria-pressed="false">%s</button>'
          % (c, c.replace("_", " ")))
    A('<span class="sep"></span>')
    for d in diffs:
        A('<button class="f" data-k="diff" data-v="%s" aria-pressed="false">%s</button>' % (d, d))
    A('<span class="sep"></span>')
    for s in ("train", "heldout"):
        A('<button class="f" data-k="split" data-v="%s" aria-pressed="false">%s</button>' % (s, s))
    A('<span class="sep"></span>')
    A('<input type="search" id="q" placeholder="search tasks, tools, text…" '
      'aria-label="search tasks">')
    A('<span class="count" id="count"></span>')
    A("</div></div>")

    A('<main><nav class="list" id="list" aria-label="task list"></nav>'
      '<section class="detail" id="detail"></section></main>')
    A('<script type="application/json" id="data">%s</script>'
      % json.dumps(T).replace("</", "<\\/"))
    A("<script>%s</script>" % JS)
    return "\n".join(o)


page = build()
pathlib.Path("/tmp/demo/traces.html").write_text(page)
print("written %.0f KB" % (len(page) / 1024))
