# External Contributor Workflow Test

This file is used to test the external contributor detection workflow.

When this PR is opened against `feat/external-contributor`, the `check-external-contributor` workflow should:
1. Run on the PR
2. Check if the PR creator is a member of the `solace-ai` GitHub team
3. Add the "external contributor" label if not a member

This is a test PR to validate the workflow is functioning correctly.
