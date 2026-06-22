#!/usr/bin/env python3
"""Interactive sandbox for the candidate ranker. Loads a sample, ranks it via
rank.py, and shows the decomposition, evidence and per-candidate detail.

    streamlit run app.py
"""
import json, os, tempfile, datetime, io, csv as _csv
from pathlib import Path

import streamlit as st
import plotly.graph_objects as go

import rank

HERE = Path(__file__).parent
JD_ROLE = "Senior AI Engineer · Founding Team"

st.set_page_config(page_title="Redrob · Candidate Intelligence",
                   page_icon="◆", layout="wide", initial_sidebar_state="expanded")

# --- styles ---
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;600&display=swap');
:root{
  --bg:#F6F7FB; --surface:#FFFFFF; --surface-2:#FBFBFE;
  --border:#E8EAF1; --border-2:#DEE1EB;
  --ink:#13151C; --ink-2:#555B6B; --ink-3:#888E9E;
  --brand:#5B50E6; --brand-ink:#4036C7; --brand-soft:#EEEDFD;
  --green:#0E9F6E; --green-ink:#07734F; --green-soft:#E6F7F0;
  --red:#E11D48; --red-ink:#A10E33; --red-soft:#FDEBEF;
  --amber:#B45309; --amber-soft:#FBF0DE;
  --sh-sm:0 1px 2px rgba(17,24,39,.05);
  --sh:0 1px 3px rgba(17,24,39,.06),0 4px 12px rgba(17,24,39,.05);
  --sh-lg:0 10px 30px rgba(17,24,39,.10);
  --r-card:16px; --r-ctl:10px;
}
/* hide toolbar chrome but keep the header (it holds the sidebar expand control) */
[data-testid="stToolbarActions"],[data-testid="stAppDeployButton"],#MainMenu,footer,[data-testid="stDecoration"]{display:none !important;}
[data-testid="stHeader"]{background:transparent;}
/* style the collapsed-sidebar expand button */
[data-testid="stSidebarCollapsedControl"] button,[data-testid="stExpandSidebarButton"]{
  background:var(--surface) !important; border:1px solid var(--border) !important; border-radius:10px !important;
  box-shadow:var(--sh-sm) !important; color:var(--brand-ink) !important;}
[data-testid="stAppViewContainer"],.main{background:transparent !important;}
.block-container{padding-top:1.4rem; padding-bottom:4rem; max-width:1300px;}
html,body,[class*="css"],.stMarkdown,p,span,div,label,input,button{font-family:'Inter',-apple-system,BlinkMacSystemFont,sans-serif;}
.stApp{background:
  radial-gradient(40rem 30rem at 88% -5%, rgba(91,80,230,.06), transparent 60%),
  linear-gradient(180deg,#FAFAFE 0%, var(--bg) 100%) !important;}

section[data-testid="stSidebar"]{background:var(--surface) !important; border-right:1px solid var(--border);}
section[data-testid="stSidebar"] *{color:var(--ink-2);}
section[data-testid="stSidebar"] h3{color:var(--ink) !important; font-size:.8rem; letter-spacing:.04em; text-transform:uppercase;}

.card{background:var(--surface); border:1px solid var(--border); border-radius:var(--r-card); box-shadow:var(--sh);}

.topbar{display:flex; align-items:center; justify-content:space-between; padding:2px 2px 18px;}
.brand{display:flex; align-items:center; gap:11px;}
.brand-mark{width:34px; height:34px; border-radius:10px; background:linear-gradient(135deg,#6D5AE6,#4F46E5);
  display:flex; align-items:center; justify-content:center; color:#fff; box-shadow:0 4px 12px rgba(79,70,229,.35);}
.brand-name{font-weight:700; color:var(--ink); font-size:1.02rem; letter-spacing:-.01em;}
.brand-dim{color:var(--ink-3); font-weight:500;}
.live{display:inline-flex; align-items:center; gap:7px; font-size:.78rem; font-weight:600; color:var(--green-ink);
  background:var(--green-soft); border:1px solid rgba(14,159,110,.22); border-radius:999px; padding:5px 12px;}
.live .dot{width:7px; height:7px; border-radius:50%; background:var(--green); box-shadow:0 0 0 3px rgba(14,159,110,.18);}

.hero-eyebrow{font-size:.74rem; font-weight:700; letter-spacing:.13em; text-transform:uppercase; color:var(--brand-ink);}
.hero-title{font-size:2.35rem; font-weight:800; letter-spacing:-.033em; line-height:1.08; color:var(--ink); margin:.5rem 0 .35rem;}
.hero-title b{background:linear-gradient(95deg,#6D5AE6,#9333EA); -webkit-background-clip:text; -webkit-text-fill-color:transparent;}
.hero-sub{color:var(--ink-2); font-size:1rem; margin:0;}
.hero-sub b{color:var(--ink); font-weight:600;}
.hero-thesis{color:var(--ink-2); font-size:.95rem; margin-top:.7rem; max-width:820px; line-height:1.62;}

.metric{padding:17px 18px;}
.metric .top{display:flex; align-items:center; justify-content:space-between;}
.metric .ic{width:30px; height:30px; border-radius:9px; background:var(--brand-soft); color:var(--brand-ink);
  display:flex; align-items:center; justify-content:center;}
.metric .v{font-size:1.7rem; font-weight:800; color:var(--ink); line-height:1; margin-top:13px; letter-spacing:-.02em;}
.metric .l{font-size:.74rem; color:var(--ink-3); margin-top:6px; font-weight:500;}
.v-green{color:var(--green-ink) !important;} .v-red{color:var(--red-ink) !important;}
.ic-green{background:var(--green-soft) !important; color:var(--green-ink) !important;}
.ic-red{background:var(--red-soft) !important; color:var(--red-ink) !important;}

.sech{display:flex; align-items:center; gap:10px; margin:.2rem 0 .15rem;}
.sech .si{width:28px; height:28px; border-radius:8px; background:var(--brand-soft); color:var(--brand-ink);
  display:flex; align-items:center; justify-content:center;}
.sech .st{font-size:1.18rem; font-weight:700; color:var(--ink); letter-spacing:-.01em;}
.sech-sub{color:var(--ink-3); font-size:.86rem; margin:.1rem 0 .8rem 38px;}

.panel{padding:16px 18px; height:100%;}
.panel-h{display:flex; align-items:center; gap:8px; font-size:.78rem; font-weight:700; text-transform:uppercase;
  letter-spacing:.05em; margin-bottom:11px;}
.row{display:flex; align-items:center; gap:9px; font-size:.88rem; color:var(--ink); padding:8px 0; border-top:1px solid var(--border);}
.row:first-of-type{border-top:none;}
.row .t{color:var(--ink-3); font-size:.78rem;}
.row .nm{font-weight:600;}

.callout{display:flex; gap:12px; padding:15px 18px;}
.callout .ci{flex-shrink:0; width:34px; height:34px; border-radius:10px; display:flex; align-items:center; justify-content:center;}
.callout .cb{color:var(--ink-2); font-size:.9rem; line-height:1.55;}
.callout .cb b{color:var(--ink);}

.lb{display:flex; align-items:center; gap:13px; padding:11px 15px; border:1px solid var(--border); border-radius:12px;
  background:var(--surface); box-shadow:var(--sh-sm); margin-bottom:8px; transition:box-shadow .14s,border-color .14s,transform .14s;}
.lb:hover{box-shadow:var(--sh); border-color:var(--border-2); transform:translateY(-1px);}
.lb-rank{font-weight:700; color:var(--ink-3); width:30px; text-align:center; font-family:'JetBrains Mono',monospace; font-size:.92rem;}
.lb-main{flex:1; min-width:0;}
.lb-name{font-weight:600; color:var(--ink); font-size:.92rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;}
.lb-meta{color:var(--ink-3); font-size:.79rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;}
.lb-barw{width:104px; height:6px; background:var(--border); border-radius:6px; overflow:hidden;}
.lb-bar{height:100%; border-radius:6px;}
.lb-score{width:48px; text-align:right; font-weight:600; color:var(--ink-2); font-family:'JetBrains Mono',monospace; font-size:.86rem;}

.pill{display:inline-flex; align-items:center; gap:5px; padding:3px 10px; border-radius:7px; font-size:.71rem; font-weight:600; white-space:nowrap;}
.p-strong{background:var(--green-soft); color:var(--green-ink);}
.p-adjacent{background:var(--brand-soft); color:var(--brand-ink);}
.p-down{background:var(--amber-soft); color:var(--amber);}
.p-floor{background:var(--red-soft); color:var(--red-ink);}

.chip{display:inline-flex; align-items:center; gap:6px; padding:5px 11px; margin:3px 5px 3px 0; border-radius:8px;
  background:var(--surface); border:1px solid var(--border); color:var(--ink-2); font-size:.81rem;}
.chip b{color:var(--ink);}
.chip-no{border-color:rgba(225,29,72,.28); color:var(--red-ink); background:var(--red-soft);}
.chip-yes{border-color:rgba(14,159,110,.28); color:var(--green-ink); background:var(--green-soft);}

.flag{display:flex; gap:9px; align-items:flex-start; background:var(--red-soft); border:1px solid rgba(225,29,72,.2);
  border-radius:10px; padding:9px 12px; margin:6px 0; color:var(--red-ink); font-size:.85rem;}
.pen{display:flex; justify-content:space-between; align-items:center; background:var(--amber-soft);
  border:1px solid rgba(180,83,9,.2); border-radius:10px; padding:8px 12px; margin:6px 0; color:var(--amber); font-size:.85rem;}
.reason{background:var(--brand-soft); border:1px solid rgba(91,80,230,.18); border-radius:12px;
  padding:14px 16px; color:var(--brand-ink); font-size:.9rem; line-height:1.55;}
.small{color:var(--ink-3); font-size:.8rem;}
.kvh{font-weight:700; color:var(--ink); font-size:.74rem; margin:14px 0 7px; text-transform:uppercase; letter-spacing:.06em;}
.job{border-left:2px solid var(--brand-soft); padding:1px 0 8px 12px; margin:6px 0;}
.job b{color:var(--ink);}

[data-testid="stTextInput"] input{border:1px solid var(--border) !important; border-radius:var(--r-ctl) !important;
  background:var(--surface) !important; color:var(--ink) !important; font-size:.88rem !important;}
[data-testid="stTextInput"] input:focus{border-color:var(--brand) !important; box-shadow:0 0 0 3px rgba(91,80,230,.14) !important;}
[data-testid="stSelectbox"] div[data-baseweb="select"]>div{border-radius:var(--r-ctl) !important; border-color:var(--border) !important;
  background:var(--surface) !important; min-height:40px;}
[data-testid="stSlider"] [data-baseweb="slider"] [role="slider"]{background:var(--brand) !important; border-color:#fff !important;}
[data-testid="stSlider"] [data-baseweb="slider"] div[style*="background"]{background:var(--brand) !important;}
[data-testid="stExpander"]{border:1px solid var(--border) !important; border-radius:12px !important; background:var(--surface) !important; box-shadow:var(--sh-sm);}
[data-testid="stExpander"] summary{font-weight:600; color:var(--ink);}
[data-testid="stExpander"] summary:hover{color:var(--brand-ink);}
[data-testid="stDataFrame"]{border:1px solid var(--border); border-radius:12px; overflow:hidden;}
[data-testid="stDownloadButton"] button{background:linear-gradient(135deg,#6D5AE6,#4F46E5) !important; color:#fff !important;
  border:none !important; border-radius:var(--r-ctl) !important; font-weight:600 !important; padding:.6rem 1.4rem !important;
  box-shadow:0 6px 16px rgba(79,70,229,.3) !important;}
[data-testid="stDownloadButton"] button:hover{filter:brightness(1.07);}
.stCheckbox label,.stSelectbox label,.stSlider label,.stTextInput label{color:var(--ink-2) !important; font-size:.82rem !important; font-weight:500 !important;}
hr{border-color:var(--border);}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

ICONS = {
    "target": "<circle cx='12' cy='12' r='9'/><circle cx='12' cy='12' r='5'/><circle cx='12' cy='12' r='1.4' fill='currentColor'/>",
    "check": "<path d='M20 6 9 17l-5-5'/>",
    "x": "<path d='M18 6 6 18M6 6l12 12'/>",
    "shield": "<path d='M12 22c5-2 8-6 8-11V5l-8-3-8 3v6c0 5 3 9 8 11z'/><path d='m9 12 2 2 4-4'/>",
    "activity": "<path d='M22 12h-4l-3 9L9 3l-3 9H2'/>",
    "search": "<circle cx='11' cy='11' r='7'/><path d='m21 21-4.3-4.3'/>",
    "sliders": "<path d='M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6'/>",
    "eye": "<path d='M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z'/><circle cx='12' cy='12' r='3'/>",
    "arrow": "<path d='M5 12h14M13 6l6 6-6 6'/>",
    "cpu": "<rect x='4' y='4' width='16' height='16' rx='2'/><rect x='9' y='9' width='6' height='6'/><path d='M9 1v3M15 1v3M9 20v3M15 20v3M1 9h3M1 15h3M20 9h3M20 15h3'/>",
    "layers": "<path d='m12 2 9 5-9 5-9-5 9-5zM3 12l9 5 9-5M3 17l9 5 9-5'/>",
    "users": "<path d='M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2'/><circle cx='9' cy='7' r='4'/><path d='M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75'/>",
    "alert": "<path d='M10.3 3.6 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.6a2 2 0 0 0-3.4 0z'/><path d='M12 9v4M12 17h.01'/>",
}

def ic(name, size=18, sw=2):
    return (f"<svg width='{size}' height='{size}' viewBox='0 0 24 24' fill='none' stroke='currentColor' "
            f"stroke-width='{sw}' stroke-linecap='round' stroke-linejoin='round' "
            f"style='display:inline-block;vertical-align:-3px'>{ICONS[name]}</svg>")

def sech(icon, title, sub):
    st.markdown(f"<div class='sech'><span class='si'>{ic(icon,17)}</span><span class='st'>{title}</span></div>"
                f"<div class='sech-sub'>{sub}</div>", unsafe_allow_html=True)

KIND_BAR = {"strong": "#0E9F6E", "adjacent": "#5B50E6", "down": "#B45309", "floor": "#E11D48"}
FLAG_EN = {
    "tenure_exceeds_experience": "Total job tenure exceeds stated years of experience by more than 4 years.",
    "job_longer_than_career": "A single job lasts longer than the candidate's entire stated career.",
    "skill_duration_exceeds_career": "A skill has reportedly been used for longer than the person has worked.",
    "expert_zero_duration": "Claims 'expert'/'advanced' proficiency in a skill used for 0 months.",
    "expert_no_endorsements": "6+ 'expert' skills with almost no endorsements to corroborate them.",
    "education_dates_reversed": "Education end year precedes its start year.",
    "overlapping_jobs": "Job dates overlap — summed tenure exceeds the real calendar span.",
}

# --- helpers (use rank.py's constants; no scoring duplicated) ---

def rel_skill_count(c, thresh=0.70):
    n = 0
    for s in c["skills"]:
        nm = rank._norm(s["name"])
        for grp, (gw, names) in rank.SKILL_GROUPS.items():
            if grp != "offtarget" and gw >= thresh and (nm in names or any(x in nm for x in names)):
                n += 1
                break
    return n

def is_offtarget(c):
    off = rel = 0
    for s in c["skills"]:
        nm = rank._norm(s["name"])
        for grp, (gw, names) in rank.SKILL_GROUPS.items():
            if nm in names or any(x in nm for x in names):
                off += grp == "offtarget"
                rel += grp != "offtarget" and gw >= 0.7
                break
    return off >= 3 and off > rel

def skill_group(name):
    nm = rank._norm(name)
    for grp, (gw, names) in rank.SKILL_GROUPS.items():
        if nm in names or any(nm == n or n in nm for n in names):
            return grp
    return "—"

def verdict(c, d):
    title = rank._norm(c["profile"]["current_title"])
    country = rank._norm(c["profile"]["country"])
    if d["hp"]:
        return ("Honeypot — floored", "floor")
    if d["gate"] == "role_gate":
        return ("Keyword-stuffer — floored", "floor")
    tags = [lbl for lbl, _ in rank.penalty_reasons(c)]
    if "research" in title:
        tags.append("research")
    if country and country != "india":
        tags.append("outside India")
    if is_offtarget(c):
        tags.append("off-target")
    if not tags and d["score"] >= 0.72:
        return ("Strong fit", "strong")
    if not tags and d["score"] >= 0.45:
        return ("Solid fit", "strong")
    if tags:
        return ("Down-weighted", "down")
    return ("Adjacent", "adjacent")

def naive_top_idx(cands, k=5):
    return sorted(range(len(cands)), key=lambda i: -rel_skill_count(cands[i]))[:k]

# --- data loading (cached; calls rank.load_candidates / rank.rank_all) ---

def _to_jsonl_bytes(raw):
    s = raw.decode("utf-8", "ignore").strip()
    if s.startswith("["):
        return ("\n".join(json.dumps(o, ensure_ascii=False) for o in json.loads(s))).encode("utf-8")
    return raw

@st.cache_data(show_spinner=False)
def rank_bytes(raw, _key):
    raw = _to_jsonl_bytes(raw)
    with tempfile.NamedTemporaryFile("wb", suffix=".jsonl", delete=False) as tf:
        tf.write(raw); tmp = tf.name
    try:
        cands, texts, ref = rank.load_candidates(tmp)
        scored = rank.rank_all(cands, texts, ref, min_df=1)
    finally:
        os.unlink(tmp)
    return cands, ref.isoformat(), scored

def source_bytes():
    st.sidebar.markdown("### Candidate sample")
    opts = ["Curated showcase (40)"]
    if (HERE / "pool_sample.jsonl").exists():
        opts.append("Random pool slice (400)")
    if (HERE / "sample_candidates.json").exists():
        opts.append("Organizer sample (50)")
    opts.append("Upload .jsonl …")
    choice = st.sidebar.radio("Input", opts, label_visibility="collapsed")
    if choice.startswith("Curated"):
        return (HERE / "showcase_candidates.jsonl").read_bytes(), "showcase"
    if choice.startswith("Random"):
        st.sidebar.caption("A random, unfiltered 400 from the real 100K pool — nothing selected for.")
        return (HERE / "pool_sample.jsonl").read_bytes(), "pool400"
    if choice.startswith("Organizer"):
        st.sidebar.caption("First 50 raw profiles — mostly adjacent. Use the curated showcase or random slice.")
        return (HERE / "sample_candidates.json").read_bytes(), "sample"
    up = st.sidebar.file_uploader("Upload candidates", type=["jsonl", "json"], label_visibility="collapsed")
    if up is None:
        st.sidebar.caption("Up to ~100 records (.jsonl or .json array).")
        st.markdown(
            f"<div class='topbar'><div class='brand'><span class='brand-mark'>{ic('target',19)}</span>"
            f"<span class='brand-name'>Redrob <span class='brand-dim'>· Candidate Intelligence</span></span></div>"
            f"<span class='live'><span class='dot'></span>Live sandbox</span></div>", unsafe_allow_html=True)
        st.markdown(
            "<div class='card' style='padding:56px 32px;text-align:center;margin-top:18px'>"
            f"<div style='display:inline-flex;width:50px;height:50px;border-radius:13px;background:var(--brand-soft);"
            f"color:var(--brand-ink);align-items:center;justify-content:center'>{ic('search',24)}</div>"
            "<div style='font-size:1.4rem;font-weight:700;color:var(--ink);margin-top:15px'>Rank a candidate file</div>"
            "<div class='small' style='margin-top:9px;max-width:460px;margin-left:auto;margin-right:auto;line-height:1.6'>"
            "Use the <b style='color:var(--ink)'>Upload</b> button on the left to add a <b style='color:var(--ink)'>.jsonl</b> "
            "or <b style='color:var(--ink)'>.json</b> file (up to ~100 records), or pick a bundled sample to explore the "
            "ranker instantly.</div></div>", unsafe_allow_html=True)
        st.stop()
    return up.getvalue(), "upload:" + up.name

# --- render helpers ---

def metric(icon, val, label, tone=""):
    vt = {"green": "v-green", "red": "v-red"}.get(tone, "")
    it = {"green": "ic-green", "red": "ic-red"}.get(tone, "")
    return (f"<div class='card metric'><div class='top'><div class='ic {it}'>{ic(icon,16)}</div></div>"
            f"<div class='v {vt}'>{val}</div><div class='l'>{label}</div></div>")

def radar(comps):
    cats = ["Role", "Career", "Semantic", "Skill", "Experience", "Location"]
    keys = ["role", "career", "semantic", "skill", "experience", "location"]
    vals = [comps[k] for k in keys]
    fig = go.Figure(go.Scatterpolar(r=vals + [vals[0]], theta=cats + [cats[0]], fill="toself",
        line=dict(color="#5B50E6", width=2.5), fillcolor="rgba(91,80,230,0.13)",
        hovertemplate="%{theta}: %{r:.2f}<extra></extra>"))
    fig.update_layout(polar=dict(bgcolor="rgba(0,0,0,0)",
        radialaxis=dict(range=[0, 1], gridcolor="#E8EAF1", tickfont=dict(color="#888E9E", size=9), tickvals=[.25, .5, .75, 1]),
        angularaxis=dict(gridcolor="#E8EAF1", tickfont=dict(color="#555B6B", size=12))),
        paper_bgcolor="rgba(0,0,0,0)", margin=dict(l=44, r=44, t=26, b=26), height=320, showlegend=False, font=dict(family="Inter"))
    return fig

def leaderboard_html(pairs):
    rows = []
    for pos, c, d in pairs:
        p = c["profile"]; lab, kind = verdict(c, d)
        pct = max(3, min(100, round(d["score"] * 100)))
        rows.append(
            f"<div class='lb'><div class='lb-rank'>{pos}</div>"
            f"<div class='lb-main'><div class='lb-name'>{p['anonymized_name']}</div>"
            f"<div class='lb-meta'>{p['current_title']} · {p['years_of_experience']:g}y · {p['location']}</div></div>"
            f"<span class='pill p-{kind}'>{lab}</span>"
            f"<div class='lb-barw'><div class='lb-bar' style='width:{pct}%;background:{KIND_BAR[kind]}'></div></div>"
            f"<div class='lb-score'>{d['score']:.3f}</div></div>")
    return "".join(rows) or "<div class='small' style='padding:10px'>No candidates match these filters.</div>"

def chips(pairs):
    out = []
    for label, val, ok in pairs:
        cls = "chip-yes" if ok is True else "chip-no" if ok is False else ""
        out.append(f"<span class='chip {cls}'><b>{val}</b> {label}</span>")
    return "<div>" + "".join(out) + "</div>"

def raw_profile_html(c):
    p = c["profile"]
    out = [f"<div class='small'>{p['summary']}</div>", "<div class='kvh'>Career history</div>"]
    for j in c["career_history"]:
        cur = " · current" if j.get("is_current") else ""
        out.append(f"<div class='job'><b>{j['title']}</b> @ {j['company']}"
                   f"<div class='small'>{j['industry']} · {j['start_date']} → {j['end_date'] or 'now'} · {j['duration_months']} mo{cur}</div>"
                   f"<div class='small' style='margin-top:3px'>{j['description']}</div></div>")
    if c.get("education"):
        out.append("<div class='kvh'>Education</div>")
        for e in c["education"]:
            out.append(f"<div class='small'>{e.get('degree','')} {e.get('field_of_study','')} · {e.get('institution','')} "
                       f"({e.get('start_year','?')}–{e.get('end_year','?')}) · tier {e.get('tier','?')}</div>")
    out.append("<div class='kvh'>All 23 Redrob signals (raw)</div>")
    sc = []
    for k, v in c["redrob_signals"].items():
        vs = json.dumps(v) if isinstance(v, (dict, list)) else str(v)
        sc.append(f"<span class='chip'><b>{k}</b> {vs[:36] + ('…' if len(vs) > 36 else '')}</span>")
    out.append("<div>" + "".join(sc) + "</div>")
    return "".join(out)

# --- page ---

raw, key = source_bytes()
with st.spinner("Ranking with rank.py …"):
    cands, ref_iso, scored = rank_bytes(raw, key)
ref_date = datetime.date.fromisoformat(ref_iso)
by_idx = {d["idx"]: d for d in scored}
n = len(cands)
n_hp = sum(1 for d in scored if d["hp"])
n_strong = sum(1 for d in scored if verdict(cands[d["idx"]], d)[1] == "strong")
hp_top10 = sum(1 for d in scored[:10] if d["hp"])

# sidebar
st.sidebar.markdown("---")
st.sidebar.markdown("### Constraints honoured")
st.sidebar.markdown("CPU only · no GPU \n\nNo network / no LLM calls \n\nDeterministic & reproducible")
st.sidebar.markdown("---")
st.sidebar.caption("Reproduce the full submission")
st.sidebar.code("python rank.py \\\n  --candidates candidates.jsonl \\\n  --out submission.csv", language="bash")

# top bar
st.markdown(f"<div class='topbar'><div class='brand'><span class='brand-mark'>{ic('target',19)}</span>"
            f"<span class='brand-name'>Redrob <span class='brand-dim'>· Candidate Intelligence</span></span></div>"
            f"<span class='live'><span class='dot'></span>Live sandbox</span></div>", unsafe_allow_html=True)

# hero
st.markdown("<div class='hero-eyebrow'>Track 1 · Data &amp; AI Challenge</div>", unsafe_allow_html=True)
st.markdown("<div class='hero-title'>Intelligent Candidate <b>Discovery &amp; Ranking</b></div>", unsafe_allow_html=True)
st.markdown(f"<p class='hero-sub'>Ranking the 100,000-profile pool against <b>{JD_ROLE}</b></p>", unsafe_allow_html=True)
st.markdown("<p class='hero-thesis'>The pool is adversarial — ~70% non-engineering titles stuffed with AI keywords, "
            "plus internally-impossible honeypots. A keyword or embedding matcher walks straight into the traps. "
            "This system reads each profile <i>structurally</i> across six signals, gates non-engineers, and floors "
            "impossible profiles. Everything below is computed live — filter it, search it, and open any source "
            "profile to verify.</p>", unsafe_allow_html=True)

st.write("")
m = st.columns(5)
cards = [("users", f"{n:,}", "Candidates ranked", ""), ("shield", f"{hp_top10}", "Honeypots in top 10", "green"),
         ("alert", f"{n_hp}", "Impossible profiles floored", ""), ("check", f"{n_strong}", "Strong fits surfaced", ""),
         ("layers", "6", "Scoring signals", "")]
for col, (i, v, l, t) in zip(m, cards):
    col.markdown(metric(i, v, l, t), unsafe_allow_html=True)

st.write("")
sech("x", "The trap, made visible", "Same candidates, two rankers — rank by AI-keyword count (what keyword/embedding matchers reward) vs this system.")
cL, cR = st.columns(2)
with cL:
    rows = []
    for i in naive_top_idx(cands, 5):
        c = cands[i]; p = c["profile"]; lab, kind = verdict(c, by_idx[i])
        rows.append(f"<div class='row'><span class='nm'>{p['anonymized_name']}</span><span class='pill p-{kind}'>{lab}</span>"
                    f"<div style='flex:1'></div><span class='t'>{rel_skill_count(c)} AI skills</span></div>")
    st.markdown(f"<div class='card panel'><div class='panel-h' style='color:var(--red-ink)'>{ic('x',15)} Naive keyword ranking</div>"
                + "".join(rows) + "</div>", unsafe_allow_html=True)
with cR:
    rows = []
    for pos, d in enumerate(scored[:5], 1):
        c = cands[d["idx"]]; p = c["profile"]; lab, kind = verdict(c, d)
        rows.append(f"<div class='row'><span class='lb-rank' style='width:18px'>{pos}</span><span class='nm'>{p['anonymized_name']}</span>"
                    f"<span class='pill p-{kind}'>{lab}</span><div style='flex:1'></div><span class='t'>{d['score']:.3f}</span></div>")
    st.markdown(f"<div class='card panel'><div class='panel-h' style='color:var(--green-ink)'>{ic('check',15)} This system</div>"
                + "".join(rows) + "</div>", unsafe_allow_html=True)

naive_rank = {idx: r + 1 for r, idx in enumerate(sorted(range(len(cands)), key=lambda i: -rel_skill_count(cands[i])))}
final_rank = {d["idx"]: r + 1 for r, d in enumerate(scored)}
traps = sorted((d for d in scored if d["hp"] or d["gate"] == "role_gate"), key=lambda d: naive_rank[d["idx"]])
if traps:
    items = []
    for d in traps[:5]:
        c = cands[d["idx"]]; p = c["profile"]
        why = "impossible honeypot" if d["hp"] else "keyword-stuffer"
        items.append(f"<div class='row'><span class='pill p-floor'>kw&nbsp;#{naive_rank[d['idx']]}</span>{ic('arrow',14)}"
                     f"<span class='pill p-strong'>rank&nbsp;{final_rank[d['idx']]}</span>"
                     f"<span class='nm' style='margin-left:4px'>{p['anonymized_name']}</span>"
                     f"<div style='flex:1'></div><span class='t'>{p['current_title']} · {why}</span></div>")
    st.markdown(f"<div class='card callout' style='margin-top:6px'><div class='ci' style='background:var(--brand-soft);color:var(--brand-ink)'>{ic('shield',18)}</div>"
                f"<div class='cb' style='flex:1'><b>Traps intercepted.</b> Profiles a keyword / embedding matcher ranks near "
                f"the very top — identified and floored out of contention:" + "".join(items) + "</div></div>", unsafe_allow_html=True)

# evidence at scale
sp = HERE / "pool_stats.json"
if sp.exists():
    try:
        S = json.loads(sp.read_text(encoding="utf-8")); T = S["top100"]; NB = S["naive_baseline"]
        st.write("")
        sech("activity", "Proven at scale", f"{S.get('runtime_note','')} Measured properties of the actual 100-row submission — not cherry-picked.")
        e = st.columns(4)
        ev = [("layers", f"{S['pool_size']:,}", "Pool ranked", ""), ("alert", f"{S['pool_nontech_pct']:g}%", "Non-engineering noise in pool", "red"),
              ("shield", f"{T['honeypots']}", "Honeypots in our top 100", "green"), ("target", f"{T['india_pct']}%", "Top-100 based in India", "")]
        for col, (i, v, l, t) in zip(e, ev):
            col.markdown(metric(i, v, l, t), unsafe_allow_html=True)
        st.markdown(f"<div class='card callout' style='margin-top:8px'><div class='ci' style='background:var(--red-soft);color:var(--red-ink)'>{ic('activity',18)}</div>"
                    f"<div class='cb'><b>Head-to-head on the full pool.</b> A naive keyword ranker would seat "
                    f"<b style='color:var(--red-ink)'>{NB['traps_in_top100']} traps</b> in its top 100 — including "
                    f"<b style='color:var(--red-ink)'>{NB['honeypots_in_top100']} impossible honeypots</b> (an automatic "
                    f"&gt;10% disqualification). This system seats <b style='color:var(--green-ink)'>{T['honeypots']} honeypots</b>, "
                    f"top-100 at a median of <b>{T['median_years']:g} yrs</b>, scores {T['score_min']:.2f}–{T['score_max']:.2f}.</div></div>",
                    unsafe_allow_html=True)
        with st.expander("Top-100 title composition (full-pool run)"):
            st.markdown(chips([(f"× {cnt}", t, None) for t, cnt in T["top_titles"]]), unsafe_allow_html=True)
    except Exception:
        pass

# explore
st.write("")
sech("sliders", "Explore the ranking", "Filter it like a recruiter — the list keeps best-fit order and shows each match's global rank.")
cities = sorted({c["profile"]["location"].split(",")[0].strip() for c in cands})
skill_names = sorted({s["name"] for c in cands for s in c["skills"]})
yrs = [c["profile"]["years_of_experience"] for c in cands]
ylo, yhi = int(min(yrs)), int(max(yrs)) + 1
f1, f2, f3, f4 = st.columns([1.3, 1.6, 1.6, 1.2])
f_loc = f1.selectbox("Location", ["All"] + cities)
f_yr = f2.slider("Years of experience", ylo, yhi, (ylo, yhi))
f_skill = f3.selectbox("Must-have skill", ["Any"] + skill_names)
f_hide = f4.checkbox("Hide floored traps")
f_india = f4.checkbox("India only")

def passes(c, d):
    p = c["profile"]
    if f_hide and (d["hp"] or d["gate"]): return False
    if f_india and rank._norm(p["country"]) != "india": return False
    if not (f_yr[0] <= p["years_of_experience"] <= f_yr[1]): return False
    if f_loc != "All" and f_loc.lower() not in p["location"].lower(): return False
    if f_skill != "Any" and not any(s["name"] == f_skill for s in c["skills"]): return False
    return True

filtered = [(pos, cands[d["idx"]], d) for pos, d in enumerate(scored, 1) if passes(cands[d["idx"]], d)]

left, right = st.columns([1.05, 1])
with left:
    show_all = st.checkbox(f"Show all {len(filtered)} matches (else top 15)")
    st.markdown(f"<div class='small' style='margin:-4px 0 10px'>Showing {len(filtered) if show_all else min(15, len(filtered))} "
                f"of {len(filtered)} matches · {n:,} ranked total</div>", unsafe_allow_html=True)
    st.markdown(leaderboard_html(filtered if show_all else filtered[:15]), unsafe_allow_html=True)

with right:
    st.markdown(f"<div class='panel-h' style='color:var(--brand-ink)'>{ic('eye',15)} Candidate inspector</div>", unsafe_allow_html=True)
    q = st.text_input("Jump to candidate", "", placeholder="search a name or CAND_id", label_visibility="collapsed")
    opt = [i for i in range(len(scored)) if not q
           or q.lower() in cands[scored[i]["idx"]]["profile"]["anonymized_name"].lower()
           or q.lower() in scored[i]["cid"].lower()]
    if not opt:
        st.warning("No candidate matches that search."); opt = list(range(len(scored)))
    sel = st.selectbox("Candidate", opt, label_visibility="collapsed",
                       format_func=lambda i: f"#{i+1}  {cands[scored[i]['idx']]['profile']['anonymized_name']}  ·  {cands[scored[i]['idx']]['profile']['current_title']}")
    d = scored[sel]; c = cands[d["idx"]]; p = c["profile"]; lab, kind = verdict(c, d)
    st.markdown(f"<div style='font-weight:700;font-size:1.02rem;color:var(--ink)'>{p['anonymized_name']} "
                f"<span class='pill p-{kind}'>{lab}</span></div>"
                f"<div class='small'>{p['current_title']} @ {p['current_company']} · {p['years_of_experience']:g} yrs · "
                f"{p['location']}, {p['country']} · {d['cid']}</div>", unsafe_allow_html=True)
    st.plotly_chart(radar(d["comps"]), use_container_width=True, config={"displayModeBar": False})

st.markdown(f"<div class='panel-h' style='color:var(--ink-2);margin-top:6px'>{ic('layers',14)} Score math</div>", unsafe_allow_html=True)
mm = st.columns(4)
fin = "honeypot floor" if d["gate"] == "honeypot" else "role gate" if d["gate"] == "role_gate" else "final score"
for col, (v, l) in zip(mm, [(f"{d['base']:.3f}", "base = Σ wᵢ·signalᵢ"), (f"×{d['mult']:.2f}", "behavioral multiplier"),
                            (f"−{d['penalty']:.2f}", "red-flag penalties"), (f"{d['score']:.3f}", fin)]):
    col.markdown(f"<div class='card metric'><div class='v'>{v}</div><div class='l'>{l}</div></div>", unsafe_allow_html=True)

dc1, dc2 = st.columns(2)
with dc1:
    st.markdown("**Grounded reasoning** <span class='small'>(written to the CSV)</span>", unsafe_allow_html=True)
    st.markdown(f"<div class='reason'>{rank.make_reasoning(c, d['comps'])}</div>", unsafe_allow_html=True)
    if rank.penalty_reasons(c):
        st.markdown("**Penalties applied**")
        for lbl, amt in rank.penalty_reasons(c):
            st.markdown(f"<div class='pen'><span>{lbl}</span><b>−{amt:.2f}</b></div>", unsafe_allow_html=True)
    if d["hp"]:
        st.markdown("**Why this is a honeypot**")
        for fl in d["hp"]:
            st.markdown(f"<div class='flag'>{ic('alert',15)}<span>{FLAG_EN.get(fl, fl)}</span></div>", unsafe_allow_html=True)
with dc2:
    s = c["redrob_signals"]; days = None
    try:
        days = (ref_date - datetime.date.fromisoformat(s["last_active_date"])).days; active = f"{days}d ago"
    except Exception:
        active = "—"
    st.markdown("**Behavioral signals**")
    st.markdown(chips([
        ("response rate", f"{s.get('recruiter_response_rate',0):.0%}", s.get('recruiter_response_rate',0) >= 0.5),
        ("last active", active, days <= 60 if isinstance(days, int) else None),
        ("interviews", f"{s.get('interview_completion_rate',0):.0%}", None),
        ("recruiter saves 30d", s.get("saved_by_recruiters_30d", 0), None),
        ("open to work", "yes" if s.get("open_to_work_flag") else "no", bool(s.get("open_to_work_flag"))),
        ("email", "ok" if s.get("verified_email") else "no", bool(s.get("verified_email"))),
        ("phone", "ok" if s.get("verified_phone") else "no", bool(s.get("verified_phone"))),
        ("notice", f"{s.get('notice_period_days',0)}d", None)]), unsafe_allow_html=True)
    st.markdown("**Top skills** <span class='small'>(trust-weighted)</span>", unsafe_allow_html=True)
    GRP = {"core_retrieval": "retrieval", "ranking_eval": "ranking/eval", "nlp_llm": "nlp/llm",
           "ml_foundation": "ml", "eng_foundation": "eng", "offtarget": "off-target", "—": "—"}
    sk = sorted(c["skills"], key=lambda x: -x.get("endorsements", 0))[:10]
    st.dataframe([{"skill": x["name"], "proficiency": x.get("proficiency", ""), "endorse": x.get("endorsements", 0),
                   "months": x.get("duration_months", 0), "relevance": GRP.get(skill_group(x["name"]), "—")} for x in sk],
                 use_container_width=True, hide_index=True, height=248)

with st.expander("Source profile — verify every field against the raw record"):
    st.markdown(raw_profile_html(c), unsafe_allow_html=True)

st.write("")
with st.expander("How the JD is encoded (must-haves, disqualifiers, weights)"):
    jc1, jc2 = st.columns(2)
    with jc1:
        st.markdown("**Must-haves the ranker rewards**")
        st.markdown(chips([("", x, True) for x in ("embeddings / vector search", "hybrid retrieval", "ranking & eval (NDCG/MRR)",
                                                   "6–8 yrs, product cos", "strong Python", "Pune / Noida / India")]), unsafe_allow_html=True)
    with jc2:
        st.markdown("**Disqualifiers the ranker punishes**")
        st.markdown(chips([("", x, False) for x in ("non-engineering title", "pure research, no production", "recent-LangChain-only",
                                                    "title-chasing", "services-only career", "CV/speech without NLP/IR", "honeypot")]), unsafe_allow_html=True)
    st.markdown("**Component weights** — `base = Σ wᵢ · signalᵢ`")
    st.markdown(chips([(k, f"{v:.2f}", None) for k, v in rank.W.items()]), unsafe_allow_html=True)
    st.caption("Half the official score is NDCG@10 — the design optimizes a clean, trap-free top of the list. Every constant lives at the top of rank.py.")

st.write("")
buf = io.StringIO(); w = _csv.writer(buf); w.writerow(["candidate_id", "rank", "score", "reasoning"])
for r, dd in enumerate(scored[:100], 1):
    w.writerow([dd["cid"], r, f"{dd['score']:.4f}", rank.make_reasoning(cands[dd["idx"]], dd["comps"])])
st.download_button("Download this ranking as CSV", buf.getvalue(), file_name="ranking.csv", mime="text/csv")
st.markdown("<div class='small' style='margin-top:.7rem'>This sandbox runs the identical scoring code as "
            "<code>rank.py</code>. On the full 100K pool it produces the 100-row submission in ~2 min on CPU, no network. "
            "· Solo entrant: Anifiesta</div>", unsafe_allow_html=True)
