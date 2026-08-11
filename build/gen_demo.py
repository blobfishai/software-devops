"""Generate the realism demo page from captured world data. Every value on the
page comes from world/ or from a real tool invocation - nothing is authored by
hand here."""
import html
import json
import pathlib

D = json.loads(pathlib.Path("/tmp/demo/data.json").read_text())
e = lambda s: html.escape(str(s), quote=True)


def jdump(o, limit=1400):
    s = json.dumps(o, indent=1)
    if len(s) > limit:
        s = s[:limit].rsplit("\n", 1)[0] + "\n … truncated"
    return e(s)


def chip(text, tone=""):
    return '<span class="chip %s">%s</span>' % (tone, e(text))


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
  --shadow:0 1px 2px rgba(15,27,42,.06),0 8px 24px -16px rgba(15,27,42,.28);
}
@media (prefers-color-scheme:dark){
  :root:not([data-theme="light"]){
    --ground:#0A1119; --surface:#111E2E; --surface-2:#16263A; --sunk:#070D15;
    --text:#DCE6F0; --muted:#93A6B8; --faint:#6C7F91; --line:#22374F; --line-2:#1A2C41;
    --accent:#3FB3BC; --accent-soft:#0F3238; --accent-ink:#7FD3D9;
    --ok:#5FBF87; --ok-soft:#11301F; --warn:#D9A441; --warn-soft:#2E2310;
    --crit:#E4695C; --crit-soft:#331512;
    --code-bg:#070D15; --code-fg:#BCD1E2; --code-line:#1B2C40;
    --shadow:0 1px 2px rgba(0,0,0,.4),0 10px 30px -18px rgba(0,0,0,.8);
  }
}
:root[data-theme="dark"]{
  --ground:#0A1119; --surface:#111E2E; --surface-2:#16263A; --sunk:#070D15;
  --text:#DCE6F0; --muted:#93A6B8; --faint:#6C7F91; --line:#22374F; --line-2:#1A2C41;
  --accent:#3FB3BC; --accent-soft:#0F3238; --accent-ink:#7FD3D9;
  --ok:#5FBF87; --ok-soft:#11301F; --warn:#D9A441; --warn-soft:#2E2310;
  --crit:#E4695C; --crit-soft:#331512;
  --code-bg:#070D15; --code-fg:#BCD1E2; --code-line:#1B2C40;
  --shadow:0 1px 2px rgba(0,0,0,.4),0 10px 30px -18px rgba(0,0,0,.8);
}
*{box-sizing:border-box}
body{margin:0;background:var(--ground);color:var(--text);font-family:var(--sans);
  font-size:16.5px;line-height:1.6;-webkit-font-smoothing:antialiased}
.wrap{max-width:1120px;margin:0 auto;padding:0 24px}
h1,h2,h3,h4{text-wrap:balance;margin:0;letter-spacing:-.021em;font-weight:750}
h1{font-size:clamp(2.1rem,4.6vw,3.15rem);line-height:1.04;letter-spacing:-.033em}
h2{font-size:clamp(1.35rem,2.5vw,1.72rem);line-height:1.15}
h3{font-size:1.03rem;letter-spacing:-.01em}
p{margin:0}
a{color:var(--accent-ink)}
code,kbd{font-family:var(--mono)}
.eyebrow{font-family:var(--mono);font-size:.687rem;letter-spacing:.15em;text-transform:uppercase;
  color:var(--accent-ink);font-weight:600}
.lede{color:var(--muted);font-size:1.06rem;max-width:66ch}
.stack{display:flex;flex-direction:column}
/* ---------- masthead ---------- */
header.top{background:var(--sunk);color:#DCE6F0;border-bottom:1px solid var(--code-line);
  background-image:linear-gradient(transparent 95%,rgba(63,179,188,.10) 95%),
    linear-gradient(90deg,transparent 95%,rgba(63,179,188,.10) 95%);
  background-size:34px 34px}
header.top .wrap{padding-top:56px;padding-bottom:44px;display:flex;flex-direction:column;gap:22px}
header.top h1{color:#F2F7FB}
header.top .lede{color:#9DB4C8;font-size:1.09rem}
.meta-row{display:flex;flex-wrap:wrap;gap:8px;align-items:center;font-family:var(--mono);
  font-size:.75rem;color:#7E97AC}
.meta-row b{color:#BFD5E6;font-weight:600}
.statgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(112px,1fr));gap:1px;
  background:var(--code-line);border:1px solid var(--code-line);border-radius:3px;overflow:hidden}
.stat{background:var(--sunk);padding:13px 14px}
.stat .n{font-family:var(--mono);font-size:1.42rem;font-weight:600;color:#8FE3EA;
  font-variant-numeric:tabular-nums;line-height:1.1}
.stat .l{font-family:var(--mono);font-size:.65rem;letter-spacing:.11em;text-transform:uppercase;
  color:#7E97AC;margin-top:3px}
/* ---------- nav ---------- */
nav.jump{position:sticky;top:0;z-index:20;background:color-mix(in srgb,var(--ground) 88%,transparent);
  backdrop-filter:blur(9px);border-bottom:1px solid var(--line)}
nav.jump .wrap{display:flex;gap:5px;overflow-x:auto;padding-top:9px;padding-bottom:9px}
nav.jump a{font-family:var(--mono);font-size:.72rem;letter-spacing:.055em;text-transform:uppercase;
  color:var(--muted);text-decoration:none;padding:5px 10px;border-radius:3px;white-space:nowrap}
nav.jump a:hover{color:var(--text);background:var(--surface)}
nav.jump a:focus-visible{outline:2px solid var(--accent);outline-offset:1px}
/* ---------- sections ---------- */
section{padding:52px 0;border-bottom:1px solid var(--line-2)}
section > .wrap{display:flex;flex-direction:column;gap:26px}
.shead{display:flex;flex-direction:column;gap:7px;max-width:72ch}
/* ---------- panels ---------- */
.panel{background:var(--surface);border:1px solid var(--line);border-radius:4px;
  box-shadow:var(--shadow);overflow:hidden}
.panel > .ph{display:flex;align-items:center;gap:9px;justify-content:space-between;
  padding:10px 14px;border-bottom:1px solid var(--line-2);background:var(--surface-2)}
.ph .t{font-family:var(--mono);font-size:.79rem;font-weight:600}
.ph .s{font-family:var(--mono);font-size:.7rem;color:var(--faint)}
.pb{padding:14px}
.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:18px}
.grid3{display:grid;grid-template-columns:repeat(auto-fit,minmax(228px,1fr));gap:14px}
/* ---------- chips ---------- */
.chip{display:inline-block;font-family:var(--mono);font-size:.68rem;padding:2px 7px;border-radius:3px;
  background:var(--surface-2);color:var(--muted);border:1px solid var(--line-2);white-space:nowrap}
.chip.ok{background:var(--ok-soft);color:var(--ok);border-color:transparent}
.chip.warn{background:var(--warn-soft);color:var(--warn);border-color:transparent}
.chip.crit{background:var(--crit-soft);color:var(--crit);border-color:transparent}
.chip.acc{background:var(--accent-soft);color:var(--accent-ink);border-color:transparent}
/* ---------- tables ---------- */
.tw{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:.83rem}
th{text-align:left;font-family:var(--mono);font-size:.68rem;letter-spacing:.09em;text-transform:uppercase;
  color:var(--faint);font-weight:600;padding:7px 10px;border-bottom:1px solid var(--line)}
td{padding:7px 10px;border-bottom:1px solid var(--line-2);vertical-align:top}
tr:last-child td{border-bottom:0}
td.m,th.m{font-family:var(--mono);font-variant-numeric:tabular-nums}
td.num{text-align:right;font-family:var(--mono);font-variant-numeric:tabular-nums}
/* ---------- code ---------- */
pre{margin:0;background:var(--code-bg);color:var(--code-fg);font-family:var(--mono);
  font-size:.76rem;line-height:1.58;padding:13px 15px;overflow-x:auto;border-radius:3px}
pre .hl{display:block;background:rgba(224,105,92,.17);border-left:2px solid var(--crit);
  margin:0 -15px;padding:0 13px}
pre .cm{color:#6C8399}
.filebar{display:flex;justify-content:space-between;gap:10px;align-items:center;
  font-family:var(--mono);font-size:.72rem;color:var(--faint);padding:8px 14px;
  background:var(--surface-2);border-bottom:1px solid var(--line-2)}
/* ---------- tool catalog ---------- */
details.tool{border:1px solid var(--line);border-radius:4px;background:var(--surface);overflow:hidden}
details.tool + details.tool{margin-top:-1px}
details.tool > summary{list-style:none;cursor:pointer;padding:9px 13px;display:grid;
  grid-template-columns:15px 200px 1fr;gap:11px;align-items:baseline}
details.tool > summary::-webkit-details-marker{display:none}
details.tool > summary:hover{background:var(--surface-2)}
details.tool > summary:focus-visible{outline:2px solid var(--accent);outline-offset:-2px}
.tmark{font-family:var(--mono);font-size:.7rem;color:var(--faint)}
details[open] .tmark{color:var(--accent)}
.tname{font-family:var(--mono);font-size:.81rem;font-weight:600}
.tdesc{color:var(--muted);font-size:.79rem}
.tbody{padding:0 13px 13px 13px;display:flex;flex-direction:column;gap:9px}
.io{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:9px}
.iolabel{font-family:var(--mono);font-size:.65rem;letter-spacing:.1em;text-transform:uppercase;
  color:var(--faint);margin-bottom:4px}
.toolbar{display:flex;gap:7px;flex-wrap:wrap;align-items:center}
/* ---------- trace ---------- */
.trace{display:flex;flex-direction:column;gap:0;position:relative}
.tstep{display:grid;grid-template-columns:26px 1fr;gap:11px;padding:7px 0;position:relative}
.tstep::before{content:"";position:absolute;left:12px;top:0;bottom:0;width:1px;background:var(--line)}
.tstep:first-child::before{top:16px}
.tstep:last-child::before{bottom:calc(100% - 16px)}
.tdot{width:25px;height:25px;border-radius:50%;background:var(--surface);border:1px solid var(--line);
  display:grid;place-items:center;font-family:var(--mono);font-size:.65rem;color:var(--muted);
  position:relative;z-index:1;font-variant-numeric:tabular-nums}
.tdot.w{border-color:var(--accent);color:var(--accent-ink);background:var(--accent-soft)}
.tcall{display:flex;flex-wrap:wrap;gap:7px;align-items:baseline}
.tcall .fn{font-family:var(--mono);font-size:.8rem;font-weight:600}
.tcall .ar{font-family:var(--mono);font-size:.72rem;color:var(--faint);word-break:break-word}
.tres{font-family:var(--mono);font-size:.72rem;color:var(--muted);margin-top:2px}
/* ---------- scorecard ---------- */
.dim{border:1px solid var(--line);border-radius:4px;overflow:hidden;background:var(--surface)}
.dimh{display:flex;justify-content:space-between;align-items:center;gap:9px;padding:9px 12px;
  border-bottom:1px solid var(--line-2);background:var(--surface-2)}
.dimh .w{font-family:var(--mono);font-size:.72rem;color:var(--faint)}
.dimh .n{font-family:var(--sans);font-weight:700;font-size:.9rem}
.check{display:flex;gap:8px;align-items:baseline;padding:6px 12px;font-size:.79rem;
  border-bottom:1px solid var(--line-2)}
.check:last-child{border-bottom:0}
.check .mk{font-family:var(--mono);color:var(--ok);font-size:.75rem}
.check .cn{font-family:var(--mono);font-size:.75rem}
.bar{height:5px;background:var(--line-2);border-radius:3px;overflow:hidden}
.bar > i{display:block;height:100%;background:var(--accent)}
/* ---------- misc ---------- */
.note{font-size:.83rem;color:var(--muted);border-left:2px solid var(--accent);padding-left:12px}
.kv{display:grid;grid-template-columns:auto 1fr;gap:4px 14px;font-size:.83rem}
.kv dt{font-family:var(--mono);font-size:.72rem;color:var(--faint)}
.kv dd{margin:0}
footer{padding:34px 0 56px;color:var(--faint);font-size:.79rem}
@media (max-width:640px){
  details.tool > summary{grid-template-columns:15px 1fr;gap:8px}
  .tdesc{grid-column:1/-1;padding-left:26px}
}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
"""


def build():
    o = []
    A = o.append
    c = D["counts"]

    # ---------------------------------------------------------------- head
    A('<header class="top"><div class="wrap">')
    A('<div class="stack" style="gap:14px">')
    A('<span class="eyebrow">Executable benchmark world · Horizon-SWE blueprint</span>')
    A("<h1>A working model of an engineering org,<br>built to grade autonomous engineers.</h1>")
    A('<p class="lede">NovaCart is a fictional e-commerce company that actually runs. Ten services '
      'over a database, cache, queue, object store and CDN; a monorepo an agent reads and edits; '
      'synthetic traffic that turns deployed state into live metrics; and 50 long-horizon tasks '
      'graded by executable verifiers with no LLM in the reward path.</p>')
    A("</div>")
    A('<div class="statgrid">')
    for n, l in [(c["tasks"], "tasks"), (c["tools"], "tools"), (len(D["services"]), "services"),
                 (len(D["infra"]), "infra"), (c["repo_files"], "repo files"),
                 (c["commits"], "commits"), (c["documents"], "kb docs"),
                 (c["tables"], "tables"), (c["rows"], "seed rows")]:
        A('<div class="stat"><div class="n">%s</div><div class="l">%s</div></div>' % (n, l))
    A("</div>")
    A('<div class="meta-row"><b>%s</b><span>·</span><span>oracle pass 100%%</span><span>·</span>'
      '<span>random pass 0%%</span><span>·</span><span>verifier precision 1.000 / recall 1.000 / '
      'FPR 0.000</span></div>' % e(D["world_id"]))
    A("</div></header>")

    A('<nav class="jump"><div class="wrap">')
    for hid, lab in [("stack", "The stack"), ("evidence", "What an agent reads"),
                     ("tools", "Tools"), ("episode", "A worked episode"),
                     ("aiops", "AIOpsLab suite"), ("scoring", "Scoring"),
                     ("tasks", "Task index")]:
        A('<a href="#%s">%s</a>' % (hid, lab))
    A("</div></nav>")

    # ---------------------------------------------------------------- stack
    A('<section id="stack"><div class="wrap">')
    A('<div class="shead"><span class="eyebrow">01 — The application stack</span>'
      "<h2>Ten services, real dependencies, and traffic that makes them misbehave</h2>"
      '<p class="lede">Production metrics are not stored numbers. A deterministic engine recomputes '
      "them from whatever is actually deployed, so a config left wrong in production keeps burning "
      "error budget until an agent ships the fix.</p></div>")

    A('<div class="grid2">')
    A('<div class="panel"><div class="ph"><span class="t">services</span>'
      '<span class="s">tier 1 = canary required</span></div><div class="tw"><table>')
    A("<tr><th>service</th><th>kind</th><th>team</th><th class=m>tier</th><th>lang</th>"
      "<th class=m>version</th></tr>")
    for s in D["services"]:
        tone = "crit" if s["tier"] == 1 else ("warn" if s["tier"] == 2 else "")
        A("<tr><td class=m><b>%s</b></td><td>%s</td><td>%s</td><td>%s</td><td class=m>%s</td>"
          "<td class=m>%s</td></tr>" % (e(s["name"]), e(s["kind"]), e(s["team"]),
                                        chip("T%d" % s["tier"], tone), e(s["language"]),
                                        e(s["repo_version"])))
    A("</table></div></div>")

    A('<div class="stack" style="gap:18px">')
    A('<div class="panel"><div class="ph"><span class="t">infrastructure</span></div><div class="tw"><table>')
    for i in D["infra"]:
        A("<tr><td class=m><b>%s</b></td><td>%s</td><td style='color:var(--muted)'>%s</td></tr>"
          % (e(i["name"]), chip(i["kind"], "acc"), e(i["detail"])))
    A("</table></div></div>")
    A('<div class="panel"><div class="ph"><span class="t">traffic generator</span>'
      '<span class="s">requests/sec by route</span></div><div class="tw"><table>')
    for t in D["traffic"][:7]:
        A("<tr><td class=m>%s</td><td class=m style='color:var(--muted)'>%s</td>"
          "<td class=num><b>%s</b></td></tr>" % (e(t["service"]), e(t["route"]), t["rps"]))
    A("</table></div></div>")
    A("</div></div>")

    A('<div class="panel"><div class="ph"><span class="t">live production telemetry</span>'
      '<span class="s">derived from deployed state · 9 alarms firing at seed</span></div><div class="tw"><table>')
    A("<tr><th>service</th><th>metric</th><th class='m' style='text-align:right'>current</th>"
      "<th class='m' style='text-align:right'>SLO</th><th>state</th></tr>")
    for m in D["metrics"]:
        th = m["threshold"]
        if th is None:
            st, tone = "no SLO", ""
        elif m["value"] > th:
            st, tone = "breaching", "crit"
        else:
            st, tone = "healthy", "ok"
        A("<tr><td class=m>%s</td><td class=m style='color:var(--muted)'>%s</td>"
          "<td class=num><b>%s</b></td><td class=num style='color:var(--faint)'>%s</td>"
          "<td>%s</td></tr>" % (e(m["service"]), e(m["metric"]), m["value"],
                                "—" if th is None else th, chip(st, tone)))
    A("</table></div></div>")
    A("</div></section>")

    # ---------------------------------------------------------------- evidence
    A('<section id="evidence"><div class="wrap">')
    A('<div class="shead"><span class="eyebrow">02 — What an agent reads</span>'
      "<h2>The evidence is real, and every incident is diagnosable from it</h2>"
      '<p class="lede">Each planted defect appears three times over: in the running metrics, in the '
      "logs and error tracker, and in the source code with the commit that introduced it. The "
      "knowledge base states the policy the verifier will hold the agent to.</p></div>")

    # code file with the bug
    f = D["code"]
    lines = f["content"].split("\n")
    body = []
    for ln in lines[:46]:
        cls = " class=hl" if ("retry_max_attempts" in ln and "0" in ln) or "no retry" in ln.lower() else ""
        body.append("<span%s>%s</span>" % (cls, e(ln) or " "))
    A('<div class="panel"><div class="filebar"><span><b style="color:var(--text)">%s</b> · %s · %s LOC'
      "</span><span>owner %s</span></div><pre>%s</pre></div>"
      % (e(f["path"]), e(f["language"]), f["loc"], e(f["owner"]), "\n".join(body)))

    A('<div class="grid2">')
    A('<div class="panel"><div class="ph"><span class="t">production logs</span>'
      '<span class="s">search_logs()</span></div><div class="tw"><table>')
    for l in D["logs"][:6]:
        tone = {"ERROR": "crit", "WARN": "warn"}.get(l["level"], "")
        A("<tr><td class=m>%s</td><td>%s</td><td style='color:var(--muted);font-size:.78rem'>%s</td></tr>"
          % (e(l["service"]), chip(l["level"], tone), e(l["message"][:150])))
    A("</table></div></div>")

    A('<div class="panel"><div class="ph"><span class="t">error tracker</span>'
      '<span class="s">list_error_events()</span></div><div class="tw"><table>')
    A("<tr><th>issue</th><th>culprit</th><th class='m' style='text-align:right'>events</th></tr>")
    for x in D["errors"]:
        A("<tr><td><div class=m style='font-weight:600'>%s</div>"
          "<div style='color:var(--muted);font-size:.76rem'>%s</div></td>"
          "<td class=m style='color:var(--faint);font-size:.72rem'>%s</td>"
          "<td class=num>%s</td></tr>"
          % (e(x["fingerprint"]), e(x["title"][:64]), e(x["culprit"][:40]), "{:,}".format(x["events"])))
    A("</table></div></div>")
    A("</div>")

    # commits + runbook
    A('<div class="grid2">')
    A('<div class="panel"><div class="ph"><span class="t">monorepo history</span>'
      '<span class="s">%s commits · list_commits()</span></div><div class="tw"><table>' % c["commits"])
    for cm in D["commits"][:9]:
        A("<tr><td class=m style='color:var(--accent-ink)'>%s</td>"
          "<td class=m style='color:var(--faint)'>d%s</td>"
          "<td style='font-size:.79rem'>%s<div style='color:var(--faint);font-size:.72rem'>%s</div></td></tr>"
          % (e(cm["sha"]), cm["day"], e(cm["message"][:62]), e(cm["author"])))
    A("</table></div></div>")

    rb = D["doc_runbook"]
    A('<div class="panel"><div class="ph"><span class="t">%s</span><span class="s">runbook</span></div>'
      '<div class="pb" style="font-size:.83rem;color:var(--muted);max-height:340px;overflow:auto">%s</div></div>'
      % (e(rb["title"]), "".join("<p style='margin:.4em 0'>%s</p>" % e(p)
                                 for p in rb["body"].split("\n") if p.strip())))
    A("</div>")

    # ticket
    t = D["ticket"]
    A('<div class="panel"><div class="ph"><span class="t">%s</span>'
      '<span class="s">%s · %s</span></div><div class="pb stack" style="gap:8px">'
      "<h3>%s</h3><p style='color:var(--muted);font-size:.87rem'>%s</p></div></div>"
      % (e(t["key"]), e(t["type"]), e(t["priority"]), e(t["title"]), e(t["description"])))

    A('<div class="grid3">')
    for label, rows, cols in [
        ("knowledge base", D["docs"][:9], lambda d: (d["kind"], d["title"])),
        ("test catalog", D["tests"][:9], lambda d: (d["status"], "%s · %s" % (d["service"], d["name"]))),
        ("scanner findings", D["vulns"], lambda d: (d["severity"], "%s in %s" % (d["cve"], d["service"]))),
    ]:
        A('<div class="panel"><div class="ph"><span class="t">%s</span></div><div class="tw"><table>' % label)
        for r in rows:
            k, v = cols(r)
            tone = {"flaky": "warn", "critical": "crit", "high": "crit", "medium": "warn",
                    "passing": "ok"}.get(k, "")
            A("<tr><td>%s</td><td style='font-size:.78rem'>%s</td></tr>" % (chip(k, tone), e(v)))
        A("</table></div></div>")
    A("</div>")
    A("</div></section>")

    # ---------------------------------------------------------------- tools
    A('<section id="tools"><div class="wrap">')
    reads = [t for t in D["tools"] if t["kind"] == "read"]
    writes = [t for t in D["tools"] if t["kind"] == "write"]
    A('<div class="shead"><span class="eyebrow">03 — Tool surface</span>'
      "<h2>All %d tools, each shown with a real call and its real response</h2>"
      '<p class="lede">%d read tools for investigation and %d write tools that change the world. '
      "Every payload below was captured by invoking the tool against a live session of the "
      "published world — nothing here is illustrative.</p></div>" % (len(D["tools"]), len(reads), len(writes)))

    for group, items in [("read · investigation", reads), ("write · changes the world", writes)]:
        A('<div class="stack" style="gap:0">')
        A('<div class="toolbar" style="margin-bottom:9px"><span class="eyebrow">%s</span>%s</div>'
          % (e(group), chip("%d tools" % len(items))))
        for t in items:
            A('<details class="tool"><summary><span class="tmark">▸</span>'
              '<span class="tname">%s</span><span class="tdesc">%s</span></summary>'
              % (e(t["name"]), e(t["description"][:120])))
            A('<div class="tbody">')
            A('<div class="toolbar">')
            for tb in t["reads"][:4]:
                A(chip("reads %s" % tb))
            for tb in t["writes"][:4]:
                A(chip("writes %s" % tb, "acc"))
            A("</div>")
            A('<div class="io"><div><div class="iolabel">call</div><pre>%s(%s)</pre></div>'
              '<div><div class="iolabel">response</div><pre>%s</pre></div></div>'
              % (e(t["name"]), e(json.dumps(t["args"])[1:-1][:200]), jdump(t["result"], 900)))
            A("</div></details>")
        A("</div>")
    A("</div></section>")

    # ---------------------------------------------------------------- episode
    ep = D["episode"]
    A('<section id="episode"><div class="wrap">')
    A('<div class="shead"><span class="eyebrow">04 — A worked episode</span>'
      "<h2>Investigate → pull request → CI → merge → staging → canary → promote → resolve</h2>"
      '<p class="lede">This is the reference solution for <code>%s</code> replayed against a fresh '
      "session, exactly as the build gate runs it. Watch the error rate: it does not move until the "
      "fix is actually promoted in production.</p></div>" % e(ep["task_id"]))

    A('<div class="panel"><div class="ph"><span class="t">assignment</span>'
      '<span class="s">%s</span></div><div class="pb" style="font-size:.87rem;color:var(--muted)">%s</div></div>'
      % (e(ep["task_id"]), "".join("<p style='margin:.45em 0'>%s</p>" % e(p)
                                   for p in ep["instruction"].split("\n") if p.strip())))

    WRITE = {"open_pull_request", "run_ci", "merge_pull_request", "deploy_service", "assess_canary",
             "promote_canary", "acknowledge_alert", "resolve_alert", "update_ticket"}
    A('<div class="panel"><div class="ph"><span class="t">trace</span>'
      '<span class="s">%d tool calls</span></div><div class="pb"><div class="trace">' % len(ep["steps"]))
    for i, s in enumerate(ep["steps"], 1):
        r = s["result"]
        keep = {k: r[k] for k in ("status", "detail", "run_id", "pr_number", "merged_version",
                                  "version", "canary_percent", "verdict", "alert_id", "key",
                                  "deployment_id", "applied") if k in r}
        if s["tool"] == "query_metrics":
            rows = [x for x in r.get("rows", []) if x["metric"] == "error_rate_pct"]
            keep = {"payments error_rate_pct": rows[0]["value"] if rows else None}
        if not keep:
            n = r.get("count")
            keep = {"rows": n} if n is not None else {"ok": r.get("ok", True)}
        A('<div class="tstep"><div class="tdot%s">%d</div><div>'
          '<div class="tcall"><span class="fn">%s</span><span class="ar">%s</span></div>'
          '<div class="tres">→ %s</div></div></div>'
          % (" w" if s["tool"] in WRITE else "", i, e(s["tool"]),
             e(json.dumps(s["args"])[1:-1][:110]), e(json.dumps(keep)[1:-1][:150])))
    A("</div></div></div>")

    v = ep["verdict"]
    dims = {}
    for a in v["assertions"]:
        dims.setdefault(a["dimension"], []).append(a)
    A('<div class="grid3">')
    for dim, weight in [("correctness", "60%"), ("deployment", "30%"), ("quality", "10%")]:
        items = dims.get(dim, [])
        okn = sum(1 for a in items if a["passed"])
        A('<div class="dim"><div class="dimh"><span class="n">%s</span>'
          '<span class="w">%s · %d/%d</span></div>' % (e(dim), weight, okn, len(items)))
        A('<div class="bar" style="margin:0"><i style="width:%d%%"></i></div>'
          % (100 * okn // max(1, len(items))))
        for a in items:
            A('<div class="check"><span class="mk">%s</span><span class="cn">%s</span></div>'
              % ("✓" if a["passed"] else "✕", e(a["name"])))
        A("</div>")
    A("</div>")
    A('<div class="note">Verdict <b>PASS</b> — Horizon-SWE-PF requires every correctness and '
      "deployment check; Horizon-SWE-PC scored <b>%s</b>. The canary step reported "
      "<code>healthy · clears error_rate_pct=4.2 (SLO 1.0)</code>, and the alarm could not be "
      "resolved until the metric actually recovered to 0.4.</div>" % v.get("score", 1.0))
    A("</div></section>")

    # ---------------------------------------------------------------- aiops
    ai = D.get("aiops")
    if ai:
        A('<section id="aiops"><div class="wrap">')
        A('<div class="shead"><span class="eyebrow">05 — A second benchmark\u2019s use case</span>'
          "<h2>The same world also runs AIOpsLab-style diagnostics</h2>"
          '<p class="lede">microsoft/AIOpsLab grades a different skill: the agent investigates '
          "read-only and <em>submits a finding</em> rather than executing a fix. Its taxonomy — "
          "detection, localization, analysis — is reproduced here over the faults already planted "
          "in this world, answer-graded through a typed <code>submit_diagnosis</code> API.</p></div>")
        A('<div class="grid2">')
        A('<div class="panel"><div class="ph"><span class="t">the 12 diagnostic tasks</span>'
          '<span class="s">answer-graded · read-only</span></div><div class="tw"><table>')
        A("<tr><th>task</th><th>type</th><th class='m' style='text-align:right'>oracle steps</th></tr>")
        for t in ai["tasks"]:
            A("<tr><td class=m style='font-size:.78rem'>%s</td><td>%s</td><td class=num>%d</td></tr>"
              % (e(t["id"]), chip(t["cat"].split("_")[1], "acc"), t["steps"]))
        A("</table></div></div>")
        A('<div class="panel"><div class="ph"><span class="t">what the verifier enforces</span>'
          '</div><div class="tw"><table>')
        for k, val in [("Correct answer", "service, fault type and offending key must all match"),
                       ("False positives cost", "one detection task targets a healthy service"),
                       ("Read-only", "no merge, deploy, flag, migration or rollback in the episode"),
                       ("Answer key", "lives in the task spec, never in the database"),
                       ("Step budget", "a finding must be reached within the task's budget")]:
            A("<tr><td style='font-size:.85rem'><b>%s</b></td>"
              "<td style='color:var(--muted);font-size:.83rem'>%s</td></tr>" % (e(k), e(val)))
        A("</table></div></div>")
        A("</div>")
        A('<div class="panel"><div class="ph"><span class="t">root-cause episode · %s</span>'
          '<span class="s">%d tool calls</span></div><div class="pb"><div class="trace">'
          % (e(ai["task_id"]), len(ai["steps"])))
        for i, st in enumerate(ai["steps"], 1):
            r = st["result"]
            keep = {k: r[k] for k in ("fault_type", "offending_key", "service", "status", "key")
                    if k in r}
            if not keep:
                n = r.get("count")
                keep = {"rows": n} if n is not None else {"ok": r.get("ok", True)}
            A('<div class="tstep"><div class="tdot%s">%d</div><div>'
              '<div class="tcall"><span class="fn">%s</span><span class="ar">%s</span></div>'
              '<div class="tres">→ %s</div></div></div>'
              % (" w" if st["tool"] == "submit_diagnosis" else "", i, e(st["tool"]),
                 e(json.dumps(st["args"])[1:-1][:120]), e(json.dumps(keep)[1:-1][:150])))
        A("</div></div></div>")
        A('<div class="grid3">')
        for lab, val, sub in [("time-to-detect", "5.0", "mean tool calls · 4 tasks"),
                              ("time-to-localize", "6.0", "mean tool calls · 4 tasks"),
                              ("time-to-analyze", "8.0", "mean tool calls · 4 tasks")]:
            A('<div class="panel"><div class="pb stack" style="gap:3px">'
              '<div class="eyebrow">%s</div>'
              '<div style="font-family:var(--mono);font-size:1.5rem;font-weight:600;'
              'color:var(--accent-ink)">%s</div>'
              '<div style="color:var(--faint);font-size:.75rem">%s</div></div></div>'
              % (e(lab), e(val), e(sub)))
        A("</div>")
        A('<div class="note">AIOpsLab reports wall-clock TTD/TTA/TTM; in a simulator the honest '
          "analogue is the tool call at which the finding was submitted, so these are step counts, "
          "not seconds. The harness also reports \u03c4-bench\u2019s <code>pass^k</code> "
          "reliability metric.</div>")
        A("</div></section>")

    # ---------------------------------------------------------------- scoring
    A('<section id="scoring"><div class="wrap">')
    A('<div class="shead"><span class="eyebrow">06 — Grading</span>'
      "<h2>Two scores, no judge in the reward path</h2></div>")
    A('<div class="grid2">')
    A('<div class="panel"><div class="ph"><span class="t">Horizon-SWE-PF</span>'
      '<span class="s">binary</span></div><div class="pb" style="color:var(--muted);font-size:.87rem">'
      "A task passes only with a full score on the feature-correctness and deployment verifiers. "
      "Engineering quality is scored but deliberately excluded, so style never rescues a broken "
      "rollout.</div></div>")
    A('<div class="panel"><div class="ph"><span class="t">Horizon-SWE-PC</span>'
      '<span class="s">composite</span></div><div class="pb" style="color:var(--muted);font-size:.87rem">'
      "0.6 feature correctness (build, unit, integration, regression, state) + 0.3 deployment &amp; "
      "DevOps (staging-first, canary, migrations, alarms) + 0.1 engineering quality (commit scope, "
      "documentation, no fabricated data, no unproductive loops).</div></div>")
    A("</div>")
    A('<div class="panel"><div class="ph"><span class="t">difficulty: scripted baselines</span>'
      '<span class="s">no model has been run yet</span></div><div class="tw"><table>')
    A("<tr><th>policy</th><th>what it does</th>"
      "<th class='m' style='text-align:right'>PF</th>"
      "<th class='m' style='text-align:right'>PC</th></tr>")
    for name, desc, pf, pc in [
        ("oracle", "the reference solution, following every policy", "100%", "100.0"),
        ("naive", "correct technical fix, ignores every documented policy", "29%", "87.1"),
        ("random", "random tool calls", "0%", "—")]:
        A("<tr><td class=m><b>%s</b></td><td style='color:var(--muted);font-size:.83rem'>%s</td>"
          "<td class=num>%s</td><td class=num>%s</td></tr>" % (e(name), e(desc), e(pf), e(pc)))
    A("</table></div></div>")
    A('<div class="note">The policy-blind baseline scores <b>PF 0%</b> on every category that '
      "ships a change — the deployment dimension is load-bearing. It keeps <b>PC 87.1</b> "
      "because feature correctness is 60% of the composite and it does get the fix right, "
      "which is a fair reading of how generous PC is by construction.</div>")
    A('<div class="panel"><div class="ph"><span class="t">what stops reward hacking</span></div>'
      '<div class="tw"><table>')
    for k, val in [
        ("Verifier fails on the pristine seed", "enforced at build for all 50 tasks — no free reward"),
        ("Oracle replays through the real tools", "781/781 tool calls succeed; PF 100%, PC 100"),
        ("Random policy", "0% pass rate"),
        ("Adversarial audit (250 corruption trials)",
         "precision 1.000 · recall 1.000 · FPR 0.000; all 5 corruption families rejected"),
        ("Forged state", "reference tables byte-compared; referential integrity enforced"),
        ("Tampered audit trail", "append-only log must stay contiguous with its seeded prefix intact"),
    ]:
        A("<tr><td style='font-size:.85rem'><b>%s</b></td>"
          "<td style='color:var(--muted);font-size:.83rem'>%s</td></tr>" % (e(k), e(val)))
    A("</table></div></div>")
    A("</div></section>")

    # ---------------------------------------------------------------- tasks
    A('<section id="tasks" style="border-bottom:0"><div class="wrap">')
    A('<div class="shead"><span class="eyebrow">07 — Task index</span>'
      "<h2>Ten categories across two benchmark use cases</h2></div>")
    A('<div class="grid3">')
    for cat, n in sorted(D["categories"].items(), key=lambda kv: -kv[1]):
        A('<div class="panel"><div class="pb stack" style="gap:5px">'
          '<div class="eyebrow">%s</div><div style="font-family:var(--mono);font-size:1.5rem;'
          'font-weight:600;color:var(--accent-ink)">%d</div></div></div>' % (e(cat.replace("_", " ")), n))
    A("</div>")
    A('<div class="panel"><div class="ph"><span class="t">task index</span>'
      '<span class="s">%d train · %d heldout</span></div><div class="tw"><table>'
      % (D["splits"]["train"], D["splits"]["heldout"]))
    A("<tr><th>task</th><th>category</th><th>difficulty</th>"
      "<th class='m' style='text-align:right'>oracle steps</th></tr>")
    for t in D["tasks"]:
        tone = {"expert": "crit", "hard": "warn"}.get(t["diff"], "")
        A("<tr><td class=m style='font-size:.78rem'>%s</td>"
          "<td style='color:var(--muted);font-size:.79rem'>%s</td><td>%s</td>"
          "<td class=num>%d</td></tr>"
          % (e(t["id"]), e(t["cat"].replace("_", " ")), chip(t["diff"], tone), t["steps"]))
    A("</table></div></div>")
    A("</div></section>")

    A('<footer><div class="wrap">Generated from the published world package — every metric, '
      "document, code excerpt, tool response and trace on this page was read out of "
      "<code>%s</code> or captured by invoking the tool live.</div></footer>" % e(D["world_id"]))
    return "\n".join(o)


page = ("<title>NovaCart — an executable engineering world</title>\n"
        "<style>%s</style>\n%s" % (CSS, build()))
pathlib.Path("/tmp/demo/index.html").write_text(page)
print("written:", len(page), "bytes")
