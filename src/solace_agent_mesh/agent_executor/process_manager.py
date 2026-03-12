"""Agent subprocess lifecycle manager."""

import logging
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

from .manifest import AgentEntry

log = logging.getLogger(__name__)

MAX_RESTART_DELAY = 60.0
INITIAL_RESTART_DELAY = 1.0


@dataclass
class AgentProcess:
    agent_id: str
    deployment_id: str
    process: Optional[subprocess.Popen]
    checksum: str
    yaml_path: Path
    started_at: float
    status: str = "starting"
    restart_count: int = 0
    last_restart_at: float = 0.0


class AgentProcessManager:
    """Manages agent subprocesses — start, stop, update, health check."""

    def __init__(self, work_dir: str, env_vars: Optional[Dict[str, str]] = None):
        self._work_dir = Path(work_dir)
        self._work_dir.mkdir(parents=True, exist_ok=True)
        self._base_env = dict(os.environ)
        if env_vars:
            self._base_env.update(env_vars)
        self._processes: Dict[str, AgentProcess] = {}

    def start_agent(self, entry: AgentEntry) -> AgentProcess:
        agent_dir = self._work_dir / entry.agent_id
        agent_dir.mkdir(parents=True, exist_ok=True)

        yaml_path = agent_dir / "config.yaml"
        yaml_path.write_text(entry.config_yaml)

        env = dict(self._base_env)
        env.update(entry.values)

        proc = subprocess.Popen(
            ["solace-agent-mesh", "run", "--system-env", str(yaml_path)],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=str(agent_dir),
        )

        agent_proc = AgentProcess(
            agent_id=entry.agent_id,
            deployment_id=entry.deployment_id,
            process=proc,
            checksum=entry.checksum,
            yaml_path=yaml_path,
            started_at=time.time(),
            status="running",
        )
        self._processes[entry.agent_id] = agent_proc

        log.info(
            "Started agent '%s' (pid=%d, deployment=%s)",
            entry.agent_id,
            proc.pid,
            entry.deployment_id,
        )
        return agent_proc

    def stop_agent(self, agent_id: str, timeout: float = 30.0) -> None:
        agent_proc = self._processes.get(agent_id)
        if not agent_proc or not agent_proc.process:
            return

        proc = agent_proc.process
        pid = proc.pid

        log.info("Stopping agent '%s' (pid=%d)...", agent_id, pid)
        proc.terminate()
        try:
            proc.wait(timeout=timeout)
            log.info("Agent '%s' (pid=%d) terminated gracefully", agent_id, pid)
        except subprocess.TimeoutExpired:
            log.warning("Agent '%s' (pid=%d) did not stop in %ds, killing", agent_id, pid, timeout)
            proc.kill()
            proc.wait(timeout=5)

        agent_proc.status = "stopped"
        agent_proc.process = None

    def update_agent(self, entry: AgentEntry) -> AgentProcess:
        existing = self._processes.get(entry.agent_id)
        if existing and existing.checksum == entry.checksum:
            return existing

        log.info(
            "Updating agent '%s' (checksum %s -> %s)",
            entry.agent_id,
            existing.checksum if existing else "none",
            entry.checksum,
        )
        self.stop_agent(entry.agent_id)
        return self.start_agent(entry)

    def remove_agent(self, agent_id: str) -> None:
        self.stop_agent(agent_id)
        self._processes.pop(agent_id, None)

        agent_dir = self._work_dir / agent_id
        if agent_dir.exists():
            import shutil

            shutil.rmtree(agent_dir, ignore_errors=True)

        log.info("Removed agent '%s'", agent_id)

    def get_all_statuses(self) -> Dict[str, dict]:
        result = {}
        for agent_id, ap in self._processes.items():
            pid = ap.process.pid if ap.process else None
            uptime = time.time() - ap.started_at if ap.status == "running" else 0
            result[agent_id] = {
                "status": ap.status,
                "pid": pid,
                "uptime": round(uptime, 1),
                "restart_count": ap.restart_count,
                "deployment_id": ap.deployment_id,
            }
        return result

    def check_health(self) -> None:
        for agent_id, ap in list(self._processes.items()):
            if ap.status not in ("running", "starting") or not ap.process:
                continue

            rc = ap.process.poll()
            if rc is None:
                continue

            ap.status = "crashed"
            log.warning("Agent '%s' (pid=%d) exited with code %d", agent_id, ap.process.pid, rc)

            delay = min(INITIAL_RESTART_DELAY * (2 ** ap.restart_count), MAX_RESTART_DELAY)
            time_since_last = time.time() - ap.last_restart_at if ap.last_restart_at else delay

            if time_since_last < delay:
                log.info(
                    "Agent '%s' restart backoff: %.1fs remaining",
                    agent_id,
                    delay - time_since_last,
                )
                continue

            ap.restart_count += 1
            ap.last_restart_at = time.time()
            log.info("Restarting agent '%s' (attempt #%d)", agent_id, ap.restart_count)

            yaml_path = ap.yaml_path
            if yaml_path.exists():
                env = dict(self._base_env)
                entry = AgentEntry(
                    agent_id=agent_id,
                    desired_state="running",
                    config_yaml=yaml_path.read_text(),
                    checksum=ap.checksum,
                    deployment_id=ap.deployment_id,
                )
                env.update(entry.values)

                proc = subprocess.Popen(
                    ["solace-agent-mesh", "run", "--system-env", str(yaml_path)],
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    cwd=str(yaml_path.parent),
                )
                ap.process = proc
                ap.started_at = time.time()
                ap.status = "running"
                log.info("Restarted agent '%s' (new pid=%d)", agent_id, proc.pid)

    def shutdown_all(self, timeout: float = 30.0) -> None:
        log.info("Shutting down all agents (%d running)...", len(self._processes))
        for agent_id in list(self._processes.keys()):
            self.stop_agent(agent_id, timeout=timeout)
        self._processes.clear()

    def is_running(self, agent_id: str) -> bool:
        ap = self._processes.get(agent_id)
        if not ap or not ap.process:
            return False
        return ap.process.poll() is None
