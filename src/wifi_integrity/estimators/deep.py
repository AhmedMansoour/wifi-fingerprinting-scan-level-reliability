"""Native adapters for the study's recovered deep training functions."""
from __future__ import annotations
import numpy as np
from .base import BasePositionEstimator


def selected_ap_indices(data, max_aps=128):
    counts = data.train_observed.astype(bool).sum(axis=0)
    names = data.ap_names or tuple(f'AP_{i:08d}' for i in range(len(counts)))
    return np.array(sorted(range(len(counts)), key=lambda i: (-counts[i], names[i]))[:max_aps])


class DeepCoordinateEstimator(BasePositionEstimator):
    family = 'deep'

    def __init__(self, estimator_id, *, seed=42, epochs=60, max_aps=128, batch_size=256):
        super().__init__(seed=seed)
        if estimator_id not in {'transformer_ap', 'residual_cnn'}:
            raise ValueError(estimator_id)
        self.estimator_id = estimator_id
        self.estimator_label = 'AP-token Transformer' if estimator_id == 'transformer_ap' else 'Residual CNN'
        self.epochs, self.max_aps, self.batch_size = epochs, max_aps, batch_size

    def fit(self, data):
        if len(data.train_xy) < 8:
            raise ValueError('At least eight training scans are required.')
        self.columns = selected_ap_indices(data, self.max_aps)
        x = data.train_rss[:, self.columns].astype(np.float32)
        mask = data.train_observed[:, self.columns]
        meta = dict(dataset=data.dataset, group=data.group, unit=data.unit_label, row_ids=['training-probe'])
        # The legacy functions also return a prediction table. A training-only
        # probe makes that unused return without admitting evaluation data to fit.
        if self.estimator_id == 'transformer_ap':
            from .recovered.transformer import TransformerConfig, fit_predict_transformer
            config = TransformerConfig(seed=self.seed, epochs=self.epochs, max_aps=self.max_aps,
                                       batch_size=self.batch_size, method='ap_tokens', noise_sigma=0)
            _, self.training_summary, self.state = fit_predict_transformer(
                x, mask, data.train_xy, x[:1], mask[:1], data.train_xy[:1], config, meta)
        else:
            from .recovered import residual_cnn as kernel
            kernel.RANDOM_STATE = self.seed
            _, self.training_summary, self.state = kernel.fit_predict_tf_estimator(
                'residual_cnn', self.estimator_label, x, data.train_xy, x[:1], data.train_xy[:1],
                meta, self.epochs, self.batch_size, 8, .15, .001, .15, 'mse')
        return self

    def predict(self, data):
        x = data.test_rss[:, self.columns].astype(np.float32)
        if self.estimator_id == 'transformer_ap':
            import torch
            model, scaler, mean, std, device = self.state
            tokens = np.stack([scaler.transform(x), data.test_observed[:, self.columns]], axis=-1).astype(np.float32)
            model.eval()
            with torch.no_grad():
                batches = [model(torch.from_numpy(tokens[i:i+self.batch_size]).to(device)).cpu().numpy()
                           for i in range(0, len(tokens), self.batch_size)]
            return np.vstack(batches) * std + mean
        model, scaler, target_scaler = self.state
        x = scaler.transform(x).astype(np.float32)
        batches = [model(x[i:i+self.batch_size], training=False).numpy() for i in range(0, len(x), self.batch_size)]
        return target_scaler.inverse_transform(np.vstack(batches))
