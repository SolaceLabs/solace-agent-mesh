"""
Session tag entity for bookmark functionality.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class SessionTag:
    """Entity representing a session tag (bookmark)."""
    
    id: str
    user_id: str
    tag: str
    description: Optional[str] = None
    count: int = 0
    position: int = 0
    created_time: int = 0
    updated_time: Optional[int] = None
    
    def update_description(self, description: str) -> None:
        """Update the tag description."""
        self.description = description
        
    def update_position(self, position: int) -> None:
        """Update the tag position."""
        self.position = position
        
    def increment_count(self) -> None:
        """Increment the usage count."""
        self.count += 1
        
    def decrement_count(self) -> None:
        """Decrement the usage count."""
        if self.count > 0:
            self.count -= 1