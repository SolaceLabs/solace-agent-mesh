"""
Artifact generators for stress testing.

Provides utilities to generate test artifacts of various sizes and types.
"""

import os
import random
import string
from typing import Optional


def generate_random_artifact(
    size_bytes: int,
    seed: Optional[int] = None,
) -> bytes:
    """
    Generate random binary artifact of specified size.

    Uses a deterministic random generator if seed is provided for reproducibility.

    Args:
        size_bytes: Size of artifact in bytes
        seed: Optional random seed for reproducibility

    Returns:
        Random bytes of specified size
    """
    if seed is not None:
        rng = random.Random(seed)
        return bytes(rng.getrandbits(8) for _ in range(size_bytes))
    else:
        return os.urandom(size_bytes)


def generate_text_artifact(
    size_bytes: int,
    pattern: str = "line",
    seed: Optional[int] = None,
) -> bytes:
    """
    Generate text artifact of specified size.

    Args:
        size_bytes: Target size in bytes
        pattern: Pattern type - "line" (numbered lines), "lorem" (lorem ipsum),
                 "json" (JSON-like structure), "random" (random chars)
        seed: Optional random seed for reproducibility

    Returns:
        Text content as bytes
    """
    rng = random.Random(seed) if seed is not None else random

    if pattern == "line":
        lines = []
        current_size = 0
        line_num = 1
        while current_size < size_bytes:
            line = f"Line {line_num}: This is test content for stress testing the artifact system.\n"
            lines.append(line)
            current_size += len(line)
            line_num += 1
        content = "".join(lines)[:size_bytes]

    elif pattern == "lorem":
        lorem = (
            "Lorem ipsum dolor sit amet, consectetur adipiscing elit. "
            "Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. "
            "Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris. "
            "Duis aute irure dolor in reprehenderit in voluptate velit esse cillum. "
            "Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia. "
        )
        repeats = (size_bytes // len(lorem)) + 1
        content = (lorem * repeats)[:size_bytes]

    elif pattern == "json":
        # Generate JSON-like content
        items = []
        current_size = 0
        item_num = 0
        while current_size < size_bytes:
            item = (
                f'{{"id": {item_num}, "name": "item_{item_num}", '
                f'"value": {rng.random():.6f}, "active": {str(rng.choice([True, False])).lower()}}},\n'
            )
            items.append(item)
            current_size += len(item)
            item_num += 1
        content = '{"items": [\n' + "".join(items)[:-2] + "\n]}"
        content = content[:size_bytes]

    elif pattern == "random":
        chars = string.ascii_letters + string.digits + " \n"
        content = "".join(rng.choice(chars) for _ in range(size_bytes))

    else:
        raise ValueError(f"Unknown pattern: {pattern}")

    return content.encode("utf-8")


def generate_json_artifact(
    num_items: int = 100,
    item_size: int = 100,
    seed: Optional[int] = None,
) -> bytes:
    """
    Generate a JSON artifact with specified structure.

    Args:
        num_items: Number of items in the JSON array
        item_size: Approximate size of each item in bytes
        seed: Optional random seed for reproducibility

    Returns:
        JSON content as bytes
    """
    rng = random.Random(seed) if seed is not None else random

    def random_string(length: int) -> str:
        return "".join(
            rng.choice(string.ascii_letters + string.digits)
            for _ in range(length)
        )

    items = []
    for i in range(num_items):
        # Adjust field sizes to get approximate item_size
        name_len = max(10, item_size // 4)
        desc_len = max(20, item_size // 2)

        item = {
            "id": i,
            "uuid": f"{rng.randint(0, 0xFFFFFFFF):08x}-{rng.randint(0, 0xFFFF):04x}-"
            f"{rng.randint(0, 0xFFFF):04x}-{rng.randint(0, 0xFFFF):04x}-"
            f"{rng.randint(0, 0xFFFFFFFFFFFF):012x}",
            "name": random_string(name_len),
            "description": random_string(desc_len),
            "value": rng.random() * 1000,
            "count": rng.randint(0, 10000),
            "active": rng.choice([True, False]),
            "tags": [random_string(8) for _ in range(rng.randint(1, 5))],
        }
        items.append(item)

    import json

    return json.dumps({"items": items}, indent=2).encode("utf-8")


def generate_csv_artifact(
    num_rows: int = 1000,
    num_columns: int = 10,
    seed: Optional[int] = None,
) -> bytes:
    """
    Generate a CSV artifact.

    Args:
        num_rows: Number of data rows
        num_columns: Number of columns
        seed: Optional random seed for reproducibility

    Returns:
        CSV content as bytes
    """
    rng = random.Random(seed) if seed is not None else random

    lines = []

    # Header
    headers = [f"column_{i}" for i in range(num_columns)]
    lines.append(",".join(headers))

    # Data rows
    for row_idx in range(num_rows):
        values = []
        for col_idx in range(num_columns):
            if col_idx == 0:
                values.append(str(row_idx))
            elif col_idx % 3 == 0:
                values.append(f"{rng.random():.6f}")
            elif col_idx % 3 == 1:
                values.append(str(rng.randint(0, 10000)))
            else:
                values.append(
                    "".join(
                        rng.choice(string.ascii_letters) for _ in range(10)
                    )
                )
        lines.append(",".join(values))

    return "\n".join(lines).encode("utf-8")


# Pre-defined size constants for convenience
KB = 1024
MB = 1024 * 1024

ARTIFACT_SIZES = {
    "tiny": 1 * KB,  # 1 KB
    "small": 10 * KB,  # 10 KB
    "medium": 1 * MB,  # 1 MB
    "large": 10 * MB,  # 10 MB
    "xlarge": 50 * MB,  # 50 MB (default max upload)
}


def get_artifact_size(name: str) -> int:
    """
    Get artifact size by name.

    Args:
        name: Size name (tiny, small, medium, large, xlarge)

    Returns:
        Size in bytes
    """
    if name not in ARTIFACT_SIZES:
        raise ValueError(
            f"Unknown size name: {name}. "
            f"Available: {list(ARTIFACT_SIZES.keys())}"
        )
    return ARTIFACT_SIZES[name]
