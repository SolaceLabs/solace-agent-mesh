"""
Agent Executor Application.

Runs multiple agents as subprocesses within a single pod.
Syncs agent configurations from S3, reconciles desired vs actual state,
publishes heartbeats, and responds to broker commands.
"""

import json
import logging
import os
import threading
import time
from typing import Any, Dict, Optional

from .manifest import AgentManifest
from .process_manager import AgentProcessManager

log = logging.getLogger(__name__)


class AgentExecutorApp:
    """
    Main application for the Remote Agent Executor.

    Lifecycle:
      1. Start S3 sync (if enabled) → wait for first sync
      2. Load manifest
      3. Create process manager
      4. Start reconcile loop (background thread)
      5. Start heartbeat publisher (background thread)
      6. Start health server
    """

    def __init__(self, config: Dict[str, Any]):
        self._config = config
        self._namespace = config["namespace"]
        self._executor_id = config.get("executor_id", "agent-executor-001")

        self._manifest_path = config.get("manifest_path", "/agents/manifest.json")
        self._work_dir = config.get("work_dir", "/agents/work")
        self._reconcile_interval = float(config.get("reconcile_interval", 15))
        self._heartbeat_interval = float(config.get("heartbeat_interval", 30))
        self._health_port = int(config.get("health_port", 8082))

        self._broker_config = config.get("broker", {})

        self._manifest: Optional[AgentManifest] = None
        self._process_manager: Optional[AgentProcessManager] = None
        self._tool_sync_service = None
        self._stop_event = threading.Event()
        self._startup_complete = False
        self._broker_publisher = None

    def run(self) -> None:
        log.info(
            "Starting AgentExecutorApp: executor_id='%s' namespace='%s'",
            self._executor_id,
            self._namespace,
        )

        sync_cfg = self._config.get("sync", {})
        if sync_cfg.get("enabled", False):
            self._start_sync(sync_cfg)

        self._manifest = AgentManifest(self._manifest_path)

        env_vars = self._collect_passthrough_env()
        self._process_manager = AgentProcessManager(self._work_dir, env_vars)

        self._setup_broker()

        self._reconcile()

        reconcile_thread = threading.Thread(
            target=self._reconcile_loop,
            name="reconcile-loop",
            daemon=True,
        )
        reconcile_thread.start()

        heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            name="heartbeat-loop",
            daemon=True,
        )
        heartbeat_thread.start()

        from ..sandbox.health_server import start_health_server

        self._health_server = start_health_server(
            checks={
                "/healthz": self._check_liveness,
                "/readyz": self._check_readiness,
                "/startup": self._check_startup,
            },
            port=self._health_port,
        )

        self._startup_complete = True
        log.info("AgentExecutorApp '%s' startup complete", self._executor_id)

    def _start_sync(self, cfg: Dict[str, Any]) -> None:
        from ..sandbox.storage import create_sync_client
        from ..sandbox.tool_sync_service import ToolSyncService

        remote_prefix = f"{self._namespace}/agent-executor/"
        local_dir = os.path.dirname(self._manifest_path)
        interval = float(cfg.get("interval", 10))

        log.info(
            "Starting agent sync: prefix=%s local=%s interval=%ds",
            remote_prefix,
            local_dir,
            interval,
        )

        client = create_sync_client(
            storage_type=cfg.get("storage_type"),
            bucket_name=cfg.get("bucket_name"),
        )
        self._tool_sync_service = ToolSyncService(
            client=client,
            remote_prefix=remote_prefix,
            local_dir=local_dir,
            interval=interval,
        )
        self._tool_sync_service.start()

        if not self._tool_sync_service.wait_for_first_sync(timeout=120.0):
            log.warning("Agent sync first cycle did not succeed within timeout")

    def _setup_broker(self) -> None:
        """Set up Solace broker connection for heartbeats and commands."""
        broker_url = self._broker_config.get("broker_url")
        if not broker_url:
            log.info("No broker URL configured — heartbeats and commands disabled")
            return

        try:
            from solace.messaging.messaging_service import MessagingService
            from solace.messaging.resources.topic import Topic
            from solace.messaging.resources.topic_subscription import TopicSubscription

            props = {
                "solace.messaging.transport.host": broker_url,
                "solace.messaging.service.vpn-name": self._broker_config.get("broker_vpn", "default"),
                "solace.messaging.authentication.scheme.basic.username": self._broker_config.get("broker_username", ""),
                "solace.messaging.authentication.scheme.basic.password": self._broker_config.get("broker_password", ""),
                "solace.messaging.tls.cert-validated": False,
                "solace.messaging.tls.cert-reject-expired": False,
                "solace.messaging.tls.cert-validate-servername": False,
            }

            service = MessagingService.builder().from_properties(props).build()
            service.connect()
            log.info("Connected to broker for heartbeats/commands")

            self._broker_publisher = service.create_direct_message_publisher_builder().build()
            self._broker_publisher.start()

            from solace.messaging.receiver.message_receiver import MessageHandler

            receiver = service.create_direct_message_receiver_builder().with_subscriptions([
                TopicSubscription.of(f"{self._namespace}/agent-executor/commands"),
            ]).build()
            receiver.start()

            class CommandHandler(MessageHandler):
                def __init__(self, app):
                    self._app = app

                def on_message(self, message):
                    log.info("Received command, triggering immediate reconcile")
                    self._app._reconcile()

            receiver.receive_async(CommandHandler(self))
            self._broker_service = service

        except ImportError:
            log.info("Solace messaging SDK not available — broker features disabled")
        except Exception as e:
            log.warning("Failed to connect to broker: %s — continuing without broker", e)

    def _collect_passthrough_env(self) -> Dict[str, str]:
        """Collect environment variables to pass through to agent subprocesses."""
        passthrough = {}
        for key in (
            "LLM_SERVICE_API_KEY",
            "LLM_SERVICE_ENDPOINT",
            "LLM_SERVICE_PLANNING_MODEL_NAME",
            "LLM_SERVICE_GENERAL_MODEL_NAME",
            "S3_ENDPOINT_URL",
            "S3_BUCKET_NAME",
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "AWS_REGION",
        ):
            val = os.environ.get(key)
            if val:
                passthrough[key] = val

        broker = self._broker_config
        if broker.get("broker_url"):
            passthrough["SOLACE_BROKER_URL"] = broker["broker_url"]
            passthrough["SOLACE_BROKER_VPN"] = broker.get("broker_vpn", "default")
            passthrough["SOLACE_BROKER_USERNAME"] = broker.get("broker_username", "")
            passthrough["SOLACE_BROKER_PASSWORD"] = broker.get("broker_password", "")

        return passthrough

    def _reconcile(self) -> None:
        if not self._manifest or not self._process_manager:
            return

        self._manifest.reload_if_changed()

        desired = self._manifest.get_all_agents()
        running_ids = set(
            aid for aid in self._process_manager.get_all_statuses()
            if self._process_manager.is_running(aid)
        )

        for agent_id, entry in desired.items():
            if entry.desired_state == "running":
                if agent_id not in running_ids:
                    log.info("Starting agent '%s'", agent_id)
                    self._process_manager.start_agent(entry)
                else:
                    self._process_manager.update_agent(entry)
            elif entry.desired_state == "stopped":
                if agent_id in running_ids:
                    log.info("Stopping agent '%s'", agent_id)
                    self._process_manager.stop_agent(agent_id)
            elif entry.desired_state == "removed":
                log.info("Removing agent '%s'", agent_id)
                self._process_manager.remove_agent(agent_id)

        desired_ids = set(desired.keys())
        for orphan_id in running_ids - desired_ids:
            log.info("Removing orphan agent '%s'", orphan_id)
            self._process_manager.remove_agent(orphan_id)

        self._process_manager.check_health()

    def _reconcile_loop(self) -> None:
        while not self._stop_event.is_set():
            self._stop_event.wait(timeout=self._reconcile_interval)
            if self._stop_event.is_set():
                break
            try:
                self._reconcile()
            except Exception as e:
                log.error("Reconcile error: %s", e, exc_info=True)

    def _heartbeat_loop(self) -> None:
        while not self._stop_event.is_set():
            self._stop_event.wait(timeout=self._heartbeat_interval)
            if self._stop_event.is_set():
                break
            try:
                self._publish_heartbeat()
            except Exception as e:
                log.error("Heartbeat error: %s", e, exc_info=True)

    def _publish_heartbeat(self) -> None:
        if not self._broker_publisher:
            return

        from solace.messaging.resources.topic import Topic

        statuses = self._process_manager.get_all_statuses() if self._process_manager else {}
        payload = json.dumps({
            "executor_id": self._executor_id,
            "timestamp": time.time(),
            "agents": statuses,
        })

        topic = Topic.of(f"{self._namespace}/agent-executor/heartbeat")
        self._broker_publisher.publish(payload, topic)

    def _check_liveness(self) -> dict:
        return {"ok": True}

    def _check_readiness(self) -> dict:
        manifest_loaded = self._manifest is not None
        return {"ok": manifest_loaded, "manifest_loaded": manifest_loaded}

    def _check_startup(self) -> dict:
        sync_ok = True
        if self._tool_sync_service:
            sync_ok = (
                self._tool_sync_service._first_sync_done.is_set()
                and self._tool_sync_service._first_sync_error is None
            )
        ok = self._startup_complete and sync_ok
        return {"ok": ok, "startup_complete": self._startup_complete, "sync": "ok" if sync_ok else "pending"}

    def stop(self) -> None:
        log.info("Stopping AgentExecutorApp '%s'...", self._executor_id)
        self._stop_event.set()

        if self._process_manager:
            self._process_manager.shutdown_all()

        if hasattr(self, "_health_server") and self._health_server:
            self._health_server.shutdown()

        if self._tool_sync_service:
            self._tool_sync_service.stop()

        if hasattr(self, "_broker_publisher") and self._broker_publisher:
            try:
                self._broker_publisher.terminate()
            except Exception:
                pass

        if hasattr(self, "_broker_service") and self._broker_service:
            try:
                self._broker_service.disconnect()
            except Exception:
                pass

        log.info("AgentExecutorApp '%s' stopped", self._executor_id)
