"""
Test selector - maps changed files to appropriate test markers.

This script analyzes git diff to determine which files have changed and maps
them to appropriate pytest markers for targeted test execution.
"""

import subprocess
import sys
from typing import List, Set
import fnmatch


class TestSelector:
    """Maps changed files to pytest markers for targeted test execution."""
    
    def __init__(self):
        # Exact file mappings - specific files that map to specific markers
        self.exact_file_mappings = {
            "src/solace_agent_mesh/agent/tools/peer_agent_tool.py": ["delegation"],
            "src/solace_agent_mesh/agent/tools/audio_tools.py": ["audio_tools"],
            "src/solace_agent_mesh/agent/tools/builtin_artifact_tools.py": ["builtin_artifact_tools"],
            "src/solace_agent_mesh/agent/tools/builtin_data_analysis_tools.py": ["builtin_data_analysis_tools"],
            "src/solace_agent_mesh/agent/tools/general_agent_tools.py": ["general_agent_tools"],
            "src/solace_agent_mesh/agent/tools/image_tools.py": ["image_tools"],
            "src/solace_agent_mesh/agent/tools/web_tools.py": ["web_tools"],
            "src/solace_agent_mesh/common/utils/push_notification_auth.py": ["notification"],
        }
        
        # Pattern mappings (order matters - most specific first)
        # Each tuple contains (pattern, list_of_markers)
        self.pattern_mappings = [
            ("src/solace_agent_mesh/agent/tools/*", ["tools"]),
            ("src/solace_agent_mesh/agent/*", ["agent", "mcp"]),
            ("src/solace_agent_mesh/core_a2a/*", ["core_a2a"]),
            ("src/solace_agent_mesh/common/client/*", ["client", "delegation", "notification"]),
            ("src/solace_agent_mesh/common/middleware/*", ["middleware"]),
            ("src/solace_agent_mesh/common/server/*", ["notification", "server"]),
            ("src/solace_agent_mesh/common/services/*", ["services"]),
            ("src/solace_agent_mesh/common/utils/embeds/*", ["embeds"]),
            ("src/solace_agent_mesh/common/*", ["common"]),
            # Modifications to test infrastructure require all tests to run
            ("tests/sam-test-infrastructure/*", ["all"]),
        ]

    def get_changed_files(self) -> List[str]:
        """
        Get list of changed files from git diff.
        
        Returns:
            List of file paths that have changed between origin/main and HEAD
        """
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", "origin/main...HEAD"],
                capture_output=True,
                text=True,
                check=True
            )
            return [f.strip() for f in result.stdout.split('\n') if f.strip()]
        except subprocess.CalledProcessError as e:
            print(f"Error getting changed files: {e}", file=sys.stderr)
            return []

    def map_file_to_markers(self, file_path: str) -> List[str]:
        """
        Map a single file to its test markers.
        
        Args:
            file_path: Path to the file to map
            
        Returns:
            List of markers for this file (empty if no matches)
        """
        # Check exact mappings first (highest priority)
        if file_path in self.exact_file_mappings:
            return self.exact_file_mappings[file_path]
        
        # Check pattern mappings (first match wins)
        for pattern, markers in self.pattern_mappings:
            if fnmatch.fnmatch(file_path, pattern):
                return markers
        
        return []

    def collect_all_markers(self) -> Set[str]:
        """
        Collect all unique markers for changed files.
        
        Returns:
            Set of unique markers including 'default'
        """
        markers = {"default"}  # Always include default marker
        
        changed_files = self.get_changed_files()
        
        for file_path in changed_files:
            file_markers = self.map_file_to_markers(file_path)
            markers.update(file_markers)
        
        return markers

    def format_marker_string(self, markers: Set[str]) -> str:
        """
        Format markers for pytest -m argument.
        
        Args:
            markers: Set of marker names
            
        Returns:
            String formatted for pytest -m (e.g., "marker1 or marker2 or marker3")
        """
        if not markers or markers == {"default"}:
            return "default"
        
        # Remove default if other markers exist
        if len(markers) > 1 and "default" in markers:
            markers.remove("default")
        
        return " or ".join(sorted(markers))

    def run(self) -> str:
        """
        Main execution method.
        
        Returns:
            Formatted marker string for pytest -m argument
        """
        markers = self.collect_all_markers()
        return self.format_marker_string(markers)


def main():
    """Entry point for the script."""
    selector = TestSelector()
    marker_string = selector.run()
    print(marker_string)


if __name__ == "__main__":
    main()
