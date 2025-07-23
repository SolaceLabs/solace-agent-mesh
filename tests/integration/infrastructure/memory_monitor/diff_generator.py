"""
Contains classes for generating a diff between two memory snapshots (MemoryNode trees).
This is used to pinpoint memory growth in specific parts of an object graph.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict
import re

from .depth_based_profiler import MemoryNode


@dataclass
class MemoryDiffNode:
    """Represents a node in the memory comparison tree."""

    name: str
    type_name: str
    status: str  # 'ADDED', 'REMOVED', 'CHANGED', 'UNCHANGED'
    size_before: int
    size_after: int
    delta: int = 0
    children: List["MemoryDiffNode"] = field(default_factory=list)

    def __post_init__(self):
        self.delta = self.size_after - self.size_before


class MemoryDiffGenerator:
    """
    Compares two MemoryNode trees (before and after snapshots) and generates
    a MemoryDiffNode tree highlighting the differences.
    """

    def __init__(self, tree_before: MemoryNode, tree_after: MemoryNode):
        """
        Initializes the generator with the two memory trees to compare.

        Args:
            tree_before: The MemoryNode tree from the 'before' snapshot.
            tree_after: The MemoryNode tree from the 'after' snapshot.
        """
        self.tree_before = tree_before
        self.tree_after = tree_after

    def generate_diff(self) -> MemoryDiffNode:
        """
        Generates the full diff tree by comparing the root nodes.
        """
        return self._diff_nodes(self.tree_before, self.tree_after)

    def _diff_nodes(
        self, node_before: Optional[MemoryNode], node_after: Optional[MemoryNode]
    ) -> MemoryDiffNode:
        """
        Recursively compares two MemoryNodes and their children to create a diff.
        """
        if node_before is None and node_after is None:
            raise ValueError("Cannot diff two None nodes.")

        if node_before is None:
            status = "ADDED"
            name = node_after.name
            type_name = node_after.type_name
            size_before = 0
            size_after = node_after.total_size
        elif node_after is None:
            status = "REMOVED"
            name = node_before.name
            type_name = node_before.type_name
            size_before = node_before.total_size
            size_after = 0
        else:
            name = node_after.name
            type_name = node_after.type_name
            size_before = node_before.total_size
            size_after = node_after.total_size
            if size_after > size_before:
                status = "CHANGED"
            elif size_after < size_before:
                status = "CHANGED"
            else:
                status = "UNCHANGED"

        diff_node = MemoryDiffNode(
            name=name,
            type_name=type_name,
            status=status,
            size_before=size_before,
            size_after=size_after,
        )

        children_before: Dict[str, MemoryNode] = (
            {child.name: child for child in node_before.children} if node_before else {}
        )
        children_after: Dict[str, MemoryNode] = (
            {child.name: child for child in node_after.children} if node_after else {}
        )

        all_child_names = set(children_before.keys()) | set(children_after.keys())

        child_diffs = []
        for child_name in sorted(list(all_child_names)):
            child_before = children_before.get(child_name)
            child_after = children_after.get(child_name)
            child_diff = self._diff_nodes(child_before, child_after)
            child_diffs.append(child_diff)

        diff_node.children = sorted(
            child_diffs, key=lambda d: abs(d.delta), reverse=True
        )

        return diff_node


class MemoryDiffReportGenerator:
    """
    Takes a MemoryDiffNode tree and generates a formatted string report.
    """

    def __init__(
        self,
        diff_root: MemoryDiffNode,
        threshold_bytes: int = 1024,
        collapse_threshold_ratio: float = 0.95,
    ):
        """
        Initializes the MemoryDiffReportGenerator.

        Args:
            diff_root: The root of the MemoryDiffNode tree.
            threshold_bytes: The minimum absolute delta for a node to be included.
            collapse_threshold_ratio: The ratio of a child's delta to its parent's
                delta to be considered for collapsing pass-through nodes.
        """
        self.diff_root = diff_root
        self.threshold_bytes = threshold_bytes
        self.collapse_threshold_ratio = collapse_threshold_ratio

    def _is_string_like_repr(self, type_name: str) -> bool:
        """Heuristically determines if a type_name string is a repr of a string."""
        return (
            isinstance(type_name, str)
            and type_name.startswith(("'", '"'))
            and type_name.endswith(("'", '"'))
        )

    def _format_size(self, size_bytes: int) -> str:
        """Formats a size in bytes into a human-readable string (B, KB, MB, GB)."""
        if abs(size_bytes) < 1024:
            return f"{size_bytes} B"
        elif abs(size_bytes) < 1024**2:
            return f"{size_bytes / 1024:.2f} KB"
        elif abs(size_bytes) < 1024**3:
            return f"{size_bytes / (1024**2):.2f} MB"
        else:
            return f"{size_bytes / (1024**3):.2f} GB"

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
        Generates the full, formatted memory diff report as a string.
        """
        if not isinstance(self.diff_root, MemoryDiffNode):
            return str(self.diff_root)

        root_delta_str = self._format_size(self.diff_root.delta)
        if self.diff_root.delta >= 0:
            root_delta_str = f"+{root_delta_str}"

        report_lines = [
            f"Memory Diff for: {self._clean_repr(self.diff_root.name)}: {self._clean_repr(self.diff_root.type_name)}",
            f"Delta: {root_delta_str}",
            f"(Before: {self._format_size(self.diff_root.size_before)}, After: {self._format_size(self.diff_root.size_after)})",
            "-" * 80,
        ]
        report_lines.extend(
            self._format_node_and_children(self.diff_root, indent_level=0)
        )
        return "\n".join(report_lines)

    def _find_significant_children(self, node: MemoryDiffNode) -> List[MemoryDiffNode]:
        """Finds children whose delta is a significant portion of the parent's delta."""
        if node.delta == 0:
            return []
        return [
            child
            for child in node.children
            if (child.delta * node.delta) >= 0
            and abs(child.delta) >= abs(node.delta) * self.collapse_threshold_ratio
        ]

    def _get_clean_node_name(self, node: MemoryDiffNode) -> str:
        """Cleans and simplifies a node's name for display."""
        if self._is_string_like_repr(node.type_name):
            content = node.name.strip("'\"")
            if len(content) > 30:
                return f'str: "{content[:30]}..."'
            return f'str: "{content}"'

        clean_name = self._clean_repr(node.name)
        if clean_name.startswith("[") and clean_name.endswith("]"):
            return f"list ({len(node.children)} items)"
        elif clean_name.startswith("{") and clean_name.endswith("}"):
            return f"dict ({len(node.children) // 2} items)"
        return clean_name.split(":", 1)[0]

    def _format_node_and_children(
        self, parent_node: MemoryDiffNode, indent_level: int
    ) -> List[str]:
        """
        Recursively formats a node's children, collapsing pass-through nodes.
        """
        lines = []
        indent = "  " * indent_level

        children_to_show = [
            child
            for child in parent_node.children
            if abs(child.delta) >= self.threshold_bytes or child.status != "UNCHANGED"
        ]
        processed_children = set()

        for child in children_to_show:
            if id(child) in processed_children:
                continue

            current_node = child
            path = [self._get_clean_node_name(current_node)]

            while True:
                significant_children = self._find_significant_children(current_node)
                if len(significant_children) == 1:
                    current_node = significant_children[0]
                    path.append(self._get_clean_node_name(current_node))
                    processed_children.add(id(current_node))
                else:
                    break

            final_node_in_chain = current_node

            status_marker = {"ADDED": "[+]", "REMOVED": "[-]", "CHANGED": "[~]"}.get(
                child.status, "   "
            )

            filtered_path = [
                segment
                for i, segment in enumerate(path)
                if segment != "__dict__" or i == len(path) - 1
            ]
            if not filtered_path:
                filtered_path = [self._get_clean_node_name(final_node_in_chain)]

            path_str = " -> ".join(filtered_path)
            final_node_type = self._clean_repr(final_node_in_chain.type_name)

            if self._is_string_like_repr(final_node_in_chain.type_name):
                name_part = path_str
            else:
                name_part = f"{path_str}: {final_node_type}"

            delta_str = self._format_size(child.delta)
            if child.delta >= 0:
                delta_str = f"+{delta_str}"

            size_info = f"({self._format_size(child.size_before)} -> {self._format_size(child.size_after)})"

            line = f"{indent}{status_marker} {name_part:<70} | Delta: {delta_str:>12} {size_info}"
            lines.append(line)

            lines.extend(
                self._format_node_and_children(final_node_in_chain, indent_level + 1)
            )

        num_pruned = len(parent_node.children) - len(children_to_show)
        if num_pruned > 0:
            lines.append(
                f"{indent}  (...and {num_pruned} other children with delta < {self._format_size(self.threshold_bytes)})"
            )

        return lines
