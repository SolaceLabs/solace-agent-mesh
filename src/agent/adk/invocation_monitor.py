import copy
import datetime
import json
import os
import yaml

from solace_ai_connector.common.log import log


class InvocationMonitor:
    LOG_DIRECTORY = "/tmp/solace-agent-mesh"
    START_TOPIC_SUFFIX = "a2a/v1/agent/request/OrchestratorAgent"
    END_TOPIC_CONTAINS = "a2a/v1/gateway/response/"
    EXCLUDE_TOPIC_SUFFIX = "/discovery/agentcards"
    LOG_FILE_VERSION = "1.0"

    def __init__(self):
        self._is_logging_active = False
        self._current_log_buffer = []
        self._current_logfile_path = None
        self._invocation_start_time = None
        self._triggering_event_details = None
        self._current_invocation_id = None
        self._current_session_id = None

        try:
            os.makedirs(self.LOG_DIRECTORY, exist_ok=True)
            log.info(
                f"InvocationMonitor initialized. Logging to directory: {self.LOG_DIRECTORY}"
            )
        except Exception as e:
            log.error(
                f"InvocationMonitor: Failed to create log directory {self.LOG_DIRECTORY}: {e}"
            )
            self.LOG_DIRECTORY = None

    def _sanitize(self, value):
        """Replace underscores with dashes and convert to string."""
        return str(value).replace("_", "-") if value is not None else "unknown"

    def _generate_logfile_path(self, invocation_id, gateway) -> str:
        if not self.LOG_DIRECTORY:
            return None
        timestamp = str(int(datetime.datetime.now(datetime.timezone.utc).timestamp()))
        invocation_id = self._sanitize(invocation_id)
        gateway = self._sanitize(gateway)
        filename = f"{invocation_id}_{gateway}_{timestamp}.stim"
        return os.path.join(self.LOG_DIRECTORY, filename)

    def _finalize_log_file(self, terminating_event_details=None):
        if not self._is_logging_active or not self._current_logfile_path:
            if self._is_logging_active:
                log.warning("InvocationMonitor: Finalize called but no log file path.")
            self._reset_session()
            return

        if not self._current_log_buffer and not self._triggering_event_details:
            log.info(
                f"InvocationMonitor: No messages were logged for {self._current_logfile_path}. Skipping file creation."
            )
            self._reset_session()
            return

        invocation_end_time = datetime.datetime.now(datetime.timezone.utc).timestamp()

        yaml_data = {
            "invocation_details": {
                "log_file_version": self.LOG_FILE_VERSION,
                "start_time": self._invocation_start_time,
                "end_time": invocation_end_time,
                "triggering_event": self._triggering_event_details,
                "terminating_event": terminating_event_details,
            },
            "invocation_flow": self._current_log_buffer,
        }

        try:
            with open(self._current_logfile_path, "w", encoding="utf-8") as f:
                yaml.dump(
                    yaml_data,
                    f,
                    sort_keys=False,
                    allow_unicode=True,
                    indent=2,
                    default_flow_style=False,
                )
            log.info(
                f"InvocationMonitor: YAML content saved to .stim file: {self._current_logfile_path}"
            )
        except Exception as e:
            log.error(
                f"InvocationMonitor: Failed to write YAML content to .stim file {self._current_logfile_path}: {e}"
            )
        finally:
            self._reset_session()

    def _reset_session(self):
        self._is_logging_active = False
        self._current_log_buffer = []
        self._current_logfile_path = None
        self._invocation_start_time = None
        self._triggering_event_details = None
        self._current_invocation_id = None
        self._current_session_id = None

    def _prepare_payload_for_yaml(self, payload):
        if isinstance(payload, str):
            try:
                return json.loads(payload)
            except json.JSONDecodeError:
                return payload
        elif isinstance(payload, (dict, list)):
            return payload
        elif isinstance(payload, bytes):
            try:
                return payload.decode("utf-8")
            except UnicodeDecodeError:
                return repr(payload)
        return str(payload)

    def _add_log_entry(
        self,
        direction: str,
        topic: str,
        payload: any,
        component_identifier: str,
        is_trigger_event=False,
    ):
        timestamp = datetime.datetime.now(datetime.timezone.utc).timestamp()
        prepared_payload = self._prepare_payload_for_yaml(payload)

        log_entry_dict = {
            "topic": topic,
            "timestamp": timestamp,
            "component": component_identifier,
            "direction": direction,
            "payload": prepared_payload,
        }

        if is_trigger_event:
            return {
                "timestamp": timestamp,
                "component": component_identifier,
                "direction": direction,
                "topic": topic,
                "payload": prepared_payload,
            }

        if self._is_logging_active:
            self._current_log_buffer.append(log_entry_dict)

        return log_entry_dict

    def log_message_event(
        self,
        direction: str,
        topic: str,
        payload: any,
        component_identifier: str = "A2A_Host",
    ):
        if not self.LOG_DIRECTORY:
            log.error(
                "InvocationMonitor: Log directory not available. Skipping log_message_event."
            )
            return

        if topic.endswith(self.EXCLUDE_TOPIC_SUFFIX):
            return

        if self.START_TOPIC_SUFFIX in topic:
            method = None
            invocation_id = None
            session_id = None
            if isinstance(payload, dict):
                method = payload.get("method")
                invocation_id = payload.get("id") or "unknown"
                session_id = payload.get("params", {}).get("sessionId", None)
            elif isinstance(payload, str):
                try:
                    payload_obj = json.loads(payload)
                    method = payload_obj.get("method")
                    invocation_id = payload_obj.get("id") or "unknown"
                    session_id = payload_obj.get("params", {}).get("sessionId", None)
                except Exception:
                    invocation_id = "unknown"
                    session_id = None

            if method != "tasks/sendSubscribe":
                if self._is_logging_active and method == "tasks/cancel":
                    log.warning(
                        f"InvocationMonitor: Cancel event received for topic {topic} (id={invocation_id}, sessionId={session_id}) while a session for {self._current_logfile_path} was active. "
                        "Finalizing previous session with reason: 'Request was canceled'."
                    )
                    self._finalize_log_file(
                        terminating_event_details={
                            "reason": "Request was canceled",
                            "topic": topic,
                            "method": method,
                            "invocation_id": invocation_id,
                            "session_id": session_id,
                        }
                    )
                return

            if self._is_logging_active:
                log.warning(
                    f"InvocationMonitor: New start event received for topic {topic} (id={invocation_id}, sessionId={session_id}, method={method}) while a session for {self._current_logfile_path} was active. "
                    "Finalizing previous session with reason: 'New session started before old one ended'."
                )
                self._finalize_log_file(
                    terminating_event_details={
                        "reason": "New session started before old one ended",
                        "topic": topic,
                        "method": method,
                        "invocation_id": invocation_id,
                        "session_id": session_id,
                    }
                )

            self._is_logging_active = True
            self._current_log_buffer = []
            self._current_invocation_id = invocation_id
            self._current_session_id = session_id

            log.debug(
                f"InvocationMonitor: Received start event for topic {topic}. Payload: {payload}"
            )

            gateway = "unknown"
            if session_id and "web-session" in session_id:
                gateway = "web"
            elif session_id and "slack" in session_id:
                gateway = "slack"

            self._current_logfile_path = self._generate_logfile_path(
                invocation_id, gateway
            )

            if not self._current_logfile_path:
                log.error(
                    "InvocationMonitor: Could not generate logfile path. Aborting logging for this session."
                )
                self._reset_session()
                return

            self._invocation_start_time = datetime.datetime.now(
                datetime.timezone.utc
            ).timestamp()
            self._triggering_event_details = self._add_log_entry(
                direction, topic, payload, component_identifier, is_trigger_event=True
            )

            if self._triggering_event_details:
                first_flow_entry = {
                    "topic": self._triggering_event_details["topic"],
                    "timestamp": self._triggering_event_details["timestamp"],
                    "component": self._triggering_event_details["component"],
                    "direction": self._triggering_event_details["direction"],
                    "payload": copy.deepcopy(self._triggering_event_details["payload"]),
                }
                self._current_log_buffer.append(first_flow_entry)

            log.info(
                f"InvocationMonitor: Started YAML logging (to .stim file) for new invocation. File: {self._current_logfile_path}. Trigger: {topic}"
            )

        elif self._is_logging_active:
            current_event_details = self._add_log_entry(
                direction, topic, payload, component_identifier, is_trigger_event=False
            )

            if self.END_TOPIC_CONTAINS in topic:
                log.info(
                    f"InvocationMonitor: End condition met by topic {topic}. Finalizing YAML content to .stim file: {self._current_logfile_path}"
                )
                terminating_event_info = {
                    "timestamp": current_event_details["timestamp"],
                    "component": current_event_details["component"],
                    "direction": current_event_details["direction"],
                    "topic": current_event_details["topic"],
                    "payload": copy.deepcopy(current_event_details["payload"]),
                }
                self._finalize_log_file(
                    terminating_event_details=terminating_event_info
                )

    def cleanup(self):
        log.info("InvocationMonitor: Cleanup called.")
        if self._is_logging_active and self._current_logfile_path:
            log.warning(
                f"InvocationMonitor: Finalizing YAML content to .stim file {self._current_logfile_path} during cleanup."
            )
            self._finalize_log_file(
                terminating_event_details={"reason": "Session finalized during cleanup"}
            )
