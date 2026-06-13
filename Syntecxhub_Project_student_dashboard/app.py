"""
Student Performance Dashboard
Run: streamlit run app.py
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ── Config ─────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Student Performance Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

DATA_PATH   = Path("data/students.csv")
SUBJECTS    = ["Math", "Science", "English", "History", "PE"]
PASS_MARK   = 50
GRADE_BANDS = [(90,"A+"), (80,"A"), (70,"B"), (60,"C"), (50,"D"), (0,"F")]
COLORS      = ["#2563eb","#3b82f6","#60a5fa","#93c5fd","#1d4ed8","#1e40af"]

# ── CSS injection ──────────────────────────────────────────────────────────────
def inject_css() -> None:
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    /* ── Base font ──────────────────────────────────── */
    html, body, p, span, div, label, input, select, textarea, button {
        font-family: 'Inter', sans-serif !important;
    }

    /* ── App background ─────────────────────────────── */
    .stApp { background: #f0f5ff; }

    /* ── Main content text ──────────────────────────── */
    .stApp p, .stApp span, .stApp li, .stApp div {
        color: #1e293b;
    }

    /* ── Inline code — override dark terminal style ──── */
    .stMarkdown code, .stText code, p code {
        background: #dbeafe !important;
        color: #1e40af !important;
        border: 1px solid #bfdbfe !important;
        border-radius: 5px !important;
        padding: 1px 6px !important;
        font-size: 0.82em !important;
        font-family: 'JetBrains Mono', 'Fira Code', monospace !important;
        font-weight: 500 !important;
    }

    /* ── Column badge used in upload description ─────── */
    .col-badge {
        display: inline-block;
        background: #dbeafe;
        color: #1e40af;
        border: 1px solid #bfdbfe;
        border-radius: 5px;
        padding: 1px 7px;
        font-size: 0.82em;
        font-family: 'JetBrains Mono', 'Fira Code', monospace;
        font-weight: 600;
        margin: 0 1px;
    }

    /* ── Sidebar ────────────────────────────────────── */
    [data-testid="stSidebar"] {
        background: linear-gradient(175deg, #1e3a8a 0%, #1e40af 55%, #2563eb 100%) !important;
        border-right: 1px solid #1d4ed8;
    }
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] div,
    [data-testid="stSidebar"] label { color: #e0eaff !important; }
    [data-testid="stSidebar"] .stRadio > label { display: none; }
    [data-testid="stSidebar"] .stRadio div[role="radiogroup"] {
        gap: 4px; display: flex; flex-direction: column;
    }
    [data-testid="stSidebar"] .stRadio label {
        background: rgba(255,255,255,0.06) !important;
        border: 1px solid rgba(255,255,255,0.1) !important;
        border-radius: 8px !important;
        padding: 0.55rem 1rem !important;
        font-size: 0.88rem !important;
        font-weight: 500 !important;
        transition: all 0.15s;
        cursor: pointer;
    }
    [data-testid="stSidebar"] .stRadio label:hover {
        background: rgba(255,255,255,0.15) !important;
    }
    [data-testid="stSidebar"] h3 {
        color: #bfdbfe !important; font-size: 0.7rem !important;
        text-transform: uppercase; letter-spacing: 0.1em; margin: 1rem 0 0.3rem;
    }
    [data-testid="stSidebar"] .stSelectbox label,
    [data-testid="stSidebar"] .stMultiSelect label {
        color: #93c5fd !important; font-size: 0.75rem !important;
        text-transform: uppercase; letter-spacing: 0.06em;
    }

    /* ── Page headings ──────────────────────────────── */
    h1 { color: #1e3a8a !important; font-weight: 700 !important; font-size: 1.75rem !important; }
    h2 { color: #1e40af !important; font-weight: 600 !important; }
    h3 { color: #2563eb !important; font-weight: 600 !important; }

    /* ── Metric cards ───────────────────────────────── */
    [data-testid="stMetric"] {
        background: #fff !important; border: 1px solid #dbeafe;
        border-radius: 14px; padding: 1.1rem 1.25rem;
        box-shadow: 0 2px 10px rgba(37,99,235,0.07);
    }
    [data-testid="stMetricLabel"] { color: #64748b !important; font-size: 0.75rem !important;
        text-transform: uppercase; letter-spacing: 0.05em; }
    [data-testid="stMetricValue"] { color: #1e3a8a !important; font-size: 1.8rem !important; font-weight: 700 !important; }
    [data-testid="stMetricDelta"] { font-size: 0.73rem !important; }

    /* ── Buttons ────────────────────────────────────── */
    .stButton > button {
        background: #2563eb !important; color: #fff !important;
        border: 1px solid #2563eb !important;
        border-radius: 8px !important; padding: 0.5rem 1.3rem;
        font-weight: 500 !important; font-size: 0.875rem !important;
        transition: background 0.2s, transform 0.1s;
    }
    .stButton > button:hover { background: #1d4ed8 !important; border-color: #1d4ed8 !important; transform: translateY(-1px); }
    .stButton > button:active { transform: translateY(0); }

    /* Secondary buttons (kind="secondary") */
    .stButton > button[kind="secondary"],
    .stButton > button[data-testid="baseButton-secondary"] {
        background: #fff !important; color: #2563eb !important;
        border: 1px solid #93c5fd !important;
    }
    .stButton > button[kind="secondary"]:hover,
    .stButton > button[data-testid="baseButton-secondary"]:hover {
        background: #eff6ff !important; border-color: #2563eb !important;
    }

    /* ── Download button ─────────────────────────────── */
    .stDownloadButton > button {
        background: #fff !important; color: #2563eb !important;
        border: 1px solid #93c5fd !important;
        border-radius: 8px !important; padding: 0.5rem 1.3rem;
        font-weight: 500 !important;
        transition: background 0.2s;
    }
    .stDownloadButton > button:hover {
        background: #eff6ff !important; border-color: #2563eb !important;
    }

    /* ── Tabs ───────────────────────────────────────── */
    .stTabs [data-baseweb="tab-list"] { gap: 6px; background: transparent !important; border: none !important; }
    .stTabs [data-baseweb="tab"] {
        background: #fff !important; border: 1px solid #dbeafe !important;
        border-radius: 8px !important; color: #2563eb !important;
        padding: 0.4rem 1rem !important; font-size: 0.875rem !important;
    }
    .stTabs [aria-selected="true"] {
        background: #2563eb !important; color: #fff !important;
        border-color: #2563eb !important;
    }
    .stTabs [data-baseweb="tab-border"] { display: none !important; }

    /* ── Upload dropzone ────────────────────────────── */
    [data-testid="stFileUploaderDropzone"] {
        border: 2px dashed #93c5fd !important;
        border-radius: 14px !important;
        background: #eff6ff !important;
    }
    [data-testid="stFileUploaderDropzone"] span { color: #2563eb !important; }
    [data-testid="stFileUploaderDropzone"] small { color: #64748b !important; }

    /* ── Cards ──────────────────────────────────────── */
    .card {
        background: #fff; border: 1px solid #dbeafe;
        border-radius: 14px; padding: 1.5rem;
        box-shadow: 0 2px 12px rgba(37,99,235,0.06);
        margin-bottom: 1rem;
    }

    /* ── Insight boxes ──────────────────────────────── */
    .insight {
        background: linear-gradient(135deg, #eff6ff, #dbeafe);
        border-left: 4px solid #2563eb;
        border-radius: 0 10px 10px 0;
        padding: 0.9rem 1.2rem;
        margin: 0.5rem 0;
        color: #1e3a8a !important;
        font-size: 0.875rem;
        line-height: 1.65;
    }
    .insight-warn {
        background: linear-gradient(135deg, #fff7ed, #fed7aa) !important;
        border-left: 4px solid #f97316 !important;
        color: #7c2d12 !important;
    }
    .insight-ok {
        background: linear-gradient(135deg, #f0fdf4, #bbf7d0) !important;
        border-left: 4px solid #16a34a !important;
        color: #14532d !important;
    }

    /* ── Divider ─────────────────────────────────────── */
    hr { border-color: #dbeafe !important; margin: 1rem 0; }

    /* ── Alerts ──────────────────────────────────────── */
    [data-testid="stAlert"] { border-radius: 10px !important; }
    [data-testid="stAlert"] p { color: inherit !important; }

    /* ── Info box ────────────────────────────────────── */
    [data-testid="stInfo"] { background: #eff6ff !important; border-color: #93c5fd !important; }
    [data-testid="stInfo"] p { color: #1e40af !important; }

    /* ── Data editor ─────────────────────────────────── */
    [data-testid="stDataEditor"] {
        border-radius: 12px; overflow: hidden;
        border: 1px solid #dbeafe !important;
    }
    /* Toolbar (add/delete row icons, top-right of grid) */
    [data-testid="stDataEditor"] [class*="toolbar"],
    [data-testid="stDataEditor"] [class*="Toolbar"],
    [data-testid="stDataEditorToolbar"] {
        background: #fff !important;
        border: 1px solid #dbeafe !important;
        border-radius: 8px !important;
    }
    [data-testid="stDataEditor"] [class*="toolbar"] button,
    [data-testid="stDataEditorToolbar"] button {
        background: #fff !important;
        color: #2563eb !important;
        border: 1px solid #dbeafe !important;
        border-radius: 6px !important;
    }
    [data-testid="stDataEditor"] [class*="toolbar"] button:hover,
    [data-testid="stDataEditorToolbar"] button:hover {
        background: #eff6ff !important;
    }

    /* ── Captions ────────────────────────────────────── */
    [data-testid="stCaptionContainer"] p { color: #64748b !important; }

    /* ── Input widgets ───────────────────────────────── */
    .stTextInput label, .stNumberInput label, .stSelectbox label,
    .stSlider label, .stMultiSelect label, .stRadio label,
    .stCheckbox label, .stTextArea label {
        color: #374151 !important;
        font-size: 0.875rem !important;
        font-weight: 500 !important;
    }

    /* ── Expander ────────────────────────────────────── */
    [data-testid="stExpander"] { border: 1px solid #dbeafe !important; border-radius: 10px !important; }
    [data-testid="stExpander"] summary { color: #2563eb !important; font-weight: 500 !important; }
    </style>
    """, unsafe_allow_html=True)


# ── Domain helpers ─────────────────────────────────────────────────────────────
def get_grade(score: float) -> str:
    for threshold, grade in GRADE_BANDS:
        if score >= threshold:
            return grade
    return "F"


def enrich(df: pd.DataFrame) -> pd.DataFrame:
    """Attach computed columns: Average, Grade, Pass."""
    scols = [s for s in SUBJECTS if s in df.columns]
    if scols:
        df["Average"] = df[scols].mean(axis=1).round(1)
        df["Grade"]   = df["Average"].apply(get_grade)
        df["Pass"]    = df["Average"].apply(lambda x: "Pass" if x >= PASS_MARK else "Fail")
    return df


def load_data() -> pd.DataFrame:
    if DATA_PATH.exists():
        return enrich(pd.read_csv(DATA_PATH))
    return _sample_data()


def save_data(df: pd.DataFrame) -> None:
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    keep = [c for c in df.columns if c not in ("Average", "Grade", "Pass")]
    df[keep].to_csv(DATA_PATH, index=False)


def _sample_data() -> pd.DataFrame:
    rng = np.random.default_rng(42)
    first = ["Emma","Liam","Olivia","Noah","Ava","Oliver","Sophia","Elijah",
             "Isabella","Lucas","Mia","Mason","Amelia","Logan","Harper","Ethan",
             "Evelyn","Aiden","Abigail","Carter","Emily","Sebastian","Scarlett",
             "James","Aria","Jacob","Luna","Michael","Chloe","Alexander"]
    last  = ["Smith","Johnson","Williams","Brown","Jones","Garcia","Miller","Davis",
             "Wilson","Taylor","Anderson","Thomas","Jackson","White","Harris","Martin",
             "Thompson","Moore","Young","Allen","King","Wright","Scott","Torres","Nguyen"]
    classes = ["Class A", "Class B", "Class C"]
    n = 75
    names   = [f"{rng.choice(first)} {rng.choice(last)}" for _ in range(n)]
    ids     = [f"STU{1000+i}" for i in range(n)]
    cls     = rng.choice(classes, n, p=[0.35, 0.35, 0.30])
    attend  = np.clip(rng.normal(82, 13, n), 35, 100).round(1)
    hours   = np.clip(rng.normal(6.5, 2.5, n), 1, 16).round(1)
    rows = []
    for i in range(n):
        base = 42 + 28*(attend[i]-35)/65 + 12*(hours[i]-1)/15
        marks = {s: int(np.clip(rng.normal(base + rng.integers(-8, 9), 13), 0, 100)) for s in SUBJECTS}
        rows.append({"StudentID": ids[i], "Name": names[i], "Class": cls[i],
                     "Attendance": attend[i], "StudyHours": hours[i], **marks})
    return enrich(pd.DataFrame(rows))


# ── Chart theme ────────────────────────────────────────────────────────────────
_LAYOUT = dict(
    font_family="Inter, sans-serif",
    plot_bgcolor="#fff",
    paper_bgcolor="#fff",
    margin=dict(l=10, r=10, t=44, b=10),
    title_font_size=14,
    title_font_color="#1e3a8a",
)


# ── Sidebar + filters ──────────────────────────────────────────────────────────
def render_sidebar(df: pd.DataFrame):
    with st.sidebar:
        st.markdown(
            "<div style='text-align:center;padding:1rem 0 0.5rem'>"
            "<span style='font-size:2rem'>📊</span>"
            "<p style='font-weight:700;font-size:1.05rem;color:#fff;margin:0.25rem 0 0'>Student Dashboard</p>"
            "<p style='font-size:0.72rem;color:#93c5fd;margin:0'>Performance Analytics</p>"
            "</div>",
            unsafe_allow_html=True,
        )
        st.markdown("---")
        st.markdown("### Navigation")
        page = st.radio(
            "_",
            ["🏠  Dashboard", "📤  Upload Data", "✏️  Manual Entry",
             "📋  Data Table", "📈  Analysis & Insights"],
            label_visibility="collapsed",
        )
        st.markdown("---")
        st.markdown("### Filters")
        classes    = ["All"] + sorted(df["Class"].unique().tolist())
        sel_class  = st.selectbox("Class / Group", classes, key="f_class")
        sel_grade  = st.selectbox("Grade", ["All"] + ["A+","A","B","C","D","F"], key="f_grade")
        att_range  = st.slider("Attendance range (%)", 0, 100, (0, 100), key="f_att")
        st.markdown("---")
        n_filtered = len(_apply(df, sel_class, sel_grade, att_range))
        st.markdown(
            f"<div style='font-size:0.75rem;color:#93c5fd;text-align:center'>"
            f"<b style='color:#fff'>{n_filtered}</b> / {len(df)} students match filters</div>",
            unsafe_allow_html=True,
        )

    return page.strip(), {"class": sel_class, "grade": sel_grade, "att": att_range}


def _apply(df: pd.DataFrame, sel_class, sel_grade, att_range) -> pd.DataFrame:
    r = df.copy()
    if sel_class != "All":          r = r[r["Class"] == sel_class]
    if sel_grade != "All" and "Grade" in r.columns:
        r = r[r["Grade"] == sel_grade]
    if "Attendance" in r.columns:
        r = r[(r["Attendance"] >= att_range[0]) & (r["Attendance"] <= att_range[1])]
    return r


def apply_filters(df, f): return _apply(df, f["class"], f["grade"], f["att"])


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Dashboard
# ══════════════════════════════════════════════════════════════════════════════
def page_dashboard(df: pd.DataFrame, f: dict) -> None:
    fdf = apply_filters(df, f)
    st.title("📊 Dashboard")
    st.caption(
        f"Filtered view: **{f['class']}** · Grade **{f['grade']}** · "
        f"Attendance {f['att'][0]}–{f['att'][1]}%"
    )

    if fdf.empty:
        st.warning("No students match the current filters. Adjust the sidebar filters.")
        return

    # ── KPI row ───────────────────────────────────────────────────────────────
    scols = [s for s in SUBJECTS if s in fdf.columns]
    avg   = fdf["Average"].mean()   if "Average"    in fdf.columns else 0
    att   = fdf["Attendance"].mean() if "Attendance" in fdf.columns else 0
    prate = (fdf["Pass"] == "Pass").mean() * 100 if "Pass" in fdf.columns else 0
    top_c = (fdf.groupby("Class")["Average"].mean().idxmax()
             if "Class" in fdf.columns and "Average" in fdf.columns else "—")

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Total Students",    len(fdf))
    k2.metric("Avg Score",         f"{avg:.1f}%")
    k3.metric("Avg Attendance",    f"{att:.1f}%")
    k4.metric("Pass Rate",         f"{prate:.1f}%")
    k5.metric("Top Class",         top_c)
    st.markdown("<br>", unsafe_allow_html=True)

    # ── Row 1: Subject bar + grade donut ──────────────────────────────────────
    c1, c2 = st.columns([3, 2])
    with c1:
        sm = fdf[scols].mean().reset_index()
        sm.columns = ["Subject", "Avg"]
        fig = px.bar(sm, x="Avg", y="Subject", orientation="h",
                     color="Avg", color_continuous_scale=["#bfdbfe","#1d4ed8"],
                     title="Average Score by Subject", text=sm["Avg"].round(1))
        fig.update_layout(**_LAYOUT, coloraxis_showscale=False, showlegend=False,
                          yaxis=dict(categoryorder="total ascending"))
        fig.update_traces(textposition="outside", textfont_size=11)
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        gd = fdf["Grade"].value_counts().reindex(["A+","A","B","C","D","F"], fill_value=0)
        fig2 = px.pie(values=gd.values, names=gd.index, hole=0.5,
                      title="Grade Distribution",
                      color_discrete_sequence=COLORS)
        fig2.update_layout(**{**_LAYOUT, "plot_bgcolor": "#fff"},
                           legend=dict(orientation="h", y=-0.15))
        fig2.update_traces(textinfo="percent+label")
        st.plotly_chart(fig2, use_container_width=True)

    # ── Row 2: Scatter + box ──────────────────────────────────────────────────
    c3, c4 = st.columns(2)
    with c3:
        fig3 = px.scatter(fdf, x="Attendance", y="Average", color="Class",
                          trendline="ols", title="Attendance vs. Average Score",
                          color_discrete_sequence=COLORS, hover_data=["Name"])
        fig3.update_layout(**{**_LAYOUT, "plot_bgcolor": "#f8fafc"})
        st.plotly_chart(fig3, use_container_width=True)
    with c4:
        fig4 = px.box(fdf, x="Class", y="Average", color="Class", points="all",
                      title="Score Distribution by Class",
                      color_discrete_sequence=COLORS)
        fig4.update_layout(**{**_LAYOUT, "plot_bgcolor": "#f8fafc"},
                           showlegend=False)
        st.plotly_chart(fig4, use_container_width=True)

    # ── Bottom: Top 5 / bottom 5 ──────────────────────────────────────────────
    c5, c6 = st.columns(2)
    with c5:
        st.markdown("**🏆 Top 5 Students**")
        top5 = fdf.nlargest(5, "Average")[["StudentID","Name","Class","Average","Grade"]]
        st.dataframe(top5, use_container_width=True, hide_index=True)
    with c6:
        st.markdown("**⚠️ Bottom 5 Students**")
        bot5 = fdf.nsmallest(5, "Average")[["StudentID","Name","Class","Average","Grade"]]
        st.dataframe(bot5, use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Upload
# ══════════════════════════════════════════════════════════════════════════════
def page_upload(df: pd.DataFrame) -> None:
    st.title("📤 Upload Student Data")
    st.markdown(
        "Upload a <b>CSV</b>, <b>Excel (.xlsx)</b>, or <b>JSON</b> file. "
        "Required columns: "
        "<span class='col-badge'>StudentID</span> "
        "<span class='col-badge'>Name</span> "
        "<span class='col-badge'>Class</span>. "
        "Subject columns: "
        "<span class='col-badge'>Math</span> "
        "<span class='col-badge'>Science</span> "
        "<span class='col-badge'>English</span> "
        "<span class='col-badge'>History</span> "
        "<span class='col-badge'>PE</span>.",
        unsafe_allow_html=True,
    )

    uploaded = st.file_uploader(
        "Drop file here or click to browse",
        type=["csv", "xlsx", "xls", "json"],
        label_visibility="collapsed",
    )

    if not uploaded:
        st.info("No file uploaded yet.")

        with st.expander("📄 Expected column format"):
            st.code(
                "StudentID, Name, Class, Attendance, StudyHours, "
                "Math, Science, English, History, PE",
                language="text",
            )
            sample = pd.DataFrame([
                {"StudentID":"STU001","Name":"Jane Smith","Class":"Class A",
                 "Attendance":90.0,"StudyHours":8.0,
                 "Math":78,"Science":82,"English":74,"History":88,"PE":92},
                {"StudentID":"STU002","Name":"John Doe","Class":"Class B",
                 "Attendance":72.5,"StudyHours":5.0,
                 "Math":55,"Science":61,"English":49,"History":58,"PE":65},
            ])
            st.dataframe(sample, use_container_width=True, hide_index=True)
        return

    # ── Parse ──────────────────────────────────────────────────────────────────
    try:
        ext = Path(uploaded.name).suffix.lower()
        if ext == ".csv":
            new_df = pd.read_csv(uploaded)
        elif ext in (".xlsx", ".xls"):
            new_df = pd.read_excel(uploaded)
        elif ext == ".json":
            raw = json.loads(uploaded.read())
            new_df = pd.DataFrame(raw if isinstance(raw, list) else [raw])
        else:
            st.error("Unsupported file type."); return
    except Exception as exc:
        st.error(f"Failed to parse file: {exc}"); return

    # ── Validate ───────────────────────────────────────────────────────────────
    required = ["StudentID", "Name", "Class"]
    missing  = [c for c in required if c not in new_df.columns]
    if missing:
        st.error(f"❌ Missing required columns: **{', '.join(missing)}**")
        st.markdown(
            "Rename your columns to match: "
            "<span class='col-badge'>StudentID</span> "
            "<span class='col-badge'>Name</span> "
            "<span class='col-badge'>Class</span>",
            unsafe_allow_html=True,
        )
        return

    if not any(s in new_df.columns for s in SUBJECTS):
        st.warning("No subject columns detected. Scores will not be calculated.")

    # Check for malformed numeric values
    num_cols = [c for c in SUBJECTS + ["Attendance","StudyHours"] if c in new_df.columns]
    for col in num_cols:
        bad = pd.to_numeric(new_df[col], errors="coerce").isna().sum()
        if bad:
            st.warning(f"Column **{col}** has {bad} non-numeric value(s) — they will be treated as 0.")
            new_df[col] = pd.to_numeric(new_df[col], errors="coerce").fillna(0)

    new_df = enrich(new_df)

    st.success(f"✅ Parsed **{len(new_df)} rows** from `{uploaded.name}`")
    st.markdown(f"**Preview (first 10 rows):**")
    st.dataframe(new_df.head(10), use_container_width=True, hide_index=True)

    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📥 Replace existing dataset", type="primary", use_container_width=True):
            save_data(new_df)
            st.success("Dataset replaced. Reloading…")
            st.rerun()
    with col2:
        if st.button("➕ Append to existing dataset", use_container_width=True):
            combined = pd.concat([df, new_df], ignore_index=True)
            combined = combined.drop_duplicates(subset=["StudentID"], keep="last")
            save_data(combined)
            st.success(f"Appended. Dataset now has **{len(combined)}** students. Reloading…")
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Manual Entry
# ══════════════════════════════════════════════════════════════════════════════
def page_manual_entry(df: pd.DataFrame) -> None:
    st.title("✏️ Add Student Manually")

    with st.form("add_student", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            sid    = st.text_input("Student ID *",  placeholder="e.g. STU1100")
            name   = st.text_input("Full Name *",   placeholder="e.g. Jane Smith")
            cls_opts = sorted(df["Class"].unique().tolist()) + ["➕ New class…"]
            cls    = st.selectbox("Class / Group *", cls_opts)
            new_cls = ""
            if cls == "➕ New class…":
                new_cls = st.text_input("New class name")
        with col2:
            attend = st.slider("Attendance (%)", 0, 100, 85)
            hours  = st.number_input("Study Hours / week", 0.0, 20.0, 6.0, step=0.5)

        st.markdown("**Subject Marks** (0–100)")
        mcols = st.columns(len(SUBJECTS))
        marks = {s: mcols[i].number_input(s, 0, 100, 60, key=f"mark_{s}") for i, s in enumerate(SUBJECTS)}

        submitted = st.form_submit_button("➕ Add Student", type="primary", use_container_width=True)

    if submitted:
        if not sid.strip() or not name.strip():
            st.error("Student ID and Name are required."); return
        if sid.strip() in df["StudentID"].astype(str).values:
            st.error(f"ID **{sid}** already exists. Edit it in the Data Table instead."); return
        final_cls = new_cls.strip() if cls == "➕ New class…" and new_cls.strip() else cls
        row = {"StudentID": sid.strip(), "Name": name.strip(), "Class": final_cls,
               "Attendance": attend, "StudyHours": hours, **marks}
        new_df = enrich(pd.concat([df, pd.DataFrame([row])], ignore_index=True))
        save_data(new_df)
        st.success(f"✅ Added **{name}** ({sid}) to {final_cls}. Reloading…")
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Data Table
# ══════════════════════════════════════════════════════════════════════════════
def page_data_table(df: pd.DataFrame) -> None:
    st.title("📋 Data Table")

    c1, c2, c3 = st.columns([3, 1.5, 1])
    with c1:
        q = st.text_input("🔍 Search name or ID", placeholder="Type to filter…", key="dt_q")
    with c2:
        cf = st.selectbox("Class", ["All"] + sorted(df["Class"].unique().tolist()), key="dt_c")
    with c3:
        gf = st.selectbox("Grade", ["All"] + ["A+","A","B","C","D","F"], key="dt_g")

    view = df.copy()
    if q:
        view = view[
            view["Name"].str.contains(q, case=False, na=False) |
            view["StudentID"].str.contains(q, case=False, na=False)
        ]
    if cf != "All": view = view[view["Class"] == cf]
    if gf != "All" and "Grade" in view.columns: view = view[view["Grade"] == gf]

    st.caption(f"Showing **{len(view)}** of **{len(df)}** records")

    editable_cols = ["StudentID","Name","Class","Attendance","StudyHours"] + SUBJECTS
    edit_df = view[[c for c in editable_cols if c in view.columns]].copy()

    classes = sorted(df["Class"].unique().tolist())
    edited  = st.data_editor(
        edit_df,
        use_container_width=True,
        num_rows="dynamic",
        hide_index=True,
        key="main_editor",
        column_config={
            "StudentID":  st.column_config.TextColumn("ID",         width="small"),
            "Name":       st.column_config.TextColumn("Full Name",  width="medium"),
            "Class":      st.column_config.SelectboxColumn("Class", options=classes),
            "Attendance": st.column_config.NumberColumn("Attend %", min_value=0, max_value=100, format="%.1f"),
            "StudyHours": st.column_config.NumberColumn("Study hrs", min_value=0, max_value=20, format="%.1f"),
            **{s: st.column_config.NumberColumn(s, min_value=0, max_value=100) for s in SUBJECTS},
        },
    )

    cs, _, cd = st.columns([1, 4, 1])
    with cs:
        if st.button("💾 Save Changes", type="primary"):
            unchanged = df[~df["StudentID"].isin(edit_df["StudentID"])]
            merged    = enrich(pd.concat([unchanged, edited], ignore_index=True))
            save_data(merged)
            st.success("✅ Changes saved.")
            st.rerun()
    with cd:
        if st.button("🗑️ Delete Filtered", help="Delete all rows currently visible"):
            remaining = df[~df["StudentID"].isin(view["StudentID"])]
            save_data(remaining)
            st.success(f"Deleted {len(view)} rows.")
            st.rerun()

    # Download
    st.markdown("---")
    csv_bytes = df.to_csv(index=False).encode()
    st.download_button("⬇️ Download full dataset as CSV", csv_bytes, "students.csv", "text/csv")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Analysis & Insights
# ══════════════════════════════════════════════════════════════════════════════
def page_analysis(df: pd.DataFrame, f: dict) -> None:
    fdf = apply_filters(df, f)
    st.title("📈 Analysis & Insights")

    if fdf.empty:
        st.warning("No data matches the current filters."); return

    scols = [s for s in SUBJECTS if s in fdf.columns]

    tab1, tab2, tab3, tab4 = st.tabs([
        "📚 Subject Performance",
        "🏫 Class Comparison",
        "📡 Attendance & Study",
        "💡 Auto Insights",
    ])

    # ── Tab 1: Subject performance ─────────────────────────────────────────────
    with tab1:
        c1, c2 = st.columns(2)
        with c1:
            sm = fdf[scols].mean().reset_index()
            sm.columns = ["Subject","Avg"]
            sm = sm.sort_values("Avg", ascending=False)
            fig = px.bar(sm, x="Subject", y="Avg",
                         color="Avg", color_continuous_scale=["#bfdbfe","#1d4ed8"],
                         title="Average Score per Subject", text=sm["Avg"].round(1))
            fig.update_layout(**_LAYOUT, coloraxis_showscale=False)
            fig.update_traces(textposition="outside")
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            fr = {s: (fdf[s] < PASS_MARK).mean()*100 for s in scols}
            fr_df = pd.DataFrame(fr.items(), columns=["Subject","Fail Rate %"])
            fr_df = fr_df.sort_values("Fail Rate %", ascending=False)
            fig2 = px.bar(fr_df, x="Subject", y="Fail Rate %",
                          color="Fail Rate %",
                          color_continuous_scale=["#bfdbfe","#dc2626"],
                          title="Fail Rate per Subject (%)", text=fr_df["Fail Rate %"].round(1))
            fig2.update_layout(**_LAYOUT, coloraxis_showscale=False)
            fig2.update_traces(textposition="outside")
            st.plotly_chart(fig2, use_container_width=True)

        long = fdf[scols].melt(var_name="Subject", value_name="Score")
        fig3 = px.violin(long, x="Subject", y="Score", box=True, points="outliers",
                         color="Subject", color_discrete_sequence=COLORS,
                         title="Score Distribution per Subject")
        fig3.update_layout(**{**_LAYOUT, "plot_bgcolor":"#f8fafc"}, showlegend=False)
        st.plotly_chart(fig3, use_container_width=True)

    # ── Tab 2: Class comparison ────────────────────────────────────────────────
    with tab2:
        cg = fdf.groupby("Class")[scols].mean().reset_index()
        cl = cg.melt(id_vars="Class", var_name="Subject", value_name="Avg")
        fig = px.bar(cl, x="Subject", y="Avg", color="Class", barmode="group",
                     title="Average Score per Subject by Class",
                     color_discrete_sequence=COLORS)
        fig.update_layout(**_LAYOUT)
        st.plotly_chart(fig, use_container_width=True)

        c1, c2 = st.columns(2)
        with c1:
            ca = fdf.groupby("Class")["Average"].mean().reset_index()
            ca.columns = ["Class","Avg"]
            fig2 = px.bar(ca, x="Class", y="Avg", color="Class",
                          title="Overall Average by Class",
                          color_discrete_sequence=COLORS, text=ca["Avg"].round(1))
            fig2.update_layout(**_LAYOUT, showlegend=False)
            fig2.update_traces(textposition="outside")
            st.plotly_chart(fig2, use_container_width=True)
        with c2:
            pr = fdf.groupby("Class")["Pass"].apply(
                lambda x: (x=="Pass").mean()*100).reset_index()
            pr.columns = ["Class","Pass Rate %"]
            fig3 = px.bar(pr, x="Class", y="Pass Rate %", color="Class",
                          title="Pass Rate by Class (%)",
                          color_discrete_sequence=COLORS, text=pr["Pass Rate %"].round(1))
            fig3.update_layout(**_LAYOUT, showlegend=False)
            fig3.update_traces(textposition="outside")
            st.plotly_chart(fig3, use_container_width=True)

    # ── Tab 3: Attendance & Study Hours ────────────────────────────────────────
    with tab3:
        c1, c2 = st.columns(2)
        with c1:
            fig = px.scatter(fdf, x="Attendance", y="Average", color="Class",
                             trendline="ols", title="Attendance vs. Average Score",
                             color_discrete_sequence=COLORS, hover_data=["Name","StudentID"])
            fig.update_layout(**{**_LAYOUT, "plot_bgcolor":"#f8fafc"})
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            fig2 = px.scatter(fdf, x="StudyHours", y="Average", color="Class",
                              trendline="ols", title="Study Hours vs. Average Score",
                              color_discrete_sequence=COLORS, hover_data=["Name","StudentID"])
            fig2.update_layout(**{**_LAYOUT, "plot_bgcolor":"#f8fafc"})
            st.plotly_chart(fig2, use_container_width=True)

        # Attendance bracket bar
        tmp = fdf.copy()
        tmp["Bracket"] = pd.cut(tmp["Attendance"],
                                bins=[0, 60, 75, 85, 100],
                                labels=["<60%","60–75%","75–85%",">85%"])
        ba = tmp.groupby("Bracket", observed=True)["Average"].mean().reset_index()
        ba.columns = ["Attendance Bracket","Avg Score"]
        fig3 = px.bar(ba, x="Attendance Bracket", y="Avg Score",
                      color="Attendance Bracket",
                      color_discrete_sequence=["#dc2626","#f97316","#60a5fa","#2563eb"],
                      title="Average Score by Attendance Bracket",
                      text=ba["Avg Score"].round(1))
        fig3.update_layout(**_LAYOUT, showlegend=False)
        fig3.update_traces(textposition="outside")
        st.plotly_chart(fig3, use_container_width=True)

    # ── Tab 4: Auto insights ───────────────────────────────────────────────────
    with tab4:
        st.markdown("### 💡 Auto-Generated Insights")
        for html_cls, text in _insights(fdf, scols):
            st.markdown(f'<div class="insight {html_cls}">{text}</div>',
                        unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("### ⚠️ Students At Risk")
        at_risk = fdf[(fdf["Average"] < 50) | (fdf["Attendance"] < 75)]
        if at_risk.empty:
            st.success("No students flagged as at-risk for the current filter. ✅")
        else:
            st.warning(f"**{len(at_risk)}** student(s) have avg < 50% or attendance < 75%.")
            show = ["StudentID","Name","Class","Average","Attendance"] + scols[:3]
            st.dataframe(at_risk[[c for c in show if c in at_risk.columns]]
                         .sort_values("Average"), use_container_width=True, hide_index=True)


def _insights(df: pd.DataFrame, scols: list) -> list:
    out = []
    if df.empty or not scols:
        return [("", "Not enough data to generate insights.")]

    # Pass rate
    pr = (df["Pass"]=="Pass").mean()*100
    cls = "insight-ok" if pr >= 70 else "insight-warn"
    out.append((cls,
        f"📊 <b>{pr:.1f}%</b> of students are passing (average ≥ {PASS_MARK}%). "
        + ("Strong overall performance. ✅" if pr >= 70
           else "Below target — consider targeted support for struggling students.")
    ))

    # Best / worst subject
    sm   = {s: df[s].mean() for s in scols}
    best = max(sm, key=sm.get); worst = min(sm, key=sm.get)
    gap  = sm[best] - sm[worst]
    out.append(("",
        f"📚 <b>{best}</b> is the strongest subject (avg {sm[best]:.1f}%). "
        f"<b>{worst}</b> is the weakest (avg {sm[worst]:.1f}%). "
        f"Gap: <b>{gap:.1f}%</b> — {'significant, may need attention.' if gap > 15 else 'within normal range.'}"
    ))

    # Attendance correlation
    corr = df["Attendance"].corr(df["Average"])
    hi   = df[df["Attendance"] >= 90]["Average"].mean()
    lo   = df[df["Attendance"] <  75]["Average"].mean()
    diff = hi - lo
    cls  = "" if abs(corr) > 0.3 else "insight-warn"
    out.append((cls,
        f"🏫 Attendance–score correlation: <b>{corr:.2f}</b>. "
        f"Students with ≥90% attendance score <b>{diff:.1f}%</b> higher on average "
        f"than those with <75% attendance."
    ))

    # Study hours correlation
    ch = df["StudyHours"].corr(df["Average"])
    dir_ = "positive" if ch > 0 else "negative"
    strength = "strong" if abs(ch) > 0.4 else ("moderate" if abs(ch) > 0.25 else "weak")
    out.append(("",
        f"📖 Study hours show a <b>{strength} {dir_}</b> correlation with performance "
        f"(r = {ch:.2f}). "
        + ("More study time is associated with better results." if ch > 0.2
           else "Correlation is weak — study quality may matter more than hours.")
    ))

    # At-risk count
    n_risk = len(df[(df["Average"] < 50) | (df["Attendance"] < 75)])
    cls    = "insight-ok" if n_risk == 0 else "insight-warn"
    out.append((cls,
        f"⚠️ <b>{n_risk}</b> student(s) flagged at-risk (avg <50% or attendance <75%). "
        + ("No students at risk currently. ✅" if n_risk == 0
           else "See the 'Students At Risk' table below.")
    ))

    # Weakest class
    if "Class" in df.columns:
        cf = df.groupby("Class")["Pass"].apply(lambda x: (x=="Fail").mean()*100)
        wc = cf.idxmax()
        out.append(("insight-warn" if cf[wc] > 30 else "",
            f"🏆 <b>{wc}</b> has the highest fail rate ({cf[wc]:.1f}%). "
            "Additional resources or tutoring may benefit this group most."
        ))

    return out


# ══════════════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════════════
def main() -> None:
    inject_css()
    df   = load_data()
    page, filters = render_sidebar(df)

    if   page == "🏠  Dashboard":         page_dashboard(df, filters)
    elif page == "📤  Upload Data":        page_upload(df)
    elif page == "✏️  Manual Entry":       page_manual_entry(df)
    elif page == "📋  Data Table":         page_data_table(df)
    elif page == "📈  Analysis & Insights": page_analysis(df, filters)


if __name__ == "__main__":
    main()
