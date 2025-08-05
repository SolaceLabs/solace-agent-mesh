#!/bin/bash

# --- Marker Configuration ---

# Initialize with a default marker. This ensures that if no other
# markers are found, a default test run is still triggered.
markers=("default")

# --- Main Logic ---

# Get the list of changed files
changed_files=$(git diff --name-only origin/main...HEAD)

# Process each file
for file in $changed_files; do
    # The case statement runs for EACH file in the loop. It checks the file
    # against a list of patterns and adds the correct marker.
    #
    # The patterns are ordered from most specific (individual files) to most
    # general (wildcard directories). The first pattern that matches is used,
    # and then the case statement for the current file ends. The loop then
    # continues to the next file.
    case "$file" in
        # Specific tool files
        src/solace_agent_mesh/agent/tools/peer_agent_tool.py)
            markers+=("delegation")
            ;;
        src/solace_agent_mesh/agent/tools/audio_tools.py)
            markers+=("audio_tools")
            ;;
        src/solace_agent_mesh/agent/tools/builtin_artifact_tools.py)
            markers+=("builtin_artifact_tools")
            ;;
        src/solace_agent_mesh/agent/tools/builtin_data_analysis_tools.py)
            markers+=("builtin_data_analysis_tools")
            ;;
        src/solace_agent_mesh/agent/tools/general_agent_tools.py)
            markers+=("general_agent_tools")
            ;;
        src/solace_agent_mesh/agent/tools/image_tools.py)
            markers+=("image_tools")
            ;;
        src/solace_agent_mesh/agent/tools/web_tools.py)
            markers+=("web_tools")
            ;;
        
        # Fallback for any other changes in the agent/tools/ directory
        src/solace_agent_mesh/agent/tools/*)
            markers+=("tools")
            ;;

        # Fallback for any other changes in the agent directory
        src/solace_agent_mesh/agent/*)
            markers+=("agent")
            ;;

        # Fallback for any other changes in the core_a2a directory
        src/solace_agent_mesh/core_a2a/*)
            markers+=("core_a2a")
            ;;
        src/solace_agent_mesh/common/client/*)
            markers+=("client" "delegation" "notification")
            ;;
        src/solace_agent_mesh/common/middleware/*)
            markers+=("middleware")
            ;;
        src/solace_agent_mesh/common/server/*)
            markers+=("notification" "server")
            ;;
        src/solace_agent_mesh/common/services/*)
            markers+=("services")
            ;;
        src/solace_agent_mesh/common/utils/embeds/*)
            markers+=("embeds")
            ;;
        src/solace_agent_mesh/common/utils/push_notification_auth.py)
            markers+=("notification")
            ;;
        
        # Fallback for any other changes in the common directory
        src/solace_agent_mesh/common/*)
            markers+=("common")
            ;;
    esac
done

# --- Test Execution ---

# Create a list of unique markers to avoid redundancy (e.g., 'notification' added multiple times).
unique_markers=($(printf "%s\n" "${markers[@]}" | sort -u))

# If there are markers to test, output the marker string for hatch test.
if [ ${#unique_markers[@]} -gt 0 ]; then
    # Join the markers with " or " for the pytest -m argument.
    # Using printf is more robust for this task.
    marker_string=$(printf " or %s" "${unique_markers[@]}")
    marker_string=${marker_string:4} # Remove leading " or "

    # Output only the marker string for use with hatch test -m
    echo "$marker_string"
else
    # If no markers found, output "default" as fallback
    echo "default"
fi
