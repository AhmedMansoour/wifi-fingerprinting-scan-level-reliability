"""CatBoost with training-only AP selection and explicit observation masks."""
import numpy as np
from sklearn.model_selection import train_test_split
from .base import BasePositionEstimator


class CatBoostCoordinateEstimator(BasePositionEstimator):
    estimator_id = 'catboost'
    estimator_label = 'CatBoost'
    family = 'boosted_tree'

    def __init__(self, *, seed=42, iterations=800, max_aps=128):
        super().__init__(seed=seed)
        self.iterations, self.max_aps = iterations, max_aps

    def _features(self, rss, observed):
        mask = observed[:, self.columns].astype(bool)
        values = np.where(mask, rss[:, self.columns], -110).astype(np.float32)
        return np.concatenate([values, mask.astype(np.float32)], axis=1)

    def fit(self, data):
        from catboost import CatBoostRegressor
        names = data.ap_names or tuple(f'AP_{i:08d}' for i in range(data.train_rss.shape[1]))
        ranks = []
        for i, name in enumerate(names):
            v = data.train_rss[data.train_observed[:, i].astype(bool), i]
            variance = max(float(np.mean(v*v) - np.mean(v)**2), 0) if len(v) else 0
            ranks.append((len(v), variance, name, i))
        selected = sorted(ranks, reverse=True)[:self.max_aps]
        self.columns = np.array([v[3] for v in sorted(selected, key=lambda t: t[2])])
        x = self._features(data.train_rss, data.train_observed)
        self.model = CatBoostRegressor(loss_function='MultiRMSE', eval_metric='MultiRMSE',
            iterations=self.iterations, depth=6, learning_rate=.05, l2_leaf_reg=3,
            random_seed=self.seed, od_type='Iter', od_wait=80, bootstrap_type='Bayesian',
            rsm=.9, thread_count=4, allow_writing_files=False, verbose=False)
        if len(x) >= 20:
            xt, xv, yt, yv = train_test_split(x, data.train_xy, test_size=.15, random_state=self.seed)
            self.model.fit(xt, yt, eval_set=(xv, yv), use_best_model=True)
        else:
            self.model.fit(x, data.train_xy)
        return self

    def predict(self, data):
        return self.model.predict(self._features(data.test_rss, data.test_observed))
