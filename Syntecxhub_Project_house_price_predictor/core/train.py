"""Model pipeline building, training, and evaluation."""

from __future__ import annotations

import datetime
import os
from typing import Optional

import joblib
import numpy as np
import pandas as pd
from sklearn.compose     import ColumnTransformer
from sklearn.ensemble    import GradientBoostingRegressor, RandomForestRegressor
from sklearn.impute      import SimpleImputer
from sklearn.linear_model import Lasso, LinearRegression, Ridge
from sklearn.metrics     import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.pipeline    import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


MODELS = {
    'Linear Regression':    LinearRegression(),
    'Ridge':                Ridge(alpha=10.0),
    'Lasso':                Lasso(alpha=1.0, max_iter=5000),
    'Random Forest':        RandomForestRegressor(n_estimators=120, random_state=42, n_jobs=-1),
    'Gradient Boosting':    GradientBoostingRegressor(n_estimators=150, random_state=42,
                                                      learning_rate=0.08, max_depth=4),
}

_SAVE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'saved_models')


# ── Preprocessor ──────────────────────────────────────────────────────────────

def build_preprocessor(num_cols: list[str], cat_cols: list[str]) -> ColumnTransformer:
    transformers = []
    if num_cols:
        num_pipe = Pipeline([
            ('imputer', SimpleImputer(strategy='median')),
            ('scaler',  StandardScaler()),
        ])
        transformers.append(('num', num_pipe, num_cols))
    if cat_cols:
        cat_pipe = Pipeline([
            ('imputer', SimpleImputer(strategy='most_frequent')),
            ('encoder', OneHotEncoder(handle_unknown='ignore', sparse_output=False)),
        ])
        transformers.append(('cat', cat_pipe, cat_cols))
    return ColumnTransformer(transformers, remainder='drop')


def get_feature_names(preprocessor: ColumnTransformer,
                      num_cols: list[str], cat_cols: list[str]) -> list[str]:
    names = list(num_cols)
    if cat_cols and 'cat' in preprocessor.named_transformers_:
        enc = preprocessor.named_transformers_['cat']['encoder']
        names.extend(enc.get_feature_names_out(cat_cols).tolist())
    return names


# ── Training ──────────────────────────────────────────────────────────────────

def train_all(
    df:          pd.DataFrame,
    target_col:  str,
    num_cols:    list[str],
    cat_cols:    list[str],
    test_size:   float = 0.20,
    log_target:  bool  = False,
    cv_folds:    int   = 0,
) -> dict:
    """
    Train all models and return a results dict containing metrics, pipelines, and metadata.
    """
    feature_cols = num_cols + cat_cols
    df_clean = df[feature_cols + [target_col]].dropna(subset=[target_col])

    X = df_clean[feature_cols]
    y = df_clean[target_col].astype(float)

    if log_target:
        y_fit = np.log1p(y)
    else:
        y_fit = y

    X_train, X_test, y_train, y_test = train_test_split(
        X, y_fit, test_size=test_size, random_state=42
    )

    preprocessor = build_preprocessor(num_cols, cat_cols)
    preprocessor.fit(X_train)
    feature_names = get_feature_names(preprocessor, num_cols, cat_cols)

    rows       = []
    pipelines  = {}
    residuals  = {}

    for name, base_model in MODELS.items():
        pipeline = Pipeline([
            ('pre', preprocessor),
            ('mdl', base_model.__class__(**base_model.get_params())),
        ])
        pipeline.fit(X_train, y_train)
        y_pred_test = pipeline.predict(X_test)
        y_pred_train= pipeline.predict(X_train)

        # Back-transform for metrics
        if log_target:
            yt_true = np.expm1(y_test)
            yt_pred = np.expm1(y_pred_test)
        else:
            yt_true = y_test
            yt_pred = y_pred_test

        rmse = float(np.sqrt(mean_squared_error(yt_true, yt_pred)))
        mae  = float(mean_absolute_error(yt_true, yt_pred))
        r2   = float(r2_score(y_test, y_pred_test))   # R² on log scale if log_target
        mape = float(np.mean(np.abs((yt_true - yt_pred) / (np.abs(yt_true) + 1e-9))) * 100)

        cv_r2 = None
        if cv_folds >= 3:
            cv_scores = cross_val_score(pipeline, X_train, y_train,
                                        cv=cv_folds, scoring='r2', n_jobs=-1)
            cv_r2 = float(cv_scores.mean())

        # Residuals (in original scale, for prediction intervals)
        train_residuals = (
            np.expm1(y_pred_train) - np.expm1(y_train)
            if log_target
            else y_pred_train - y_train.values
        )

        rows.append({
            'Model':  name,
            'RMSE':   round(rmse, 2),
            'MAE':    round(mae, 2),
            'R²':     round(r2, 4),
            'MAPE %': round(mape, 2),
            'CV R²':  round(cv_r2, 4) if cv_r2 is not None else '—',
        })
        pipelines[name]  = pipeline
        residuals[name]  = train_residuals

    results_df = pd.DataFrame(rows).sort_values('RMSE')

    return {
        'results_df':    results_df,
        'pipelines':     pipelines,
        'preprocessor':  preprocessor,
        'feature_names': feature_names,
        'X_train':       X_train,
        'X_test':        X_test,
        'y_train':       y_train,
        'y_test':        y_test,
        'log_target':    log_target,
        'residuals':     residuals,
        'num_cols':      num_cols,
        'cat_cols':      cat_cols,
        'target_col':    target_col,
    }


# ── Prediction with interval ──────────────────────────────────────────────────

def predict_with_interval(
    pipeline:  Pipeline,
    X_input:   pd.DataFrame,
    residuals: np.ndarray,
    log_target: bool = False,
    confidence: float = 0.90,
) -> tuple[float, float, float]:
    """
    Return (prediction, lower_bound, upper_bound).
    Interval is based on the empirical distribution of training residuals.
    """
    raw = pipeline.predict(X_input)[0]

    alpha  = 1 - confidence
    lower_r = float(np.quantile(residuals, alpha / 2))
    upper_r = float(np.quantile(residuals, 1 - alpha / 2))

    if log_target:
        pred  = float(np.expm1(raw))
        lower = max(0.0, pred + lower_r)
        upper = pred + upper_r
    else:
        pred  = float(raw)
        lower = max(0.0, pred + lower_r)
        upper = pred + upper_r

    return pred, lower, upper


# ── Model persistence ─────────────────────────────────────────────────────────

def save_model(
    pipeline:     Pipeline,
    model_name:   str,
    metadata:     dict,
) -> str:
    os.makedirs(_SAVE_DIR, exist_ok=True)
    ts   = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    slug = model_name.lower().replace(' ', '_')
    path = os.path.join(_SAVE_DIR, f"{slug}_{ts}.joblib")
    joblib.dump({'pipeline': pipeline, 'metadata': metadata}, path)
    return path


def list_saved_models() -> list[dict]:
    if not os.path.isdir(_SAVE_DIR):
        return []
    models = []
    for fname in sorted(os.listdir(_SAVE_DIR), reverse=True):
        if fname.endswith('.joblib'):
            path = os.path.join(_SAVE_DIR, fname)
            try:
                obj  = joblib.load(path)
                models.append({'file': fname, 'path': path, **obj.get('metadata', {})})
            except Exception:
                pass
    return models


def load_model(path: str) -> dict:
    return joblib.load(path)
