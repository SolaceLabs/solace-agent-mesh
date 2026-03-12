#!/usr/bin/env python3
"""
Agent Executor Container Entrypoint.

Configures and runs the AgentExecutorApp inside a container.
Configuration is read from environment variables.
"""

import logging
import os
import signal
import sys
import threading

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger(__name__)


def get_env(key: str, default=None, required=False):
    value = os.environ.get(key, default)
    if required and not value:
        log.error("Required environment variable not set: %s", key)
        sys.exit(1)
    return value


def get_env_bool(key: str, default: bool = False) -> bool:
    value = os.environ.get(key, "").lower()
    if value in ("true", "1", "yes", "on"):
        return True
    if value in ("false", "0", "no", "off"):
        return False
    return default


def get_env_int(key: str, default: int) -> int:
    value = os.environ.get(key)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        log.warning("Invalid integer for %s: %s, using default: %d", key, value, default)
        return default


def build_config():
    namespace = get_env("SAM_NAMESPACE", required=True)
    executor_id = get_env("SAM_EXECUTOR_ID", "agent-executor-001")

    broker_config = {}
    solace_host = get_env("SOLACE_HOST")
    if solace_host:
        broker_config = {
            "broker_url": solace_host,
            "broker_vpn": get_env("SOLACE_VPN", "default"),
            "broker_username": get_env("SOLACE_USERNAME", ""),
            "broker_password": get_env("SOLACE_PASSWORD", ""),
        }

    sync_config = {
        "enabled": get_env_bool("AGENT_SYNC_ENABLED", False),
        "interval": get_env_int("AGENT_SYNC_INTERVAL", 10),
        "storage_type": get_env("OBJECT_STORAGE_TYPE"),
        "bucket_name": get_env("OBJECT_STORAGE_BUCKET_NAME") or get_env("S3_BUCKET_NAME"),
    }

    return {
        "namespace": namespace,
        "executor_id": executor_id,
        "manifest_path": get_env("MANIFEST_PATH", "/agents/manifest.json"),
        "work_dir": get_env("WORK_DIR", "/agents/work"),
        "reconcile_interval": get_env_int("RECONCILE_INTERVAL", 15),
        "heartbeat_interval": get_env_int("HEARTBEAT_INTERVAL", 30),
        "health_port": get_env_int("HEALTH_PORT", 8082),
        "broker": broker_config,
        "sync": sync_config,
    }


def main():
    log.info("Starting SAM Agent Executor...")

    try:
        config = build_config()
    except SystemExit:
        raise
    except Exception as e:
        log.error("Failed to build configuration: %s", e)
        sys.exit(1)

    log.info(
        "Configuration: namespace=%s, executor_id=%s, broker=%s",
        config["namespace"],
        config["executor_id"],
        config["broker"].get("broker_url", "none"),
    )

    try:
        from solace_agent_mesh.agent_executor import AgentExecutorApp
    except ImportError as e:
        log.error("Failed to import AgentExecutorApp. Ensure solace-agent-mesh is installed: %s", e)
        sys.exit(1)

    stop_event = threading.Event()

    try:
        app = AgentExecutorApp(config)
    except Exception as e:
        log.error("Failed to create AgentExecutorApp: %s", e)
        sys.exit(1)

    def signal_handler(signum, frame):
        log.info("Received signal %d, shutting down...", signum)
        stop_event.set()
        try:
            app.stop()
        except Exception as e:
            log.error("Error during shutdown: %s", e)
        sys.exit(0)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    log.info("Starting AgentExecutorApp...")
    try:
        app.run()
        stop_event.wait()
    except KeyboardInterrupt:
        log.info("Interrupted, shutting down...")
        stop_event.set()
        app.stop()
    except Exception as e:
        log.error("AgentExecutorApp failed: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
