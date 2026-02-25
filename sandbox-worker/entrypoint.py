#!/usr/bin/env python3
"""
Sandbox Worker Container Entrypoint.

This script configures and runs the SandboxWorkerApp inside a container.
Configuration is read from environment variables and/or a config file.
"""

import logging
import os
import signal
import sys
from typing import Any, Dict, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger(__name__)


def get_env(key: str, default: Optional[str] = None, required: bool = False) -> Optional[str]:
    """Get environment variable with optional default and validation."""
    value = os.environ.get(key, default)
    if required and not value:
        log.error("Required environment variable not set: %s", key)
        sys.exit(1)
    return value


def get_env_bool(key: str, default: bool = False) -> bool:
    """Get boolean environment variable."""
    value = os.environ.get(key, "").lower()
    if value in ("true", "1", "yes", "on"):
        return True
    if value in ("false", "0", "no", "off"):
        return False
    return default


def get_env_int(key: str, default: int) -> int:
    """Get integer environment variable."""
    value = os.environ.get(key)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        log.warning("Invalid integer for %s: %s, using default: %d", key, value, default)
        return default


def build_app_info() -> Dict[str, Any]:
    """Build the application info dictionary from environment variables."""
    # Required configuration
    namespace = get_env("SAM_NAMESPACE", required=True)
    worker_id = get_env("SAM_WORKER_ID", "sandbox-worker-001")

    # Check if using dev broker (network mode)
    dev_broker_host = get_env("DEV_BROKER_HOST")
    dev_broker_port = get_env_int("DEV_BROKER_PORT", 55555)

    if dev_broker_host:
        # Use network dev broker (for local testing with containers)
        log.info(
            "Using network dev broker at %s:%d",
            dev_broker_host,
            dev_broker_port,
        )
        broker_config = {
            "dev_mode": True,
            "dev_broker_host": dev_broker_host,
            "dev_broker_port": dev_broker_port,
            "connect_retries": get_env_int("CONNECT_RETRIES", 0),
            "connect_retry_delay_ms": get_env_int("CONNECT_RETRY_DELAY_MS", 3000),
        }
    else:
        # Use real Solace broker
        solace_host = get_env("SOLACE_HOST", required=True)
        solace_vpn = get_env("SOLACE_VPN", "default")
        solace_username = get_env("SOLACE_USERNAME", "admin")
        solace_password = get_env("SOLACE_PASSWORD", "admin")

        # Optional broker settings
        trust_store_path = get_env("SOLACE_TRUST_STORE_PATH")
        client_cert_path = get_env("SOLACE_CLIENT_CERT_PATH")
        client_key_path = get_env("SOLACE_CLIENT_KEY_PATH")

        broker_config = {
            "broker_url": solace_host,
            "broker_vpn": solace_vpn,
            "broker_username": solace_username,
            "broker_password": solace_password,
            "reconnect_retries": get_env_int("SOLACE_RECONNECT_RETRIES", 10),
            "reconnect_delay_ms": get_env_int("SOLACE_RECONNECT_DELAY_MS", 3000),
        }

        # Add optional TLS settings
        if trust_store_path:
            broker_config["trust_store_path"] = trust_store_path
        if client_cert_path:
            broker_config["client_cert_path"] = client_cert_path
        if client_key_path:
            broker_config["client_key_path"] = client_key_path

    # Sandbox (bubblewrap) configuration
    sandbox_config = {
        "bwrap_bin": get_env("SANDBOX_BWRAP_BIN", "/usr/bin/bwrap"),
        "python_bin": get_env("SANDBOX_PYTHON_BIN", "/usr/bin/python3"),
        "work_base_dir": get_env("SANDBOX_WORK_DIR", "/sandbox/work"),
        "default_profile": get_env("SANDBOX_DEFAULT_PROFILE", "standard"),
        "max_concurrent_executions": get_env_int("SANDBOX_MAX_CONCURRENT", 4),
    }

    # Artifact service configuration — must match the agent's settings for shared access.
    artifact_type = get_env("ARTIFACT_SERVICE_TYPE", "memory")
    artifact_config: Dict[str, Any] = {"type": artifact_type}

    # Scoping — must match the agent's artifact_scope for shared access
    artifact_scope = get_env("ARTIFACT_SCOPE", "namespace")
    artifact_config["artifact_scope"] = artifact_scope
    if artifact_scope == "custom":
        artifact_config["artifact_scope_value"] = get_env(
            "ARTIFACT_SCOPE_VALUE", required=True
        )

    if artifact_type == "filesystem":
        artifact_config["base_path"] = get_env("ARTIFACT_BASE_PATH", "/sam/artifacts")
    elif artifact_type == "s3":
        artifact_config["bucket_name"] = get_env("ARTIFACT_S3_BUCKET", required=True)
        artifact_config["region"] = get_env("ARTIFACT_S3_REGION", "us-east-1")
    elif artifact_type == "gcs":
        artifact_config["bucket_name"] = get_env("ARTIFACT_GCS_BUCKET", required=True)

    # Tool manifest configuration
    manifest_path = get_env("MANIFEST_PATH", "/tools/manifest.yaml")
    tools_python_dir = get_env("TOOLS_PYTHON_DIR", "/tools/python")

    # Tool sync configuration (replaces aws-cli sidecar for S3/GCS/Azure sync)
    tool_sync_config: Dict[str, Any] = {
        "enabled": get_env_bool("TOOL_SYNC_ENABLED", False),
        "interval": get_env_int("TOOL_SYNC_INTERVAL", 10),
        "storage_type": get_env("OBJECT_STORAGE_TYPE"),
        "bucket_name": get_env("OBJECT_STORAGE_BUCKET_NAME") or get_env("S3_BUCKET_NAME"),
    }

    # Build app info
    app_info: Dict[str, Any] = {
        "name": f"sandbox-worker-{worker_id}",
        "app_config": {
            "namespace": namespace,
            "worker_id": worker_id,
            "manifest_path": manifest_path,
            "tools_python_dir": tools_python_dir,
            "default_timeout_seconds": get_env_int("DEFAULT_TIMEOUT_SECONDS", 300),
            "sandbox": sandbox_config,
            "artifact_service": artifact_config,
            "tool_sync": tool_sync_config,
        },
        "broker": broker_config,
    }

    return app_info


def main():
    """Main entry point for the sandbox worker."""
    log.info("Starting SAM Sandbox Worker...")

    # Build configuration from environment
    try:
        app_info = build_app_info()
    except SystemExit:
        raise
    except Exception as e:
        log.error("Failed to build configuration: %s", e)
        sys.exit(1)

    broker = app_info["broker"]
    if broker.get("dev_broker_host"):
        broker_desc = f"dev_broker@{broker['dev_broker_host']}:{broker['dev_broker_port']}"
    else:
        broker_desc = broker.get("broker_url", "unknown")

    log.info(
        "Configuration: namespace=%s, worker_id=%s, broker=%s",
        app_info["app_config"]["namespace"],
        app_info["app_config"]["worker_id"],
        broker_desc,
    )

    # Import SAM components
    try:
        from solace_agent_mesh.sandbox import SandboxWorkerApp
    except ImportError as e:
        log.error(
            "Failed to import SAM sandbox worker. "
            "Ensure solace-agent-mesh is installed: %s",
            e,
        )
        sys.exit(1)

    import threading

    stop_signal = threading.Event()

    # Create and configure the app
    try:
        app = SandboxWorkerApp(app_info, app_index=0, stop_signal=stop_signal)
    except Exception as e:
        log.error("Failed to create SandboxWorkerApp: %s", e)
        sys.exit(1)

    # Set up signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        log.info("Received signal %d, shutting down...", signum)
        stop_signal.set()
        try:
            app.stop()
        except Exception as e:
            log.error("Error during shutdown: %s", e)
        sys.exit(0)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # Run the app
    log.info("Starting SandboxWorkerApp...")
    try:
        app.run()
        # Wait for stop signal
        stop_signal.wait()
    except KeyboardInterrupt:
        log.info("Interrupted, shutting down...")
        stop_signal.set()
        app.stop()
    except Exception as e:
        log.error("SandboxWorkerApp failed: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
