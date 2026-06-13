"""
Cybersecurity Expert System — Streamlit UI
Run: streamlit run app.py
"""

import json
import math
import networkx as nx
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from engine import (
    DIAGNOSIS_FACTS, FACT_CATEGORIES, FACT_LABELS, RULES, THRESHOLD,
    InferenceEngine, NLParser, Rule, FiredRule, cf_combine,
)

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="CyberXpert — Cybersecurity Expert System",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.stApp { background: #060612; color: #e2e8f0; }

/* Sidebar */
[data-testid="stSidebar"] {
  background: linear-gradient(175deg,#0f0f1a 0%,#0d0d20 60%,#111128 100%) !important;
  border-right: 1px solid #1e1e3a;
}
[data-testid="stSidebar"] * { color: #c7d2fe !important; }
[data-testid="stSidebar"] h1,[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 { color: #a5b4fc !important; }
[data-testid="stSidebar"] .stRadio label {
  background: rgba(99,102,241,.08) !important;
  border: 1px solid rgba(99,102,241,.2) !important;
  border-radius: 8px !important;
  padding: 0.5rem 0.9rem !important;
  font-size: 0.85rem !important;
  margin-bottom: 3px !important;
}
[data-testid="stSidebar"] .stRadio label:hover {
  background: rgba(99,102,241,.18) !important;
}

/* Main content */
h1,h2,h3 { color: #e2e8f0 !important; }
p, li, span { color: #cbd5e1; }

/* Metrics */
[data-testid="stMetric"] {
  background: #0f0f1e !important;
  border: 1px solid #1e1e3a !important;
  border-radius: 12px !important;
  padding: 1rem !important;
}
[data-testid="stMetricValue"] { color: #a5b4fc !important; font-weight: 700 !important; }
[data-testid="stMetricLabel"] { color: #64748b !important; font-size: 0.72rem !important; text-transform: uppercase; }

/* Buttons */
.stButton > button {
  background: #6366f1 !important; color: #fff !important; border: none !important;
  border-radius: 8px !important; font-weight: 600 !important;
  transition: background .15s !important;
}
.stButton > button:hover { background: #4f46e5 !important; }

/* Tabs */
.stTabs [data-baseweb="tab-list"] { background: transparent !important; gap: 4px; }
.stTabs [data-baseweb="tab"] {
  background: #0f0f1e !important; color: #94a3b8 !important;
  border: 1px solid #1e1e3a !important; border-radius: 8px !important;
}
.stTabs [aria-selected="true"] {
  background: #6366f1 !important; color: #fff !important; border-color: #6366f1 !important;
}
.stTabs [data-baseweb="tab-border"] { display: none !important; }

/* Inputs */
.stTextArea textarea, .stTextInput input {
  background: #0f0f1e !important; color: #e2e8f0 !important;
  border: 1px solid #2a2a4a !important; border-radius: 8px !important;
  font-family: 'Inter', sans-serif !important;
}
.stTextArea textarea:focus, .stTextInput input:focus {
  border-color: #6366f1 !important; box-shadow: 0 0 0 3px rgba(99,102,241,.15) !important;
}

/* Checkbox */
.stCheckbox label { color: #cbd5e1 !important; font-size: 0.85rem !important; }

/* Selectbox */
.stSelectbox > div > div {
  background: #0f0f1e !important; border-color: #2a2a4a !important; color: #e2e8f0 !important;
}

/* Progress bars */
.stProgress > div > div { background: linear-gradient(90deg, #6366f1, #ec4899) !important; }

/* Alerts */
[data-testid="stAlert"] { border-radius: 10px !important; }

/* Expander */
.streamlit-expanderHeader { color: #a5b4fc !important; }

/* Slider */
.stSlider [data-baseweb="slider"] { color: #6366f1 !important; }

/* Data editor / dataframe */
[data-testid="stDataEditor"], .dataframe {
  background: #0f0f1e !important; border: 1px solid #1e1e3a !important;
  border-radius: 10px !important; color: #e2e8f0 !important;
}
</style>
""", unsafe_allow_html=True)

# ── Session state ──────────────────────────────────────────────────────────────
def init_state():
    defaults = {
        "wm":             {},       # working memory {fact_id: cf}
        "fired":          [],       # list of FiredRule
        "conflicts":      [],       # list of ConflictEvent
        "ran":            False,
        "mode":           "Forward Chaining",
        "bc_goal":        "malware_infection",
        "bc_result":      None,
        "bc_ask":         [],
        "bc_extra":       {},
        "nl_text":        "",
        "nl_extracted":   {},
        "manual_facts":   {},
        "explanation":    "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()
engine = InferenceEngine()
parser = NLParser()

# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown(
        "<div style='padding:1rem 0 0.5rem'>"
        "<span style='font-size:1.5rem;font-weight:900;background:linear-gradient(135deg,#818cf8,#ec4899);-webkit-background-clip:text;-webkit-text-fill-color:transparent'>CyberXpert</span><br>"
        "<span style='font-size:.68rem;color:#475569;text-transform:uppercase;letter-spacing:.1em'>Cybersecurity Expert System</span>"
        "</div>", unsafe_allow_html=True,
    )
    st.markdown("---")

    st.markdown("### ⚙️ Inference Mode")
    mode = st.radio(
        "_",
        ["Forward Chaining", "Backward Chaining"],
        label_visibility="collapsed",
        index=0 if st.session_state.mode == "Forward Chaining" else 1,
    )
    st.session_state.mode = mode

    if mode == "Forward Chaining":
        st.caption("Start from observed facts → derive all possible conclusions.")
    else:
        st.caption("Pick a hypothesis → engine asks only for evidence it needs.")

    st.markdown("---")

    if mode == "Backward Chaining":
        st.markdown("### 🎯 Hypothesis")
        goal_options = {FACT_LABELS[f]: f for f in DIAGNOSIS_FACTS}
        goal_label   = st.selectbox("Investigate this threat:", list(goal_options.keys()))
        st.session_state.bc_goal = goal_options[goal_label]

    st.markdown("---")
    stats = engine.get_learning_stats()
    st.markdown("### 📊 Learning Stats")
    if stats["total"] > 0:
        acc = stats["accuracy"]
        st.metric("Feedback sessions", stats["total"])
        st.metric("Rule accuracy",     f"{acc:.0%}" if acc else "N/A")
        adj_count = len(stats["adjustments"])
        st.metric("Rules adjusted",    adj_count)
    else:
        st.caption("No feedback recorded yet. Run the system and submit feedback to start learning.")

    st.markdown("---")
    st.markdown("### 🧠 Knowledge Base")
    st.metric("Rules loaded", len(RULES))
    obs_count = sum(1 for c in FACT_CATEGORIES.values() if c == "observable")
    st.metric("Observable facts", obs_count)
    st.metric("Threat categories", len(DIAGNOSIS_FACTS))

# ══════════════════════════════════════════════════════════════════════════════
# MAIN CONTENT
# ══════════════════════════════════════════════════════════════════════════════
st.title("🛡️ CyberXpert — Cybersecurity Threat Diagnosis")
st.caption(
    "A hybrid expert system combining symbolic reasoning with natural-language input. "
    "Certainty factors (MYCIN-style) model uncertainty across the full inference chain."
)

tab_input, tab_results, tab_graph, tab_explain, tab_kb, tab_learn = st.tabs([
    "🔍 Input", "📊 Results", "🕸️ Reasoning Graph", "💬 Explanation", "📚 Knowledge Base", "🎓 Learning"
])

# ═══════════════════════════════════════════════════════════════
# TAB 1 — INPUT
# ═══════════════════════════════════════════════════════════════
with tab_input:
    col_nl, col_manual = st.columns([1, 1], gap="large")

    with col_nl:
        st.subheader("💬 Natural Language Input")
        st.markdown(
            "Describe what you are observing on the system in plain English. "
            "The parser will extract relevant indicators and confidence scores automatically."
        )
        nl_text = st.text_area(
            "Describe the incident:",
            height=180,
            placeholder=(
                "e.g. We noticed unusual network traffic going out to unknown IPs, "
                "and several system files were modified without authorisation. "
                "There are also multiple failed login attempts in the logs..."
            ),
            key="nl_textarea",
        )

        if st.button("🔎 Extract Indicators", use_container_width=True):
            extracted = parser.parse(nl_text)
            st.session_state.nl_extracted = extracted
            st.session_state.nl_text = nl_text
            if extracted:
                st.success(f"Extracted **{len(extracted)}** indicator(s) from your description.")
                expl = parser.explain_extraction(nl_text)
                for fact_id, trigger, cf in expl:
                    st.markdown(
                        f"- **{FACT_LABELS.get(fact_id, fact_id)}** — {trigger} "
                        f"(CF: {cf:.0%})",
                        unsafe_allow_html=True,
                    )
            else:
                st.warning("No specific indicators detected. Try adding more detail or use the manual checklist.")

    with col_manual:
        st.subheader("☑️ Manual Indicator Checklist")
        st.markdown("Tick the symptoms you've observed and set your confidence level:")

        observables = {k: v for k, v in FACT_LABELS.items() if FACT_CATEGORIES[k] == "observable"}
        manual_facts: dict[str, float] = {}
        for fact_id, label in observables.items():
            c1, c2 = st.columns([3, 2])
            with c1:
                checked = st.checkbox(label, key=f"chk_{fact_id}")
            with c2:
                if checked:
                    cf_val = st.slider("CF", 0.3, 1.0, 0.8, 0.05, key=f"cf_{fact_id}", label_visibility="collapsed")
                    manual_facts[fact_id] = round(cf_val, 2)
        st.session_state.manual_facts = manual_facts

    st.markdown("---")

    # Backward chaining extra inputs
    if st.session_state.mode == "Backward Chaining" and st.session_state.bc_ask:
        st.subheader("❓ Additional Evidence Needed")
        st.markdown(
            f"To evaluate **{FACT_LABELS.get(st.session_state.bc_goal)}**, "
            "the engine needs the following indicators:"
        )
        bc_extra: dict[str, float] = {}
        for fact_id in st.session_state.bc_ask:
            c1, c2 = st.columns([4, 2])
            with c1:
                present = st.checkbox(f"{FACT_LABELS.get(fact_id, fact_id)} present?", key=f"bc_{fact_id}")
            with c2:
                if present:
                    cf_val = st.slider("CF", 0.3, 1.0, 0.75, 0.05, key=f"bccf_{fact_id}", label_visibility="collapsed")
                    bc_extra[fact_id] = round(cf_val, 2)
        st.session_state.bc_extra = bc_extra

    # Merge all evidence
    merged_wm: dict[str, float] = {}
    for fid, cf in st.session_state.nl_extracted.items():
        merged_wm[fid] = cf_combine(merged_wm.get(fid, 0.0), cf)
    for fid, cf in st.session_state.manual_facts.items():
        merged_wm[fid] = cf_combine(merged_wm.get(fid, 0.0), cf)

    total_indicators = len(merged_wm)
    st.info(f"**{total_indicators}** indicator(s) in working memory. Click **Run Inference** to analyse.")

    run_btn = st.button("⚡ Run Inference", type="primary", use_container_width=True)

    if run_btn:
        if total_indicators == 0 and not st.session_state.bc_extra:
            st.error("Please provide at least one indicator via the natural-language input or checklist.")
        else:
            all_wm = dict(merged_wm)
            all_wm.update(st.session_state.bc_extra)

            if st.session_state.mode == "Forward Chaining":
                final_wm, fired, conflicts = engine.forward_chain(all_wm)
                st.session_state.wm        = final_wm
                st.session_state.fired     = fired
                st.session_state.conflicts = conflicts
                st.session_state.bc_ask    = []
                explanation = engine.explain(final_wm, fired, conflicts)
                st.session_state.explanation = explanation

            else:  # Backward chaining
                goal = st.session_state.bc_goal
                bc_cf, fired, to_ask = engine.backward_chain(goal, all_wm)
                if to_ask and not st.session_state.bc_extra:
                    st.session_state.bc_ask = list(set(to_ask))
                    st.warning(f"Engine needs more evidence ({len(st.session_state.bc_ask)} indicator(s)). See above.")
                    st.rerun()
                else:
                    final_wm = dict(all_wm)
                    final_wm[goal] = bc_cf
                    st.session_state.wm        = final_wm
                    st.session_state.fired     = fired
                    st.session_state.conflicts = []
                    explanation = engine.explain(final_wm, fired, [])
                    st.session_state.explanation = explanation

            st.session_state.ran = True
            st.success("Inference complete. See the **Results** tab.")

# ═══════════════════════════════════════════════════════════════
# TAB 2 — RESULTS
# ═══════════════════════════════════════════════════════════════
with tab_results:
    if not st.session_state.ran:
        st.info("Run the inference engine from the **Input** tab first.")
    else:
        wm      = st.session_state.wm
        fired   = st.session_state.fired
        conflicts = st.session_state.conflicts

        # ── KPI row ───────────────────────────────────────────────────────────
        diagnoses = [(f, wm[f]) for f in DIAGNOSIS_FACTS if wm.get(f, 0) >= THRESHOLD]
        diagnoses.sort(key=lambda x: x[1], reverse=True)
        obs_found = sum(1 for f, c in FACT_CATEGORIES.items() if c == "observable" and wm.get(f, 0) >= THRESHOLD)

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Threats identified", len(diagnoses))
        k2.metric("Rules fired",        len(fired))
        k3.metric("Conflicts resolved", len(conflicts))
        k4.metric("Indicators used",    obs_found)

        # ── Threat findings ───────────────────────────────────────────────────
        st.markdown("---")
        st.subheader("🚨 Threat Assessment")

        if not diagnoses:
            st.success("No threats reached the confidence threshold. The evidence does not point to a known attack pattern.")
        else:
            severity_color = {0.80: "🔴", 0.60: "🟠", 0.40: "🟡", 0.0: "🟢"}

            for fact_id, cf in diagnoses:
                sev = next(e for t, e in sorted(severity_color.items(), reverse=True) if cf >= t)
                label = FACT_LABELS[fact_id]
                with st.expander(f"{sev} **{label}** — Confidence: {cf:.0%}", expanded=(fact_id == diagnoses[0][0])):
                    st.progress(cf, text=f"Certainty factor: {cf:.3f}")

                    # Contributing rules
                    contrib = [fr for fr in fired if fr.rule.conclusion == fact_id]
                    if contrib:
                        st.markdown("**Contributing rules:**")
                        for fr in contrib:
                            ants = ", ".join(f"`{FACT_LABELS.get(a,a)}` ({fr.antecedent_cfs.get(a,0):.0%})" for a in fr.rule.antecedents)
                            st.markdown(f"- **{fr.rule.id}** · {fr.rule.label}  →  CF contributed: **{fr.conclusion_cf:.0%}**")
                            st.caption(f"  Antecedents: {ants}")

                    # Feedback widget
                    st.markdown("**Was this diagnosis correct?**")
                    fb_col1, fb_col2, _ = st.columns([1, 1, 4])
                    if fb_col1.button("👍 Correct", key=f"ok_{fact_id}"):
                        engine.record_feedback(fact_id, True)
                        st.success("Feedback saved. Rule confidence updated.")
                    if fb_col2.button("👎 Wrong",   key=f"no_{fact_id}"):
                        engine.record_feedback(fact_id, False)
                        st.warning("Feedback saved. Rule confidence reduced.")

        # ── Intermediate facts ────────────────────────────────────────────────
        intermediate = [(f, wm[f]) for f, c in FACT_CATEGORIES.items()
                        if c == "intermediate" and wm.get(f, 0) >= THRESHOLD]
        if intermediate:
            st.markdown("---")
            st.subheader("🔗 Intermediate Conclusions")
            for fact_id, cf in intermediate:
                st.markdown(f"- **{FACT_LABELS[fact_id]}** — CF: {cf:.0%}")

        # ── Conflict resolution ───────────────────────────────────────────────
        if conflicts:
            st.markdown("---")
            st.subheader("⚔️ Conflict Resolution")
            for ce in conflicts:
                st.markdown(
                    f"**Conflict** for conclusion '{FACT_LABELS.get(ce.conclusion, ce.conclusion)}'  \n"
                    f"Rule **{ce.rule_a.id}** vs Rule **{ce.rule_b.id}**  \n"
                    f"✅ Winner: Rule **{ce.winner.id}** — reason: *{ce.reason}*"
                )

        # ── Full working memory ───────────────────────────────────────────────
        with st.expander("🗃️ Full Working Memory"):
            wm_data = [
                {
                    "Fact": FACT_LABELS.get(k, k),
                    "Category": FACT_CATEGORIES.get(k, "derived"),
                    "Certainty Factor": f"{v:.3f}",
                    "Confidence %": f"{v:.0%}",
                }
                for k, v in sorted(wm.items(), key=lambda x: x[1], reverse=True)
                if v >= THRESHOLD
            ]
            if wm_data:
                st.dataframe(pd.DataFrame(wm_data), use_container_width=True, hide_index=True)

# ═══════════════════════════════════════════════════════════════
# TAB 3 — REASONING GRAPH
# ═══════════════════════════════════════════════════════════════
with tab_graph:
    if not st.session_state.ran or not st.session_state.fired:
        st.info("Run the inference engine to generate a reasoning graph.")
    else:
        st.subheader("🕸️ Reasoning Path Visualisation")
        st.caption(
            "Nodes = facts and conclusions · Edges = inference rules · "
            "Purple = diagnosis · Green = observable · Blue = intermediate · "
            "Brighter nodes = higher confidence."
        )
        wm    = st.session_state.wm
        fired = st.session_state.fired

        # ── Build graph ───────────────────────────────────────────────────────
        G     = nx.DiGraph()
        nodes_in_path: set[str] = set()

        for fr in fired:
            for a in fr.rule.antecedents:
                G.add_edge(a, fr.rule.conclusion, label=fr.rule.id, cf=fr.conclusion_cf)
                nodes_in_path.update([a, fr.rule.conclusion])

        # Hierarchical layout: layer by category
        layer_map = {"observable": 0, "intermediate": 1, "diagnosis": 2}
        by_layer: dict[int, list[str]] = {0: [], 1: [], 2: []}
        for n in G.nodes():
            layer = layer_map.get(FACT_CATEGORIES.get(n, "observable"), 2)
            by_layer[layer].append(n)

        pos: dict[str, tuple[float, float]] = {}
        for layer, nodes_l in by_layer.items():
            x = layer * 3.0
            for i, nd in enumerate(nodes_l):
                y = (i - len(nodes_l) / 2) * 1.6
                pos[nd] = (x, y)

        # ── Plotly traces ─────────────────────────────────────────────────────
        edge_x, edge_y, edge_labels = [], [], []
        for u, v, data in G.edges(data=True):
            x0, y0 = pos[u]
            x1, y1 = pos[v]
            edge_x += [x0, x1, None]
            edge_y += [y0, y1, None]

        edge_trace = go.Scatter(
            x=edge_x, y=edge_y, mode="lines",
            line=dict(width=1.5, color="#4f46e5"),
            hoverinfo="none", opacity=0.6,
        )

        cat_colors = {"observable": "#22c55e", "intermediate": "#60a5fa", "diagnosis": "#a78bfa"}
        active_diagnoses = {f for f, c in FACT_CATEGORIES.items() if c == "diagnosis" and wm.get(f, 0) >= THRESHOLD}

        node_x, node_y, node_text, node_color, node_size = [], [], [], [], []
        for nd in G.nodes():
            x, y = pos[nd]
            node_x.append(x); node_y.append(y)
            cat   = FACT_CATEGORIES.get(nd, "observable")
            cf    = wm.get(nd, 0.0)
            label = FACT_LABELS.get(nd, nd)
            node_text.append(f"<b>{label}</b><br>CF: {cf:.0%}<br>Category: {cat}")
            if nd in active_diagnoses:
                node_color.append("#ec4899")   # hot pink for confirmed diagnoses
            else:
                node_color.append(cat_colors.get(cat, "#94a3b8"))
            node_size.append(max(18, int(cf * 40) + 18))

        node_trace = go.Scatter(
            x=node_x, y=node_y, mode="markers+text",
            marker=dict(size=node_size, color=node_color,
                        line=dict(width=2, color="#1e1e3a")),
            text=[FACT_LABELS.get(n, n).replace(" ","\n") for n in G.nodes()],
            textposition="top center",
            textfont=dict(size=10, color="#e2e8f0"),
            hovertext=node_text,
            hoverinfo="text",
        )

        fig = go.Figure(
            data=[edge_trace, node_trace],
            layout=go.Layout(
                showlegend=False,
                hovermode="closest",
                margin=dict(b=20, l=5, r=5, t=40),
                height=540,
                plot_bgcolor="#060612",
                paper_bgcolor="#060612",
                xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                font=dict(family="Inter, sans-serif", color="#e2e8f0"),
                title=dict(
                    text="Inference Reasoning Graph",
                    font=dict(size=15, color="#a5b4fc"),
                    x=0.01,
                ),
                annotations=[
                    dict(x=0, y=-0.08, xref="paper", yref="paper",
                         text="🟢 Observable  🔵 Intermediate  🟣 Diagnosis  🩷 Confirmed threat",
                         showarrow=False, font=dict(size=11, color="#64748b")),
                ],
            ),
        )

        st.plotly_chart(fig, use_container_width=True)

        # ── Inference trace (step-by-step) ────────────────────────────────────
        with st.expander("📋 Step-by-step Inference Trace"):
            for i, fr in enumerate(fired, 1):
                ants = " ∧ ".join(f"{FACT_LABELS.get(a,a)} ({fr.antecedent_cfs.get(a,0):.0%})" for a in fr.rule.antecedents)
                conc = FACT_LABELS.get(fr.rule.conclusion, fr.rule.conclusion)
                st.markdown(
                    f"**Step {i}** · Rule `{fr.rule.id}` (priority {fr.rule.priority}, CF {fr.rule.cf:.0%})  \n"
                    f"IF {ants}  \n"
                    f"→ **{conc}** with CF **{fr.conclusion_cf:.0%}**"
                )
                st.markdown("---")

# ═══════════════════════════════════════════════════════════════
# TAB 4 — EXPLANATION
# ═══════════════════════════════════════════════════════════════
with tab_explain:
    if not st.session_state.ran:
        st.info("Run the inference engine to generate an explanation.")
    else:
        st.subheader("💬 Natural-Language Reasoning Explanation")
        st.markdown(st.session_state.explanation or "_No explanation generated._")

        wm = st.session_state.wm
        diagnoses = [(f, wm[f]) for f in DIAGNOSIS_FACTS if wm.get(f, 0) >= THRESHOLD]
        if diagnoses:
            st.markdown("---")
            st.subheader("📈 Confidence Summary")
            summary_data = [
                {"Threat": FACT_LABELS[f], "Certainty Factor": round(c, 3), "Confidence": f"{c:.0%}"}
                for f, c in sorted(diagnoses, key=lambda x: x[1], reverse=True)
            ]
            df_sum = pd.DataFrame(summary_data)
            st.dataframe(df_sum, use_container_width=True, hide_index=True)

            # Bar chart
            fig_bar = go.Figure(go.Bar(
                x=[r["Confidence"] for r in summary_data],
                y=[r["Threat"]     for r in summary_data],
                orientation="h",
                marker_color=["#ec4899" if i == 0 else "#6366f1" for i in range(len(summary_data))],
                text=[r["Confidence"] for r in summary_data],
                textposition="outside",
                textfont=dict(color="#e2e8f0"),
            ))
            fig_bar.update_layout(
                plot_bgcolor="#060612", paper_bgcolor="#060612",
                xaxis=dict(range=[0, 1.1], tickformat=".0%", color="#94a3b8", gridcolor="#1e1e3a"),
                yaxis=dict(color="#94a3b8"),
                height=max(200, len(summary_data) * 52),
                margin=dict(l=10, r=60, t=20, b=20),
                font=dict(color="#e2e8f0"),
            )
            st.plotly_chart(fig_bar, use_container_width=True)

# ═══════════════════════════════════════════════════════════════
# TAB 5 — KNOWLEDGE BASE
# ═══════════════════════════════════════════════════════════════
with tab_kb:
    st.subheader("📚 Rule Knowledge Base")
    st.markdown(
        f"**{len(RULES)} rules** across **{len(DIAGNOSIS_FACTS)} threat categories**. "
        "Rules are sorted by priority then specificity during conflict resolution."
    )

    search_q = st.text_input("🔍 Filter rules:", placeholder="e.g. malware, APT, R07…")
    cat_filter = st.selectbox("Filter by conclusion:", ["All threats"] + [FACT_LABELS[f] for f in DIAGNOSIS_FACTS])

    filtered_rules = RULES
    if search_q:
        q = search_q.lower()
        filtered_rules = [r for r in filtered_rules if q in r.id.lower() or q in r.label.lower() or q in r.conclusion.lower()]
    if cat_filter != "All threats":
        target = next(f for f in DIAGNOSIS_FACTS if FACT_LABELS[f] == cat_filter)
        filtered_rules = [r for r in filtered_rules if r.conclusion == target]

    learn_stats = engine.get_learning_stats()
    adj = learn_stats.get("adjustments", {})

    rows = []
    for r in sorted(filtered_rules, key=lambda x: (x.priority, x.specificity), reverse=True):
        cf_display = f"{r.cf:.3f}"
        if r.id in adj:
            cf_display += f" (Δ {adj[r.id]:+.3f})"
        rows.append({
            "ID":           r.id,
            "Label":        r.label,
            "Antecedents":  " ∧ ".join(FACT_LABELS.get(a, a) for a in r.antecedents),
            "Conclusion":   FACT_LABELS.get(r.conclusion, r.conclusion),
            "CF":           cf_display,
            "Priority":     r.priority,
            "Specificity":  r.specificity,
        })

    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("No rules match the filter.")

    st.markdown("---")
    st.subheader("🗂️ Observable Facts")
    obs_rows = [
        {"ID": fid, "Label": FACT_LABELS[fid], "Category": FACT_CATEGORIES[fid]}
        for fid in FACT_LABELS if FACT_CATEGORIES.get(fid) == "observable"
    ]
    st.dataframe(pd.DataFrame(obs_rows), use_container_width=True, hide_index=True)

# ═══════════════════════════════════════════════════════════════
# TAB 6 — LEARNING
# ═══════════════════════════════════════════════════════════════
with tab_learn:
    st.subheader("🎓 Self-Improving Rule Base")
    st.markdown(
        "Every time you submit feedback (👍 / 👎) on a diagnosis, the certainty factors of the "
        "contributing rules are adjusted. Rules that frequently lead to correct diagnoses are "
        "reinforced; incorrect ones are down-weighted. This is a simple form of **neuro-symbolic** "
        "reinforcement — symbolic rules adapt from empirical feedback."
    )

    stats = engine.get_learning_stats()
    if stats["total"] == 0:
        st.info("No feedback recorded yet. Run the system, review results, and submit feedback in the **Results** tab.")
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("Total feedback sessions", stats["total"])
        acc = stats["accuracy"]
        c2.metric("Overall accuracy", f"{acc:.0%}" if acc is not None else "—")
        c3.metric("Rules with adjustments", len(stats["adjustments"]))

        if stats["adjustments"]:
            st.markdown("### Rule Adjustments")
            adj_rows = []
            for rule_id, delta in stats["adjustments"].items():
                r = next((x for x in RULES if x.id == rule_id), None)
                if r:
                    adj_rows.append({
                        "Rule": rule_id,
                        "Description": r.label,
                        "Current CF": f"{r.cf:.3f}",
                        "Total adjustment": f"{delta:+.3f}",
                        "Direction": "⬆ Reinforced" if delta > 0 else "⬇ Down-weighted",
                    })
            if adj_rows:
                st.dataframe(pd.DataFrame(adj_rows), use_container_width=True, hide_index=True)

        st.markdown("---")
        st.markdown("### Architectural Note")
        st.markdown(
            "This feedback loop implements a lightweight version of **neuro-symbolic learning**: "
            "the symbolic rule engine provides full **transparency** (every inference step is "
            "explainable), while the feedback mechanism provides **adaptability** "
            "(the system improves from experience). This mirrors the direction of current "
            "AI research — combining the interpretability of expert systems with the "
            "learning capability of neural models."
        )
