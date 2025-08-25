"""
This script automates the migration of declarative test YAML files to conform
to the new A2A specification format. It identifies files in the old format
and transforms their `expected_gateway_output` sections in-place, while
preserving comments and formatting.
"""

import argparse
import sys
from pathlib import Path
from ruamel.yaml import YAML


def is_migrated(data: dict) -> bool:
    """Checks if the YAML data appears to be in the new format."""
    if "expected_gateway_output" not in data:
        return True  # No section to migrate, so it's "done"

    events = data.get("expected_gateway_output")
    if not events:  # Handles empty list case: expected_gateway_output: []
        return True  # Nothing to migrate, so consider it done.

    for event in events:
        if isinstance(event, dict) and event.get("kind") == "task":
            return True
    return False


def transform_data(data: dict) -> tuple[dict, bool]:
    """Transforms the YAML data from the old format to the new format."""
    if "expected_gateway_output" not in data:
        return data, False

    original_events = data.get("expected_gateway_output")
    if not original_events:
        return data, False

    transformed_events = []
    was_transformed = False

    for event in original_events:
        # Transform if it's a dictionary and doesn't have the new format's 'kind' key.
        if isinstance(event, dict) and event.get("kind") != "task":
            was_transformed = True

            # 1. Create the new root structure
            new_event = {
                "type": event.get("type"),
                "kind": "task",
                "id": "*",
            }

            # 2. Derive contextId
            context_id = (
                data.get("gateway_input", {})
                .get("external_context", {})
                .get("a2a_session_id")
            )
            if not context_id:
                # Fallback for older tests that might not have this structure
                test_case_id = data.get("test_case_id", "unknown_test")
                context_id = f"session_{test_case_id}"  # Best guess
                print(
                    f"    [WARNING] Could not find a2a_session_id for '{test_case_id}'. Falling back to generated contextId: {context_id}",
                    file=sys.stderr,
                )
            new_event["contextId"] = context_id

            # 3. Build the status object, inferring task_state if missing.
            task_state = event.get("task_state")
            if task_state is None:
                if event.get("type") == "final_response":
                    task_state = "completed"
                else:
                    task_state = "unknown"
                    print(
                        f"    [WARNING] 'task_state' missing in non-final_response event. Defaulting to 'unknown'. Event: {event}",
                        file=sys.stderr,
                    )
            status = {"state": task_state}

            # 4. Build the status.message object
            message = {
                "kind": "message",
                "messageId": "*",
                "role": "agent",
            }

            # 5. Relocate content_parts
            content_parts = event.get("content_parts", [])
            if content_parts:
                # Handle text_contains string-to-list conversion
                for part in content_parts:
                    if "text_contains" in part and isinstance(
                        part["text_contains"], str
                    ):
                        part["text_contains"] = [part["text_contains"]]
                message["parts"] = content_parts

            status["message"] = message
            new_event["status"] = status

            # 6. Handle other assertions
            for key, value in event.items():
                if key not in ["type", "task_state", "content_parts"]:
                    new_event[key] = value

            transformed_events.append(new_event)
        else:
            # If it's already migrated or not a dict, keep it as is
            transformed_events.append(event)

    if was_transformed:
        data["expected_gateway_output"] = transformed_events

    return data, was_transformed


def main():
    """Main script execution."""
    parser = argparse.ArgumentParser(
        description="Migrate declarative test YAML files to the new A2A spec format.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "path",
        type=str,
        help="The root directory to scan for YAML files (e.g., 'tests/integration/scenarios_declarative/test_data').",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform a dry run without modifying any files. Reports which files would be changed.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose output.",
    )
    args = parser.parse_args()

    root_path = Path(args.path)
    if not root_path.is_dir():
        print(f"Error: Path '{root_path}' is not a valid directory.", file=sys.stderr)
        sys.exit(1)

    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)
    # Set a very large width to prevent line wrapping, which can break long JSON strings.
    yaml.width = 4096

    files_to_migrate = []
    files_skipped = []

    print(f"Scanning for YAML files in '{root_path}'...")
    yaml_files = sorted(list(root_path.glob("**/*.yaml")))

    for file_path in yaml_files:
        if args.verbose:
            print(f"\n--- Processing: {file_path.relative_to(root_path)} ---")
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = yaml.load(f)

            if is_migrated(content):
                if args.verbose:
                    print("Status: Already migrated. Skipping.")
                files_skipped.append(file_path)
            else:
                if args.verbose:
                    print("Status: Needs migration.")
                files_to_migrate.append(file_path)

                if not args.dry_run:
                    transformed_content, was_transformed = transform_data(content)
                    if was_transformed:
                        with open(file_path, "w", encoding="utf-8") as f:
                            yaml.dump(transformed_content, f)
                        if args.verbose:
                            print("Action: Transformed and saved.")
                    else:
                        if args.verbose:
                            print(
                                "Action: No transformation was applied despite detection."
                            )

        except Exception as e:
            print(f"Error processing file {file_path}: {e}", file=sys.stderr)

    print("\n--- Migration Summary ---")
    print(f"Total YAML files found: {len(yaml_files)}")
    print(f"Files already migrated (skipped): {len(files_skipped)}")
    print(f"Files to be migrated: {len(files_to_migrate)}")

    if files_to_migrate:
        print("\nFiles to be migrated:")
        for f in files_to_migrate:
            print(f"  - {f.relative_to(root_path.parent)}")

    if args.dry_run:
        print("\n** DRY RUN COMPLETE. No files were modified. **")
    else:
        if files_to_migrate:
            print(
                f"\n** MIGRATION COMPLETE. {len(files_to_migrate)} files were modified. **"
            )
        else:
            print("\n** No files needed migration. **")


if __name__ == "__main__":
    main()
