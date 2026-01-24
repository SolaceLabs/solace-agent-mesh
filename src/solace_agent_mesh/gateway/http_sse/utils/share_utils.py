"""
Utility functions for share link functionality.
"""

import re
import logging
from typing import Optional, Dict, Any, List
from nanoid import generate

log = logging.getLogger(__name__)

# Nanoid alphabet (URL-safe characters)
NANOID_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
NANOID_SIZE = 21  # 126 bits of entropy


def generate_share_id() -> str:
    """
    Generate a unique share ID using nanoid.
    
    Returns:
        21-character URL-safe string with 126 bits of entropy
    """
    return generate(NANOID_ALPHABET, NANOID_SIZE)


def validate_domain(domain: str) -> bool:
    """
    Validate email domain format.
    
    Args:
        domain: Domain string to validate (e.g., "company.com")
    
    Returns:
        True if valid, False otherwise
    """
    if not domain or '.' not in domain:
        return False
    
    # Prevent common mistakes
    if domain.startswith('@') or domain.startswith('.') or domain.endswith('.'):
        return False
    
    # Check for valid characters (RFC 1035)
    # Domain labels can contain letters, digits, and hyphens
    # Labels must start and end with alphanumeric
    pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$'
    
    if not re.match(pattern, domain):
        return False
    
    # Additional checks
    if len(domain) > 253:  # Max domain length
        return False
    
    # Check each label length
    labels = domain.split('.')
    for label in labels:
        if len(label) > 63:  # Max label length
            return False
    
    return True


def extract_email_domain(email: str) -> Optional[str]:
    """
    Safely extract domain from email address.
    
    Args:
        email: Email address
    
    Returns:
        Domain string (lowercase) or None if invalid
    """
    if not email or '@' not in email:
        return None
    
    parts = email.split('@')
    if len(parts) != 2:
        return None
    
    domain = parts[1].lower().strip()
    return domain if validate_domain(domain) else None


def validate_domains_list(domains: List[str]) -> tuple[bool, Optional[str]]:
    """
    Validate a list of domains.
    
    Args:
        domains: List of domain strings
    
    Returns:
        Tuple of (is_valid: bool, error_message: Optional[str])
    """
    if not domains:
        return (True, None)
    
    if len(domains) > 10:  # Max 10 domains per share
        return (False, "Maximum 10 domains allowed")
    
    seen = set()
    for domain in domains:
        domain_lower = domain.lower().strip()
        
        if not validate_domain(domain_lower):
            return (False, f"Invalid domain format: {domain}")
        
        if domain_lower in seen:
            return (False, f"Duplicate domain: {domain}")
        
        seen.add(domain_lower)
    
    return (True, None)


def anonymize_id(original_id: str, prefix: str = "anon") -> str:
    """
    Create an anonymized version of an ID.
    
    Args:
        original_id: Original ID to anonymize
        prefix: Prefix for anonymized ID
    
    Returns:
        Anonymized ID string
    """
    # Use a hash-based approach for consistent anonymization within a session
    import hashlib
    hash_obj = hashlib.sha256(original_id.encode())
    hash_hex = hash_obj.hexdigest()[:16]  # Use first 16 chars of hash
    return f"{prefix}_{hash_hex}"


def anonymize_chat_task(task: Dict[str, Any]) -> Dict[str, Any]:
    """
    Anonymize a chat task for public sharing.
    
    Args:
        task: Chat task dictionary
    
    Returns:
        Anonymized task dictionary
    """
    import json as json_module
    
    anonymized = task.copy()
    
    # Extract A2A task_id from task_metadata for workflow lookup
    # This is the key used in task_events dictionary
    task_metadata = anonymized.get('task_metadata')
    a2a_task_id = None
    
    if task_metadata:
        if isinstance(task_metadata, str):
            try:
                task_metadata = json_module.loads(task_metadata)
            except:
                task_metadata = None
        
        if task_metadata and isinstance(task_metadata, dict):
            a2a_task_id = task_metadata.get("task_id")
    
    # Store the A2A task ID for workflow lookup (falls back to chat task id)
    anonymized['workflow_task_id'] = a2a_task_id or anonymized.get('id')
    
    # Anonymize session_id but keep task id
    if 'session_id' in anonymized:
        anonymized['session_id'] = anonymize_id(anonymized['session_id'], 'session')
    
    # Remove user-identifying information
    if 'user_id' in anonymized:
        anonymized['user_id'] = 'anonymous'
    
    # Keep message content but anonymize metadata
    if 'message_bubbles' in anonymized:
        import json
        try:
            bubbles = json.loads(anonymized['message_bubbles']) if isinstance(anonymized['message_bubbles'], str) else anonymized['message_bubbles']
            for bubble in bubbles:
                # Keep message content but remove user-specific metadata
                if 'metadata' in bubble:
                    bubble['metadata'] = {k: v for k, v in bubble['metadata'].items() if k not in ['userId', 'sessionId']}
            anonymized['message_bubbles'] = json.dumps(bubbles) if isinstance(anonymized['message_bubbles'], str) else bubbles
        except Exception as e:
            log.warning(f"Failed to anonymize message bubbles: {e}")
    
    return anonymized


def build_share_url(share_id: str, base_url: str) -> str:
    """
    Build the full share URL.
    
    Args:
        share_id: Share ID
        base_url: Base URL of the application
    
    Returns:
        Full share URL
    """
    # Remove trailing slash from base_url
    base_url = base_url.rstrip('/')
    # Use hash router format for frontend compatibility
    return f"{base_url}/#/share/{share_id}"


def parse_allowed_domains(domains_str: Optional[str]) -> List[str]:
    """
    Parse comma-separated domains string into a list.
    
    Args:
        domains_str: Comma-separated domains string
    
    Returns:
        List of domain strings
    """
    if not domains_str:
        return []
    return [d.strip() for d in domains_str.split(',') if d.strip()]


def format_allowed_domains(domains: List[str]) -> Optional[str]:
    """
    Format domains list into comma-separated string.
    
    Args:
        domains: List of domain strings
    
    Returns:
        Comma-separated string or None if empty
    """
    if not domains:
        return None
    return ','.join(domains)
