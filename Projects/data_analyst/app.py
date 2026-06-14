"""
DataLens — Self-Service Data Analyst
Run: streamlit run app.py
"""

import io
import json
import re
import datetime
from typing import Optional

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ══════════════════════════════════════════════════════════════════════════════
# PAGE CONFIG + THEME
# ══════════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="DataLens",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }

/* Sidebar */
[data-testid="stSidebar"] {
  background: linear-gradient(175deg,#0f0f1a 0%,#0d0d20 100%) !important;
  border-right: 1px solid #1e1e3a;
}
[data-testid="stSidebar"] * { color: #c7d2fe !important; }
[data-testid="stSidebar"] h1,[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 { color: #a5b4fc !important; }

/* Metrics */
[data-testid="stMetric"] {
  background: #0f0f1e !important;
  border: 1px solid #1e1e3a !important;
  border-radius: 10px !important;
  padding: .9rem !important;
}
[data-testid="stMetricValue"] { color: #a5b4fc !important; font-weight: 700 !important; }
[data-testid="stMetricLabel"] { color: #64748b !important; font-size: .7rem !important; text-transform: uppercase; }

/* Tabs */
.stTabs [data-baseweb="tab-list"] { background: transparent !important; gap: 3px; }
.stTabs [data-baseweb="tab"] {
  background: #0f0f1e !important; color: #94a3b8 !important;
  border: 1px solid #1e1e3a !important; border-radius: 8px !important; font-size: .85rem;
}
.stTabs [aria-selected="true"] {
  background: #6366f1 !important; color: #fff !important; border-color: #6366f1 !important;
}
.stTabs [data-baseweb="tab-border"] { display: none !important; }

/* Inputs */
.stTextInput input, .stSelectbox > div > div, .stNumberInput input {
  background: #0f0f1e !important; border-color: #2a2a4a !important; color: #e2e8f0 !important;
}
.stTextArea textarea { background: #0f0f1e !important; border-color: #2a2a4a !important; color: #e2e8f0 !important; }

/* Buttons */
.stButton > button {
  background: #6366f1 !important; color: #fff !important;
  border: none !important; border-radius: 8px !important; font-weight: 600 !important;
}
.stButton > button:hover { background: #4f46e5 !important; }
[data-testid="baseButton-secondary"] > div > button,
button[kind="secondary"] {
  background: transparent !important; color: #6366f1 !important;
  border: 1px solid #6366f1 !important;
}

/* DataFrames */
[data-testid="stDataFrame"] { border: 1px solid #1e1e3a !important; border-radius: 10px !important; }

/* Suggestion cards */
.suggestion-card {
  background: rgba(99,102,241,.08);
  border: 1px solid rgba(99,102,241,.3);
  border-radius: 10px;
  padding: .75rem 1rem;
  margin-bottom: .5rem;
}
.outlier-card {
  background: rgba(239,68,68,.07);
  border: 1px solid rgba(239,68,68,.3);
  border-radius: 10px;
  padding: .75rem 1rem;
  margin-bottom: .5rem;
}

/* History timeline */
.history-item {
  display: flex; align-items: flex-start; gap: .6rem;
  padding: .4rem 0; border-bottom: 1px solid #1e1e3a; font-size: .8rem;
}
.h-dot { width: 8px; height: 8px; border-radius: 50%; background: #6366f1;
         margin-top: .3rem; flex-shrink: 0; }
.h-dot.active { background: #22c55e; }

/* Code blocks */
code { background: #1e1e3a !important; color: #a5b4fc !important;
       padding: .15rem .4rem; border-radius: 4px; font-family: 'JetBrains Mono', monospace; }

/* Compare diff badges */
.col-only-a { background: rgba(99,102,241,.15); color: #818cf8;
              padding: .1rem .5rem; border-radius: 99px; font-size: .72rem; }
.col-only-b { background: rgba(236,72,153,.15); color: #f472b6;
              padding: .1rem .5rem; border-radius: 99px; font-size: .72rem; }
.col-both   { background: rgba(34,197,94,.12);  color: #4ade80;
              padding: .1rem .5rem; border-radius: 99px; font-size: .72rem; }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# SESSION STATE
# ══════════════════════════════════════════════════════════════════════════════

def _init():
    defaults = {
        'df':           None,       # current working DataFrame
        'df_original':  None,       # immutable copy from upload
        'filename':     '',
        'history':      [],         # [{desc, df, ts, rows}]
        'filters':      [],         # [{col, op, val, logic}]
        'suggestions':  [],         # smart type suggestions
        'df_compare':   None,       # second file for comparison tab
        'fname_compare':'',
        'audit_log':    [],         # [{ts, action, detail}]
        'n_filter_rows': 0,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init()


def _audit(action: str, detail: str = ''):
    st.session_state.audit_log.append({
        'ts':     datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'action': action,
        'detail': detail,
    })


def _push_history(desc: str):
    st.session_state.history.append({
        'desc': desc,
        'df':   st.session_state.df.copy(),
        'ts':   datetime.datetime.now().strftime('%H:%M:%S'),
        'rows': len(st.session_state.df),
    })
    _audit(desc)


def _undo():
    if len(st.session_state.history) > 1:
        st.session_state.history.pop()
        st.session_state.df = st.session_state.history[-1]['df'].copy()
        st.session_state.filters = []
        _audit('Undo')

# ══════════════════════════════════════════════════════════════════════════════
# DATA LOADING
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(show_spinner=False)
def _load(content: bytes, filename: str) -> pd.DataFrame:
    try:
        if filename.lower().endswith(('.xls', '.xlsx')):
            return pd.read_excel(io.BytesIO(content))
        return pd.read_csv(io.BytesIO(content))
    except Exception as e:
        raise ValueError(f"Could not read '{filename}': {e}")

# ══════════════════════════════════════════════════════════════════════════════
# SMART TYPE DETECTION
# ══════════════════════════════════════════════════════════════════════════════

def detect_suggestions(df: pd.DataFrame) -> list[dict]:
    suggestions = []
    for col in df.columns:
        if df[col].dtype == object:
            # Date detection: try parsing a sample
            sample = df[col].dropna().astype(str).head(100)
            try:
                parsed = pd.to_datetime(sample, infer_datetime_format=True, errors='coerce')
                rate   = parsed.notna().mean()
                if rate > 0.80:
                    suggestions.append({'kind': 'date', 'col': col,
                        'msg': f"**'{col}'** looks like a date column ({rate:.0%} parseable). Convert it?",
                        'icon': '📅'})
            except Exception:
                pass

            # Low-cardinality → categorical
            n_unique = df[col].nunique()
            n_total  = len(df)
            if 1 < n_unique <= 20 and n_total >= 30 and {'kind': 'date', 'col': col} not in suggestions:
                suggestions.append({'kind': 'cat', 'col': col,
                    'msg': f"**'{col}'** has only {n_unique} unique values — treat as category?",
                    'icon': '🏷️'})

        elif pd.api.types.is_numeric_dtype(df[col]):
            # Outlier detection via IQR
            q1, q3 = df[col].quantile([0.25, 0.75])
            iqr = q3 - q1
            if iqr > 0:
                out = df[(df[col] < q1 - 1.5 * iqr) | (df[col] > q3 + 1.5 * iqr)]
                n = len(out)
                if n > 0:
                    pct = n / len(df)
                    suggestions.append({'kind': 'outlier', 'col': col,
                        'msg': f"**'{col}'** has **{n} potential outliers** ({pct:.1%} of rows, IQR method).",
                        'icon': '⚠️', 'count': n})
    return suggestions

# ══════════════════════════════════════════════════════════════════════════════
# FILTER CHAIN
# ══════════════════════════════════════════════════════════════════════════════

OPERATORS = ['equals', '>', '<', '>=', '<=', '!=', 'contains', 'starts with',
             'ends with', 'is null', 'is not null']

def apply_filters(df: pd.DataFrame, filters: list[dict]) -> pd.DataFrame:
    mask = None
    for f in filters:
        col, op, val, logic = f['col'], f['op'], f.get('val', ''), f.get('logic', 'AND')
        try:
            if op == 'is null':
                m = df[col].isna()
            elif op == 'is not null':
                m = df[col].notna()
            elif op == 'contains':
                m = df[col].astype(str).str.contains(str(val), case=False, na=False)
            elif op == 'starts with':
                m = df[col].astype(str).str.startswith(str(val))
            elif op == 'ends with':
                m = df[col].astype(str).str.endswith(str(val))
            else:
                op_sym = {'equals': '==', '>': '>', '<': '<',
                          '>=': '>=', '<=': '<=', '!=': '!='}[op]
                try:
                    num = float(val)
                    m = df[col].apply(lambda x: eval(f"{x} {op_sym} {num}", {}, {}))
                except (ValueError, TypeError):
                    m = df[col].astype(str).apply(lambda x: eval(f'"{x}" {op_sym} "{val}"', {}, {}))
        except Exception:
            continue

        mask = m if mask is None else (mask | m if logic == 'OR' else mask & m)

    return df[mask] if mask is not None else df


def filter_code(filters: list[dict]) -> str:
    parts = []
    for f in filters:
        col, op, val, logic = f['col'], f['op'], f.get('val', ''), f.get('logic', 'AND')
        prefix = '' if not parts else f' {logic} '
        if op in ('is null', 'is not null'):
            part = f"df['{col}'].{'isna()' if 'null' in op and 'not' not in op else 'notna()'}"
        elif op == 'contains':
            part = f"df['{col}'].str.contains('{val}', case=False)"
        elif op in ('starts with', 'ends with'):
            fn = 'startswith' if 'start' in op else 'endswith'
            part = f"df['{col}'].str.{fn}('{val}')"
        else:
            sym = {'equals': '==', '>': '>', '<': '<', '>=': '>=', '<=': '<=', '!=': '!='}[op]
            part = f"df['{col}'] {sym} {val!r}"
        parts.append(prefix + part)
    return f"df[{''.join(parts)}]" if parts else 'df'

# ══════════════════════════════════════════════════════════════════════════════
# NATURAL LANGUAGE QUERY ENGINE
# ══════════════════════════════════════════════════════════════════════════════

def nl_query(query: str, df: pd.DataFrame) -> tuple[str, pd.DataFrame, str]:
    """
    Rule-based NL → pandas. Returns (code, result_df, explanation).
    No external API — pattern matching handles most real data questions.
    """
    q = query.lower().strip()
    cols = list(df.columns)
    col_map = {c.lower(): c for c in cols}
    num_cols = df.select_dtypes(include='number').columns.tolist()
    cat_cols = df.select_dtypes(exclude='number').columns.tolist()

    def find_col(hint: str) -> Optional[str]:
        hint = hint.strip()
        if hint in col_map:
            return col_map[hint]
        for cl, c in col_map.items():
            if cl in hint or hint in cl:
                return c
        return None

    # ── Aggregation: [agg] [of] X [by/per Y] ────────────────────────────────
    AGG_WORDS = r'(average|mean|sum|total|count|minimum|min|maximum|max|median|std|variance|stdev)'
    m = re.search(
        AGG_WORDS + r'\s+(?:of\s+)?([a-zA-Z_][\w ]*?)'
        r'(?:\s+(?:by|per|grouped? by|group by)\s+([a-zA-Z_][\w ]*))?$', q
    )
    if m:
        agg_word = m.group(1)
        col_h    = m.group(2).strip()
        by_h     = m.group(3).strip() if m.group(3) else None
        func = {'average':'mean','mean':'mean','sum':'sum','total':'sum','count':'count',
                'minimum':'min','min':'min','maximum':'max','max':'max','median':'median',
                'std':'std','stdev':'std','variance':'var'}[agg_word]
        col  = find_col(col_h) or (num_cols[0] if num_cols else cols[0])
        if by_h:
            by   = find_col(by_h) or (cat_cols[0] if cat_cols else cols[0])
            code = f"df.groupby('{by}')['{col}'].{func}().reset_index().sort_values('{col}', ascending=False)"
            res  = df.groupby(by)[col].agg(func).reset_index().sort_values(col, ascending=False)
            expl = f"**{func.title()}** of `{col}` grouped by `{by}`"
        else:
            val  = getattr(df[col], func)()
            code = f"df['{col}'].{func}()"
            res  = pd.DataFrame({f"{func}({col})": [round(float(val), 4)]})
            expl = f"**{func.title()}** of `{col}` = **{val:.4g}**"
        return code, res, expl

    # ── Filter: filter/show/where X [op] val ────────────────────────────────
    m = re.search(
        r'(?:filter|show|where|select|find)\s+(?:rows?\s+)?(?:where\s+)?'
        r'([a-zA-Z_][\w ]*?)\s+'
        r'(is not null|is null|>=|<=|!=|>|<|contains?|starts? with|ends? with|equals?|is|not equals?|greater than|less than)'
        r'\s*(?:"([^"]+)"|\'([^\']+)\'|(\S+))?', q
    )
    if m:
        col_h   = m.group(1).strip()
        op_raw  = m.group(2).strip()
        val_str = next((x for x in m.groups()[2:] if x), '') or ''
        col     = find_col(col_h) or (cols[0] if cols else None)
        if not col:
            raise ValueError("Column not found.")

        OP = {'is':'==','equals':'==','equal':'==','not equals':'!=','not equal':'!=',
              '>':'>','<':'<','>=':'>=','<=':'<=','!=':'!=',
              'greater than':'>','less than':'<'}

        if 'null' in op_raw and 'not' in op_raw:
            code = f"df[df['{col}'].notna()]";  res = df[df[col].notna()]
            expl = f"Rows where `{col}` is **not null** ({len(res):,} rows)"
        elif 'null' in op_raw:
            code = f"df[df['{col}'].isna()]";   res = df[df[col].isna()]
            expl = f"Rows where `{col}` is **null** ({len(res):,} rows)"
        elif 'contain' in op_raw:
            code = f"df[df['{col}'].astype(str).str.contains('{val_str}', case=False, na=False)]"
            res  = df[df[col].astype(str).str.contains(val_str, case=False, na=False)]
            expl = f"Rows where `{col}` **contains** '{val_str}' ({len(res):,} rows)"
        elif 'starts' in op_raw:
            code = f"df[df['{col}'].astype(str).str.startswith('{val_str}')]"
            res  = df[df[col].astype(str).str.startswith(val_str)]
            expl = f"Rows where `{col}` **starts with** '{val_str}' ({len(res):,} rows)"
        elif op_raw in OP and val_str:
            sym = OP[op_raw]
            try:
                num = float(val_str)
                mask = df[col].apply(lambda x: eval(f"{x}{sym}{num}", {}, {}))
                code = f"df[df['{col}'] {sym} {num}]"
            except (ValueError, TypeError):
                mask = df[col].astype(str) == val_str if sym == '==' else df[col].astype(str) != val_str
                code = f"df[df['{col}'] {sym} '{val_str}']"
            res  = df[mask]
            expl = f"Rows where `{col}` **{op_raw}** '{val_str}' ({len(res):,} rows)"
        else:
            raise ValueError(f"Unrecognised filter pattern.")
        return code, res, expl

    # ── Sort ─────────────────────────────────────────────────────────────────
    m = re.search(r'sort(?:ed)?\s+by\s+([a-zA-Z_][\w ]*?)(?:\s+(desc(?:ending)?|asc(?:ending)?))?(?:\s*$)', q)
    if m:
        col_h = m.group(1).strip(); asc_kw = m.group(2) or 'asc'
        col   = find_col(col_h) or cols[0]
        asc   = 'desc' not in asc_kw
        code  = f"df.sort_values('{col}', ascending={asc})"
        res   = df.sort_values(col, ascending=asc)
        expl  = f"Sorted by `{col}` {'ascending' if asc else 'descending'}"
        return code, res, expl

    # ── Top / Bottom N ───────────────────────────────────────────────────────
    m = re.search(r'(?:top|largest?|bottom|smallest?)\s+(\d+)(?:\s+rows?)?\s+(?:by\s+)?([a-zA-Z_][\w ]*)', q)
    if m:
        n = int(m.group(1)); col_h = m.group(2).strip()
        col = find_col(col_h) or (num_cols[0] if num_cols else cols[0])
        bottom = 'bottom' in q or 'small' in q
        code   = f"df.n{'smallest' if bottom else 'largest'}({n}, '{col}')"
        res    = df.nsmallest(n, col) if bottom else df.nlargest(n, col)
        expl   = f"**{'Bottom' if bottom else 'Top'} {n}** rows by `{col}`"
        return code, res, expl

    # ── Value counts / unique ────────────────────────────────────────────────
    m = re.search(r'(?:unique|distinct|value counts?|count by|frequency of|frequencies?)\s+(?:values?\s+(?:of|in)\s+)?([a-zA-Z_][\w ]*)', q)
    if m:
        col_h = m.group(1).strip()
        col   = find_col(col_h) or (cat_cols[0] if cat_cols else cols[0])
        res   = df[col].value_counts().reset_index()
        res.columns = [col, 'count']
        code  = f"df['{col}'].value_counts().reset_index()"
        expl  = f"Value counts for `{col}`"
        return code, res, expl

    # ── Correlation ──────────────────────────────────────────────────────────
    if any(w in q for w in ['correlation', 'corr', 'correlate', 'heatmap']):
        res   = df[num_cols].corr().round(3) if num_cols else pd.DataFrame()
        code  = "df.select_dtypes('number').corr().round(3)"
        expl  = "Correlation matrix for all numeric columns"
        return code, res, expl

    # ── Describe / summary ───────────────────────────────────────────────────
    if any(w in q for w in ['describe', 'summary', 'statistics', 'profile', 'overview']):
        res  = df.describe(include='all').T.round(3)
        code = "df.describe(include='all').T"
        expl = "Descriptive statistics for all columns"
        return code, res, expl

    # ── Missing / nulls ───────────────────────────────────────────────────────
    if any(w in q for w in ['missing', 'null', 'nan', 'empty', 'na']):
        res  = pd.DataFrame({'column': df.columns, 'missing': df.isna().sum().values,
                             'missing_%': (df.isna().mean() * 100).round(1).values})
        code = "df.isna().sum().reset_index()"
        expl = "Missing value counts per column"
        return code, res, expl

    # ── Duplicates ────────────────────────────────────────────────────────────
    if any(w in q for w in ['duplicate', 'duplicates', 'dupe']):
        res  = df[df.duplicated()]
        code = "df[df.duplicated()]"
        expl = f"Duplicate rows: **{len(res):,}** found"
        return code, res, expl

    raise ValueError(
        "Query not understood.\n\n"
        "**Try these patterns:**\n"
        "- `average price by category`\n"
        "- `filter where age > 30`\n"
        "- `top 10 by revenue`\n"
        "- `sort by date desc`\n"
        "- `unique values of country`\n"
        "- `sum of sales by region`\n"
        "- `correlation`\n"
        "- `missing values`\n"
        "- `duplicates`"
    )

# ══════════════════════════════════════════════════════════════════════════════
# VISUALIZATION
# ══════════════════════════════════════════════════════════════════════════════

PLOTLY_THEME = dict(
    template='plotly_dark',
    paper_bgcolor='#07071a',
    plot_bgcolor='#07071a',
)

def _apply_theme(fig: go.Figure) -> go.Figure:
    fig.update_layout(**PLOTLY_THEME, margin=dict(l=20, r=20, t=40, b=20))
    fig.update_traces(marker_color='#6366f1') if hasattr(fig, 'data') and fig.data and not any(
        t.type in ('heatmap', 'scatter', 'box', 'violin') for t in fig.data if hasattr(t, 'type')
    ) else None
    return fig


def suggest_chart_types(df: pd.DataFrame, cols: list[str]) -> list[str]:
    """Return a list of appropriate chart types for the selected columns."""
    n     = len(cols)
    types = [df[c].dtype for c in cols]
    is_num = [pd.api.types.is_numeric_dtype(t) for t in types]
    is_dt  = [pd.api.types.is_datetime64_any_dtype(t) for t in types]

    if n == 1:
        if is_num[0]:
            return ['Histogram', 'Box Plot', 'Violin', 'KDE']
        elif is_dt[0]:
            return ['Time Series']
        else:
            return ['Bar Chart', 'Pie Chart', 'Treemap']
    elif n == 2:
        if all(is_num):
            return ['Scatter Plot', 'Line Plot', 'Hexbin']
        elif is_num[0] and not is_num[1]:
            return ['Box by Category', 'Bar Chart', 'Violin by Category']
        elif not is_num[0] and is_num[1]:
            return ['Box by Category', 'Bar Chart', 'Violin by Category']
        else:
            return ['Bar Chart', 'Stacked Bar']
    elif n >= 3 and all(is_num):
        return ['Correlation Heatmap', 'Scatter Matrix', 'Parallel Coordinates']
    return ['Bar Chart']


def render_chart(df: pd.DataFrame, cols: list[str], chart_type: str) -> Optional[go.Figure]:
    try:
        n = len(cols)
        c0 = cols[0] if cols else None
        c1 = cols[1] if n > 1 else None
        num_c = df.select_dtypes('number').columns.tolist()
        colors = px.colors.qualitative.Set3

        if chart_type == 'Histogram' and c0:
            fig = px.histogram(df, x=c0, nbins=40, color_discrete_sequence=['#6366f1'])
        elif chart_type == 'Box Plot' and c0:
            fig = px.box(df, y=c0, color_discrete_sequence=['#6366f1'])
        elif chart_type == 'Violin' and c0:
            fig = px.violin(df, y=c0, box=True, color_discrete_sequence=['#6366f1'])
        elif chart_type == 'KDE' and c0:
            import numpy as np
            from scipy.stats import gaussian_kde  # noqa: soft import
            data = df[c0].dropna().values
            kde  = gaussian_kde(data)
            x    = np.linspace(data.min(), data.max(), 300)
            fig  = go.Figure(go.Scatter(x=x, y=kde(x), fill='tozeroy',
                                        line=dict(color='#6366f1'), name='KDE'))
        elif chart_type == 'Bar Chart' and c0:
            if c1 and pd.api.types.is_numeric_dtype(df[c1]):
                fig = px.bar(df.groupby(c0)[c1].mean().reset_index().sort_values(c1, ascending=False).head(30),
                             x=c0, y=c1, color_discrete_sequence=['#6366f1'])
            else:
                vc = df[c0].value_counts().head(30)
                fig = px.bar(x=vc.index, y=vc.values, labels={'x': c0, 'y': 'Count'},
                             color_discrete_sequence=['#6366f1'])
        elif chart_type == 'Pie Chart' and c0:
            vc = df[c0].value_counts().head(12)
            fig = px.pie(values=vc.values, names=vc.index,
                         color_discrete_sequence=px.colors.qualitative.Pastel)
        elif chart_type == 'Treemap' and c0:
            vc = df[c0].value_counts().head(30).reset_index()
            vc.columns = [c0, 'count']
            fig = px.treemap(vc, path=[c0], values='count')
        elif chart_type == 'Scatter Plot' and c0 and c1:
            color_col = cols[2] if n > 2 else None
            fig = px.scatter(df.sample(min(5000, len(df))), x=c0, y=c1,
                             color=color_col, opacity=0.7,
                             color_discrete_sequence=px.colors.qualitative.Vivid)
        elif chart_type == 'Line Plot' and c0 and c1:
            fig = px.line(df.sort_values(c0), x=c0, y=c1,
                          color_discrete_sequence=['#6366f1'])
        elif chart_type == 'Hexbin' and c0 and c1:
            fig = go.Figure(go.Histogram2dContour(x=df[c0], y=df[c1],
                            colorscale='Blues', reversescale=True))
        elif 'Box by Category' in chart_type and c0 and c1:
            xc, yc = (c1, c0) if pd.api.types.is_numeric_dtype(df[c0]) else (c0, c1)
            fig = px.box(df, x=xc, y=yc, color=xc,
                         color_discrete_sequence=px.colors.qualitative.Pastel)
        elif 'Violin by Category' in chart_type and c0 and c1:
            xc, yc = (c1, c0) if pd.api.types.is_numeric_dtype(df[c0]) else (c0, c1)
            fig = px.violin(df, x=xc, y=yc, color=xc, box=True,
                            color_discrete_sequence=px.colors.qualitative.Pastel)
        elif chart_type == 'Correlation Heatmap':
            sel = df[cols].select_dtypes('number') if cols else df.select_dtypes('number')
            corr = sel.corr()
            fig  = px.imshow(corr, text_auto='.2f', color_continuous_scale='RdBu_r',
                             zmin=-1, zmax=1)
        elif chart_type == 'Scatter Matrix':
            sel = df[cols].select_dtypes('number') if cols else df.select_dtypes('number')
            fig = px.scatter_matrix(sel, color_discrete_sequence=['#6366f1'])
        elif chart_type == 'Parallel Coordinates':
            sel = df[cols].select_dtypes('number') if cols else df.select_dtypes('number')
            fig = px.parallel_coordinates(sel, color=sel.columns[0],
                                          color_continuous_scale='Viridis')
        elif chart_type == 'Time Series' and c0:
            yc = c1 if c1 and pd.api.types.is_numeric_dtype(df[c1]) else (num_c[0] if num_c else None)
            if yc:
                fig = px.line(df.sort_values(c0), x=c0, y=yc,
                              color_discrete_sequence=['#6366f1'])
            else:
                return None
        else:
            return None

        fig.update_layout(**PLOTLY_THEME, margin=dict(l=20, r=20, t=40, b=20))
        return fig

    except Exception as e:
        st.error(f"Chart error: {e}")
        return None

# ══════════════════════════════════════════════════════════════════════════════
# STATS COMPARISON (before / after filtering)
# ══════════════════════════════════════════════════════════════════════════════

def quick_stats(df: pd.DataFrame) -> dict:
    num = df.select_dtypes('number')
    return {
        'rows':   len(df),
        'cols':   len(df.columns),
        'nulls':  int(df.isna().sum().sum()),
        'means':  num.mean().round(3).to_dict() if not num.empty else {},
    }

# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown(
        "<div style='padding:.5rem 0 .25rem'>"
        "<span style='font-size:1.4rem;font-weight:900;"
        "background:linear-gradient(135deg,#818cf8,#ec4899);"
        "-webkit-background-clip:text;-webkit-text-fill-color:transparent'>📊 DataLens</span><br>"
        "<span style='font-size:.7rem;color:#475569;text-transform:uppercase;letter-spacing:.1em'>"
        "Self-Service Data Analyst</span></div>",
        unsafe_allow_html=True,
    )
    st.markdown("---")

    # ── Primary file upload ──────────────────────────────────────────────────
    st.markdown("### 📂 Upload Dataset")
    uploaded = st.file_uploader(
        "CSV or Excel", type=['csv', 'xlsx', 'xls'],
        label_visibility='collapsed', key='primary_upload',
    )
    if uploaded and uploaded.name != st.session_state.filename:
        with st.spinner("Loading…"):
            try:
                df_new = _load(uploaded.read(), uploaded.name)
                st.session_state.df           = df_new
                st.session_state.df_original  = df_new.copy()
                st.session_state.filename     = uploaded.name
                st.session_state.history      = []
                st.session_state.filters      = []
                st.session_state.suggestions  = detect_suggestions(df_new)
                st.session_state.audit_log    = []
                _push_history(f"Loaded '{uploaded.name}'")
                st.success(f"Loaded {len(df_new):,} rows × {len(df_new.columns)} cols")
            except ValueError as e:
                st.error(str(e))

    st.markdown("---")

    # ── Current state summary ────────────────────────────────────────────────
    if st.session_state.df is not None:
        df   = st.session_state.df
        orig = st.session_state.df_original
        st.markdown("### 📋 Current State")
        c1, c2 = st.columns(2)
        c1.metric("Rows", f"{len(df):,}")
        c2.metric("Cols", len(df.columns))
        if len(df) != len(orig):
            delta = len(df) - len(orig)
            st.caption(f"{delta:+,} rows vs. original ({len(orig):,})")

        st.markdown("---")

        # ── Session history / undo ───────────────────────────────────────────
        st.markdown("### ⏱️ Session History")
        for i, h in enumerate(reversed(st.session_state.history[-8:])):
            is_latest = i == 0
            dot_cls   = 'active' if is_latest else ''
            st.markdown(
                f"<div class='history-item'>"
                f"<div class='h-dot {dot_cls}'></div>"
                f"<div><div style='font-size:.78rem;color:#e2e8f0'>{h['desc']}</div>"
                f"<div style='font-size:.68rem;color:#475569'>{h['ts']} · {h['rows']:,} rows</div>"
                f"</div></div>",
                unsafe_allow_html=True,
            )

        col_a, col_b = st.columns(2)
        if col_a.button("↩ Undo", use_container_width=True, disabled=len(st.session_state.history) <= 1):
            _undo()
            st.rerun()
        if col_b.button("⟳ Reset", use_container_width=True):
            st.session_state.df      = st.session_state.df_original.copy()
            st.session_state.filters = []
            _push_history("Reset to original")
            st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# MAIN AREA
# ══════════════════════════════════════════════════════════════════════════════

if st.session_state.df is None:
    # ── Landing page ─────────────────────────────────────────────────────────
    st.markdown("""
<div style='text-align:center;padding:4rem 2rem'>
  <div style='font-size:3rem;font-weight:900;
    background:linear-gradient(135deg,#818cf8,#ec4899);
    -webkit-background-clip:text;-webkit-text-fill-color:transparent;
    margin-bottom:1rem'>📊 DataLens</div>
  <div style='font-size:1.2rem;color:#94a3b8;margin-bottom:2rem'>
    Drop a CSV or Excel file in the sidebar to start exploring.<br>
    No code. No setup. Just data.
  </div>
  <div style='display:grid;grid-template-columns:repeat(3,1fr);gap:1rem;max-width:800px;margin:0 auto'>
    <div style='background:#0f0f1e;border:1px solid #1e1e3a;border-radius:12px;padding:1.5rem'>
      <div style='font-size:1.5rem'>🔍</div><div style='font-weight:600;margin:.5rem 0'>Auto Profile</div>
      <div style='font-size:.8rem;color:#64748b'>Instant stats, missing values, and distributions</div>
    </div>
    <div style='background:#0f0f1e;border:1px solid #1e1e3a;border-radius:12px;padding:1.5rem'>
      <div style='font-size:1.5rem'>💬</div><div style='font-weight:600;margin:.5rem 0'>NL Queries</div>
      <div style='font-size:.8rem;color:#64748b'>"average price by region" — generates real pandas code</div>
    </div>
    <div style='background:#0f0f1e;border:1px solid #1e1e3a;border-radius:12px;padding:1.5rem'>
      <div style='font-size:1.5rem'>📈</div><div style='font-weight:600;margin:.5rem 0'>Smart Charts</div>
      <div style='font-size:.8rem;color:#64748b'>Auto-suggested visualizations for your column types</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)
    st.stop()

# ── File is loaded — show main content ─────────────────────────────────────
df = st.session_state.df

st.markdown(
    f"<div style='display:flex;align-items:center;gap:.75rem;margin-bottom:.25rem'>"
    f"<span style='font-size:1.25rem;font-weight:700;color:#e2e8f0'>{st.session_state.filename}</span>"
    f"<span style='background:#1e1e3a;color:#818cf8;font-size:.72rem;padding:.15rem .6rem;"
    f"border-radius:99px'>{len(df):,} rows × {len(df.columns)} cols</span>"
    f"</div>",
    unsafe_allow_html=True,
)

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🔍 Overview", "🔧 Explore", "📈 Visualize", "💬 NL Query", "🔀 Compare", "⬇️ Export"
])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — OVERVIEW (Auto Profile)
# ══════════════════════════════════════════════════════════════════════════════
with tab1:
    orig = st.session_state.df_original

    # ── Summary metrics ──────────────────────────────────────────────────────
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Rows",        f"{len(df):,}")
    m2.metric("Columns",     len(df.columns))
    m3.metric("Missing",     f"{df.isna().sum().sum():,}")
    m4.metric("Duplicates",  f"{df.duplicated().sum():,}")
    m5.metric("Memory",      f"{df.memory_usage(deep=True).sum() / 1024:.1f} KB")

    st.markdown("---")

    # ── Smart suggestions ────────────────────────────────────────────────────
    sugs = st.session_state.suggestions
    if sugs:
        st.markdown("#### 🤖 Smart Suggestions")
        for s in sugs:
            card_cls = 'outlier-card' if s['kind'] == 'outlier' else 'suggestion-card'
            st.markdown(
                f"<div class='{card_cls}'>{s['icon']} {s['msg']}</div>",
                unsafe_allow_html=True,
            )
            if s['kind'] == 'date':
                if st.button(f"Convert '{s['col']}' to datetime", key=f"cvt_{s['col']}"):
                    st.session_state.df[s['col']] = pd.to_datetime(
                        st.session_state.df[s['col']], errors='coerce'
                    )
                    st.session_state.suggestions = detect_suggestions(st.session_state.df)
                    _push_history(f"Converted '{s['col']}' to datetime")
                    _audit('type_conversion', f"{s['col']} → datetime")
                    st.rerun()

    st.markdown("---")

    # ── Column profile table ─────────────────────────────────────────────────
    st.markdown("#### 📋 Column Profile")
    profile_rows = []
    for col in df.columns:
        null_n   = int(df[col].isna().sum())
        null_pct = null_n / len(df) * 100
        unique   = df[col].nunique()
        dtype    = str(df[col].dtype)
        sample   = df[col].dropna().head(3).tolist()
        sample_s = ', '.join(str(x) for x in sample[:3])

        row = {
            'Column':   col,
            'Type':     dtype,
            'Missing':  null_n,
            'Missing%': f"{null_pct:.1f}%",
            'Unique':   unique,
            'Sample':   sample_s,
        }
        if pd.api.types.is_numeric_dtype(df[col]):
            row['Mean'] = f"{df[col].mean():.3g}"
            row['Std']  = f"{df[col].std():.3g}"
            row['Min']  = f"{df[col].min():.3g}"
            row['Max']  = f"{df[col].max():.3g}"
        else:
            row['Mean'] = row['Std'] = row['Min'] = row['Max'] = '—'

        profile_rows.append(row)

    st.dataframe(pd.DataFrame(profile_rows), use_container_width=True, hide_index=True)

    # ── Distributions mini-grid ──────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### 📊 Distributions")
    num_cols = df.select_dtypes('number').columns.tolist()
    cat_cols = df.select_dtypes(exclude='number').columns.tolist()

    if num_cols:
        st.markdown("**Numeric columns**")
        grid_cols = st.columns(min(4, len(num_cols)))
        for i, col in enumerate(num_cols[:8]):
            with grid_cols[i % 4]:
                fig = px.histogram(df, x=col, nbins=25,
                                   color_discrete_sequence=['#6366f1'], height=180)
                fig.update_layout(**PLOTLY_THEME, showlegend=False,
                                  margin=dict(l=5,r=5,t=30,b=5), title=col,
                                  title_font_size=11, xaxis=dict(showticklabels=False),
                                  yaxis=dict(showticklabels=False))
                st.plotly_chart(fig, use_container_width=True, key=f"dist_{col}")

    if cat_cols:
        st.markdown("**Categorical columns**")
        grid_cols2 = st.columns(min(3, len(cat_cols)))
        for i, col in enumerate(cat_cols[:6]):
            with grid_cols2[i % 3]:
                vc = df[col].value_counts().head(8)
                fig = px.bar(x=vc.index.astype(str), y=vc.values, height=200,
                             color_discrete_sequence=['#ec4899'],
                             labels={'x': col, 'y': 'count'})
                fig.update_layout(**PLOTLY_THEME, showlegend=False,
                                  margin=dict(l=5,r=5,t=30,b=5), title=col,
                                  title_font_size=11)
                st.plotly_chart(fig, use_container_width=True, key=f"cat_{col}")

    # ── Correlation heatmap ──────────────────────────────────────────────────
    if len(num_cols) >= 2:
        st.markdown("---")
        st.markdown("#### 🔗 Correlation Matrix")
        corr = df[num_cols].corr()
        fig  = px.imshow(corr, text_auto='.2f', color_continuous_scale='RdBu_r',
                         zmin=-1, zmax=1, height=400)
        fig.update_layout(**PLOTLY_THEME)
        st.plotly_chart(fig, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — EXPLORE (Filter Builder + Before/After)
# ══════════════════════════════════════════════════════════════════════════════
with tab2:
    col_sel, col_table = st.columns([1, 2], gap='large')

    with col_sel:
        st.markdown("#### 🔧 Filter Builder")

        filters: list[dict] = st.session_state.filters

        for i, f in enumerate(filters):
            fc1, fc2, fc3, fc4, fc5 = st.columns([2, 1.5, 1.5, 1, 0.5])
            with fc1:
                cols_list = list(df.columns)
                f['col'] = st.selectbox("", cols_list, index=cols_list.index(f['col'])
                    if f['col'] in cols_list else 0, key=f"fcol_{i}", label_visibility='collapsed')
            with fc2:
                f['op'] = st.selectbox("", OPERATORS, index=OPERATORS.index(f['op'])
                    if f['op'] in OPERATORS else 0, key=f"fop_{i}", label_visibility='collapsed')
            with fc3:
                if f['op'] not in ('is null', 'is not null'):
                    f['val'] = st.text_input("", f.get('val', ''), key=f"fval_{i}",
                                             label_visibility='collapsed', placeholder='value')
            with fc4:
                if i > 0:
                    f['logic'] = st.selectbox("", ['AND', 'OR'], index=0 if f.get('logic', 'AND') == 'AND' else 1,
                                              key=f"flog_{i}", label_visibility='collapsed')
            with fc5:
                if st.button("✕", key=f"fdel_{i}"):
                    filters.pop(i); st.rerun()

        if st.button("＋ Add Filter", use_container_width=True):
            filters.append({'col': df.columns[0], 'op': 'equals', 'val': '', 'logic': 'AND'})
            st.rerun()

        st.markdown("---")
        col_apply, col_clear = st.columns(2)
        if col_apply.button("▶ Apply", use_container_width=True, type='primary'):
            filtered = apply_filters(st.session_state.df_original, filters)
            st.session_state.df = filtered
            desc = f"Filter: {len(filters)} condition(s) → {len(filtered):,} rows"
            _push_history(desc)
            _audit('filter_applied', filter_code(filters))
            st.rerun()
        if col_clear.button("✕ Clear All", use_container_width=True):
            st.session_state.filters = []
            st.session_state.df = st.session_state.df_original.copy()
            _push_history("Cleared filters")
            st.rerun()

        if filters:
            st.markdown("**Generated code:**")
            st.code(filter_code(filters), language='python')

        # ── Column selector ──────────────────────────────────────────────────
        st.markdown("---")
        st.markdown("#### 🗂️ Columns to Show")
        all_cols = list(df.columns)
        visible  = st.multiselect("", all_cols, default=all_cols[:min(8, len(all_cols))],
                                  key='col_select', label_visibility='collapsed')

    with col_table:
        orig = st.session_state.df_original
        filtered = apply_filters(orig, filters)

        # ── Before / After comparison ────────────────────────────────────────
        if len(filtered) != len(orig):
            st.markdown("#### ↔ Before / After")
            before_s = quick_stats(orig)
            after_s  = quick_stats(filtered)

            ba1, ba2, ba3 = st.columns(3)
            ba1.metric("Rows",    f"{after_s['rows']:,}",    delta=f"{after_s['rows']-before_s['rows']:+,}")
            ba2.metric("Nulls",   f"{after_s['nulls']:,}",   delta=f"{after_s['nulls']-before_s['nulls']:+,}")

            common_means = {k: v for k, v in after_s['means'].items() if k in before_s['means']}
            if common_means:
                first_col = next(iter(common_means))
                delta_mean = after_s['means'][first_col] - before_s['means'][first_col]
                ba3.metric(f"Mean({first_col})", f"{after_s['means'][first_col]:.3g}",
                           delta=f"{delta_mean:+.3g}")

            # Side-by-side numeric summary
            num_cols_ = filtered.select_dtypes('number').columns.tolist()
            if num_cols_:
                b_desc = orig[num_cols_].describe().T[['mean','std','min','max']].round(3)
                a_desc = filtered[num_cols_].describe().T[['mean','std','min','max']].round(3)
                b_desc.columns = ['before_mean','before_std','before_min','before_max']
                a_desc.columns = ['after_mean','after_std','after_min','after_max']
                cmp_df = pd.concat([b_desc, a_desc], axis=1)
                cmp_df.index.name = 'column'
                st.dataframe(cmp_df.reset_index(), use_container_width=True, hide_index=True)

            st.markdown("---")

        # ── Live table ───────────────────────────────────────────────────────
        disp_df = filtered[visible] if visible else filtered
        st.markdown(
            f"<div style='color:#64748b;font-size:.8rem;margin-bottom:.4rem'>"
            f"Showing <b style='color:#e2e8f0'>{len(disp_df):,}</b> of <b style='color:#e2e8f0'>"
            f"{len(orig):,}</b> rows · {len(visible or df.columns)} columns</div>",
            unsafe_allow_html=True,
        )
        st.dataframe(disp_df.head(500), use_container_width=True, hide_index=False)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — VISUALIZE
# ══════════════════════════════════════════════════════════════════════════════
with tab3:
    st.markdown("#### 📈 Visualization Gallery")

    vc1, vc2 = st.columns([1, 3], gap='large')

    with vc1:
        all_cols = list(df.columns)
        sel_cols = st.multiselect(
            "Select columns (1–4):", all_cols,
            default=[all_cols[0]] if all_cols else [],
            max_selections=4, key='viz_cols',
        )

        chart_types = suggest_chart_types(df, sel_cols) if sel_cols else ['Histogram']
        chart_type  = st.radio("Chart type:", chart_types, key='chart_type')

        sample_n = st.slider("Max rows to plot:", 500, min(10000, len(df)), min(2000, len(df)), 500)

    with vc2:
        if not sel_cols:
            st.info("Select one or more columns on the left to generate a chart.")
        else:
            plot_df = df.sample(min(sample_n, len(df))) if len(df) > sample_n else df
            fig = render_chart(plot_df, sel_cols, chart_type)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("Could not generate this chart for the selected columns.")

    # ── Auto-gallery: all numeric vs first cat ───────────────────────────────
    if df.select_dtypes('number').shape[1] >= 2:
        st.markdown("---")
        with st.expander("📊 Auto-Gallery — all numeric column distributions"):
            n_num = df.select_dtypes('number').columns.tolist()
            gcols = st.columns(min(4, len(n_num)))
            for i, c in enumerate(n_num[:8]):
                with gcols[i % 4]:
                    fig2 = px.box(df, y=c, height=200, color_discrete_sequence=['#ec4899'])
                    fig2.update_layout(**PLOTLY_THEME, margin=dict(l=5,r=5,t=30,b=5),
                                       title=c, title_font_size=11, showlegend=False)
                    st.plotly_chart(fig2, use_container_width=True, key=f"box_{c}")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — NATURAL LANGUAGE QUERY
# ══════════════════════════════════════════════════════════════════════════════
with tab4:
    st.markdown("#### 💬 Natural Language Query")
    st.markdown(
        "Type a question in plain English. The engine translates it to pandas code, "
        "runs it, and shows you the result **and** the code — so it's never a black box."
    )

    # ── Quick example chips ──────────────────────────────────────────────────
    examples = [
        "average price by category",
        "filter where age > 30",
        "top 10 by revenue",
        "sort by date desc",
        "unique values of country",
        "correlation",
        "missing values",
    ]
    st.markdown("**Quick examples:**")
    ex_cols = st.columns(len(examples))
    selected_ex = None
    for i, ex in enumerate(examples):
        if ex_cols[i].button(ex, key=f"ex_{i}"):
            selected_ex = ex

    query = st.text_input(
        "Your question:",
        value=selected_ex or '',
        placeholder='e.g. "average salary by department"',
        key='nl_input',
    )

    if st.button("▶ Run Query", type='primary') and query:
        with st.spinner("Thinking…"):
            try:
                code, result, expl = nl_query(query, df)

                st.success(expl)

                # Show generated code
                st.markdown("**Generated pandas code:**")
                st.code(code, language='python')

                # Show result
                st.markdown(f"**Result** ({len(result):,} rows × {len(result.columns)} cols):")
                st.dataframe(result, use_container_width=True, hide_index=True)

                # Auto-visualize result if numeric
                num_r = result.select_dtypes('number').columns.tolist()
                if len(result) > 1 and num_r:
                    if len(result.columns) == 2:
                        str_c = [c for c in result.columns if result[c].dtype == object]
                        if str_c:
                            fig = px.bar(result.head(30), x=str_c[0], y=num_r[0],
                                         color_discrete_sequence=['#6366f1'])
                            fig.update_layout(**PLOTLY_THEME)
                            st.plotly_chart(fig, use_container_width=True)

                _audit('nl_query', f"Q: {query} → {len(result)} rows")
                _push_history(f"NL: \"{query[:40]}\"")

            except ValueError as e:
                st.error(str(e))

# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — COMPARE (Multi-file)
# ══════════════════════════════════════════════════════════════════════════════
with tab5:
    st.markdown("#### 🔀 Multi-File Comparison")
    st.markdown("Upload a second file to compare side-by-side with your primary dataset.")

    up2 = st.file_uploader("Second file (CSV or Excel)", type=['csv','xlsx','xls'],
                            key='compare_upload', label_visibility='collapsed')
    if up2 and up2.name != st.session_state.fname_compare:
        try:
            st.session_state.df_compare   = _load(up2.read(), up2.name)
            st.session_state.fname_compare = up2.name
        except ValueError as e:
            st.error(str(e))

    df_a = st.session_state.df_original
    df_b = st.session_state.df_compare

    if df_b is None:
        st.info("No second file uploaded yet.")
    else:
        st.markdown("---")
        fa = st.session_state.filename
        fb = st.session_state.fname_compare

        # ── Shape comparison ─────────────────────────────────────────────────
        r1, r2, r3, r4 = st.columns(4)
        r1.metric(f"Rows ({fa})",    f"{len(df_a):,}")
        r2.metric(f"Rows ({fb})",    f"{len(df_b):,}", delta=f"{len(df_b)-len(df_a):+,}")
        r3.metric(f"Cols ({fa})",    len(df_a.columns))
        r4.metric(f"Cols ({fb})",    len(df_b.columns), delta=len(df_b.columns)-len(df_a.columns))

        # ── Column diff ───────────────────────────────────────────────────────
        st.markdown("---")
        st.markdown("#### Column Inventory")
        only_a = set(df_a.columns) - set(df_b.columns)
        only_b = set(df_b.columns) - set(df_a.columns)
        in_both = set(df_a.columns) & set(df_b.columns)

        col_diff_rows = []
        for c in sorted(in_both):
            col_diff_rows.append({'Column': c, 'Status': '✅ Both', 'Type A': str(df_a[c].dtype), 'Type B': str(df_b[c].dtype)})
        for c in sorted(only_a):
            col_diff_rows.append({'Column': c, 'Status': f'⬅ {fa} only', 'Type A': str(df_a[c].dtype), 'Type B': '—'})
        for c in sorted(only_b):
            col_diff_rows.append({'Column': c, 'Status': f'➡ {fb} only', 'Type A': '—', 'Type B': str(df_b[c].dtype)})

        st.dataframe(pd.DataFrame(col_diff_rows), use_container_width=True, hide_index=True)

        # ── Summary stats diff ────────────────────────────────────────────────
        common_num = [c for c in in_both if pd.api.types.is_numeric_dtype(df_a[c]) and c in df_b.columns]
        if common_num:
            st.markdown("---")
            st.markdown("#### Side-by-Side Numeric Statistics")
            desc_a = df_a[common_num].describe().T[['mean','std','min','max']].round(3)
            desc_b = df_b[common_num].describe().T[['mean','std','min','max']].round(3)
            desc_a.columns = [f'A_{c}' for c in desc_a.columns]
            desc_b.columns = [f'B_{c}' for c in desc_b.columns]
            cmp = pd.concat([desc_a, desc_b], axis=1)
            cmp.index.name = 'Column'
            st.dataframe(cmp.reset_index(), use_container_width=True, hide_index=True)

            # Distribution overlay charts
            st.markdown("---")
            st.markdown("#### Distribution Overlays")
            plot_col = st.selectbox("Column to compare:", common_num, key='cmp_col')
            fig_cmp = go.Figure()
            fig_cmp.add_trace(go.Histogram(x=df_a[plot_col], name=fa, opacity=0.65,
                                           marker_color='#6366f1', nbinsx=40))
            fig_cmp.add_trace(go.Histogram(x=df_b[plot_col], name=fb, opacity=0.65,
                                           marker_color='#ec4899', nbinsx=40))
            fig_cmp.update_layout(**PLOTLY_THEME, barmode='overlay',
                                  xaxis_title=plot_col, yaxis_title='Count',
                                  legend=dict(bgcolor='rgba(0,0,0,0)'))
            st.plotly_chart(fig_cmp, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 6 — EXPORT
# ══════════════════════════════════════════════════════════════════════════════
with tab6:
    st.markdown("#### ⬇️ Export")

    exp1, exp2 = st.columns(2, gap='large')

    with exp1:
        st.markdown("**Filtered Dataset**")
        active_filters = st.session_state.filters
        filtered_df    = apply_filters(st.session_state.df_original, active_filters)

        csv_bytes = filtered_df.to_csv(index=False).encode()
        st.download_button(
            label=f"Download CSV ({len(filtered_df):,} rows)",
            data=csv_bytes,
            file_name=f"{st.session_state.filename.rsplit('.',1)[0]}_filtered.csv",
            mime='text/csv',
            use_container_width=True,
        )

        try:
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='openpyxl') as w:
                filtered_df.to_excel(w, index=False)
            st.download_button(
                label=f"Download Excel ({len(filtered_df):,} rows)",
                data=buf.getvalue(),
                file_name=f"{st.session_state.filename.rsplit('.',1)[0]}_filtered.xlsx",
                mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                use_container_width=True,
            )
        except Exception:
            st.caption("Excel export unavailable — openpyxl may not be installed.")

    with exp2:
        st.markdown("**Audit Log / Provenance**")
        st.caption(
            "Every filter, query, and transformation is tracked here, so your analysis "
            "is fully reproducible."
        )

        audit = st.session_state.audit_log
        if audit:
            audit_lines = [
                f"DataLens Audit Log — {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                f"File: {st.session_state.filename}",
                f"Original rows: {len(st.session_state.df_original):,}",
                f"Exported rows: {len(filtered_df):,}",
                "─" * 60,
            ]
            for entry in audit:
                audit_lines.append(f"[{entry['ts']}] {entry['action']}")
                if entry.get('detail'):
                    audit_lines.append(f"    {entry['detail']}")
            audit_lines.append("─" * 60)
            if active_filters:
                audit_lines.append("Active filters applied:")
                audit_lines.append(f"  {filter_code(active_filters)}")

            audit_text = '\n'.join(audit_lines)
            st.code(audit_text[:1500] + ('…' if len(audit_text) > 1500 else ''), language='text')
            st.download_button(
                "Download Audit Log (.txt)",
                data=audit_text.encode(),
                file_name=f"{st.session_state.filename.rsplit('.',1)[0]}_audit.txt",
                mime='text/plain',
                use_container_width=True,
            )
        else:
            st.info("No operations recorded yet. Run some queries or filters first.")

    # ── JSON summary ─────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("**Session Summary (JSON)**")
    summary = {
        'file':           st.session_state.filename,
        'original_rows':  len(st.session_state.df_original),
        'original_cols':  len(st.session_state.df_original.columns),
        'exported_rows':  len(filtered_df),
        'filters_applied': len(active_filters),
        'operations':     len(st.session_state.history),
        'generated_at':   datetime.datetime.now().isoformat(),
    }
    st.download_button(
        "Download Session Summary (.json)",
        data=json.dumps(summary, indent=2).encode(),
        file_name="session_summary.json",
        mime='application/json',
        use_container_width=False,
    )
