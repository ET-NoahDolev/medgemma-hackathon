#!/usr/bin/env python3
"""Check MLflow runs in the database."""

import mlflow
from pathlib import Path
from dotenv import find_dotenv

# Get tracking URI
env_path = find_dotenv()
if env_path:
    repo_root = Path(env_path).parent.absolute()
else:
    repo_root = Path.cwd()
db_path = repo_root / "mlflow.db"
tracking_uri = f"sqlite:///{db_path}"

mlflow.set_tracking_uri(tracking_uri)
client = mlflow.tracking.MlflowClient()

print("=" * 60)
print("MLflow Runs Check")
print("=" * 60)
print(f"Tracking URI: {tracking_uri}")
print(f"Database exists: {db_path.exists()}")
print()

# Get all experiments
exps = client.search_experiments()
print(f"Found {len(exps)} experiments:\n")

for exp in exps:
    print(f"Experiment: {exp.name} (ID: {exp.experiment_id})")
    runs = client.search_runs(
        exp.experiment_id, 
        max_results=10, 
        order_by=["start_time DESC"]
    )
    print(f"  Runs: {len(runs)}")
    
    if runs:
        # Show all runs, not just first 5
        for r in runs:
            status_icon = "✓" if r.info.status == "FINISHED" else "⚠" if r.info.status == "RUNNING" else "✗"
            print(f"    {status_icon} {r.info.run_name} (ID: {r.info.run_id[:12]}...)")
            print(f"      Status: {r.info.status}, Start: {r.info.start_time}")
            if r.info.end_time:
                print(f"      End: {r.info.end_time}")
            if r.data.metrics:
                print(f"      Metrics: {list(r.data.metrics.keys())}")
            if r.data.params:
                print(f"      Params: {len(r.data.params)} params")
    else:
        print("    (no runs)")
    print()
