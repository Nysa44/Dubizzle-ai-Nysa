from __future__ import annotations

import html
import streamlit as st
import streamlit.components.v1 as components

from api_client import APIClient

API_URL = "http://127.0.0.1:8000"
api = APIClient(API_URL)

st.set_page_config(page_title="dubizzle Cars", page_icon="🚘", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
:root{--red:#d71920;--yellow:#ffd21f;--ink:#171717;--cream:#fffdf8;--muted:#777;--line:#e9e3d8}
.stApp{background:var(--cream);color:var(--ink)}
.block-container{max-width:1500px;padding:3.2rem 2.4rem 5rem}.main .block-container{padding-top:2.2rem}
section[data-testid="stSidebar"]{background:#171717;border-right:1px solid #292929}
section[data-testid="stSidebar"] [data-testid="stSidebarContent"]{padding:1.5rem 1.15rem}
section[data-testid="stSidebar"] *{color:#fff}
section[data-testid="stSidebar"] .stCaption{color:#aaa!important}
section[data-testid="stSidebar"] input{background:#242424!important;color:#fff!important;border:1px solid #555!important;border-radius:12px!important}
/* Sidebar buttons: dark + white by default; no invisible white-on-white text. */
section[data-testid="stSidebar"] div.stButton>button{background:#242424!important;color:#fff!important;border:1px solid #444!important;border-radius:12px!important;font-weight:800!important}
section[data-testid="stSidebar"] div.stButton>button:hover{background:var(--yellow)!important;color:#171717!important;border-color:var(--yellow)!important}
section[data-testid="stSidebar"] hr{border-color:#303030}
.brand{display:flex;align-items:center;gap:12px;margin:4px 0 20px}
.brand-mark{width:50px;height:50px;border-radius:15px;background:var(--red);color:#fff;display:flex;align-items:center;justify-content:center;font-size:23px;font-weight:950;box-shadow:0 10px 28px rgba(215,25,32,.22)}
.brand-title{font-size:29px;font-weight:950;letter-spacing:-1.2px}.brand-sub{font-size:12px;color:#777;margin-top:4px}
.hero{background:linear-gradient(135deg,#171717 0%,#262626 66%,#b9151b 100%);color:#fff;border-radius:26px;padding:30px 34px;margin-bottom:20px;position:relative;overflow:hidden;box-shadow:0 18px 50px rgba(0,0,0,.08)}
.hero:after{content:"";position:absolute;right:-60px;top:-80px;width:250px;height:250px;border-radius:50%;background:var(--yellow)}
.hero h1,.hero p,.hero .pill{position:relative;z-index:2}.hero h1{margin:0;font-size:42px;letter-spacing:-1.5px}.hero p{max-width:780px;color:#dedede;margin:9px 0 0;line-height:1.55}.pill{display:inline-block;background:var(--yellow);color:#171717;padding:7px 11px;border-radius:999px;font-size:11px;font-weight:950;margin-bottom:12px}
.metrics-row{margin-bottom:12px}.metric{background:#fff;border:1px solid var(--line);border-radius:18px;padding:17px 18px;box-shadow:0 8px 28px rgba(0,0,0,.045)}.metric .num{font-size:25px;font-weight:950}.metric .label{font-size:10px;color:#888;text-transform:uppercase;letter-spacing:.1em;margin-top:3px}
.section-title{font-size:22px;font-weight:950;letter-spacing:-.4px;margin-top:10px}.start-request{margin-top:28px!important}.section-kicker{font-size:12px;color:#888;margin-bottom:14px}.suggestion-note{font-size:11px;color:#888;margin:8px 0 18px}
.car{background:#fff;border:1px solid var(--line);border-radius:20px;overflow:hidden;margin:8px 0 16px;box-shadow:0 10px 30px rgba(0,0,0,.055)}
.car img{width:100%;height:215px;object-fit:cover;background:#eee}.car-body{padding:16px 17px 8px}.rank{color:var(--red);font-size:10px;font-weight:950;letter-spacing:.05em}.car-title{font-size:20px;font-weight:950;margin-top:4px}.car-meta{font-size:12px;color:#666;margin:5px 0 9px}.price{color:var(--red);font-size:21px;font-weight:950}.fact-row{display:grid;grid-template-columns:1fr 1fr;gap:7px;margin-top:12px}.fact{background:#f7f5ef;border-radius:11px;padding:9px}.fact b{display:block;font-size:10px;text-transform:uppercase;color:#888;letter-spacing:.06em}.fact span{font-size:12px;font-weight:800}
.tag{display:inline-block;background:#fff1ad;color:#5e4c00;padding:4px 8px;border-radius:8px;margin:7px 5px 0 0;font-size:10px;font-weight:900}
.chat-user{background:#171717;color:#fff;border-radius:18px 18px 5px 18px;padding:13px 16px;margin:9px 0 9px 23%;line-height:1.5}.chat-ai{background:#fff;border:1px solid var(--line);border-left:4px solid var(--red);border-radius:5px 18px 18px 18px;padding:14px 17px;margin:9px 23% 9px 0;line-height:1.55;box-shadow:0 5px 18px rgba(0,0,0,.025)}
.evidence{background:#171717;color:#fff;border-radius:18px;padding:18px;margin:16px 0}.evidence h2{color:#fff!important;margin:4px 0}.evidence div{color:#ddd!important}.evidence small{color:#bbb}.source{border-left:3px solid var(--yellow);padding:11px 13px;background:#222;color:#fff!important;margin:8px 0;border-radius:0 10px 10px 0;font-size:12px;line-height:1.55;word-break:break-word}.source *{color:#fff!important}.source *{color:#fff!important}
div.stButton>button{border-radius:12px;border:1px solid #ddd7ca;background:#fff;color:#171717;font-weight:850;min-height:42px}div.stButton>button:hover{border-color:var(--red);color:var(--red);background:#fff8f7}
button[kind="primary"]{background:var(--red)!important;color:#fff!important;border-color:var(--red)!important}
.stTextInput input,.stTextArea textarea{border-radius:13px!important}
div[data-testid="stChatInput"]{border-top:0!important}
</style>
""",unsafe_allow_html=True)

for key, default in [("user_id","demo_dubizzle"),("session_id",None),("messages",[]),("results",[]),("total_matches",0),("inspect_id",None),("last_memory",{}),("auto_scroll_target",None)]:
    if key not in st.session_state: st.session_state[key]=default

with st.sidebar:
    st.markdown("## 🚘 DUBIZZLE CARS")
    st.caption("Inventory-first car discovery")
    st.markdown("---")
    user=st.text_input("Your name / user ID",value=st.session_state.user_id)
    if user.strip()!=st.session_state.user_id:
        st.session_state.user_id=user.strip(); st.session_state.session_id=None; st.session_state.messages=[]; st.session_state.results=[]; st.session_state.total_matches=0; st.rerun()
    if st.button("＋ New conversation",use_container_width=True):
        st.session_state.session_id=None; st.session_state.messages=[]; st.session_state.results=[]; st.session_state.total_matches=0; st.session_state.inspect_id=None; st.rerun()
    try: mem=api.memory(st.session_state.user_id)
    except Exception: mem={}
    st.markdown("### 🧠 Memory")
    if mem.get("max_budget") is not None: st.write(f"💰 Up to AED {mem['max_budget']:,.0f}")
    if mem.get("min_budget") is not None: st.write(f"💰 From AED {mem['min_budget']:,.0f}")
    recent_searches = mem.get("recent_searches") or [x.strip() for x in (mem.get("preferences") or "").split(" | ") if x.strip()]
    if recent_searches:
        st.markdown("**Recent searches / preferences**")
        for item in reversed(recent_searches[-6:]):
            st.write(f"🎯 {item}")
    st.write(f"⭐ {len(mem.get('favorite_listing_ids',[]))} saved favourite(s)")
    if st.session_state.get("last_memory",{}).get("short_term"):
        st.markdown("**Short-term:** active results + recent turns")
    st.markdown("---")
    st.caption("VIEWING WINDOW")
    st.markdown("**MON–SAT · 8:00 AM–8:00 PM**")
    st.caption("Bookings are simulated for the assessment.")

st.markdown("""
<div class="brand"><div class="brand-mark">D</div><div><div class="brand-title">dubizzle Cars</div><div class="brand-sub">Smart search · grounded inventory · persistent memory</div></div></div>
<div class="hero"><span class="pill">100 VERIFIED LISTINGS · EXCEL-GROUNDED</span><h1>Find your next car.</h1><p>Ask in plain English. dubizzle Cars searches the supplied inventory, reads facts directly from listing descriptions, keeps your current conversation in context, and remembers your shortlist across sessions.</p></div>
""",unsafe_allow_html=True)

try:
    health=api.health(); cols=st.columns(4)
    metrics=[(health.get("inventory_rows",0),"inventory listings"),("LIVE" if health.get("llm_enabled") else "FALLBACK","language layer"),("SHORT + LONG","memory"),("MON–SAT","viewings")]
    for col,(n,l) in zip(cols,metrics):
        with col: st.markdown(f'<div class="metric"><div class="num">{html.escape(str(n))}</div><div class="label">{html.escape(l)}</div></div>',unsafe_allow_html=True)
except Exception: st.warning("Backend is not reachable. Start FastAPI first.")

st.markdown("<div class='section-title start-request'>Start with a natural request</div><div class='section-kicker'>Try filters, details, comparisons or a viewing request.</div>",unsafe_allow_html=True)
quick=st.columns(4)
examples=[
    "Find cars under AED 50k",
    "Show me the newest Mercedes",
    "I want a booking",
    "Show me SUVS",
]
for col,text in zip(quick,examples):
    with col:
        if st.button(text,use_container_width=True): st.session_state.pending_prompt=text
st.markdown("<div class='suggestion-note'>Every suggestion is chosen from requests with verified matches in the supplied Excel inventory.</div>",unsafe_allow_html=True)
st.markdown("---")

for msg in st.session_state.messages:
    cls="chat-user" if msg["role"]=="user" else "chat-ai"
    st.markdown(f'<div class="{cls}">{html.escape(msg["content"]).replace(chr(10),"<br>")}</div>',unsafe_allow_html=True)

# After each submitted message, bring the latest conversation turn into view so
# users never have to guess where the new result appeared.
if st.session_state.get("auto_scroll_target"):
    target = str(st.session_state.auto_scroll_target).replace("'", "\'")
    components.html(f"""
    <script>
    setTimeout(() => {{
      const doc = window.parent.document;
      const target = {target!r};
      let el = null;
      if (target === 'latest-chat') {{
        const items = doc.querySelectorAll('.chat-user, .chat-ai');
        if (items.length) el = items[items.length - 1];
      }} else {{
        el = doc.getElementById(target);
      }}
      if (el) el.scrollIntoView({{behavior:'smooth', block:'center'}});
    }}, 700);
    </script>
    """, height=0)
    st.session_state.auto_scroll_target=None

prompt=st.chat_input("Ask about the available dubizzle Cars…")
if "pending_prompt" in st.session_state: prompt=st.session_state.pop("pending_prompt")
if prompt:
    st.session_state.messages.append({"role":"user","content":prompt})
    with st.spinner("Reading the provided Excel inventory…"):
        try:
            result=api.chat(st.session_state.user_id,prompt,st.session_state.session_id)
            st.session_state.session_id=result["session_id"]; st.session_state.results=result.get("matched_cars",[]); st.session_state.total_matches=result.get("total_matches",len(st.session_state.results)); st.session_state.last_memory=result.get("memory",{})
            st.session_state.messages.append({"role":"assistant","content":result["response"]})
        except Exception as e: st.session_state.messages.append({"role":"assistant","content":f"I couldn't reach the backend: {e}"})
    st.session_state.auto_scroll_target="latest-chat"
    st.rerun()

if st.session_state.results:
    st.markdown("<div id='match-radar' class='section-title'>Match Radar</div>", unsafe_allow_html=True)
    shown = len(st.session_state.results)
    total = st.session_state.get("total_matches", shown)
    st.caption(f"{total} verified listing(s) match the supplied Excel inventory" + (f" · showing strongest {shown}" if total > shown else ""))
    if total > shown:
        if st.button(f"Show all {total} matching listings", key="show_all_matches", use_container_width=True):
            st.session_state.pending_prompt="show all matches"
            st.session_state.auto_scroll_target=None
            st.rerun()

    compare_ids = st.multiselect(
        "Compare up to 3",
        [c["listing_id"] for c in st.session_state.results],
        format_func=lambda x: next((f"#{x} — {c['year']} {c['make'].title()} {c['model'].title()}" for c in st.session_state.results if c["listing_id"] == x), str(x)),
        max_selections=3,
    )
    if compare_ids:
        st.markdown("#### Side-by-side")
        selected = [c for c in st.session_state.results if c["listing_id"] in compare_ids]
        cols = st.columns(len(selected))
        for col, c in zip(cols, selected):
            with col:
                price = f"AED {c['price_aed']:,.0f}" if c.get("price_aed") is not None else "Not stated"
                monthly = f"AED {c['monthly_aed']:,.0f}" if c.get("monthly_aed") is not None else "Not stated"
                mileage = f"{c['mileage_km']:,.0f} km" if c.get("mileage_km") is not None else "Not stated"
                st.markdown(f"**#{c['listing_id']} · {c['year']} {c['make'].title()} {c['model'].title()}**")
                st.write(f"Cash price: {price}")
                st.write(f"Monthly: {monthly}")
                st.write(f"Mileage: {mileage}")
                st.write(f"Spec: {c.get('regional_spec') or 'Not stated'}")
                st.write(f"Warranty: {'Stated' if c.get('warranty') is True else 'Not stated'}")

    cards = st.columns(2)
    for idx, c in enumerate(st.session_state.results):
        with cards[idx % 2]:
            img = c.get("photo_url") or ""
            if img:
                st.image(img, use_container_width=True)

            price = f"AED {c['price_aed']:,.0f}" if c.get("price_aed") is not None else "Price not stated"
            mileage = f"{c['mileage_km']:,.0f} km" if c.get("mileage_km") is not None else "Not stated"
            monthly = f"AED {c['monthly_aed']:,.0f}" if c.get("monthly_aed") is not None else "Not stated"
            engine = f"{c['engine_l']:g} L" if c.get("engine_l") is not None else "Not stated"
            power = f"{c['horsepower']:,.0f} hp" if c.get("horsepower") is not None else "Not stated"
            tags = [c.get("regional_spec"), c.get("condition"), "Warranty stated" if c.get("warranty") is True else None, c.get("body_type")]
            tag_html = "".join(f"<span class='tag'>{html.escape(str(t))}</span>" for t in tags if t)
            st.markdown(
                f"<div class='car'><div class='car-body'>"
                f"<div class='rank'>MATCH #{idx+1} · LISTING #{c['listing_id']}</div>"
                f"<div class='car-title'>{html.escape(str(c['year']))} {html.escape(c['make'].title())} {html.escape(c['model'].title())}</div>"
                f"<div class='car-meta'>{html.escape(c.get('trim') or 'Standard')}</div>"
                f"<div class='price'>{html.escape(price)}</div>"
                f"<div>{tag_html}</div>"
                f"<div class='fact-row'>"
                f"<div class='fact'><b>Mileage</b><span>{html.escape(mileage)}</span></div>"
                f"<div class='fact'><b>Monthly</b><span>{html.escape(monthly)}</span></div>"
                f"<div class='fact'><b>Engine</b><span>{html.escape(engine)}</span></div>"
                f"<div class='fact'><b>Power</b><span>{html.escape(power)}</span></div>"
                f"</div></div></div>",
                unsafe_allow_html=True,
            )
            b1, b2 = st.columns(2)
            with b1:
                if st.button("⭐ Save", key=f"save_{c['listing_id']}", use_container_width=True):
                    api.favorite(st.session_state.user_id, c["listing_id"])
                    st.toast("Saved to your long-term shortlist.")
                    st.session_state.last_memory = api.memory(st.session_state.user_id)
                    st.rerun()
            with b2:
                if st.button("Close details ↑" if st.session_state.get("inspect_id")==c["listing_id"] else "Inspect details ↓", key=f"inspect_{c['listing_id']}", use_container_width=True):
                    st.session_state.inspect_id = None if st.session_state.get("inspect_id")==c["listing_id"] else c["listing_id"]
                    if st.session_state.inspect_id is not None:
                        st.session_state.auto_scroll_target=f"inspect-{c['listing_id']}"
                    st.rerun()

            # Details are rendered directly beneath the selected listing, not at
            # the bottom of the entire result page.
            if st.session_state.get("inspect_id") == c["listing_id"]:
                st.markdown(f"<div id='inspect-{c['listing_id']}'></div>", unsafe_allow_html=True)
                st.markdown(
                    f"<div class='evidence'><small>EXCEL EVIDENCE PANEL</small>"
                    f"<h2>{html.escape(c['title'])}</h2>"
                    f"<div>Listing #{c['listing_id']} · Facts are read from the supplied Excel title/description.</div></div>",
                    unsafe_allow_html=True,
                )
                left, right = st.columns([1, 1.2])
                with left:
                    if c.get("photo_url"):
                        st.image(c["photo_url"], use_container_width=True)
                    st.markdown("#### Extracted source facts")
                    for fact in c.get("key_facts", [])[:20]:
                        st.markdown(f"<div class='source'>{html.escape(fact)}</div>", unsafe_allow_html=True)
                with right:
                    price = f"AED {c['price_aed']:,.0f}" if c.get('price_aed') is not None else "Not stated"
                    monthly = f"AED {c['monthly_aed']:,.0f}" if c.get('monthly_aed') is not None else "Not stated"
                    mileage = f"{c['mileage_km']:,.0f} km" if c.get('mileage_km') is not None else "Not stated"
                    speed = f"{c['top_speed_mph']:,.0f} mph (~{c['top_speed_kmh']:,.0f} km/h)" if c.get('top_speed_mph') is not None else (f"{c['top_speed_kmh']:,.0f} km/h" if c.get('top_speed_kmh') is not None else "Not stated")
                    hp = f"{c['horsepower']:,.0f} hp" if c.get('horsepower') is not None else "Not stated"
                    engine = f"{c['engine_l']:g} L" if c.get('engine_l') is not None else "Not stated"
                    accel = f"{c['acceleration_0_100_s']:g} s" if c.get('acceleration_0_100_s') is not None else "Not stated"
                    fields = [
                        ("Cash price", price, c.get("price_evidence")),
                        ("Monthly payment", monthly, c.get("monthly_evidence")),
                        ("Mileage", mileage, c.get("mileage_evidence")),
                        ("Top speed", speed, c.get("speed_mph_evidence") or c.get("speed_kmh_evidence")),
                        ("Horsepower", hp, c.get("horsepower_evidence")),
                        ("Engine", engine, c.get("engine_evidence")),
                        ("0–100 km/h", accel, c.get("acceleration_evidence")),
                        ("Regional spec", c.get("regional_spec") or "Not stated", None),
                        ("Condition", c.get("condition") or "Not stated", c.get("condition_evidence")),
                        ("Warranty", "Stated" if c.get("warranty") is True else "Not stated" if c.get("warranty") is None else "No warranty stated", None),
                    ]
                    for label, value, evidence in fields:
                        st.markdown(f"**{label}:** {value}")
                        if evidence: st.caption(f"Excel evidence: {evidence}")
                    st.markdown("#### Full listing description")
                    st.write(c["description"])
