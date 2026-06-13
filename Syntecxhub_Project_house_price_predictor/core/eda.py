"""EDA chart generation and data quality analysis."""

from typing import Optional
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

_THEME = dict(
    template='plotly_dark',
    paper_bgcolor='#07071a',
    plot_bgcolor='#07071a',
)
_ACCENT  = '#6366f1'
_ACCENT2 = '#ec4899'


def _apply(fig: go.Figure, margin=(20, 20, 40, 20)) -> go.Figure:
    l, r, t, b = margin
    fig.update_layout(**_THEME, margin=dict(l=l, r=r, t=t, b=b))
    return fig


# ── Quality warnings ──────────────────────────────────────────────────────────

def quality_warnings(df: pd.DataFrame, target_col: str) -> list[dict]:
    warnings = []

    if len(df) < 200:
        warnings.append({'level': 'high', 'msg':
            f"Dataset has only {len(df):,} rows — model reliability may be limited. "
            "Consider collecting more data or using regularized models (Ridge/Lasso)."})

    missing_pct = df.isnull().mean() * 100
    for col, pct in missing_pct.items():
        if pct > 30:
            warnings.append({'level': 'high', 'msg':
                f"Column '{col}' has {pct:.1f}% missing values — consider excluding it."})
        elif pct > 5:
            warnings.append({'level': 'medium', 'msg':
                f"Column '{col}' has {pct:.1f}% missing values — will be imputed with median/mode."})

    if target_col and target_col in df.columns:
        t = df[target_col].dropna()
        skew = float(t.skew())
        if abs(skew) > 1.0:
            warnings.append({'level': 'medium', 'msg':
                f"Target '{target_col}' is skewed (skewness={skew:.2f}). "
                "A log-transform often improves model performance — enable it below."})

        dups = df.duplicated().sum()
        if dups > 0:
            warnings.append({'level': 'medium', 'msg':
                f"{dups} duplicate rows detected — consider removing them."})

    num_cols = df.select_dtypes('number').columns
    for col in num_cols:
        if col == target_col:
            continue
        q1, q3 = df[col].quantile([0.25, 0.75])
        iqr = q3 - q1
        if iqr > 0:
            n_out = ((df[col] < q1 - 3 * iqr) | (df[col] > q3 + 3 * iqr)).sum()
            if n_out / len(df) > 0.05:
                warnings.append({'level': 'low', 'msg':
                    f"'{col}' has {n_out} extreme outliers ({n_out/len(df):.1%}) — "
                    "review before training."})

    return warnings


# ── Target distribution ───────────────────────────────────────────────────────

def target_distribution_fig(df: pd.DataFrame, target_col: str, log_scale: bool = False) -> go.Figure:
    vals = df[target_col].dropna()
    if log_scale:
        vals = np.log1p(vals)
        x_label = f'log({target_col})'
    else:
        x_label = target_col

    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=vals, nbinsx=50, name='Distribution',
        marker_color=_ACCENT, opacity=0.85,
    ))
    fig.update_layout(
        **_THEME, xaxis_title=x_label, yaxis_title='Count',
        title=f'Target Distribution: {target_col}',
        margin=dict(l=20, r=20, t=50, b=20),
    )
    return fig


# ── Feature distributions ─────────────────────────────────────────────────────

def feature_distributions_fig(df: pd.DataFrame, num_cols: list[str]) -> go.Figure:
    n    = min(len(num_cols), 12)
    cols = num_cols[:n]
    ncol = min(4, n)
    nrow = (n + ncol - 1) // ncol

    fig = make_subplots(rows=nrow, cols=ncol, subplot_titles=cols)
    colors = px.colors.qualitative.Pastel
    for i, col in enumerate(cols):
        r, c = divmod(i, ncol)
        fig.add_trace(
            go.Histogram(x=df[col].dropna(), nbinsx=30,
                         marker_color=colors[i % len(colors)], showlegend=False),
            row=r + 1, col=c + 1,
        )
    fig.update_layout(**_THEME, height=280 * nrow, showlegend=False,
                      margin=dict(l=10, r=10, t=30, b=10))
    return fig


# ── Correlation heatmap ───────────────────────────────────────────────────────

def correlation_heatmap_fig(df: pd.DataFrame, num_cols: list[str], target_col: str) -> go.Figure:
    all_cols = sorted(set([target_col] + num_cols)) if target_col else num_cols
    corr = df[all_cols].corr()
    fig  = px.imshow(
        corr, text_auto='.2f', color_continuous_scale='RdBu_r',
        zmin=-1, zmax=1, aspect='auto',
    )
    fig.update_layout(**_THEME, title='Correlation Matrix', margin=dict(l=5, r=5, t=50, b=5))
    return fig


# ── Missing values heatmap ────────────────────────────────────────────────────

def missing_value_fig(df: pd.DataFrame) -> go.Figure:
    missing = (df.isnull().mean() * 100).sort_values(ascending=False)
    missing = missing[missing > 0]
    if missing.empty:
        fig = go.Figure()
        fig.add_annotation(text='No missing values — dataset is complete!',
                           xref='paper', yref='paper', x=0.5, y=0.5,
                           showarrow=False, font=dict(size=16, color='#4ade80'))
        fig.update_layout(**_THEME, margin=dict(l=20, r=20, t=40, b=20))
        return fig

    fig = go.Figure(go.Bar(
        x=missing.values, y=missing.index,
        orientation='h', marker_color=_ACCENT2, text=[f'{v:.1f}%' for v in missing.values],
        textposition='outside',
    ))
    fig.update_layout(**_THEME, title='Missing Values (%)', xaxis_title='Missing (%)',
                      margin=dict(l=10, r=60, t=50, b=10))
    return fig


# ── Target vs feature scatter ─────────────────────────────────────────────────

def scatter_vs_target_fig(df: pd.DataFrame, feature_col: str, target_col: str) -> go.Figure:
    sample = df[[feature_col, target_col]].dropna().sample(min(2000, len(df)))
    fig = px.scatter(sample, x=feature_col, y=target_col,
                     opacity=0.5, color_discrete_sequence=[_ACCENT],
                     trendline='ols', trendline_color_override=_ACCENT2)
    fig.update_layout(**_THEME, title=f'{feature_col} vs {target_col}',
                      margin=dict(l=20, r=20, t=50, b=20))
    return fig


# ── Categorical feature vs target box plots ───────────────────────────────────

def boxplot_vs_target_fig(df: pd.DataFrame, cat_col: str, target_col: str) -> go.Figure:
    top_cats = df[cat_col].value_counts().nlargest(12).index
    sub = df[df[cat_col].isin(top_cats)]
    fig = px.box(sub, x=cat_col, y=target_col,
                 color=cat_col, color_discrete_sequence=px.colors.qualitative.Pastel)
    fig.update_layout(**_THEME, title=f'{cat_col} vs {target_col}', showlegend=False,
                      margin=dict(l=20, r=20, t=50, b=20))
    return fig


# ── Outlier detection summary ─────────────────────────────────────────────────

def outlier_summary(df: pd.DataFrame, num_cols: list[str]) -> pd.DataFrame:
    rows = []
    for col in num_cols:
        q1, q3 = df[col].quantile([0.25, 0.75])
        iqr = q3 - q1
        if iqr == 0:
            continue
        n_mild    = ((df[col] < q1 - 1.5 * iqr) | (df[col] > q3 + 1.5 * iqr)).sum()
        n_extreme = ((df[col] < q1 - 3.0 * iqr) | (df[col] > q3 + 3.0 * iqr)).sum()
        rows.append({
            'Column':          col,
            'Mild outliers':   n_mild,
            'Extreme outliers': n_extreme,
            'Mild %':          f'{n_mild / len(df) * 100:.1f}%',
            'Extreme %':       f'{n_extreme / len(df) * 100:.1f}%',
            'Q1':              round(q1, 2),
            'Q3':              round(q3, 2),
            'IQR':             round(iqr, 2),
        })
    return pd.DataFrame(rows)
