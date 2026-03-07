"""
Records SSE events to YAML files for debugging and replay.
"""
import yaml
from pathlib import Path
from typing import List, Dict, Any
from dataclasses import dataclass, asdict
from datetime import datetime, timezone


@dataclass
class RecordedEvent:
    """A recorded SSE event with metadata."""

    sequence: int
    timestamp: str
    event_type: str
    data: Dict[str, Any]


class EventRecorder:
    """
    Records SSE events to YAML files.
    """

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._events: List[RecordedEvent] = []
        self._sequence = 0

    def record_event(self, event_type: str, data: Dict[str, Any]):
        """Record a single SSE event."""
        self._sequence += 1
        event = RecordedEvent(
            sequence=self._sequence,
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type=event_type,
            data=data,
        )
        self._events.append(event)

    def save(self, filename: str = "sse_events.yaml") -> Path:
        """Save all recorded events to a YAML file."""
        output_path = self.output_dir / filename

        events_data = {
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "total_events": len(self._events),
            "events": [asdict(e) for e in self._events],
        }

        with open(output_path, "w") as f:
            yaml.dump(
                events_data,
                f,
                sort_keys=False,
                allow_unicode=True,
                default_flow_style=False,
                width=120,
            )

        return output_path

    def get_events(self) -> List[RecordedEvent]:
        """Get all recorded events."""
        return list(self._events)

    def get_event_count(self) -> int:
        """Get the count of recorded events."""
        return len(self._events)
