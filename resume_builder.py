"""Resume builder: pick the points you want from dropdowns, reword them, and watch the resume update.

Separate from the Job Hunter dashboard. Run with:  streamlit run resume_builder.py --server.port 8502
It reads the active profile's master resume and never changes it; your picks are saved as drafts.
"""

from __future__ import annotations

import re

import streamlit as st

from job_hunter import builder, export, profiles, theme, themes, userdata
from job_hunter.resume import resume_lines
from job_hunter.theme import escape

st.set_page_config(page_title="Resume builder", page_icon="📝", layout="wide")
st.logo(theme.logo_uri())

DRAFT, WIDGET = "rb-draft", "rb-w-"

PAGE_CSS = """
<style>
.block-container {padding-top: 3rem;}
.rb-page {background:#fff; color:#111827; font-family:Calibri, 'Segoe UI', Arial, sans-serif; font-size:13.5px;
          line-height:1.35; padding:34px 40px; border:1px solid #D1D5DB; border-radius:4px;
          box-shadow:0 2px 10px rgba(15,23,42,.12);}
.rb-page * {color:#111827 !important;}
.rb-page .n {font-size:24px; font-weight:700; text-align:center;}
.rb-page .h {font-size:15px; text-align:center;}
.rb-page .c {font-size:11.5px; text-align:center; margin-bottom:8px; color:#374151 !important;}
.rb-page .s {font-weight:700; font-size:14px; letter-spacing:.04em; border-bottom:1px solid #111827;
             margin:12px 0 4px 0;}
.rb-page .r {margin-top:6px;}
.rb-page .d {float:right; font-style:italic;}
.rb-page ul {margin:2px 0 2px 0; padding-left:20px;}
.rb-page li {margin:0;}
.rb-page p {margin:0 0 2px 0;}
.rb-empty {color:#9CA3AF !important; font-style:italic;}
</style>
"""


def reset(draft: dict) -> None:
    """Make draft the working copy and drop every widget's state so they redraw from it."""
    for key in [k for k in st.session_state if k.startswith(WIDGET)]:
        st.session_state.pop(key)
    st.session_state[DRAFT] = draft


def wkey(name: str, initial) -> str:
    """A widget key, seeded from the draft the first time the widget is drawn."""
    key = WIDGET + name
    st.session_state.setdefault(key, initial)
    return key


def short(text: str, limit: int = 110) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


# ---------- sidebar: profile and drafts ----------

def switch_profile() -> None:
    profiles.set_active(st.session_state["rb-profile"])
    reset({})  # an empty draft is rebuilt from the new profile's master resume


names = profiles.list_profiles()
current = profiles.active_profile()
with st.sidebar:
    st.selectbox("Profile", names, index=names.index(current), key="rb-profile", on_change=switch_profile,
                 help="Uses this profile's master resume. Same profiles as the Job Hunter dashboard.")

master = userdata.load_resume()
st.markdown(PAGE_CSS + theme.CSS.replace("{vars}", themes.css(themes.saved())), unsafe_allow_html=True)
st.markdown(
    f'<div class="jh-header">{theme.LOGO_SVG.format(size=44, fill=themes.logo_fill(themes.saved()))}'
    f'<h1>Resume builder</h1></div><p class="jh-sub">Pick the points you want from each dropdown, reword them, '
    f'and the resume on the right updates as you go. Your master resume is never changed.</p>',
    unsafe_allow_html=True,
)
if not master:
    st.info("This profile has no master resume yet. Open the Job Hunter dashboard and upload your resume on its "
            "welcome screen, then come back here.")
    st.stop()

if not st.session_state.get(DRAFT):
    reset(builder.default_draft(master))
draft = st.session_state[DRAFT]


def save_current() -> None:
    name = st.session_state.get("rb-save-name", "")
    try:
        builder.save_draft(name, st.session_state[DRAFT])
    except ValueError as exc:
        st.session_state["rb-flash"] = ("error", str(exc))
    else:
        st.session_state["rb-flash"] = ("success", f"Saved draft “{builder.clean_draft_name(name)}”.")
        st.session_state["rb-open"] = builder.clean_draft_name(name)


def open_draft() -> None:
    name = st.session_state.get("rb-open")
    if name:
        reset({**builder.default_draft(master), **builder.load_draft(name)})
        st.session_state["rb-save-name"] = name
        st.session_state["rb-flash"] = ("success", f"Opened “{name}”.")


def delete_draft() -> None:
    name = st.session_state.get("rb-open")
    if name:
        builder.delete_draft(name)
        st.session_state.pop("rb-open", None)
        st.session_state["rb-flash"] = ("success", f"Deleted “{name}”.")


def start_over() -> None:
    reset(builder.default_draft(master, st.session_state[DRAFT].get("track")))
    st.session_state.pop("rb-save-name", None)


with st.sidebar:
    st.subheader("Drafts")
    st.text_input("Draft name", key="rb-save-name", placeholder="e.g. Sys admin - Boeing")
    st.button("Save draft", on_click=save_current, type="primary", use_container_width=True)
    saved = builder.list_drafts()
    if saved:
        if st.session_state.get("rb-open") not in saved:
            st.session_state.pop("rb-open", None)
        st.selectbox("Saved drafts", saved, key="rb-open")
        c1, c2 = st.columns(2)
        c1.button("Open", on_click=open_draft, use_container_width=True)
        c2.button("Delete", on_click=delete_draft, use_container_width=True)
    else:
        st.caption("No saved drafts yet.")
    st.divider()
    st.button("Start over", on_click=start_over, use_container_width=True,
              help="Every point back in, in master order, for the current track.")
    st.caption("Drafts are kept with this profile's files. The Job Hunter dashboard is at http://localhost:8501.")
    flash = st.session_state.pop("rb-flash", None)
    if flash:
        getattr(st, flash[0])(flash[1])


# ---------- editor (left) ----------

def pick_track() -> None:
    track = st.session_state[WIDGET + "track"]
    pick = master.get("tracks", {}).get(track, {})
    st.session_state[WIDGET + "headline"] = pick.get("headline", "")
    st.session_state[WIDGET + "summary"] = pick.get("summary", "")


def move(pick_key: str, bid: str, step: int) -> None:
    order = list(st.session_state[pick_key])
    i = order.index(bid)
    j = max(0, min(len(order) - 1, i + step))
    order[i], order[j] = order[j], order[i]
    st.session_state[pick_key] = order


def add_point(kind: str, index: int) -> None:
    key = builder.section_key(kind, index)
    text = st.session_state.get(WIDGET + f"new-{key}", "").strip()
    if not text:
        return
    custom = st.session_state[DRAFT].setdefault("custom", {}).setdefault(key, [])
    custom.append(text)
    bid = f"c{len(custom) - 1}"
    pick_key = WIDGET + f"pick-{key}"
    st.session_state[pick_key] = list(st.session_state.get(pick_key, [])) + [bid]
    st.session_state[WIDGET + f"new-{key}"] = ""


def section_editor(kind: str, index: int, item: dict) -> None:
    key = builder.section_key(kind, index)
    section = draft["sections"].setdefault(key, {"on": True, "picked": []})
    label = f"{item['title']}, {item['org']}" if kind == "role" else item["name"]
    with st.expander(label, expanded=index == 0 and kind == "role"):
        section["on"] = st.checkbox("Include on the resume", key=wkey(f"on-{key}", section.get("on", True)))
        options = builder.bullet_options(master, draft, kind, index)
        pick_key = wkey(f"pick-{key}", [b for b in section.get("picked", []) if b in options])
        st.session_state[pick_key] = [b for b in st.session_state[pick_key] if b in options]
        picked = st.multiselect("Points to use, in the order you pick them", list(options),
                                format_func=lambda b: ("✎ " if b.startswith("c") else "") + short(options[b]),
                                key=pick_key, disabled=not section["on"], placeholder="Choose points")
        section["picked"] = list(picked)
        if picked and section["on"]:
            st.caption("Reword any point here. Changes show in the preview and are kept in this draft only.")
        for n, bid in enumerate(picked if section["on"] else []):
            c1, c2 = st.columns([12, 1])
            text = c1.text_area(f"Point {n + 1}", key=wkey(f"edit-{key}-{bid}", options[bid]), height=80,
                                label_visibility="collapsed")
            c2.button("", icon=":material/arrow_upward:", key=f"rb-up-{key}-{bid}", on_click=move, args=(pick_key, bid, -1), disabled=n == 0,
                      help="Move up")
            c2.button("", icon=":material/arrow_downward:", key=f"rb-dn-{key}-{bid}", on_click=move, args=(pick_key, bid, 1),
                      disabled=n == len(picked) - 1, help="Move down")
            edit_id = f"{key}:{bid}"
            original = builder.bullet_options(master, {**draft, "edits": {}}, kind, index)[bid]
            if text != original:
                draft["edits"][edit_id] = text
            else:
                draft["edits"].pop(edit_id, None)
        if section["on"]:
            c1, c2 = st.columns([4, 1])
            c1.text_input("Add your own point", key=wkey(f"new-{key}", ""), label_visibility="collapsed",
                          placeholder="Add your own point for this section")
            c2.button("Add", key=f"rb-add-{key}", on_click=add_point, args=(kind, index), use_container_width=True)


left, right = st.columns([1, 1], gap="large")
with left:
    st.subheader("Pick your points")
    tracks = list(master.get("tracks", {}))
    if tracks:
        st.selectbox("Starting headline and summary", tracks, key=wkey("track", draft.get("track") or tracks[0]),
                     on_change=pick_track, help="Fills the headline and summary from that track. You can edit both.")
        draft["track"] = st.session_state[WIDGET + "track"]
    draft["headline"] = st.text_input("Headline", key=wkey("headline", draft.get("headline", "")))
    draft["summary"] = st.text_area("Summary", key=wkey("summary", draft.get("summary", "")), height=110)

    st.markdown("**Experience**")
    for i, role in enumerate(master.get("experience", [])):
        section_editor("role", i, role)
    if master.get("projects"):
        st.markdown("**Projects**")
        for i, project in enumerate(master["projects"]):
            section_editor("project", i, project)

    st.markdown("**Skills, education and certifications**")
    with st.expander("Skills"):
        for name, items in master.get("skills", {}).items():
            current_items = [s for s in draft["skills"].get(name, []) if s in items]
            draft["skills"][name] = st.multiselect(name, items, key=wkey(f"skills-{name}", current_items))
    with st.expander("Education, certifications and awards"):
        education = master.get("education", [])
        if education:
            draft["education"] = st.multiselect(
                "Education", list(range(len(education))), format_func=lambda i: education[i]["name"],
                key=wkey("education", [i for i in draft.get("education", []) if i < len(education)]))
        certs = master.get("certifications", [])
        if certs:
            draft["certifications"] = st.multiselect(
                "Certifications (in the order you pick them)", certs,
                key=wkey("certs", [c for c in draft.get("certifications", []) if c in certs]))
        awards = master.get("awards", [])
        if awards:
            draft["awards"] = st.multiselect("Awards", awards,
                                             key=wkey("awards", [a for a in draft.get("awards", []) if a in awards]))


# ---------- preview and export (right) ----------

def preview_html(resume: dict) -> str:
    e = escape
    contact = resume["contact"]
    parts = [f'<div class="rb-page"><div class="n">{e(contact.get("name", ""))}</div>',
             f'<div class="h">{e(resume["headline"])}</div>',
             f'<div class="c">{e(export.contact_line(contact))}</div>']

    def bullets(items):
        return "<ul>" + "".join(f"<li>{e(b)}</li>" for b in items) + "</ul>" if items else \
            '<p class="rb-empty">No points picked</p>'

    if resume["summary"]:
        parts += ['<div class="s">SUMMARY</div>', f'<p>{e(resume["summary"])}</p>']
    if resume["skills"]:
        parts.append('<div class="s">SKILLS</div>')
        parts += [f'<p><b>{e(g["name"])}:</b> {e(", ".join(g["items"]))}</p>' for g in resume["skills"]]
    if resume["experience"]:
        parts.append('<div class="s">EXPERIENCE</div>')
        for role in resume["experience"]:
            parts.append(f'<div class="r"><b>{e(role["title"])}</b>, {e(role["org"])}'
                         f'<span class="d">{e(role.get("dates", ""))}</span></div>' + bullets(role["bullets"]))
    if resume["projects"]:
        parts.append('<div class="s">PROJECTS</div>')
        for project in resume["projects"]:
            link = f' &nbsp;{e(project["link"])}' if project.get("link") else ""
            parts.append(f'<div class="r"><b>{e(project["name"])}</b>{link}</div>' + bullets(project["bullets"]))
    if resume["education"]:
        parts.append('<div class="s">EDUCATION</div>')
        parts += [f'<p>{e(item["name"])}<span class="d">{e(item.get("dates", ""))}</span></p>'
                  for item in resume["education"]]
    if resume["certifications"]:
        parts += ['<div class="s">CERTIFICATIONS</div>', bullets(resume["certifications"])]
    if resume["awards"]:
        parts += ['<div class="s">AWARDS</div>', bullets(resume["awards"])]
    return "".join(parts) + "</div>"


resume = builder.compose(master, draft)
with right:
    st.subheader("Your resume")
    stem_label = st.session_state.get("rb-save-name") or draft.get("track") or "Resume"
    stem = re.sub(r"[^A-Za-z0-9_-]+", "_", f"{master['contact'].get('name', 'Resume')}_{stem_label}").strip("_")[:90]
    c1, c2 = st.columns(2)
    c1.download_button("Download Word", export.to_docx(resume), f"{stem}.docx",
                       "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                       use_container_width=True, type="primary")
    c2.download_button("Download PDF", export.to_pdf(resume), f"{stem}.pdf", "application/pdf",
                       use_container_width=True)
    count = sum(len(r["bullets"]) for r in resume["experience"] + resume["projects"])
    st.caption(f"{count} points picked. Word is best if you want to keep editing after you download.")
    with st.container(height=900, border=False):
        st.markdown(preview_html(resume), unsafe_allow_html=True)
    with st.expander("Copy as plain text (for application forms)"):
        st.code("\n".join(resume_lines(resume)), language=None)
