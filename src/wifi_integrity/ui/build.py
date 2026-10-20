"""Build the dependency-free static research dashboard."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pandas as pd
import yaml

from wifi_integrity.benchmark.registry import estimator_registry


def _read_json(path: Path, default: object | None = None):
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return default if default is not None else {"status": "missing"}


def _records(path: Path) -> list[dict]:
    return pd.read_csv(path).where(lambda frame: frame.notna(), None).to_dict("records") if path.is_file() else []


def _unit_records(root: Path) -> list[dict]:
    with (root / 'config/datasets.yaml').open() as handle:
        config = yaml.safe_load(handle)
    audit_path = root / 'data/processed/unit_harmonization_audit.csv'
    audit = pd.read_csv(audit_path).set_index('unit_id').to_dict('index') if audit_path.exists() else {}
    return [dict(unit_id=u['id'], unit_label=u['label'], dataset=u['dataset'], group=u['group'],
                 n_train=u['expected_train'], n_test=u['expected_test'],
                 train_ap_vocabulary=audit.get(u['id'], {}).get('train_ap_vocabulary'),
                 diagnostic_ap_vocabulary=audit.get(u['id'], {}).get('diagnostic_ap_vocabulary'),
                 floor_labels=u['floor_labels_available']) for u in config['units']]


def _matrix_payload(path: Path) -> dict:
    matrix = pd.read_csv(path, index_col=0)
    return {
        "rows": matrix.index.astype(str).tolist(),
        "columns": matrix.columns.astype(str).tolist(),
        "values": [
            [None if pd.isna(value) else float(value) for value in row]
            for row in matrix.to_numpy()
        ],
    }


def _indicator_payload(root: Path) -> list[dict]:
    association = pd.read_csv(
        root / "reference/approved/revision_summaries/A3/A3_indicator_error_association_summary_ci_bh.csv"
    )
    adaptive = pd.read_csv(
        root / "reference/approved/revision_summaries/A3/A3_gross_error_adaptive_summary_ci.csv"
    )
    fixed = pd.read_csv(
        root / "reference/approved/revision_summaries/A3/A3_gross_error_fixed7m_summary_ci.csv"
    )
    keep_assoc = [
        "indicator_id", "label", "family", "n_conditions", "median_aligned_rho",
        "ci95_low", "ci95_high", "direction_consistency_pct", "bh_significant_pct",
    ]
    available_assoc = [column for column in keep_assoc if column in association.columns]
    merged = association[available_assoc].merge(
        adaptive[
            ["indicator_id", "median_auroc", "ci95_low_auroc", "ci95_high_auroc", "median_auprc"]
        ].rename(
            columns={
                "median_auroc": "adaptive_auroc",
                "ci95_low_auroc": "adaptive_auroc_low",
                "ci95_high_auroc": "adaptive_auroc_high",
                "median_auprc": "adaptive_auprc",
            }
        ),
        on="indicator_id",
        how="left",
    ).merge(
        fixed[
            ["indicator_id", "median_auroc", "ci95_low_auroc", "ci95_high_auroc", "median_auprc"]
        ].rename(
            columns={
                "median_auroc": "fixed_auroc",
                "ci95_low_auroc": "fixed_auroc_low",
                "ci95_high_auroc": "fixed_auroc_high",
                "median_auprc": "fixed_auprc",
            }
        ),
        on="indicator_id",
        how="left",
    )
    return merged.where(merged.notna(), None).to_dict("records")


def _sqs_payload(root: Path) -> dict:
    component = pd.read_csv(
        root / "reference/approved/revision_summaries/A1/A1_SQS_main_component_ablation_summary.csv"
    )
    audit = _read_json(root / "results/logs/reference_replay.json")
    return {
        "variants": component.where(component.notna(), None).to_dict("records"),
        "reconstruction": {"matched_rows": audit.get("sqs_rows", 0), "published_sqs_reconstruction_max_abs_difference": audit.get("sqs_max_abs_difference")},
        "components": [
            {"id": "signal_support", "label": "Signal compatibility", "weight": 0.20},
            {"id": "geometry_support", "label": "Candidate geometry", "weight": 0.20},
            {"id": "ap_count_support", "label": "AP count", "weight": 0.20},
            {"id": "ap_overlap_support", "label": "AP overlap", "weight": 0.20},
            {"id": "local_density_support", "label": "Local RP density", "weight": 0.20},
        ],
    }


def dashboard_payload(root: Path) -> dict:
    overall = pd.read_csv(root / 'results/tables/estimator_overall_summary.csv')
    reference = _read_json(root / 'results/logs/reference_replay.json')
    bench = reference.get('benchmark', {})
    association = reference.get('reliability_analysis', {})
    uncertainty = _read_json(root / 'results/logs/uncertainty_regression.json')
    units = _unit_records(root)
    cases = _read_json(root / 'results/cases/case_atlas.json', default=[])
    case_report = _read_json(root / 'results/cases/case_selection_report.json')
    artifacts = [
        ('Stored-reference predictions', 'results/predictions/estimator_predictions_published.csv.gz'),
        ('Indicator association', 'results/tables/reliability_association_by_condition.csv'),
        ('Gross-error discrimination', 'results/tables/gross_error_discrimination_by_condition.csv'),
        ('Bootstrap checks', 'results/tables/uncertainty_regression.csv'),
        ('Reference validation', 'results/logs/reference_replay.json'),
    ]
    return {
        'meta': {'version':'1.0.0-rc1', 'release_status':'Reference checks passed' if bench.get('status')=='passed' else 'Run reference checks',
                 'result_mode':'Recomputed statistics from stored study records'},
        'counts': {'units':len(units), 'training_scans':sum(u['n_train'] for u in units),
                   'test_scans':sum(u['n_test'] for u in units), 'estimators':8,
                   'predictions':bench.get('prediction_rows',0), 'indicators':18, 'cases':len(cases)},
        'pipeline': [
            {'name':'Reference statistics','status':bench.get('status','missing'), 'description':'Estimator summaries, SQS, association, and discrimination from included records.'},
            {'name':'Statistical uncertainty','status':uncertainty.get('status','missing'), 'description':'Unit-cluster bootstrap with the original A3 seed schedule.'},
            {'name':'Native experiments','status':'review', 'description':'Fresh model outputs are evaluated separately from stored-reference results.'},
        ],
        'units':units, 'estimators':overall.to_dict('records'),
        'estimator_registry':estimator_registry(root).to_dict('records'),
        'matrix':_matrix_payload(root/'results/tables/estimator_unit_median_matrix.csv'),
        'indicators':_indicator_payload(root), 'sqs':_sqs_payload(root), 'cases':cases, 'case_report':case_report,
        'tests': [
            {'name':'Estimator summaries','status':bench.get('status','missing'), 'detail':str(bench.get('max_summary_difference','Run reference checks'))},
            {'name':'SQS reconstruction','status':'passed' if reference.get('sqs_max_abs_difference',1)<1e-12 else 'missing', 'detail':str(reference.get('sqs_max_abs_difference','Run reference checks'))},
            {'name':'Association summaries','status':'passed' if association.get('max_abs_association_median_difference',1)<1e-9 else 'missing', 'detail':str(association.get('valid_association_tests',0))+' valid condition tests'},
            {'name':'Bootstrap intervals','status':uncertainty.get('status','missing'), 'detail':str(uncertainty.get('intervals',0))+' intervals checked'},
        ],
        'reports':{'reference':reference,'uncertainty':uncertainty},
        'artifacts':[{'label':label,'path':'../'+name,'description':'Locally generated; see the reproducibility guide for scope.'} for label,name in artifacts if (root/name).exists()],
    }


def build_dashboard(root: Path, output: Path | None = None) -> dict:
    root = root.resolve()
    output = (output or root / "site").resolve()
    output.mkdir(parents=True, exist_ok=True)
    (output / "assets").mkdir(exist_ok=True)
    (output / "data").mkdir(exist_ok=True)
    shutil.copy2(root / "web/index.html", output / "index.html")
    shutil.copy2(root / "web/assets/styles.css", output / "assets/styles.css")
    shutil.copy2(root / "web/assets/app.js", output / "assets/app.js")
    payload = dashboard_payload(root)
    (output / "data/dashboard.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (output / "data/dashboard-data.js").write_text(
        "window.DASHBOARD_DATA = " + json.dumps(payload, separators=(",", ":")) + ";\n",
        encoding="utf-8",
    )
    return {
        "status": "completed",
        "output": str(output / "index.html"),
        "sections": 12,
        "indicator_rows": len(payload["indicators"]),
        "case_rows": len(payload["cases"]),
    }
