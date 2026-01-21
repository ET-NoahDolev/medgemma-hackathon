import types

import pytest

from model_training.gcs_upload import upload_training_data_to_gcs
from model_training.vertex_train import train_vertex_lora


def test_train_vertex_lora_requires_project(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GCP_PROJECT_ID", raising=False)
    with pytest.raises(ValueError, match="GCP_PROJECT_ID"):
        train_vertex_lora(
            train_dataset_gcs="gs://b/train.jsonl",
            validation_dataset_gcs="gs://b/eval.jsonl",
            output_uri="gs://b/out/",
        )


def test_train_vertex_lora_uses_sdk(monkeypatch: pytest.MonkeyPatch) -> None:
    # Stub out vertexai + vertexai.tuning modules so we don't hit the network.
    calls: dict[str, object] = {}

    def _init(*, project: str, location: str) -> None:
        calls["init"] = (project, location)

    class _Job:
        resource_name = "projects/p/locations/r/tuningJobs/123"

    def _train(**kwargs):
        calls["train_kwargs"] = kwargs
        return _Job()

    class _SourceModel:
        def __init__(self, *, base_model: str) -> None:
            self.base_model = base_model

    tuning = types.SimpleNamespace(sft=types.SimpleNamespace(train=_train), SourceModel=_SourceModel)
    vertexai = types.SimpleNamespace(init=_init, tuning=tuning)

    monkeypatch.setenv("GCP_PROJECT_ID", "p")
    monkeypatch.setenv("GCP_REGION", "r")
    monkeypatch.setitem(__import__("sys").modules, "vertexai", vertexai)
    monkeypatch.setitem(__import__("sys").modules, "vertexai.tuning", tuning)

    job_name = train_vertex_lora(
        train_dataset_gcs="gs://b/train.jsonl",
        validation_dataset_gcs="gs://b/eval.jsonl",
        output_uri="gs://b/out/",
        base_model="google/medgemma-4b-it",
        epochs=3,
        learning_rate=2e-4,
    )
    assert job_name.endswith("/123")
    assert calls["init"] == ("p", "r")
    assert isinstance(calls["train_kwargs"], dict)


def test_upload_training_data_to_gcs(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Stub google.cloud.storage import path.
    uploaded: dict[str, str] = {}

    class _Blob:
        def __init__(self, name: str) -> None:
            self.name = name

        def upload_from_filename(self, filename: str) -> None:
            uploaded["filename"] = filename

    class _Bucket:
        def __init__(self, name: str) -> None:
            self.name = name

        def blob(self, name: str) -> _Blob:
            uploaded["object_name"] = name
            return _Blob(name)

    class _Client:
        def __init__(self, project=None) -> None:
            self.project = project

        def bucket(self, name: str) -> _Bucket:
            uploaded["bucket"] = name
            return _Bucket(name)

    storage_module = types.SimpleNamespace(Client=_Client)
    google_cloud_module = types.SimpleNamespace(storage=storage_module)
    google_module = types.SimpleNamespace(cloud=google_cloud_module)

    monkeypatch.setitem(__import__("sys").modules, "google", google_module)
    monkeypatch.setitem(__import__("sys").modules, "google.cloud", google_cloud_module)
    monkeypatch.setitem(__import__("sys").modules, "google.cloud.storage", storage_module)

    p = tmp_path / "train.jsonl"
    p.write_text('{"messages":[]}\n')

    uri = upload_training_data_to_gcs(
        local_path=str(p),
        gcs_bucket="gs://my-bucket",
        gcs_path="training/train.jsonl",
        project_id="p",
    )
    assert uri == "gs://my-bucket/training/train.jsonl"
    assert uploaded["bucket"] == "my-bucket"
