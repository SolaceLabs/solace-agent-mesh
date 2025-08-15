# A2A SDK Migration: Phase 0 Checklist

This document tracks the completion of tasks for Phase 0: Preparation & Tooling.

## Task 1: Integrate `a2a-sdk` Dependency

- [x] **Add `a2a-sdk` to `pyproject.toml`:** Add `"a2a-sdk"` to the `[project.dependencies]` section.
- [x] **Update Environment:** Run the appropriate command (e.g., `hatch env create`) to install the new dependency.
- [x] **Verify Installation:** Temporarily add `from a2a.types import Task` to a test file and run the test suite to confirm no import or dependency conflicts arise.

## Task 2: Implement Automated Schema Synchronization

- [x] **Create Script:** Create a new Python script at `scripts/sync_a2a_schema.py`.
- [x] **Get SDK Version:** The script uses `importlib.metadata.version("a2a-sdk")` to get the installed SDK version.
- [x] **Construct Git Tag:** The script transforms the version string into a Git tag (e.g., "0.5.1" -> "v0.5.1").
- [x] **Parse Base URL:** The script locates the installed `a2a/types.py` file and parses the source URL from its header comment.
- [x] **Modify URL:** The script replaces the branch part of the URL (e.g., `refs/heads/main`) with the constructed Git tag to create a version-locked URL.
- [x] **Download and Save:** The script downloads the schema from the version-locked URL and saves it to `src/solace_agent_mesh/common/a2a_spec/a2a.json`.
- [x] **Add Error Handling:** The script includes error handling for HTTP 404 errors, failing with a clear message if the corresponding tag/schema is not found.
- [x] **Integrate into Workflows:** Add a command to run `scripts/sync_a2a_schema.py` to the development setup process (e.g., `hatch` environment setup) and the CI pipeline.

## Task 3: Refactor `A2AMessageValidator`

- [x] **Add `jsonschema` Dependency:** Add `jsonschema` to the test dependencies in `pyproject.toml`.
- [x] **Update Validator Logic:**
    - [x] Modify `A2AMessageValidator.__init__` to load the schema from `src/solace_agent_mesh/common/a2a_spec/a2a.json`.
    - [x] Replace Pydantic validation with `jsonschema.validate()`.
    - [x] Implement logic to handle discriminated unions by inspecting the `method` field of requests to select the correct sub-schema for validation.
- [x] **Rewrite Validator Tests:**
    - [x] Create new valid and invalid mock payloads that conform to the official `a2a.json` specification.
    - [x] Update the unit tests for `A2AMessageValidator` to use these new payloads and assert correct behavior.

## Task 4: Create Type Migration Mapping Document

- [x] **Create Document:** Create a new Markdown file at `docs/refactoring/A2A-Type-Migration-Map.md`.
- [x] **Populate Document:**
    - [x] Create tables mapping legacy types (`common/types.py`) to new SDK types (`a2a.types`).
    - [x] Document key structural changes (e.g., `Task.sessionId` to `Message.contextId`).
    - [x] Document field name changes (e.g., `pushNotifications` to `push_notifications`).
    - [x] Provide a clear "before and after" JSON example for migrating a status update from a `metadata` field to a `DataPart`.
