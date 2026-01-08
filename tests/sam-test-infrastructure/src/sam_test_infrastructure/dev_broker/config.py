"""
Configuration management for the development Solace broker simulator.
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass, field
import socket


def find_free_port() -> int:
    """Finds and returns an available TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


@dataclass
class BrokerConfig:
    """Configuration for the development Solace broker."""
    
    host: str = "127.0.0.1"
    port: int = field(default_factory=find_free_port)
    vpn: str = "test_vpn"
    username: str = "test_user"
    password: str = "test_password"
    client_name: str = "dev_broker_client"
    
    # Message handling configuration
    max_queue_size: int = 1000
    message_ttl_seconds: int = 300
    enable_persistence: bool = False
    
    # Topic configuration
    default_qos: int = 1
    max_subscriptions: int = 100
    
    # Logging configuration
    log_level: str = "INFO"
    enable_message_logging: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary format."""
        return {
            "broker_url": f"tcp://{self.host}:{self.port}",
            "broker_vpn": self.vpn,
            "broker_username": self.username,
            "broker_password": self.password,
            "broker_client_name": self.client_name,
            "max_queue_size": self.max_queue_size,
            "message_ttl_seconds": self.message_ttl_seconds,
            "enable_persistence": self.enable_persistence,
            "default_qos": self.default_qos,
            "max_subscriptions": self.max_subscriptions,
            "log_level": self.log_level,
            "enable_message_logging": self.enable_message_logging,
        }
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "BrokerConfig":
        """Create configuration from dictionary."""
        # Extract host and port from broker_url if provided
        broker_url = config_dict.get("broker_url", "")
        if broker_url.startswith("tcp://"):
            url_part = broker_url[6:]  # Remove 'tcp://'
            if ":" in url_part:
                host, port_str = url_part.split(":", 1)
                try:
                    port = int(port_str)
                except ValueError:
                    host = "127.0.0.1"
                    port = find_free_port()
            else:
                host = url_part
                port = find_free_port()
        else:
            host = config_dict.get("host", "127.0.0.1")
            port = config_dict.get("port", find_free_port())
        
        return cls(
            host=host,
            port=port,
            vpn=config_dict.get("broker_vpn", "test_vpn"),
            username=config_dict.get("broker_username", "test_user"),
            password=config_dict.get("broker_password", "test_password"),
            client_name=config_dict.get("broker_client_name", "dev_broker_client"),
            max_queue_size=config_dict.get("max_queue_size", 1000),
            message_ttl_seconds=config_dict.get("message_ttl_seconds", 300),
            enable_persistence=config_dict.get("enable_persistence", False),
            default_qos=config_dict.get("default_qos", 1),
            max_subscriptions=config_dict.get("max_subscriptions", 100),
            log_level=config_dict.get("log_level", "INFO"),
            enable_message_logging=config_dict.get("enable_message_logging", True),
        )
    
    @property
    def broker_url(self) -> str:
        """Get the broker URL."""
        return f"tcp://{self.host}:{self.port}"
    
    def get_sac_broker_config(self) -> Dict[str, Any]:
        """Get configuration in SAC broker format."""
        return {
            "broker_url": self.broker_url,
            "broker_vpn": self.vpn,
            "broker_username": self.username,
            "broker_password": self.password,
            "broker_client_name": self.client_name,
        }
