from __future__ import annotations

import argparse

import json

import math

import os

import random

import shutil

import time

import warnings

import zipfile

from dataclasses import dataclass

from pathlib import Path

from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

import pandas as pd

from sklearn.decomposition import PCA

from sklearn.ensemble import ExtraTreesRegressor

from sklearn.linear_model import Ridge

from sklearn.metrics import mean_squared_error

from sklearn.pipeline import make_pipeline

from sklearn.preprocessing import StandardScaler

RSS_MISSING_VALUE = -110.0

RANDOM_STATE = 42

DEFAULT_MAX_APS = 128

DEFAULT_EPOCHS_FULL = 60

DEFAULT_EPOCHS_QUICK = 12

DEFAULT_BATCH_SIZE = 256

DEFAULT_D_MODEL = 64

DEFAULT_NHEAD = 4

DEFAULT_NUM_LAYERS = 2

DEFAULT_DROPOUT = 0.05

DEFAULT_LR = 1e-3

DEFAULT_WEIGHT_DECAY = 1e-4

DEFAULT_VAL_FRAC = 0.15

DEFAULT_PATIENCE = 8

DEFAULT_NOISE_SIGMA = 0.0  # set 0.05--0.15 later if you want feature-noise augmentation

def set_reproducibility(seed: int = RANDOM_STATE) -> None:
    random.seed(seed)
    np.random.seed(seed)
    try:
        import torch

        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
    except Exception:
        pass

def compute_error(x_pred, y_pred, x_true, y_true) -> np.ndarray:
    return np.sqrt((x_pred - x_true) ** 2 + (y_pred - y_true) ** 2)

def summarize_prediction_df(pred_df: pd.DataFrame, estimator_name: str, extra: Optional[dict] = None) -> dict:
    err = pred_df["error_m"].to_numpy()
    row = {
        "dataset": pred_df["dataset"].iloc[0],
        "group": pred_df["group"].iloc[0],
        "unit": pred_df["unit"].iloc[0],
        "estimator_display": estimator_name,
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

@dataclass
class TransformerConfig:
    method: str = "ap_tokens"  # ap_tokens or pca_tokens
    max_aps: int = DEFAULT_MAX_APS
    epochs: int = DEFAULT_EPOCHS_FULL
    batch_size: int = DEFAULT_BATCH_SIZE
    d_model: int = DEFAULT_D_MODEL
    nhead: int = DEFAULT_NHEAD
    num_layers: int = DEFAULT_NUM_LAYERS
    dropout: float = DEFAULT_DROPOUT
    lr: float = DEFAULT_LR
    weight_decay: float = DEFAULT_WEIGHT_DECAY
    val_frac: float = DEFAULT_VAL_FRAC
    patience: int = DEFAULT_PATIENCE
    noise_sigma: float = DEFAULT_NOISE_SIGMA
    pca_variance: float = 0.95
    pca_max_components: int = 96
    torch_threads: int = 4
    seed: int = RANDOM_STATE
    estimator_name: str = "Transformer"

def import_torch_or_raise():
    try:
        import torch
        import torch.nn as nn
        from torch.utils.data import DataLoader, Dataset, random_split

        return torch, nn, DataLoader, Dataset, random_split
    except Exception as e:
        raise ImportError(
            "PyTorch is required for the Transformer estimator. Install it in your environment, e.g.\n"
            "  pip install torch\n"
            "or use the official PyTorch command for your CUDA/CPU setup."
        ) from e

def fit_predict_transformer(
    X_train_raw: np.ndarray,
    M_train: np.ndarray,
    y_train: np.ndarray,
    X_test_raw: np.ndarray,
    M_test: np.ndarray,
    y_test: np.ndarray,
    cfg: TransformerConfig,
    metadata: dict,
) -> Tuple[pd.DataFrame, dict]:
    torch, nn, DataLoader, Dataset, random_split = import_torch_or_raise()

    if cfg.torch_threads and cfg.torch_threads > 0:
        try:
            torch.set_num_threads(int(cfg.torch_threads))
        except Exception:
            pass

    set_reproducibility(cfg.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # ---------- 1) Train-only RSS standardization ----------
    rss_scaler = StandardScaler(with_mean=True, with_std=True)
    X_train_scaled = rss_scaler.fit_transform(X_train_raw).astype(np.float32)
    X_test_scaled = rss_scaler.transform(X_test_raw).astype(np.float32)

    # ---------- 2) Train-only target normalization ----------
    y_mean = y_train.mean(axis=0).astype(np.float32)
    y_std = y_train.std(axis=0).astype(np.float32)
    y_std[y_std == 0] = 1.0

    y_train_norm = ((y_train - y_mean) / y_std).astype(np.float32)
    y_test_norm = ((y_test - y_mean) / y_std).astype(np.float32)

    # ---------- 3) Feature encoding ----------
    # Method A: AP tokens. Each token has [standardized_RSS, observed_mask].
    # Method B: PCA tokens. Each token is one standardized PC value.
    n_pca_components = 0
    if cfg.method == "ap_tokens":
        Xtr_tokens = np.stack([X_train_scaled, M_train.astype(np.float32)], axis=-1).astype(np.float32)
        Xte_tokens = np.stack([X_test_scaled, M_test.astype(np.float32)], axis=-1).astype(np.float32)
        in_channels = 2

    elif cfg.method == "pca_tokens":
        pca = PCA(n_components=cfg.pca_variance, svd_solver="full", whiten=False, random_state=cfg.seed)
        Xtr_pca = pca.fit_transform(X_train_scaled)
        Xte_pca = pca.transform(X_test_scaled)

        if cfg.pca_max_components and Xtr_pca.shape[1] > cfg.pca_max_components:
            Xtr_pca = Xtr_pca[:, : cfg.pca_max_components]
            Xte_pca = Xte_pca[:, : cfg.pca_max_components]

        n_pca_components = int(Xtr_pca.shape[1])
        Xtr_tokens = Xtr_pca[:, :, None].astype(np.float32)
        Xte_tokens = Xte_pca[:, :, None].astype(np.float32)
        in_channels = 1

    else:
        raise ValueError("cfg.method must be 'ap_tokens' or 'pca_tokens'.")

    # Optional noise augmentation on training token values only.
    # For AP tokens, add noise only to the RSS channel and keep the observed mask unchanged.
    if cfg.noise_sigma and cfg.noise_sigma > 0:
        rng = np.random.default_rng(cfg.seed)
        noisy = Xtr_tokens.copy()
        noisy[:, :, 0] += rng.normal(0.0, cfg.noise_sigma, size=noisy[:, :, 0].shape).astype(np.float32)
        Xtr_tokens = np.concatenate([Xtr_tokens, noisy], axis=0)
        y_train_norm = np.concatenate([y_train_norm, y_train_norm], axis=0)

    class FingerprintTokenDataset(Dataset):
        def __init__(self, X_tokens, y_norm):
            self.X = torch.tensor(X_tokens, dtype=torch.float32)
            self.y = torch.tensor(y_norm, dtype=torch.float32)

        def __len__(self):
            return self.X.shape[0]

        def __getitem__(self, idx):
            return self.X[idx], self.y[idx]

    class TokenTransformerRegressor(nn.Module):
        def __init__(
            self,
            n_tokens: int,
            in_channels: int,
            d_model: int,
            nhead: int,
            num_layers: int,
            dropout: float,
        ):
            super().__init__()
            self.value_proj = nn.Linear(in_channels, d_model)
            self.pos_embedding = nn.Parameter(torch.zeros(1, n_tokens, d_model))

            enc_layer = nn.TransformerEncoderLayer(
                d_model=d_model,
                nhead=nhead,
                dim_feedforward=4 * d_model,
                dropout=dropout,
                batch_first=True,
                activation="relu",
                norm_first=False,
            )
            self.encoder = nn.TransformerEncoder(enc_layer, num_layers=num_layers)
            self.norm = nn.LayerNorm(d_model)
            self.head = nn.Sequential(
                nn.Linear(d_model, d_model),
                nn.ReLU(),
                nn.Dropout(dropout),
                nn.Linear(d_model, 2),
            )

            nn.init.trunc_normal_(self.pos_embedding, std=0.02)

        def forward(self, x):
            # x: (B, F, C), where F is AP-token count or PCA-token count
            h = self.value_proj(x) + self.pos_embedding
            h = self.encoder(h)
            h = self.norm(h)
            h = h.mean(dim=1)
            return self.head(h)

    full_ds = FingerprintTokenDataset(Xtr_tokens, y_train_norm)
    n_total = len(full_ds)
    n_val = max(1, int(round(n_total * cfg.val_frac)))
    n_train2 = max(1, n_total - n_val)
    if n_train2 + n_val != n_total:
        n_val = n_total - n_train2

    g = torch.Generator().manual_seed(cfg.seed)
    train_ds, val_ds = random_split(full_ds, [n_train2, n_val], generator=g)
    test_ds = FingerprintTokenDataset(Xte_tokens, y_test_norm)

    train_loader = DataLoader(train_ds, batch_size=cfg.batch_size, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_ds, batch_size=cfg.batch_size, shuffle=False, num_workers=0)
    test_loader = DataLoader(test_ds, batch_size=cfg.batch_size, shuffle=False, num_workers=0)

    model = TokenTransformerRegressor(
        n_tokens=Xtr_tokens.shape[1],
        in_channels=in_channels,
        d_model=cfg.d_model,
        nhead=cfg.nhead,
        num_layers=cfg.num_layers,
        dropout=cfg.dropout,
    ).to(device)

    opt = torch.optim.AdamW(model.parameters(), lr=cfg.lr, weight_decay=cfg.weight_decay)
    loss_fn = nn.MSELoss()
    scheduler = torch.optim.lr_scheduler.CosineAnnealingWarmRestarts(
        opt, T_0=10, T_mult=2, eta_min=1e-5
    )

    best_val = float("inf")
    best_state = None
    bad_epochs = 0

    t0 = time.perf_counter()
    epochs_completed = 0

    for ep in range(int(cfg.epochs)):
        model.train()
        for xb, yb in train_loader:
            xb = xb.to(device)
            yb = yb.to(device)
            pred = model(xb)
            loss = loss_fn(pred, yb)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=5.0)
            opt.step()

        scheduler.step()

        model.eval()
        val_losses = []
        with torch.no_grad():
            for xb, yb in val_loader:
                xb = xb.to(device)
                yb = yb.to(device)
                val_losses.append(loss_fn(model(xb), yb).item())

        val_loss = float(np.mean(val_losses)) if val_losses else float("inf")
        epochs_completed = ep + 1

        if val_loss + 1e-9 < best_val:
            best_val = val_loss
            bad_epochs = 0
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
        else:
            bad_epochs += 1
            if bad_epochs >= cfg.patience:
                break

    if best_state is not None:
        model.load_state_dict(best_state)

    t1 = time.perf_counter()

    # ---------- 4) Predict and invert target normalization ----------
    model.eval()
    preds_norm = []
    trues_norm = []

    t2 = time.perf_counter()
    with torch.no_grad():
        for xb, yb in test_loader:
            xb = xb.to(device)
            p = model(xb).cpu().numpy()
            preds_norm.append(p)
            trues_norm.append(yb.numpy())
    t3 = time.perf_counter()

    preds_norm = np.vstack(preds_norm)
    y_pred = preds_norm * y_std + y_mean

    error_m = compute_error(y_pred[:, 0], y_pred[:, 1], y_test[:, 0], y_test[:, 1])

    pred_df = pd.DataFrame({
        "dataset": metadata["dataset"],
        "group": metadata["group"],
        "unit": metadata["unit"],
        "row_id": metadata["row_ids"],
        "estimator_display": cfg.estimator_name,
        "x_pred": y_pred[:, 0],
        "y_pred": y_pred[:, 1],
        "x_true": y_test[:, 0],
        "y_true": y_test[:, 1],
        "error_m": error_m,
        "transformer_method": cfg.method,
        "n_tokens": int(Xtr_tokens.shape[1]),
    })

    summary = summarize_prediction_df(
        pred_df,
        cfg.estimator_name,
        extra={
            "transformer_method": cfg.method,
            "n_tokens": int(Xtr_tokens.shape[1]),
            "n_pca_components": n_pca_components,
            "epochs_completed": int(epochs_completed),
            "best_val_loss": float(best_val),
            "train_time_s": float(t1 - t0),
            "infer_ms_per_scan": float((t3 - t2) / max(1, len(test_ds)) * 1000.0),
            "device": str(device),
            "d_model": int(cfg.d_model),
            "num_layers": int(cfg.num_layers),
            "nhead": int(cfg.nhead),
            "max_aps": int(cfg.max_aps),
            "noise_sigma": float(cfg.noise_sigma),
        },
    )

    return pred_df, summary, (model, rss_scaler, y_mean, y_std, device)
