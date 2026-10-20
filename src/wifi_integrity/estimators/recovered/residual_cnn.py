from __future__ import annotations

import argparse

import json

import os

import random

import shutil

import time

import warnings

import zipfile

from pathlib import Path

from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

import pandas as pd

from sklearn.model_selection import train_test_split

from sklearn.preprocessing import StandardScaler

RSS_MISSING_VALUE = -110.0

RANDOM_STATE = 42

DEFAULT_MAX_APS = 128

DEFAULT_BATCH_SIZE = 256

DEFAULT_EPOCHS_QUICK = 15

DEFAULT_EPOCHS_FULL = 60

DEFAULT_PATIENCE = 8

DEFAULT_VAL_FRAC = 0.15

def set_reproducibility(seed: int = RANDOM_STATE) -> None:
    random.seed(seed)
    np.random.seed(seed)
    os.environ.setdefault("PYTHONHASHSEED", str(seed))
    try:
        import tensorflow as tf
        tf.keras.utils.set_random_seed(seed)
        try:
            tf.config.experimental.enable_op_determinism()
        except Exception:
            pass
    except Exception:
        pass

def compute_error(pred_xy: np.ndarray, true_xy: np.ndarray) -> np.ndarray:
    return np.sqrt(np.sum((pred_xy[:, :2] - true_xy[:, :2]) ** 2, axis=1))

def make_prediction_frame(metadata: dict, pred_xy: np.ndarray, y_test: np.ndarray, estimator_display: str) -> pd.DataFrame:
    error_m = compute_error(pred_xy, y_test)
    return pd.DataFrame({
        "dataset": metadata["dataset"],
        "group": metadata["group"],
        "unit": metadata["unit"],
        "row_id": metadata["row_ids"],
        "estimator_display": estimator_display,
        "x_pred": pred_xy[:, 0],
        "y_pred": pred_xy[:, 1],
        "x_true": y_test[:, 0],
        "y_true": y_test[:, 1],
        "error_m": error_m,
    })

def summarize_prediction_df(pred_df: pd.DataFrame, estimator_display: str, extra: Optional[dict] = None) -> dict:
    err = pred_df["error_m"].to_numpy()
    row = {
        "dataset": pred_df["dataset"].iloc[0],
        "group": pred_df["group"].iloc[0],
        "unit": pred_df["unit"].iloc[0],
        "estimator_display": estimator_display,
        "n_test": int(len(pred_df)),
        "median_error_m": float(np.median(err)),
        "mean_error_m": float(np.mean(err)),
        "rmse_error_m": float(np.sqrt(np.mean(err ** 2))),
        "p90_error_m": float(np.percentile(err, 90)),
        "p95_error_m": float(np.percentile(err, 95)),
    }
    if extra:
        row.update(extra)
    return row

def import_tensorflow_or_raise():
    try:
        import tensorflow as tf
        return tf
    except Exception as e:
        raise ImportError(
            "TensorFlow is required for the attached deep estimators. Install it with:\n"
            "  pip install tensorflow\n"
            "or use a TensorFlow version compatible with your Python environment."
        ) from e

def euclidean_loss_tf(tf):
    def loss(y_true, y_pred):
        err = y_true - y_pred
        return tf.reduce_mean(tf.sqrt(tf.reduce_sum(tf.square(err), axis=1) + 1e-8))
    return loss

def build_dnn(tf, n_features: int, dropout: float = 0.20):
    """Dense NN adapted from Script2, with scaling handled outside the model."""
    return tf.keras.Sequential([
        tf.keras.Input(shape=(n_features,)),
        tf.keras.layers.Dense(128, activation="tanh"),
        tf.keras.layers.Dropout(dropout),
        tf.keras.layers.Dense(128, activation="tanh"),
        tf.keras.layers.Dropout(dropout),
        tf.keras.layers.Dense(128, activation="tanh"),
        tf.keras.layers.Dropout(dropout),
        tf.keras.layers.Dense(2),
    ])

def build_cnn1d(tf, n_features: int, dropout: float = 0.20):
    """Conv1D/LeNet-style model adapted from Script2."""
    return tf.keras.Sequential([
        tf.keras.Input(shape=(n_features,)),
        tf.keras.layers.Reshape((n_features, 1)),
        tf.keras.layers.Conv1D(16, 7, activation="tanh", padding="same"),
        tf.keras.layers.Conv1D(16, 7, activation="tanh", padding="same"),
        tf.keras.layers.Conv1D(16, 7, activation="tanh", padding="same"),
        tf.keras.layers.Flatten(),
        tf.keras.layers.Dense(128, activation="tanh"),
        tf.keras.layers.Dropout(dropout),
        tf.keras.layers.Dense(128, activation="tanh"),
        tf.keras.layers.Dropout(dropout),
        tf.keras.layers.Dense(128, activation="tanh"),
        tf.keras.layers.Dropout(dropout),
        tf.keras.layers.Dense(2),
    ])

def build_residual_cnn(tf, n_features: int, dropout: float = 0.15):
    """
    Safe residual CNN adapted from the Experiment model in Script2.
    A 1x1 projection is used so skip tensors have matching channel dimensions.
    """
    inp = tf.keras.Input(shape=(n_features,))
    x0 = tf.keras.layers.Reshape((n_features, 1))(inp)
    x0p = tf.keras.layers.Conv1D(16, 1, padding="same", activation=None)(x0)

    x1 = tf.keras.layers.Conv1D(16, 7, activation="tanh", padding="same")(x0)
    x1 = tf.keras.layers.Add()([x1, x0p])

    x2 = tf.keras.layers.Conv1D(16, 7, activation="tanh", padding="same")(x1)
    x2 = tf.keras.layers.Add()([x2, x1])

    x3 = tf.keras.layers.Conv1D(16, 7, activation="tanh", padding="same")(x2)
    x3 = tf.keras.layers.Add()([x3, x2])

    x = tf.keras.layers.Flatten()(x3)
    d1 = tf.keras.layers.Dense(128, activation="tanh")(x)
    d1 = tf.keras.layers.Dropout(dropout)(d1)
    d2 = tf.keras.layers.Dense(128, activation="tanh")(d1)
    d2 = tf.keras.layers.Dropout(dropout)(d2)
    d3 = tf.keras.layers.Dense(128, activation="tanh")(d2)
    d3 = tf.keras.layers.Concatenate()([d3, d1])
    out = tf.keras.layers.Dense(2)(d3)
    return tf.keras.Model(inp, out)

def fit_predict_tf_estimator(
    estimator_key: str,
    estimator_display: str,
    X_train_raw: np.ndarray,
    y_train: np.ndarray,
    X_test_raw: np.ndarray,
    y_test: np.ndarray,
    metadata: dict,
    epochs: int,
    batch_size: int,
    patience: int,
    val_frac: float,
    lr: float,
    dropout: float,
    loss_name: str,
) -> Tuple[pd.DataFrame, dict]:
    """Train one TensorFlow estimator and return predictions in the ESWA schema."""
    tf = import_tensorflow_or_raise()
    set_reproducibility(RANDOM_STATE)

    # Train-only RSS standardization, following the important lesson in Script1.
    x_scaler = StandardScaler(with_mean=True, with_std=True)
    X_train = x_scaler.fit_transform(X_train_raw).astype(np.float32)
    X_test = x_scaler.transform(X_test_raw).astype(np.float32)

    # Target normalization stabilizes deep training across datasets/buildings.
    y_scaler = StandardScaler(with_mean=True, with_std=True)
    y_train_sc = y_scaler.fit_transform(y_train).astype(np.float32)

    X_tr, X_val, y_tr, y_val = train_test_split(
        X_train,
        y_train_sc,
        test_size=val_frac,
        random_state=RANDOM_STATE,
        shuffle=True,
    )

    n_features = X_train.shape[1]
    if estimator_key == "residual_cnn":
        model = build_residual_cnn(tf, n_features=n_features, dropout=dropout)
    elif estimator_key == "cnn1d":
        model = build_cnn1d(tf, n_features=n_features, dropout=dropout)
    elif estimator_key == "dnn":
        model = build_dnn(tf, n_features=n_features, dropout=dropout)
    else:
        raise ValueError(f"Unknown TensorFlow estimator: {estimator_key}")

    if loss_name == "euclidean":
        loss_fn = euclidean_loss_tf(tf)
    elif loss_name == "mse":
        loss_fn = "mse"
    else:
        raise ValueError("loss_name must be 'mse' or 'euclidean'.")

    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=lr),
        loss=loss_fn,
        metrics=["mse"],
    )

    callbacks = [
        tf.keras.callbacks.EarlyStopping(
            monitor="val_loss",
            patience=patience,
            start_from_epoch=min(10, max(0, epochs // 4)),
            restore_best_weights=True,
        ),
        tf.keras.callbacks.ReduceLROnPlateau(
            monitor="val_loss",
            factor=0.5,
            patience=max(3, patience // 2),
            min_lr=1e-5,
            verbose=0,
        ),
    ]

    t0 = time.perf_counter()
    history = model.fit(
        X_tr,
        y_tr,
        validation_data=(X_val, y_val),
        epochs=epochs,
        batch_size=batch_size,
        verbose=1,
        callbacks=callbacks,
    )
    t1 = time.perf_counter()

    pred_sc = model.predict(X_test, batch_size=batch_size, verbose=0).astype(np.float32)
    pred_xy = y_scaler.inverse_transform(pred_sc).astype(np.float32)

    pred_df = make_prediction_frame(metadata, pred_xy, y_test, estimator_display)
    best_val = float(np.min(history.history.get("val_loss", [np.nan])))
    epochs_completed = int(len(history.history.get("loss", [])))

    summary = summarize_prediction_df(
        pred_df,
        estimator_display,
        extra={
            "source_notebook_family": "attached_tensorflow",
            "estimator_key": estimator_key,
            "n_features": int(n_features),
            "epochs_completed": epochs_completed,
            "best_val_loss": best_val,
            "train_time_s": float(t1 - t0),
            "batch_size": int(batch_size),
            "loss_name": loss_name,
            "lr": float(lr),
            "dropout": float(dropout),
        },
    )
    return pred_df, summary, (model, x_scaler, y_scaler)
