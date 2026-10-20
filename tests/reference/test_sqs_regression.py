import numpy as np
import pandas as pd

from wifi_integrity.reliability.sqs import reconstruct_sqs


def test_verified_sqs_reconstructs_exactly():
    features = pd.read_csv(
        "reference/approved/legacy_canonical/reliability_features_approved.csv.gz"
    )
    reconstructed = reconstruct_sqs(features)
    difference = np.abs(reconstructed.to_numpy() - features["SQS"].to_numpy())
    assert np.nanmax(difference) < 1e-12
