"""SHAP-based model explainability — summary and individual waterfall plots."""

from __future__ import annotations

from typing import Optional
import numpy as np
import pandas as pd
import plotly.graph_objects as go

_THEME  = dict(template='plotly_dark', paper_bgcolor='#07071a', plot_bgcolor='#07071a')
_POS    = '#6366f1'  # positive SHAP (raises price)
_NEG    = '#ec4899'  # negative SHAP (lowers price)


# ── SHAP computation ──────────────────────────────────────────────────────────

def compute_shap(
    model_name:    str,
    pipeline,
    X_sample:      pd.DataFrame,
    feature_names: list[str],
    max_rows:      int = 500,
) -> tuple[np.ndarray, float]:
    """
    Returns (shap_values [n_rows × n_features], base_value).
    Samples up to max_rows rows to keep computation fast.
    """
    try:
        import shap
    except ImportError:
        raise ImportError("Install shap: pip install shap")

    if len(X_sample) > max_rows:
        X_sample = X_sample.sample(max_rows, random_state=42)

    preprocessor = pipeline.named_steps['pre']
    model        = pipeline.named_steps['mdl']
    X_pre        = preprocessor.transform(X_sample)

    is_tree   = model_name in ('Random Forest', 'Gradient Boosting')
    is_linear = model_name in ('Linear Regression', 'Ridge', 'Lasso')

    if is_tree:
        explainer = shap.TreeExplainer(model)
        sv        = explainer.shap_values(X_pre)
        base_val  = float(explainer.expected_value)
    elif is_linear:
        background = shap.maskers.Independent(X_pre, max_samples=100)
        explainer  = shap.LinearExplainer(model, background)
        sv         = explainer.shap_values(X_pre)
        base_val   = float(explainer.expected_value)
    else:
        background = shap.sample(X_pre, 50)
        explainer  = shap.KernelExplainer(model.predict, background)
        sv         = explainer.shap_values(X_pre, nsamples=100)
        base_val   = float(explainer.expected_value)

    if isinstance(sv, list):
        sv = sv[0]
    return sv, base_val


# ── Original-column aggregation ───────────────────────────────────────────────

def aggregate_to_original(
    shap_values:   np.ndarray,
    feature_names: list[str],
    num_cols:      list[str],
    cat_cols:      list[str],
) -> tuple[np.ndarray, list[str]]:
    """
    Sum one-hot encoded category SHAP values back to original column level.
    Returns (aggregated_shap [n_rows × n_original_features], original_names).
    """
    orig_names = list(num_cols) + list(cat_cols)
    n_rows     = shap_values.shape[0]
    aggregated = np.zeros((n_rows, len(orig_names)))

    for i, orig in enumerate(orig_names):
        indices = [
            j for j, fn in enumerate(feature_names)
            if fn == orig or fn.startswith(f'{orig}_')
        ]
        if indices:
            aggregated[:, i] = shap_values[:, indices].sum(axis=1)

    return aggregated, orig_names


# ── Summary bar chart ─────────────────────────────────────────────────────────

def shap_summary_fig(
    shap_values:   np.ndarray,
    orig_names:    list[str],
    log_target:    bool = False,
) -> go.Figure:
    mean_abs = np.abs(shap_values).mean(axis=0)
    order    = np.argsort(mean_abs)
    names_s  = [orig_names[i] for i in order]
    vals_s   = mean_abs[order]

    fig = go.Figure(go.Bar(
        x=vals_s, y=names_s,
        orientation='h',
        marker=dict(
            color=vals_s,
            colorscale=[[0, '#1e1e3a'], [0.5, _NEG], [1, _POS]],
            showscale=False,
        ),
        text=[f'{v:.2f}' for v in vals_s],
        textposition='outside',
    ))
    label = 'mean(|SHAP|) — log scale' if log_target else 'mean(|SHAP|)'
    fig.update_layout(
        **_THEME,
        title='Feature Importance (mean |SHAP value|)',
        xaxis_title=label,
        margin=dict(l=10, r=60, t=50, b=20),
        height=max(350, 30 * len(orig_names)),
    )
    return fig


# ── Waterfall chart for one prediction ───────────────────────────────────────

def shap_waterfall_fig(
    shap_row:      np.ndarray,
    orig_names:    list[str],
    base_value:    float,
    prediction:    float,
    log_target:    bool = False,
) -> go.Figure:
    order    = np.argsort(np.abs(shap_row))[::-1][:12]
    names_s  = [orig_names[i] for i in order][::-1]
    vals_s   = shap_row[order][::-1]

    colors   = [_POS if v >= 0 else _NEG for v in vals_s]
    text     = [f'+{v:.2f}' if v >= 0 else f'{v:.2f}' for v in vals_s]

    base_label = f'Base: {np.expm1(base_value):,.0f}' if log_target else f'Base: {base_value:,.0f}'
    pred_label = f'Prediction: {prediction:,.0f}'

    fig = go.Figure(go.Bar(
        x=vals_s, y=names_s,
        orientation='h',
        marker_color=colors,
        text=text, textposition='outside',
    ))
    fig.add_vline(x=0, line_color='#475569', line_width=1)
    fig.update_layout(
        **_THEME,
        title=f'{pred_label}  (starting from {base_label})',
        xaxis_title='SHAP contribution',
        margin=dict(l=10, r=60, t=50, b=20),
        height=max(300, 32 * len(names_s)),
    )
    return fig


# ── SHAP scatter (dependence) ─────────────────────────────────────────────────

def shap_scatter_fig(
    shap_col:    np.ndarray,
    feature_col: pd.Series,
    feature_name:str,
) -> go.Figure:
    fig = go.Figure(go.Scatter(
        x=feature_col.values, y=shap_col,
        mode='markers',
        marker=dict(
            color=shap_col,
            colorscale=[[0, _NEG], [0.5, '#f8fafc'], [1, _POS]],
            opacity=0.7, size=6, showscale=True,
            colorbar=dict(title='SHAP'),
        ),
    ))
    fig.update_layout(
        **_THEME,
        title=f'SHAP dependence: {feature_name}',
        xaxis_title=feature_name,
        yaxis_title='SHAP value',
        margin=dict(l=20, r=20, t=50, b=20),
    )
    return fig
