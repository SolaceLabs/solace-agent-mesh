"""
Tests for project upload size limits.

Test-specific overrides (see conftest.py):
- Per-file limit: 1MB (gateway_max_upload_size_bytes)
- Batch limit: 2MB (gateway_max_batch_upload_size_bytes)
- Project total limit: 3MB (gateway_max_project_size_bytes)
"""

import io
import json
import zipfile

from fastapi.testclient import TestClient

from tests.integration.apis.infrastructure.gateway_adapter import GatewayAdapter

KB = 1024
MB = 1024 * KB


def make_file(name: str, size: int):
    return ("files", (name, io.BytesIO(b"x" * size), "text/plain"))


def make_files(count: int, size: int, prefix: str = "file"):
    return [
        (
            "files",
            (f"{prefix}_{i}.txt", io.BytesIO(bytes([i % 256]) * size), "text/plain"),
        )
        for i in range(count)
    ]


def seed(gw: GatewayAdapter, project_id: str):
    gw.seed_project(
        project_id=project_id,
        name=project_id,
        user_id="sam_dev_user",
        description="",
    )


class TestPerFileSizeLimit:

    def test_file_over_limit_rejected(self, both_enabled_client: TestClient):
        response = both_enabled_client.post(
            "/api/v1/projects",
            data={"name": "Test", "description": ""},
            files=[make_file("big.txt", MB + 1)],
        )
        assert response.status_code == 413
        assert "exceeds maximum" in response.json()["detail"]

    def test_file_at_limit_succeeds(self, both_enabled_client: TestClient):
        response = both_enabled_client.post(
            "/api/v1/projects",
            data={"name": "Test", "description": ""},
            files=[make_file("exact.txt", MB)],
        )
        assert response.status_code == 201

    def test_oversized_file_in_batch_rejects_entire_upload(
        self, both_enabled_client: TestClient
    ):
        response = both_enabled_client.post(
            "/api/v1/projects",
            data={"name": "Test", "description": ""},
            files=[make_file("ok.txt", 100 * KB), make_file("big.txt", MB + 1)],
        )
        assert response.status_code == 413

    def test_file_over_limit_on_artifact_upload(
        self, both_enabled_client: TestClient, gateway_adapter: GatewayAdapter
    ):
        seed(gateway_adapter, "per-file-artifact")
        response = both_enabled_client.post(
            "/api/v1/projects/per-file-artifact/artifacts",
            files=[make_file("big.txt", MB + 1)],
        )
        assert response.status_code == 413


class TestBatchUploadSizeLimit:

    def test_batch_exceeds_limit_on_creation(self, both_enabled_client: TestClient):
        response = both_enabled_client.post(
            "/api/v1/projects",
            data={"name": "Test", "description": ""},
            files=make_files(3, 800 * KB),  # 2.4MB > 2MB
        )
        assert response.status_code == 400
        assert "Batch upload size limit exceeded" in response.json()["detail"]

    def test_batch_at_limit_succeeds(self, both_enabled_client: TestClient):
        response = both_enabled_client.post(
            "/api/v1/projects",
            data={"name": "Test", "description": ""},
            files=[make_file("f1.txt", MB), make_file("f2.txt", MB)],  # exactly 2MB
        )
        assert response.status_code == 201

    def test_batch_limit_checked_before_project_limit(
        self, both_enabled_client: TestClient, gateway_adapter: GatewayAdapter
    ):
        seed(gateway_adapter, "batch-before-project")
        both_enabled_client.post(
            "/api/v1/projects/batch-before-project/artifacts",
            files=[make_file("seed.txt", MB)],
        )
        # 2.4MB batch exceeds 2MB batch limit; also would exceed 3MB project total,
        # but batch validation fires first
        response = both_enabled_client.post(
            "/api/v1/projects/batch-before-project/artifacts",
            files=make_files(3, 800 * KB),
        )
        assert response.status_code == 400
        assert "Batch upload size limit exceeded" in response.json()["detail"]


class TestProjectTotalSizeLimit:

    def test_cumulative_uploads_exceed_limit(
        self, both_enabled_client: TestClient, gateway_adapter: GatewayAdapter
    ):
        seed(gateway_adapter, "project-total")
        for i in range(3):
            r = both_enabled_client.post(
                "/api/v1/projects/project-total/artifacts",
                files=[make_file(f"f{i}.txt", 900 * KB)],
            )
            assert r.status_code == 201

        response = both_enabled_client.post(
            "/api/v1/projects/project-total/artifacts",
            files=[make_file("f3.txt", 900 * KB)],
        )
        assert response.status_code == 400
        assert "Project size limit exceeded" in response.json()["detail"]

    def test_batch_under_batch_limit_but_over_project_limit(
        self, both_enabled_client: TestClient, gateway_adapter: GatewayAdapter
    ):
        seed(gateway_adapter, "batch-vs-project")
        r = both_enabled_client.post(
            "/api/v1/projects/batch-vs-project/artifacts",
            files=[
                make_file("f1.txt", 900 * KB),
                make_file("f2.txt", 900 * KB),
            ],  # 1.8MB batch
        )
        assert r.status_code == 201

        # 1.8MB batch (under 2MB batch limit), but 3.6MB total (over 3MB project limit)
        response = both_enabled_client.post(
            "/api/v1/projects/batch-vs-project/artifacts",
            files=[
                make_file("f3.txt", 900 * KB),
                make_file("f4.txt", 900 * KB),
            ],
        )
        assert response.status_code == 400
        assert "Project size limit exceeded" in response.json()["detail"]


class TestZipImportLimits:

    def _make_zip(self, file_count: int, file_size: int):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            meta = {
                "version": "1.0",
                "exportedAt": 1234567890,
                "project": {
                    "name": "Imported",
                    "description": "",
                    "systemPrompt": None,
                    "defaultAgentId": None,
                    "metadata": {
                        "originalCreatedAt": "2024-01-01T00:00:00Z",
                        "artifactCount": file_count,
                        "totalSizeBytes": file_count * file_size,
                    },
                },
                "artifacts": [],
            }
            for i in range(file_count):
                meta["artifacts"].append(
                    {
                        "filename": f"f{i}.txt",
                        "mimeType": "text/plain",
                        "size": file_size,
                        "metadata": {"source": "project"},
                    }
                )
                zf.writestr(f"artifacts/f{i}.txt", bytes([i % 256]) * file_size)
            zf.writestr("project.json", json.dumps(meta))
        buf.seek(0)
        return buf

    def test_zip_exceeding_project_limit_rejected(
        self, both_enabled_client: TestClient
    ):
        response = both_enabled_client.post(
            "/api/v1/projects/import",
            files={
                "file": (
                    "large.zip",
                    self._make_zip(4, 900 * KB),  # 3.6MB > 3MB
                    "application/zip",
                )
            },
        )
        assert response.status_code == 400

    def test_zip_within_limits_succeeds(self, both_enabled_client: TestClient):
        response = both_enabled_client.post(
            "/api/v1/projects/import",
            files={
                "file": (
                    "valid.zip",
                    self._make_zip(3, 900 * KB),  # 2.7MB < 3MB
                    "application/zip",
                )
            },
        )
        assert response.status_code == 200
        assert response.json()["artifactsImported"] == 3

    def test_zip_skips_oversized_individual_files(
        self, both_enabled_client: TestClient
    ):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            meta = {
                "version": "1.0",
                "exportedAt": 1234567890,
                "project": {
                    "name": "Mixed",
                    "description": "",
                    "systemPrompt": None,
                    "defaultAgentId": None,
                    "metadata": {
                        "originalCreatedAt": "2024-01-01T00:00:00Z",
                        "artifactCount": 3,
                        "totalSizeBytes": (MB + 1) + 2 * (100 * KB),
                    },
                },
                "artifacts": [
                    {
                        "filename": "big.txt",
                        "mimeType": "text/plain",
                        "size": MB + 1,
                        "metadata": {"source": "project"},
                    },
                    {
                        "filename": "ok1.txt",
                        "mimeType": "text/plain",
                        "size": 100 * KB,
                        "metadata": {"source": "project"},
                    },
                    {
                        "filename": "ok2.txt",
                        "mimeType": "text/plain",
                        "size": 100 * KB,
                        "metadata": {"source": "project"},
                    },
                ],
            }
            zf.writestr("artifacts/big.txt", b"x" * (MB + 1))
            zf.writestr("artifacts/ok1.txt", b"y" * (100 * KB))
            zf.writestr("artifacts/ok2.txt", b"z" * (100 * KB))
            zf.writestr("project.json", json.dumps(meta))
        buf.seek(0)
        response = both_enabled_client.post(
            "/api/v1/projects/import",
            files={"file": ("mixed.zip", buf, "application/zip")},
        )
        assert response.status_code == 200
        assert response.json()["artifactsImported"] == 2


class TestFileDeletionAndReupload:

    def test_delete_frees_space_for_upload(
        self, both_enabled_client: TestClient, gateway_adapter: GatewayAdapter
    ):
        seed(gateway_adapter, "delete-reupload")
        for i in range(3):
            both_enabled_client.post(
                "/api/v1/projects/delete-reupload/artifacts",
                files=[make_file(f"f{i}.txt", 900 * KB)],
            )

        both_enabled_client.delete(
            "/api/v1/projects/delete-reupload/artifacts/f0.txt"
        )
        response = both_enabled_client.post(
            "/api/v1/projects/delete-reupload/artifacts",
            files=[make_file("f3.txt", 900 * KB)],
        )
        assert response.status_code == 201

    def test_replace_with_larger_file_exceeds_limit(
        self, both_enabled_client: TestClient, gateway_adapter: GatewayAdapter
    ):
        seed(gateway_adapter, "replace-larger")
        for i in range(3):
            both_enabled_client.post(
                "/api/v1/projects/replace-larger/artifacts",
                files=[make_file(f"f{i}.txt", 900 * KB)],
            )
        both_enabled_client.post(
            "/api/v1/projects/replace-larger/artifacts",
            files=[make_file("small.txt", 100 * KB)],
        )

        response = both_enabled_client.post(
            "/api/v1/projects/replace-larger/artifacts",
            files=[make_file("small.txt", 900 * KB)],
        )
        assert response.status_code == 400
