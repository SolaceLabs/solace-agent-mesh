"""
Generates a human-readable, hierarchical report from a MemoryNode tree.
"""

import re
from typing import List

from .depth_based_profiler import MemoryNode


class MemoryReportGenerator:
    """
    Takes a MemoryNode tree and generates a formatted string report.
    """

    def __init__(self, root_node: MemoryNode, threshold_bytes: int = 512):
        """
        Initializes the MemoryReportGenerator.

        Args:
            root_node: The root of the MemoryNode tree from MemoryProfiler.
            threshold_bytes: The minimum size for a child node to be included in the report.
        """
        self.root_node = root_node
        self.threshold_bytes = threshold_bytes

    def _clean_repr(self, text: str) -> str:
        """Cleans a repr() string to be more readable."""
        if not isinstance(text, str):
            return str(text)
        text = re.sub(r"^\[[KV]\] ", "", text)
        text = re.sub(r" at 0x[0-9a-fA-F]+", "", text)
        text = re.sub(r"^<([^>]+) object>$", r"\1", text)
        if len(text) > 80 and ("[" in text or "{" in text):
            text = text[:40] + "...." + text[-35:]
        return text

    def generate_report(self) -> str:
        """
        Generates the full, formatted memory report as a string.
        """
        if not isinstance(self.root_node, MemoryNode):
            return str(self.root_node)

        clean_name = self._clean_repr(self.root_node.name)
        clean_type = self._clean_repr(self.root_node.type_name)
        title = (
            f"Memory Profile for: {clean_name}"
            if clean_name == clean_type
            else f"Memory Profile for: {clean_name}: {clean_type}"
        )

        dict_child = next(
            (c for c in self.root_node.children if c.name == "__dict__"), None
        )
        exclusive_size_str = (
            f"Exclusive Size: {self._format_size(self.root_node.exclusive_size)}"
        )
        if dict_child:
            combined_exclusive = (
                self.root_node.exclusive_size + dict_child.exclusive_size
            )
            exclusive_size_str = (
                f"Exclusive Size: {self._format_size(combined_exclusive)}"
            )

        summary_line = f"Total Size: {self._format_size(self.root_node.total_size)} | {exclusive_size_str}"

        report_lines = [
            title,
            summary_line,
            "-" * 80,
        ]
        report_lines.extend(self._format_node_children(self.root_node, indent_level=0))
        return "\n".join(report_lines)

    def _format_size(self, size_bytes: int) -> str:
        """Formats a size in bytes into a human-readable string (B, KB, MB, GB)."""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024**2:
            return f"{size_bytes / 1024:.2f} KB"
        elif size_bytes < 1024**3:
            return f"{size_bytes / (1024**2):.2f} MB"
        else:
            return f"{size_bytes / (1024**3):.2f} GB"

    def _format_node_children(
        self, node: MemoryNode, indent_level: int = 0
    ) -> List[str]:
        """
        Recursively formats a node's children into a list of strings.
        This version "flattens" __dict__ children into their parent for a cleaner report.
        """
        lines = []
        indent = "  " * indent_level

        effective_children = []
        for child in node.children:
            if child.name == "__dict__":
                effective_children.extend(child.children)
            else:
                effective_children.append(child)

        sorted_children = sorted(
            effective_children, key=lambda c: c.total_size, reverse=True
        )

        shared_children = [child for child in sorted_children if child.is_shared]
        regular_children = [child for child in sorted_children if not child.is_shared]

        pruned_children = [
            child
            for child in regular_children
            if child.total_size >= self.threshold_bytes
        ]

        for child in pruned_children:

            clean_child_name = self._clean_repr(child.name)
            clean_child_type = self._clean_repr(child.type_name)
            if clean_child_name == clean_child_type:
                clean_child_type = ""

            if clean_child_name.startswith("[") and clean_child_name.endswith("]"):
                clean_child_name = f"list ({len(child.children)} items)"
            elif clean_child_name.startswith("{") and clean_child_name.endswith("}"):
                clean_child_name = f"dict ({len(child.children) // 2} items)"
            elif clean_child_name.endswith("]"):
                clean_child_name = clean_child_name.split("[", 1)[0].strip()

            if clean_child_type.startswith(("[", "{")):
                name_part = clean_child_name.split(":", 1)[0]
            elif clean_child_name == clean_child_type:
                name_part = clean_child_name
            else:
                name_part = f"{clean_child_name} "

            dict_of_child = next(
                (c for c in child.children if c.name == "__dict__"), None
            )
            exclusive_size_str = f"Exclusive: {self._format_size(child.exclusive_size)}"
            if dict_of_child:
                combined_exclusive = child.exclusive_size + dict_of_child.exclusive_size
                exclusive_size_str = (
                    f"Exclusive: {self._format_size(combined_exclusive)}"
                )

            line = (
                f"{indent}- {name_part}: "
                f"Total: {self._format_size(child.total_size)}, "
                f"{exclusive_size_str}"
            )
            lines.append(line)
            lines.extend(self._format_node_children(child, indent_level + 1))

        num_pruned = len(regular_children) - len(pruned_children)
        if num_pruned > 0:
            lines.append(
                f"{indent}  (...and {num_pruned} other children smaller than {self._format_size(self.threshold_bytes)})"
            )

        for child in shared_children:
            clean_child_name = self._clean_repr(child.name)
            clean_child_type = self._clean_repr(child.type_name)
            name_part = (
                clean_child_name
                if clean_child_name == clean_child_type
                else f"{clean_child_name} ({clean_child_type})"
            )
            line = f"{indent}- {name_part}: <shared>"
            lines.append(line)

        return lines
