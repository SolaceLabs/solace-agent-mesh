"""
Tests for project upload size limits.

These tests run with reduced, test-specific upload size overrides and do not
reflect the production defaults (which are higher, e.g. 50MB per file and
100MB total at the time of writing; see application configuration for
current values).

Test-specific override values used here (see conftest.py):
- Per-file upload limit (gateway_max_upload_size_bytes = 1MB)
- Total project upload limit (gateway_max_total_upload_size_bytes = 3MB)
"""

import io
import json
import zipfile

from fastapi.testclient import TestClient

from tests.integration.apis.infrastructure.gateway_adapter import GatewayAdapter


class TestTotalUploadSizeLimits:
    # Test that multiple files, each under the per-file limit, but exceeding the total limit when combined, are rejected
    def test_multiple_files_under_individual_but_over_total_limit(
        self, both_enabled_client: TestClient
    ):
        file_size = 900 * 1024  # 900KB
        files = []

        for i in range(4):
            file_content = bytes([i % 256]) * file_size
            files.append(
                ("files", (f"file_{i}.txt", io.BytesIO(file_content), "text/plain"))
            )

        # Attempt to create project with files exceeding total limit
        response = both_enabled_client.post(
            "/api/v1/projects",
            data={
                "name": "Test Project Multiple Files",
                "description": "Test project with multiple files over total limit",
            },
            files=files,
        )

        assert (
            response.status_code == 400
        )  # Should be rejected with 400 (Bad Request) due to validation error

    # Test that adding a new file to a project with existing files, where the combined size exceeds the total limit, errors appropriately
    def test_existing_files_plus_new_file_exceeds_total_limit(
        self, both_enabled_client: TestClient, gateway_adapter: GatewayAdapter
    ):
        project_id = "test-project-existing-files"
        gateway_adapter.seed_project(
            project_id=project_id,
            name="Test Project",
            user_id="sam_dev_user",
            description="Test project with existing files",
        )

        file_size = 900 * 1024  # 900KB

        files = []
        for i in range(3):
            file_content = bytes([i % 256]) * file_size
            files.append(
                (
                    "files",
                    (f"existing_file_{i}.txt", io.BytesIO(file_content), "text/plain"),
                )
            )
        response = both_enabled_client.post(
            f"/api/v1/projects/{project_id}/artifacts",
            files=files,
        )

        assert response.status_code == 201, "All 3 file uploads should have succeeded"

        # Attempt to add a new file that pushes total over 3MB limit
        new_file_size = 900 * 1024  # 900KB

        response3 = both_enabled_client.post(
            f"/api/v1/projects/{project_id}/artifacts",
            files={
                "files": (
                    "new_file.txt",
                    io.BytesIO(b"c" * new_file_size),
                    "text/plain",
                )
            },
        )

        assert response3.status_code == 400, (
            f"Expected 400 Bad Request when total size exceeds limit, got {response3.status_code}"
        )  # Should be rejected with 400 Bad Request


class TestZipImportLimits:
    # Test importing a zip file where total artifact size exceeds the limit
    def test_zip_import_with_total_size_exceeding_limit(
        self, both_enabled_client: TestClient
    ):
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            meta = {
                "version": "1.0",
                "exportedAt": 1234567890,
                "project": {
                    "name": "Large",
                    "description": "",
                    "systemPrompt": None,
                    "defaultAgentId": None,
                    "metadata": {
                        "originalCreatedAt": "2024-01-01T00:00:00Z",
                        "artifactCount": 4,
                        "totalSizeBytes": 4 * 900 * 1024,
                    },
                },
                "artifacts": [],
            }
            for i in range(4):
                meta["artifacts"].append(
                    {
                        "filename": f"f{i}.txt",
                        "mimeType": "text/plain",
                        "size": 900 * 1024,
                        "metadata": {"source": "project"},
                    }
                )
                zf.writestr(f"artifacts/f{i}.txt", bytes([i % 256]) * 900 * 1024)
            zf.writestr("project.json", json.dumps(meta))
        zip_buffer.seek(0)
        response = both_enabled_client.post(
            "/api/v1/projects/import",
            files={"file": ("large.zip", zip_buffer, "application/zip")},
        )
        assert (
            response.status_code == 400
        )  # Should be rejected with 400 Bad Request due to total size exceeding limit

    # Test importing a zip file where all artifacts are within limits
    def test_zip_import_within_limits_succeeds(self, both_enabled_client: TestClient):
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            meta = {
                "version": "1.0",
                "exportedAt": 1234567890,
                "project": {
                    "name": "Valid",
                    "description": "",
                    "systemPrompt": None,
                    "defaultAgentId": None,
                    "metadata": {
                        "originalCreatedAt": "2024-01-01T00:00:00Z",
                        "artifactCount": 3,
                        "totalSizeBytes": 3 * 900 * 1024,
                    },
                },
                "artifacts": [],
            }
            for i in range(3):
                meta["artifacts"].append(
                    {
                        "filename": f"f{i}.txt",
                        "mimeType": "text/plain",
                        "size": 900 * 1024,
                        "metadata": {"source": "project"},
                    }
                )
                zf.writestr(f"artifacts/f{i}.txt", bytes([i % 256]) * 900 * 1024)
            zf.writestr("project.json", json.dumps(meta))
        zip_buffer.seek(0)
        response = both_enabled_client.post(
            "/api/v1/projects/import",
            files={"file": ("valid.zip", zip_buffer, "application/zip")},
        )
        assert response.status_code == 200
        assert response.json()["artifactsImported"] == 3


class TestFileDeletionAndReupload:
    # Test deleting a file then uploading a new file within the freed space
    def test_delete_file_then_upload_new_within_freed_space(
        self, both_enabled_client: TestClient, gateway_adapter: GatewayAdapter
    ):
        project_id = "test-delete"
        gateway_adapter.seed_project(
            project_id=project_id, name="Test", user_id="sam_dev_user", description=""
        )

        both_enabled_client.post(
            f"/api/v1/projects/{project_id}/artifacts",
            files={"files": ("f1.txt", io.BytesIO(b"x" * 900 * 1024), "text/plain")},
        )
        both_enabled_client.post(
            f"/api/v1/projects/{project_id}/artifacts",
            files={"files": ("f2.txt", io.BytesIO(b"y" * 900 * 1024), "text/plain")},
        )
        r = both_enabled_client.post(
            f"/api/v1/projects/{project_id}/artifacts",
            files={"files": ("f3.txt", io.BytesIO(b"z" * 900 * 1024), "text/plain")},
        )
        assert r.status_code == 201
        both_enabled_client.delete(f"/api/v1/projects/{project_id}/artifacts/f1.txt")
        response = both_enabled_client.post(
            f"/api/v1/projects/{project_id}/artifacts",
            files={"files": ("f4.txt", io.BytesIO(b"w" * 900 * 1024), "text/plain")},
        )
        assert response.status_code == 201

    # Test replacing an existing file with a larger version that would exceed the total limit
    def test_replace_file_with_larger_version_respects_limit(
        self, both_enabled_client: TestClient, gateway_adapter: GatewayAdapter
    ):
        project_id = "test-replace"
        gateway_adapter.seed_project(
            project_id=project_id, name="Test", user_id="sam_dev_user", description=""
        )

        both_enabled_client.post(
            f"/api/v1/projects/{project_id}/artifacts",
            files={"files": ("f1.txt", io.BytesIO(b"x" * 900 * 1024), "text/plain")},
        )
        both_enabled_client.post(
            f"/api/v1/projects/{project_id}/artifacts",
            files={"files": ("f2.txt", io.BytesIO(b"y" * 900 * 1024), "text/plain")},
        )
        both_enabled_client.post(
            f"/api/v1/projects/{project_id}/artifacts",
            files={"files": ("f3.txt", io.BytesIO(b"z" * 900 * 1024), "text/plain")},
        )
        r = both_enabled_client.post(
            f"/api/v1/projects/{project_id}/artifacts",
            files={"files": ("small.txt", io.BytesIO(b"s" * 100 * 1024), "text/plain")},
        )
        assert r.status_code == 201
        response = both_enabled_client.post(
            f"/api/v1/projects/{project_id}/artifacts",
            files={"files": ("small.txt", io.BytesIO(b"S" * 900 * 1024), "text/plain")},
        )
        assert response.status_code == 400
