"""
HouseLens — AI-powered Housing Price Prediction & Analysis
Run: streamlit run app.py
"""

import os
import warnings
warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from core import ingest, eda, train as tr, explain as ex, report as rp

# ══════════════════════════════════════════════════════════════════════════════
# PAGE CONFIG + GLOBAL CSS
# ══════════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title='HouseLens',
    page_icon='🏠',
    layout='wide',
    initial_sidebar_state='expanded',
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }

[data-testid="stSidebar"] {
  background: linear-gradient(175deg,#0f0f1a 0%,#0d0d20 100%) !important;
  border-right: 1px solid #1e1e3a;
}
[data-testid="stMetric"] {
  background: #0f0f1e !important; border: 1px solid #1e1e3a !important;
  border-radius: 10px !important; padding: .9rem !important;
}
[data-testid="stMetricValue"] { color: #a5b4fc !important; font-weight: 700 !important; }
[data-testid="stMetricLabel"] { color: #64748b !important; font-size: .7rem !important; text-transform: uppercase; }

.stTabs [data-baseweb="tab-list"] { gap: 3px; }
.stTabs [data-baseweb="tab"] {
  background: #0f0f1e !important; color: #94a3b8 !important;
  border: 1px solid #1e1e3a !important; border-radius: 8px !important;
}
.stTabs [aria-selected="true"] {
  background: #6366f1 !important; color: #fff !important; border-color: #6366f1 !important;
}
.stTabs [data-baseweb="tab-border"] { display: none !important; }

.stButton > button {
  background: #6366f1 !important; color: #fff !important;
  border: none !important; border-radius: 8px !important; font-weight: 600 !important;
}
.stButton > button:hover { background: #4f46e5 !important; }

.stTextInput input, .stSelectbox > div > div, .stNumberInput input {
  background: #0f0f1e !important; border-color: #2a2a4a !important; color: #e2e8f0 !important;
}

.warn-high   { background:rgba(239,68,68,.1); border:1px solid rgba(239,68,68,.4);
               border-radius:8px; padding:.6rem .9rem; margin-bottom:.4rem; }
.warn-medium { background:rgba(234,179,8,.08); border:1px solid rgba(234,179,8,.3);
               border-radius:8px; padding:.6rem .9rem; margin-bottom:.4rem; }
.warn-low    { background:rgba(99,102,241,.08); border:1px solid rgba(99,102,241,.3);
               border-radius:8px; padding:.6rem .9rem; margin-bottom:.4rem; }
.ok-card     { background:rgba(34,197,94,.08); border:1px solid rgba(34,197,94,.3);
               border-radius:8px; padding:.6rem .9rem; margin-bottom:.4rem; }
.role-tag    { display:inline-block; padding:.1rem .5rem; border-radius:99px; font-size:.72rem; }
.tag-target  { background:rgba(99,102,241,.2); color:#818cf8; }
.tag-num     { background:rgba(34,197,94,.15); color:#4ade80; }
.tag-cat     { background:rgba(236,72,153,.15); color:#f472b6; }
.tag-id      { background:rgba(71,85,105,.3);  color:#94a3b8; }
.predict-box { background:#0f0f1e; border:1px solid #2a2a4a; border-radius:12px; padding:1.5rem; }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# SESSION STATE
# ══════════════════════════════════════════════════════════════════════════════

_DEFAULTS = {
    'df':             None,
    'filename':       '',
    'roles':          {},
    'col_config':     {},
    'warnings':       [],
    'log_target':     False,
    'train_results':  None,   # dict from tr.train_all()
    'best_model':     None,
    'shap_values':    None,   # aggregated [n_rows × n_orig_feats]
    'shap_orig_names':None,
    'shap_base':      0.0,
    'report_text':    '',
}
for k, v in _DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

S = st.session_state   # shorthand

# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown(
        "<div style='padding:.5rem 0 .25rem'>"
        "<span style='font-size:1.4rem;font-weight:900;"
        "background:linear-gradient(135deg,#818cf8,#ec4899);"
        "-webkit-background-clip:text;-webkit-text-fill-color:transparent'>🏠 HouseLens</span><br>"
        "<span style='font-size:.7rem;color:#475569;text-transform:uppercase;letter-spacing:.1em'>"
        "Housing Price Prediction</span></div>",
        unsafe_allow_html=True,
    )
    st.markdown('---')

    uploaded = st.file_uploader(
        'Upload dataset', type=['csv', 'json', 'xlsx', 'xls'],
        label_visibility='collapsed',
    )

    if uploaded and uploaded.name != S.filename:
        with st.spinner('Loading…'):
            try:
                df = ingest.load_file(uploaded)
                S.df             = df
                S.filename       = uploaded.name
                S.roles          = ingest.auto_detect_roles(df)
                S.col_config     = ingest.apply_roles(df, S.roles)
                S.warnings       = []
                S.train_results  = None
                S.best_model     = None
                S.shap_values    = None
                S.report_text    = ''
                st.success(f"Loaded {len(df):,} rows × {len(df.columns)} cols")
            except Exception as e:
                st.error(str(e))

    if S.df is not None:
        st.markdown('---')
        st.markdown('### 📋 Dataset')
        c1, c2 = st.columns(2)
        c1.metric('Rows', f'{len(S.df):,}')
        c2.metric('Cols', len(S.df.columns))

        if S.train_results:
            best = S.train_results['results_df'].iloc[0]
            st.markdown('### 🏆 Best Model')
            st.metric('Model',  S.best_model or best['Model'])
            st.metric('R²',     f"{best['R²']:.3f}")
            st.metric('RMSE',   f"{best['RMSE']:,.0f}")

# ══════════════════════════════════════════════════════════════════════════════
# LANDING PAGE
# ══════════════════════════════════════════════════════════════════════════════

if S.df is None:
    st.markdown("""
<div style='text-align:center;padding:4rem 2rem'>
  <div style='font-size:3rem;font-weight:900;background:linear-gradient(135deg,#818cf8,#ec4899);
    -webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:.75rem'>
    🏠 HouseLens</div>
  <div style='font-size:1.15rem;color:#94a3b8;margin-bottom:2.5rem'>
    Upload your housing dataset and get instant<br>
    ML-powered price predictions with full explainability.
  </div>
  <div style='display:grid;grid-template-columns:repeat(4,1fr);gap:1rem;max-width:900px;margin:0 auto'>
    <div style='background:#0f0f1e;border:1px solid #1e1e3a;border-radius:12px;padding:1.25rem'>
      <div style='font-size:1.4rem'>🔍</div><div style='font-weight:600;margin:.4rem 0;font-size:.9rem'>Auto EDA</div>
      <div style='font-size:.78rem;color:#64748b'>Distributions, correlations & outlier detection</div>
    </div>
    <div style='background:#0f0f1e;border:1px solid #1e1e3a;border-radius:12px;padding:1.25rem'>
      <div style='font-size:1.4rem'>🤖</div><div style='font-weight:600;margin:.4rem 0;font-size:.9rem'>5 Models</div>
      <div style='font-size:.78rem;color:#64748b'>Linear, Ridge, Lasso, Random Forest, Gradient Boosting</div>
    </div>
    <div style='background:#0f0f1e;border:1px solid #1e1e3a;border-radius:12px;padding:1.25rem'>
      <div style='font-size:1.4rem'>💡</div><div style='font-weight:600;margin:.4rem 0;font-size:.9rem'>SHAP</div>
      <div style='font-size:.78rem;color:#64748b'>Feature importance & per-prediction explanation</div>
    </div>
    <div style='background:#0f0f1e;border:1px solid #1e1e3a;border-radius:12px;padding:1.25rem'>
      <div style='font-size:1.4rem'>🎛️</div><div style='font-weight:600;margin:.4rem 0;font-size:.9rem'>What-If</div>
      <div style='font-size:.78rem;color:#64748b'>Interactive sliders — live price updates</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)
    st.stop()

df = S.df

# ══════════════════════════════════════════════════════════════════════════════
# HEADER
# ══════════════════════════════════════════════════════════════════════════════

st.markdown(
    f"<div style='display:flex;align-items:center;gap:.75rem;margin-bottom:.25rem'>"
    f"<span style='font-size:1.2rem;font-weight:700'>{S.filename}</span>"
    f"<span style='background:#1e1e3a;color:#818cf8;font-size:.72rem;padding:.15rem .6rem;"
    f"border-radius:99px'>{len(df):,} rows · {len(df.columns)} cols</span>"
    f"</div>",
    unsafe_allow_html=True,
)

tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    '📂 Configure', '🔍 EDA', '🤖 Train Models',
    '💡 Explainability', '🎛️ Predict', '🗺️ Map', '📝 Report',
])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — CONFIGURE (column role mapping)
# ══════════════════════════════════════════════════════════════════════════════

with tab1:
    st.markdown('#### 🗂️ Column Roles')
    st.markdown(
        'Assign each column a role. **Target** = the value you want to predict (e.g. price). '
        'ID and freetext columns should be **Excluded**.'
    )

    ROLE_OPTIONS = ['target', 'numeric', 'categorical', 'lat', 'lon', 'id', 'exclude']
    ROLE_COLORS  = {
        'target':'tag-target','numeric':'tag-num','categorical':'tag-cat',
        'id':'tag-id','exclude':'tag-id','lat':'tag-num','lon':'tag-num',
    }

    updated_roles: dict[str, str] = {}
    n_cols = 3
    col_chunks = [list(df.columns)[i:i+n_cols] for i in range(0, len(df.columns), n_cols)]

    for chunk in col_chunks:
        cols_ui = st.columns(n_cols)
        for col_name, ui_col in zip(chunk, cols_ui):
            with ui_col:
                cur = S.roles.get(col_name, 'numeric')
                role = st.selectbox(
                    col_name,
                    ROLE_OPTIONS,
                    index=ROLE_OPTIONS.index(cur) if cur in ROLE_OPTIONS else 1,
                    key=f'role_{col_name}',
                )
                updated_roles[col_name] = role
                n_miss = int(df[col_name].isna().sum())
                n_uniq = df[col_name].nunique()
                tag = ROLE_COLORS.get(role, 'tag-id')
                st.markdown(
                    f"<span class='role-tag {tag}'>{role}</span>"
                    f"<span style='font-size:.7rem;color:#64748b;margin-left:.5rem'>"
                    f"{n_miss} missing · {n_uniq} unique</span>",
                    unsafe_allow_html=True,
                )

    if st.button('✓ Apply Role Mapping', use_container_width=True):
        S.roles      = updated_roles
        S.col_config = ingest.apply_roles(df, updated_roles)

        target_cols = S.col_config['target']
        S.warnings  = eda.quality_warnings(df, target_cols[0] if target_cols else '')
        S.train_results = None
        S.shap_values   = None
        st.rerun()

    st.markdown('---')

    # Preview + data quality
    col_left, col_right = st.columns([2, 1])

    with col_left:
        st.markdown('#### 📋 Data Preview')
        st.dataframe(df.head(8), use_container_width=True)

    with col_right:
        target_cols = S.col_config.get('target', [])
        num_cols    = S.col_config.get('numeric', [])
        cat_cols    = S.col_config.get('categorical', [])

        st.markdown('#### ✅ Role Summary')
        if target_cols:
            st.success(f"Target: **{target_cols[0]}**")
        else:
            st.error("No target column selected!")
        st.info(f"Numeric features: **{len(num_cols)}**")
        st.info(f"Categorical features: **{len(cat_cols)}**")

        if S.warnings:
            st.markdown('#### ⚠️ Data Quality')
            for w in S.warnings:
                css = f"warn-{w['level']}"
                icon = '🔴' if w['level'] == 'high' else ('🟡' if w['level'] == 'medium' else '🔵')
                st.markdown(
                    f"<div class='{css}'>{icon} {w['msg']}</div>",
                    unsafe_allow_html=True,
                )

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — EDA
# ══════════════════════════════════════════════════════════════════════════════

with tab2:
    target_col = S.col_config.get('target', [None])[0]
    num_cols   = S.col_config.get('numeric', [])
    cat_cols   = S.col_config.get('categorical', [])

    if not target_col:
        st.warning('Set the target column in the Configure tab first.')
        st.stop()

    # ── Target distribution ──────────────────────────────────────────────────
    st.markdown('#### 🎯 Target Variable Analysis')
    t_col, t_right = st.columns([2, 1])
    with t_col:
        log_opt = st.checkbox('Apply log-transform to target', value=S.log_target, key='log_eda')
        S.log_target = log_opt
        fig = eda.target_distribution_fig(df, target_col, log_scale=log_opt)
        st.plotly_chart(fig, use_container_width=True)
    with t_right:
        t = df[target_col].dropna()
        st.metric('Mean',   f'{t.mean():,.0f}')
        st.metric('Median', f'{t.median():,.0f}')
        st.metric('Std',    f'{t.std():,.0f}')
        st.metric('Skew',   f'{t.skew():.2f}')
        if abs(t.skew()) > 1.0 and not log_opt:
            st.markdown(
                "<div class='warn-medium'>🟡 Skewed distribution — "
                "enable log-transform above for better results.</div>",
                unsafe_allow_html=True,
            )

    st.markdown('---')

    # ── Correlation heatmap ──────────────────────────────────────────────────
    if num_cols:
        st.markdown('#### 🔗 Correlation Matrix')
        fig = eda.correlation_heatmap_fig(df, num_cols, target_col)
        st.plotly_chart(fig, use_container_width=True)
        st.markdown('---')

    # ── Feature distributions ────────────────────────────────────────────────
    if num_cols:
        st.markdown('#### 📊 Feature Distributions')
        fig = eda.feature_distributions_fig(df, num_cols)
        st.plotly_chart(fig, use_container_width=True)
        st.markdown('---')

    # ── Scatter: feature vs target ────────────────────────────────────────────
    if num_cols:
        st.markdown('#### 🔍 Feature vs Target')
        feat_pick = st.selectbox('Select feature:', num_cols + cat_cols, key='scatter_feat')
        if feat_pick in num_cols:
            fig = eda.scatter_vs_target_fig(df, feat_pick, target_col)
        else:
            fig = eda.boxplot_vs_target_fig(df, feat_pick, target_col)
        st.plotly_chart(fig, use_container_width=True)
        st.markdown('---')

    # ── Missing values ────────────────────────────────────────────────────────
    st.markdown('#### ❓ Missing Values')
    fig = eda.missing_value_fig(df)
    st.plotly_chart(fig, use_container_width=True)
    st.markdown('---')

    # ── Outlier summary ────────────────────────────────────────────────────────
    if num_cols:
        st.markdown('#### 🎯 Outlier Summary (IQR method)')
        out_df = eda.outlier_summary(df, num_cols)
        if not out_df.empty:
            st.dataframe(out_df, use_container_width=True, hide_index=True)
        else:
            st.success('No outliers detected in numeric columns.')

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — TRAIN MODELS
# ══════════════════════════════════════════════════════════════════════════════

with tab3:
    target_col = S.col_config.get('target', [None])[0]
    num_cols   = S.col_config.get('numeric', [])
    cat_cols   = S.col_config.get('categorical', [])

    if not target_col:
        st.warning('Configure column roles first.')
        st.stop()
    if not num_cols and not cat_cols:
        st.warning('Select at least one numeric or categorical feature column.')
        st.stop()

    # ── Training options ─────────────────────────────────────────────────────
    st.markdown('#### ⚙️ Training Settings')
    opt1, opt2, opt3 = st.columns(3)
    with opt1:
        test_size = st.slider('Test set size', 0.10, 0.40, 0.20, 0.05,
                              help='Fraction held out for evaluation')
    with opt2:
        cv_folds  = st.selectbox('Cross-validation folds',
                                 [0, 3, 5, 10], index=1,
                                 help='0 = disabled. Cross-val uses the training split only.')
    with opt3:
        use_log   = st.checkbox('Log-transform target', value=S.log_target,
                                help='Recommended for skewed price distributions')
        S.log_target = use_log

    st.markdown('**Features used:**')
    fc1, fc2 = st.columns(2)
    with fc1:
        st.markdown(f'Numeric ({len(num_cols)}): ' +
                    ', '.join(f'`{c}`' for c in num_cols[:8]) +
                    (' …' if len(num_cols) > 8 else ''))
    with fc2:
        st.markdown(f'Categorical ({len(cat_cols)}): ' +
                    ', '.join(f'`{c}`' for c in cat_cols[:8]) +
                    (' …' if len(cat_cols) > 8 else ''))

    st.markdown('---')

    if st.button('🚀 Train All 5 Models', use_container_width=True, type='primary'):
        with st.spinner('Training Linear Regression, Ridge, Lasso, Random Forest, Gradient Boosting…'):
            try:
                results = tr.train_all(
                    df=df, target_col=target_col,
                    num_cols=num_cols, cat_cols=cat_cols,
                    test_size=test_size, log_target=use_log, cv_folds=cv_folds,
                )
                S.train_results = results
                # Default best model = lowest RMSE
                S.best_model = results['results_df'].iloc[0]['Model']
                S.shap_values  = None  # reset SHAP cache
                S.report_text  = ''
                st.success('All models trained successfully!')
            except Exception as e:
                st.error(f'Training failed: {e}')
                import traceback; st.code(traceback.format_exc())

    # ── Results ──────────────────────────────────────────────────────────────
    if S.train_results:
        res = S.train_results
        rd  = res['results_df']

        st.markdown('#### 🏆 Model Comparison')

        # Colour the best row
        best_rmse = rd['RMSE'].min()

        # Metrics for best model
        best_row = rd.iloc[0]
        m1, m2, m3, m4 = st.columns(4)
        m1.metric('Best Model',  best_row['Model'])
        m2.metric('R²',          f"{best_row['R²']:.4f}")
        m3.metric('RMSE',        f"{best_row['RMSE']:,.0f}")
        m4.metric('MAE',         f"{best_row['MAE']:,.0f}")

        st.dataframe(
            rd.style.highlight_min(subset=['RMSE'], color='rgba(99,102,241,0.25)')
                    .highlight_max(subset=['R²'],   color='rgba(99,102,241,0.25)'),
            use_container_width=True, hide_index=True,
        )

        # Bar chart comparison
        fig_bar = px.bar(
            rd, x='Model', y='R²',
            color='R²', color_continuous_scale='Viridis',
            title='R² Score by Model (higher is better)',
        )
        fig_bar.update_layout(
            template='plotly_dark', paper_bgcolor='#07071a', plot_bgcolor='#07071a',
            margin=dict(l=20, r=20, t=50, b=20),
        )
        st.plotly_chart(fig_bar, use_container_width=True)

        # Residual plot for best model
        st.markdown('---')
        st.markdown('#### 📉 Residual Analysis')
        res_model = st.selectbox(
            'Model for residual plot:', list(res['pipelines'].keys()),
            index=0, key='resid_model_sel',
        )
        pipe = res['pipelines'][res_model]
        X_t  = res['X_test']
        y_t  = res['y_test']
        y_pred = pipe.predict(X_t)

        if use_log:
            y_actual = np.expm1(y_t)
            y_fitted = np.expm1(y_pred)
        else:
            y_actual = y_t
            y_fitted = y_pred

        residuals_plot = y_fitted - np.array(y_actual)

        r_c1, r_c2 = st.columns(2)
        with r_c1:
            fig_rv = go.Figure()
            fig_rv.add_trace(go.Scatter(
                x=y_fitted, y=residuals_plot,
                mode='markers', marker=dict(color='#6366f1', opacity=0.5, size=5),
                name='Residual',
            ))
            fig_rv.add_hline(y=0, line_dash='dash', line_color='#ec4899')
            fig_rv.update_layout(
                template='plotly_dark', paper_bgcolor='#07071a', plot_bgcolor='#07071a',
                title='Predicted vs Residuals',
                xaxis_title='Predicted', yaxis_title='Residual',
                margin=dict(l=20, r=20, t=50, b=20),
            )
            st.plotly_chart(fig_rv, use_container_width=True)
        with r_c2:
            fig_rh = go.Figure(go.Histogram(
                x=residuals_plot, nbinsx=40,
                marker_color='#ec4899', opacity=0.8,
            ))
            fig_rh.update_layout(
                template='plotly_dark', paper_bgcolor='#07071a', plot_bgcolor='#07071a',
                title='Residual Distribution',
                xaxis_title='Residual', yaxis_title='Count',
                margin=dict(l=20, r=20, t=50, b=20),
            )
            st.plotly_chart(fig_rh, use_container_width=True)

        # Actual vs predicted
        fig_ap = go.Figure()
        fig_ap.add_trace(go.Scatter(
            x=list(y_actual), y=list(y_fitted),
            mode='markers', marker=dict(color='#6366f1', opacity=0.6, size=5),
            name='Predictions',
        ))
        lim = [min(min(y_actual), min(y_fitted)), max(max(y_actual), max(y_fitted))]
        fig_ap.add_trace(go.Scatter(
            x=lim, y=lim, mode='lines', line=dict(color='#ec4899', dash='dash'),
            name='Perfect prediction',
        ))
        fig_ap.update_layout(
            template='plotly_dark', paper_bgcolor='#07071a', plot_bgcolor='#07071a',
            title='Actual vs Predicted',
            xaxis_title='Actual', yaxis_title='Predicted',
            margin=dict(l=20, r=20, t=50, b=20),
        )
        st.plotly_chart(fig_ap, use_container_width=True)

        # Deploy selection + model save
        st.markdown('---')
        st.markdown('#### 💾 Deploy a Model')
        dc1, dc2 = st.columns([2, 1])
        with dc1:
            deploy_choice = st.selectbox(
                'Select model to use for predictions:',
                list(res['pipelines'].keys()),
                index=list(res['pipelines'].keys()).index(S.best_model)
                if S.best_model in res['pipelines'] else 0,
            )
        with dc2:
            st.write('')
            if st.button('Set as active model'):
                S.best_model = deploy_choice
                S.shap_values = None
                st.success(f'Active model: **{deploy_choice}**')

        if st.button('💾 Save model to disk'):
            meta = {
                'model_name':  deploy_choice,
                'target_col':  target_col,
                'num_cols':    num_cols,
                'cat_cols':    cat_cols,
                'log_target':  use_log,
                'r2':          float(rd[rd['Model'] == deploy_choice]['R²'].iloc[0]),
                'rmse':        float(rd[rd['Model'] == deploy_choice]['RMSE'].iloc[0]),
            }
            path = tr.save_model(res['pipelines'][deploy_choice], deploy_choice, meta)
            st.success(f'Saved → `{path}`')

# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — EXPLAINABILITY
# ══════════════════════════════════════════════════════════════════════════════

with tab4:
    if not S.train_results:
        st.info('Train models first (Tab 3).')
        st.stop()

    res       = S.train_results
    target_col= res['target_col']
    num_cols  = res['num_cols']
    cat_cols  = res['cat_cols']
    feat_names= res['feature_names']
    best_m    = S.best_model or res['results_df'].iloc[0]['Model']

    st.markdown(f'#### 💡 SHAP Explainability — {best_m}')
    shap_model_sel = st.selectbox(
        'Model to explain:', list(res['pipelines'].keys()),
        index=list(res['pipelines'].keys()).index(best_m),
        key='shap_model_sel',
    )

    if st.button('🔬 Compute SHAP values', use_container_width=True):
        with st.spinner('Computing SHAP values (sampling up to 500 rows)…'):
            try:
                X_sample = res['X_train']
                sv, base_val = ex.compute_shap(
                    shap_model_sel, res['pipelines'][shap_model_sel],
                    X_sample, feat_names, max_rows=500,
                )
                agg_sv, orig_names = ex.aggregate_to_original(sv, feat_names, num_cols, cat_cols)
                S.shap_values    = agg_sv
                S.shap_orig_names= orig_names
                S.shap_base      = base_val
                st.success('SHAP values computed!')
            except ImportError:
                st.error('Install shap: `pip install shap`')
            except Exception as e:
                st.error(f'SHAP error: {e}')
                import traceback; st.code(traceback.format_exc())

    if S.shap_values is not None:
        sv   = S.shap_values
        orig = S.shap_orig_names

        # Summary bar
        st.markdown('##### Feature Importance (mean |SHAP|)')
        fig_sum = ex.shap_summary_fig(sv, orig, log_target=res['log_target'])
        st.plotly_chart(fig_sum, use_container_width=True)

        # Feature importance dict for report
        mean_abs = {orig[i]: float(np.abs(sv[:, i]).mean()) for i in range(len(orig))}

        st.markdown('---')
        st.markdown('##### SHAP Dependence Plot')
        dep_col = st.selectbox('Feature:', orig, key='shap_dep_col')
        col_idx = orig.index(dep_col)
        if dep_col in num_cols:
            X_vals = res['X_train'][dep_col].reset_index(drop=True)[:len(sv)]
            fig_dep = ex.shap_scatter_fig(sv[:, col_idx], X_vals, dep_col)
            st.plotly_chart(fig_dep, use_container_width=True)
        else:
            st.info('Dependence scatter is available for numeric features.')

        st.markdown('---')
        st.markdown('##### Individual Prediction Explanation (Waterfall)')
        row_idx = st.slider('Row index in training set:', 0, len(sv) - 1, 0, key='wfall_row')
        shap_row = sv[row_idx]
        pipe_sel = res['pipelines'][shap_model_sel]
        raw_pred = pipe_sel.predict(res['X_train'].iloc[[row_idx]])[0]
        pred_val = float(np.expm1(raw_pred)) if res['log_target'] else float(raw_pred)
        base_disp= float(np.expm1(S.shap_base)) if res['log_target'] else float(S.shap_base)

        fig_wf = ex.shap_waterfall_fig(
            shap_row, orig, S.shap_base, pred_val, log_target=res['log_target']
        )
        st.plotly_chart(fig_wf, use_container_width=True)
        st.caption(
            f'Baseline (average prediction): **{base_disp:,.0f}** → '
            f'This prediction: **{pred_val:,.0f}**'
        )

# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — INTERACTIVE PREDICTION
# ══════════════════════════════════════════════════════════════════════════════

with tab5:
    if not S.train_results:
        st.info('Train models first (Tab 3).')
        st.stop()

    res        = S.train_results
    target_col = res['target_col']
    num_cols   = res['num_cols']
    cat_cols   = res['cat_cols']
    best_m     = S.best_model or res['results_df'].iloc[0]['Model']
    pipeline   = res['pipelines'][best_m]
    log_target = res['log_target']
    residuals  = res['residuals'][best_m]

    st.markdown(f'#### 🎛️ What-If Predictor — {best_m}')
    st.caption('Adjust feature values to see how the predicted price changes.')

    p_left, p_right = st.columns([1, 1], gap='large')

    input_vals: dict = {}
    with p_left:
        st.markdown('**Numeric features**')
        for col in num_cols:
            col_data = df[col].dropna()
            mn, mx   = float(col_data.min()), float(col_data.max())
            med      = float(col_data.median())
            step     = max((mx - mn) / 200, 0.01)
            input_vals[col] = st.slider(
                col, min_value=mn, max_value=mx, value=med, step=step,
                key=f'pred_num_{col}',
            )
        if not num_cols:
            st.info('No numeric features configured.')

    with p_right:
        st.markdown('**Categorical features**')
        for col in cat_cols:
            options = sorted(df[col].dropna().unique().tolist())
            mode    = df[col].mode().iloc[0] if not df[col].mode().empty else options[0]
            input_vals[col] = st.selectbox(
                col, options,
                index=options.index(mode) if mode in options else 0,
                key=f'pred_cat_{col}',
            )
        if not cat_cols:
            st.info('No categorical features configured.')

    # ── Live prediction ───────────────────────────────────────────────────────
    st.markdown('---')
    X_pred = pd.DataFrame([input_vals])[num_cols + cat_cols]

    try:
        pred, lower, upper = tr.predict_with_interval(
            pipeline, X_pred, residuals, log_target=log_target, confidence=0.90
        )

        st.markdown('<div class="predict-box">', unsafe_allow_html=True)
        pc1, pc2, pc3 = st.columns(3)
        pc1.metric('📍 Predicted Price', f'{pred:,.0f}')
        pc2.metric('📉 Lower (90% CI)',  f'{lower:,.0f}')
        pc3.metric('📈 Upper (90% CI)',  f'{upper:,.0f}')

        # Confidence gauge bar
        full_range = max(upper - lower, 1)
        centre_pct = (pred - lower) / full_range * 100
        st.markdown(
            f"<div style='background:#1e1e3a;border-radius:8px;height:10px;margin:.5rem 0;'>"
            f"<div style='background:linear-gradient(90deg,#6366f1,#ec4899);"
            f"width:{min(centre_pct, 95):.0f}%;height:100%;border-radius:8px'></div></div>"
            f"<div style='font-size:.72rem;color:#64748b;text-align:center'>"
            f"90% confidence interval: {lower:,.0f} – {upper:,.0f}</div>",
            unsafe_allow_html=True,
        )
        st.markdown('</div>', unsafe_allow_html=True)

        # Per-prediction SHAP waterfall if computed
        if S.shap_values is not None and S.shap_orig_names:
            st.markdown('##### Why this price?')
            pipe_expl = res['pipelines'][best_m]
            pre       = pipe_expl.named_steps['pre']
            mdl       = pipe_expl.named_steps['mdl']
            X_pre_one = pre.transform(X_pred)

            try:
                import shap
                is_tree = best_m in ('Random Forest', 'Gradient Boosting')
                if is_tree:
                    expln = shap.TreeExplainer(mdl)
                    sv1   = expln.shap_values(X_pre_one)
                    base1 = float(expln.expected_value)
                else:
                    feat_arr = pre.transform(res['X_train'][:100])
                    mask = shap.maskers.Independent(feat_arr, max_samples=50)
                    expln = shap.LinearExplainer(mdl, mask)
                    sv1   = expln.shap_values(X_pre_one)
                    base1 = float(expln.expected_value)

                if isinstance(sv1, list): sv1 = sv1[0]
                agg1, _ = ex.aggregate_to_original(sv1, res['feature_names'], num_cols, cat_cols)
                fig_wf_pred = ex.shap_waterfall_fig(
                    agg1[0], S.shap_orig_names, base1, pred, log_target=log_target,
                )
                st.plotly_chart(fig_wf_pred, use_container_width=True)
            except Exception:
                pass   # SHAP for this row failed — skip gracefully

    except Exception as e:
        st.error(f'Prediction error: {e}')

# ══════════════════════════════════════════════════════════════════════════════
# TAB 6 — MAP (conditional on lat/lon columns)
# ══════════════════════════════════════════════════════════════════════════════

with tab6:
    lat_cols = S.col_config.get('lat', [])
    lon_cols = S.col_config.get('lon', [])
    target_col = S.col_config.get('target', [None])[0]

    if not lat_cols or not lon_cols:
        st.info(
            'No latitude/longitude columns detected.\n\n'
            'Mark columns with the **lat** and **lon** roles in the Configure tab '
            'to enable geographic visualization.'
        )
        st.stop()

    lat_col = lat_cols[0]
    lon_col = lon_cols[0]

    map_df = df[[lat_col, lon_col]].copy()
    if target_col and target_col in df.columns:
        map_df[target_col] = df[target_col]

    map_df = map_df.dropna(subset=[lat_col, lon_col])

    # Add predictions if model trained
    if S.train_results and target_col:
        res      = S.train_results
        best_m   = S.best_model or res['results_df'].iloc[0]['Model']
        pipeline = res['pipelines'][best_m]
        num_c    = res['num_cols']
        cat_c    = res['cat_cols']
        feat_c   = num_c + cat_c

        shared_idx = df.index[df[feat_c].notna().all(axis=1)]
        X_all = df.loc[shared_idx, feat_c]
        y_hat = pipeline.predict(X_all)
        if res['log_target']:
            y_hat = np.expm1(y_hat)

        map_df = map_df.loc[map_df.index.isin(shared_idx)].copy()
        map_df['predicted'] = y_hat[map_df.index.isin(shared_idx)]

        if target_col in map_df.columns:
            map_df['delta'] = map_df['predicted'] - map_df[target_col]

    st.markdown('#### 🗺️ Geographic Price Map')
    map_mode = st.radio(
        'Colour by:', ['Actual price', 'Predicted price', 'Over/Under valued'],
        horizontal=True,
    )

    if map_mode == 'Actual price' and target_col in map_df.columns:
        color_col   = target_col
        color_scale = 'Viridis'
        title       = f'Actual {target_col}'
    elif map_mode == 'Predicted price' and 'predicted' in map_df.columns:
        color_col   = 'predicted'
        color_scale = 'Viridis'
        title       = 'Predicted price'
    elif 'delta' in map_df.columns:
        color_col   = 'delta'
        color_scale = 'RdBu'
        title       = 'Over(+) / Under(−) valued vs prediction'
    else:
        color_col   = lat_col
        color_scale = 'Viridis'
        title       = 'Properties'

    fig_map = px.scatter_mapbox(
        map_df.sample(min(5000, len(map_df))),
        lat=lat_col, lon=lon_col,
        color=color_col, color_continuous_scale=color_scale,
        zoom=10, height=600,
        title=title, mapbox_style='open-street-map',
        opacity=0.7, size_max=8,
    )
    fig_map.update_layout(
        paper_bgcolor='#07071a', margin=dict(l=0, r=0, t=50, b=0),
    )
    st.plotly_chart(fig_map, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 7 — REPORT
# ══════════════════════════════════════════════════════════════════════════════

with tab7:
    if not S.train_results:
        st.info('Train models first (Tab 3) to generate a report.')
        st.stop()

    res        = S.train_results
    target_col = res['target_col']
    num_cols   = res['num_cols']
    cat_cols   = res['cat_cols']
    best_m     = S.best_model or res['results_df'].iloc[0]['Model']

    # Feature importance from SHAP if available, else fall back to RF feature importance
    if S.shap_values is not None and S.shap_orig_names:
        fi = {S.shap_orig_names[i]: float(np.abs(S.shap_values[:, i]).mean())
              for i in range(len(S.shap_orig_names))}
    else:
        # Fallback: use model feature importances if available
        mdl = res['pipelines'][best_m].named_steps['mdl']
        feat_names = res['feature_names']
        if hasattr(mdl, 'feature_importances_'):
            fi = {}
            orig = num_cols + cat_cols
            for i, name in enumerate(orig):
                idxs = [j for j, fn in enumerate(feat_names)
                        if fn == name or fn.startswith(f'{name}_')]
                fi[name] = float(mdl.feature_importances_[idxs].sum()) if idxs else 0.0
        elif hasattr(mdl, 'coef_'):
            fi = {}
            orig = num_cols + cat_cols
            coef = np.abs(mdl.coef_)
            for i, name in enumerate(orig):
                idxs = [j for j, fn in enumerate(feat_names)
                        if fn == name or fn.startswith(f'{name}_')]
                fi[name] = float(coef[idxs].mean()) if idxs else 0.0
        else:
            fi = {c: 1.0 for c in (num_cols + cat_cols)}

    if st.button('📝 Generate Report', use_container_width=True):
        report_text = rp.generate_report(
            df=df, target_col=target_col,
            num_cols=num_cols, cat_cols=cat_cols,
            results_df=res['results_df'],
            feature_importance=fi,
            warnings=S.warnings,
            log_target=res['log_target'],
            best_model=best_m,
        )
        S.report_text = report_text

    if S.report_text:
        st.markdown(S.report_text)
        st.markdown('---')
        r1, r2 = st.columns(2)
        r1.download_button(
            '⬇️ Download Markdown Report',
            data=S.report_text,
            file_name=f'houselens_report_{target_col}.md',
            mime='text/markdown',
            use_container_width=True,
        )
        r2.download_button(
            '⬇️ Download as Text',
            data=S.report_text,
            file_name=f'houselens_report_{target_col}.txt',
            mime='text/plain',
            use_container_width=True,
        )
