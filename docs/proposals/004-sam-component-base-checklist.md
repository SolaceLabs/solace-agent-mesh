6.  [x] **Update Design Document**
    -   [x] In `docs/proposals/002-sam-component-base-design.md`, update the signature of `publish_a2a_message` to reflect its public status.

7.  [ ] **Refactor Artifact Handling**
    -   [x] Add `artifact_handling_mode` to gateway configuration.
    -   [x] Create `prepare_file_part_for_publishing` utility in `common/a2a/artifact.py`.
    -   [x] Create `resolve_file_part_uri` utility in `common/a2a/artifact.py`.
    -   [x] Refactor `BaseGatewayComponent` to use the new utilities for sending and receiving artifacts.
    -   [x] Update `a2a` `__init__.py` to export new functions.
    -   [ ] Update developer documentation for new `a2a` functions.

8.  [ ] **Frontend Inline Artifact Rendering**
    -   [x] **Docs**: Create design document `005-frontend-inline-artifact-rendering.md`.
    -   [ ] **Backend**: Implement secure `/api/v1/artifacts/download` endpoint in the gateway.
    -   [ ] **Frontend**: Refactor file rendering component to be a "smart renderer" with on-demand fetching and MIME-type-based views.
