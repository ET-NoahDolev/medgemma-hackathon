#!/usr/bin/env python3
"""Clean up stuck MLflow runs that are in RUNNING status."""

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
print("MLflow Run Cleanup")
print("=" * 60)
print(f"Tracking URI: {tracking_uri}")
print()

# Find all RUNNING runs
running_runs = []
for exp in client.search_experiments():
    runs = client.search_runs(exp.experiment_id, filter_string='status = "RUNNING"')
    for run in runs:
        running_runs.append((exp.name, run))

if not running_runs:
    print("✓ No RUNNING runs found. All runs are properly finished.")
    exit(0)

print(f"Found {len(running_runs)} RUNNING run(s):\n")
for exp_name, run in running_runs:
    print(f"  - {exp_name}: {run.info.run_name} ({run.info.run_id[:12]}...)")
    print(f"    Started: {run.info.start_time}")

print("\n" + "=" * 60)
response = input("Do you want to mark these runs as FAILED? (y/N): ")
if response.lower() != "y":
    print("Cancelled.")
    exit(0)

# Mark runs as FAILED
for exp_name, run in running_runs:
    try:
        client.set_terminated(run.info.run_id, status="FAILED")
        print(f"✓ Marked {run.info.run_name} ({run.info.run_id[:12]}...) as FAILED")
    except Exception as e:
        print(f"✗ Failed to mark {run.info.run_id[:12]}... as FAILED: {e}")

print("\n✓ Cleanup complete!")
