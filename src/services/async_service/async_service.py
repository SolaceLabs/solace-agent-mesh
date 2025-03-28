"""AsyncService for managing asynchronous tasks."""

import json
import os
from uuid import uuid4
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union

from solace_ai_connector.common.log import log

# Import database classes conditionally to handle missing dependencies
try:
    from ...common.mysql_database import MySQLDatabase
    MYSQL_AVAILABLE = True
except ImportError:
    MySQLDatabase = None
    MYSQL_AVAILABLE = False

try:
    from ...common.postgres_database import PostgresDatabase
    POSTGRES_AVAILABLE = True
except ImportError:
    PostgresDatabase = None
    POSTGRES_AVAILABLE = False


class AsyncService:
    """
    Service for managing asynchronous tasks such as approval requests.
    
    This service can store task state in memory or in a database.
    """
    
    def __init__(self, db_config: Dict[str, Any] = None):
        """
        Initialize the AsyncService.
        
        Args:
            db_config: Database configuration dictionary
        """
        self.db = self._initialize_db(db_config or {})
        self.tasks = {}  # In-memory cache of tasks
        self.default_timeout_seconds = db_config.get("default_timeout_seconds", 3600) if db_config else 3600
        
        # Initialize database tables if needed
        if self.db:
            self._initialize_tables()
    
    def _initialize_db(self, db_config: Dict[str, Any]) -> Optional[Any]:
        """
        Initialize database connection based on config.
        
        Args:
            db_config: Database configuration dictionary
            
        Returns:
            Database connection object or None if using in-memory storage
        """
        db_type = db_config.get("type", "memory")
        
        if db_type == "mysql":
            if not MYSQL_AVAILABLE:
                log.warning("MySQL database requested but mysql-connector-python is not installed. Falling back to in-memory storage.")
                return None
                
            return MySQLDatabase(
                host=db_config.get("host", "localhost"),
                user=db_config.get("username", "root"),
                password=db_config.get("password", ""),
                database=db_config.get("database", "async_service")
            )
        elif db_type == "postgres":
            if not POSTGRES_AVAILABLE:
                log.warning("PostgreSQL database requested but psycopg2 is not installed. Falling back to in-memory storage.")
                return None
                
            return PostgresDatabase(
                host=db_config.get("host", "localhost"),
                user=db_config.get("username", "postgres"),
                password=db_config.get("password", ""),
                database=db_config.get("database", "async_service")
            )
        else:
            # Use in-memory storage
            log.info("Using in-memory storage for AsyncService")
            return None
    
    def _initialize_tables(self) -> None:
        """Initialize database tables if they don't exist."""
        if self.db is None:
            return
            
        if MYSQL_AVAILABLE and isinstance(self.db, MySQLDatabase):
            self._initialize_mysql_tables()
        elif POSTGRES_AVAILABLE and isinstance(self.db, PostgresDatabase):
            self._initialize_postgres_tables()
    
    def _initialize_mysql_tables(self) -> None:
        """Initialize MySQL database tables."""
        cursor = self.db.cursor()
        
        # Create async_tasks table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS async_tasks (
                task_id VARCHAR(36) PRIMARY KEY,
                stimulus_id VARCHAR(36) NOT NULL,
                created_at TIMESTAMP NOT NULL,
                timeout_at TIMESTAMP NOT NULL,
                status VARCHAR(20) NOT NULL,
                session_state TEXT,
                stimulus_state TEXT,
                agent_list_state TEXT,
                gateway_id VARCHAR(255),
                INDEX (status),
                INDEX (timeout_at)
            )
        """)
        
        # Create async_approvals table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS async_approvals (
                approval_id VARCHAR(36) PRIMARY KEY,
                task_id VARCHAR(36) NOT NULL,
                originator VARCHAR(255) NOT NULL,
                form_schema TEXT NOT NULL,
                approval_data TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL,
                FOREIGN KEY (task_id) REFERENCES async_tasks(task_id) ON DELETE CASCADE
            )
        """)
        
        # Create async_decisions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS async_decisions (
                decision_id VARCHAR(36) PRIMARY KEY,
                approval_id VARCHAR(36) NOT NULL,
                decision VARCHAR(20) NOT NULL,
                form_data TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL,
                FOREIGN KEY (approval_id) REFERENCES async_approvals(approval_id) ON DELETE CASCADE
            )
        """)
    
    def _initialize_postgres_tables(self) -> None:
        """Initialize PostgreSQL database tables."""
        cursor = self.db.cursor()
        
        # Create async_tasks table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS async_tasks (
                task_id VARCHAR(36) PRIMARY KEY,
                stimulus_id VARCHAR(36) NOT NULL,
                created_at TIMESTAMP NOT NULL,
                timeout_at TIMESTAMP NOT NULL,
                status VARCHAR(20) NOT NULL,
                session_state TEXT,
                stimulus_state TEXT,
                agent_list_state TEXT,
                gateway_id VARCHAR(255)
            )
        """)
        
        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_async_tasks_status ON async_tasks (status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_async_tasks_timeout ON async_tasks (timeout_at)")
        
        # Create async_approvals table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS async_approvals (
                approval_id VARCHAR(36) PRIMARY KEY,
                task_id VARCHAR(36) NOT NULL,
                originator VARCHAR(255) NOT NULL,
                form_schema TEXT NOT NULL,
                approval_data TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL,
                CONSTRAINT fk_task_id FOREIGN KEY (task_id) REFERENCES async_tasks(task_id) ON DELETE CASCADE
            )
        """)
        
        # Create async_decisions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS async_decisions (
                decision_id VARCHAR(36) PRIMARY KEY,
                approval_id VARCHAR(36) NOT NULL,
                decision VARCHAR(20) NOT NULL,
                form_data TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL,
                CONSTRAINT fk_approval_id FOREIGN KEY (approval_id) REFERENCES async_approvals(approval_id) ON DELETE CASCADE
            )
        """)
    
    def create_task(
        self, 
        stimulus_id: str, 
        session_state: Dict[str, Any], 
        stimulus_state: Dict[str, Any], 
        agent_list_state: Dict[str, Any],
        gateway_id: str,
        timeout_seconds: int = None
    ) -> str:
        """
        Create a new async task.
        
        Args:
            stimulus_id: ID of the stimulus
            session_state: Session state to store
            stimulus_state: Stimulus state to store
            agent_list_state: Agent list state to store
            gateway_id: ID of the gateway that originated the request
            timeout_seconds: Timeout in seconds (default: use default_timeout_seconds)
            
        Returns:
            Task ID
        """
        if timeout_seconds is None:
            timeout_seconds = self.default_timeout_seconds
            
        task_id = str(uuid4())
        created_at = datetime.now()
        timeout_at = created_at + timedelta(seconds=timeout_seconds)
        
        task = {
            "task_id": task_id,
            "stimulus_id": stimulus_id,
            "created_at": created_at,
            "timeout_at": timeout_at,
            "status": "pending",
            "session_state": json.dumps(session_state) if session_state else None,
            "stimulus_state": json.dumps(stimulus_state) if stimulus_state else None,
            "agent_list_state": json.dumps(agent_list_state) if agent_list_state else None,
            "gateway_id": gateway_id,
            "approvals": {},
            "approval_decisions": {}
        }
        
        # Store in database
        if self.db:
            if isinstance(self.db, MySQLDatabase):
                cursor = self.db.cursor()
                cursor.execute(
                    """
                    INSERT INTO async_tasks 
                    (task_id, stimulus_id, created_at, timeout_at, status, session_state, stimulus_state, agent_list_state, gateway_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        task_id, stimulus_id, created_at, timeout_at, "pending",
                        task["session_state"], task["stimulus_state"], task["agent_list_state"], gateway_id
                    )
                )
            elif isinstance(self.db, PostgresDatabase):
                self.db.execute(
                    """
                    INSERT INTO async_tasks 
                    (task_id, stimulus_id, created_at, timeout_at, status, session_state, stimulus_state, agent_list_state, gateway_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        task_id, stimulus_id, created_at, timeout_at, "pending",
                        task["session_state"], task["stimulus_state"], task["agent_list_state"], gateway_id
                    )
                )
        
        # Cache in memory
        self.tasks[task_id] = task
        
        return task_id
    
    def add_approval(
        self, 
        task_id: str, 
        originator: str, 
        form_schema: Dict[str, Any], 
        approval_data: Dict[str, Any]
    ) -> str:
        """
        Add an approval request to a task.
        
        Args:
            task_id: Task ID
            originator: Originator of the approval request
            form_schema: Form schema for the approval request
            approval_data: Data for the approval request
            
        Returns:
            Approval ID
        """
        task = self.get_task(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
            
        approval_id = str(uuid4())
        created_at = datetime.now()
        
        # Store in database
        if self.db:
            form_schema_json = json.dumps(form_schema)
            approval_data_json = json.dumps(approval_data)
            
            if isinstance(self.db, MySQLDatabase):
                cursor = self.db.cursor()
                cursor.execute(
                    """
                    INSERT INTO async_approvals 
                    (approval_id, task_id, originator, form_schema, approval_data, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (approval_id, task_id, originator, form_schema_json, approval_data_json, created_at)
                )
            elif isinstance(self.db, PostgresDatabase):
                self.db.execute(
                    """
                    INSERT INTO async_approvals 
                    (approval_id, task_id, originator, form_schema, approval_data, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (approval_id, task_id, originator, form_schema_json, approval_data_json, created_at)
                )
        
        # Update in-memory cache
        if task_id in self.tasks:
            if "approvals" not in self.tasks[task_id]:
                self.tasks[task_id]["approvals"] = {}
                
            self.tasks[task_id]["approvals"][approval_id] = {
                "originator": originator,
                "form_schema": form_schema,
                "approval_data": approval_data,
                "created_at": created_at
            }
        
        return approval_id
    
    def add_decision(
        self, 
        approval_id: str, 
        decision: str, 
        form_data: Dict[str, Any]
    ) -> str:
        """
        Add a decision to an approval request.
        
        Args:
            approval_id: Approval ID
            decision: Decision (approve/reject)
            form_data: Form data from the decision
            
        Returns:
            Decision ID
        """
        # Find the task containing this approval
        task_id = None
        for tid, task in self.tasks.items():
            if "approvals" in task and approval_id in task["approvals"]:
                task_id = tid
                break
                
        if not task_id:
            if self.db:
                # Try to find the approval in the database
                if isinstance(self.db, MySQLDatabase):
                    cursor = self.db.cursor(dictionary=True)
                    cursor.execute(
                        "SELECT task_id FROM async_approvals WHERE approval_id = %s",
                        (approval_id,)
                    )
                    result = cursor.fetchone()
                    if result:
                        task_id = result["task_id"]
                elif isinstance(self.db, PostgresDatabase):
                    cursor = self.db.execute(
                        "SELECT task_id FROM async_approvals WHERE approval_id = %s",
                        (approval_id,)
                    )
                    result = cursor.fetchone()
                    if result:
                        task_id = result["task_id"]
            
            if not task_id:
                raise ValueError(f"Approval {approval_id} not found")
        
        decision_id = str(uuid4())
        created_at = datetime.now()
        
        # Store in database
        if self.db:
            form_data_json = json.dumps(form_data)
            
            if isinstance(self.db, MySQLDatabase):
                cursor = self.db.cursor()
                cursor.execute(
                    """
                    INSERT INTO async_decisions 
                    (decision_id, approval_id, decision, form_data, created_at)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (decision_id, approval_id, decision, form_data_json, created_at)
                )
            elif isinstance(self.db, PostgresDatabase):
                self.db.execute(
                    """
                    INSERT INTO async_decisions 
                    (decision_id, approval_id, decision, form_data, created_at)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (decision_id, approval_id, decision, form_data_json, created_at)
                )
        
        # Update in-memory cache
        if task_id in self.tasks:
            if "approval_decisions" not in self.tasks[task_id]:
                self.tasks[task_id]["approval_decisions"] = {}
                
            self.tasks[task_id]["approval_decisions"][approval_id] = {
                "decision_id": decision_id,
                "decision": decision,
                "form_data": form_data,
                "created_at": created_at
            }
            
            # Check if all approvals are received
            all_approved = True
            for aid in self.tasks[task_id].get("approvals", {}):
                if aid not in self.tasks[task_id].get("approval_decisions", {}):
                    all_approved = False
                    break
                    
            if all_approved:
                self.update_task_status(task_id, "approved")
        
        return decision_id
    
    def update_task_status(self, task_id: str, status: str) -> None:
        """
        Update the status of a task.
        
        Args:
            task_id: Task ID
            status: New status
        """
        # Update in database
        if self.db:
            if isinstance(self.db, MySQLDatabase):
                cursor = self.db.cursor()
                cursor.execute(
                    "UPDATE async_tasks SET status = %s WHERE task_id = %s",
                    (status, task_id)
                )
            elif isinstance(self.db, PostgresDatabase):
                self.db.execute(
                    "UPDATE async_tasks SET status = %s WHERE task_id = %s",
                    (status, task_id)
                )
        
        # Update in-memory cache
        if task_id in self.tasks:
            self.tasks[task_id]["status"] = status
    
    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get task by ID.
        
        Args:
            task_id: Task ID
            
        Returns:
            Task dictionary or None if not found
        """
        # Check in-memory cache first
        if task_id in self.tasks:
            return self.tasks[task_id]
            
        # Check database
        if self.db:
            task = None
            
            if isinstance(self.db, MySQLDatabase):
                cursor = self.db.cursor(dictionary=True)
                cursor.execute(
                    "SELECT * FROM async_tasks WHERE task_id = %s",
                    (task_id,)
                )
                task = cursor.fetchone()
            elif isinstance(self.db, PostgresDatabase):
                cursor = self.db.execute(
                    "SELECT * FROM async_tasks WHERE task_id = %s",
                    (task_id,)
                )
                task = cursor.fetchone()
            
            if task:
                # Convert stored JSON strings back to dictionaries
                if task["session_state"]:
                    task["session_state"] = json.loads(task["session_state"])
                if task["stimulus_state"]:
                    task["stimulus_state"] = json.loads(task["stimulus_state"])
                if task["agent_list_state"]:
                    task["agent_list_state"] = json.loads(task["agent_list_state"])
                
                # Get approvals
                approvals = {}
                if isinstance(self.db, MySQLDatabase):
                    cursor = self.db.cursor(dictionary=True)
                    cursor.execute(
                        "SELECT * FROM async_approvals WHERE task_id = %s",
                        (task_id,)
                    )
                    for approval in cursor.fetchall():
                        approval_id = approval["approval_id"]
                        approvals[approval_id] = {
                            "originator": approval["originator"],
                            "form_schema": json.loads(approval["form_schema"]),
                            "approval_data": json.loads(approval["approval_data"]),
                            "created_at": approval["created_at"]
                        }
                elif isinstance(self.db, PostgresDatabase):
                    cursor = self.db.execute(
                        "SELECT * FROM async_approvals WHERE task_id = %s",
                        (task_id,)
                    )
                    for approval in cursor.fetchall():
                        approval_id = approval["approval_id"]
                        approvals[approval_id] = {
                            "originator": approval["originator"],
                            "form_schema": json.loads(approval["form_schema"]),
                            "approval_data": json.loads(approval["approval_data"]),
                            "created_at": approval["created_at"]
                        }
                
                task["approvals"] = approvals
                
                # Get decisions
                approval_decisions = {}
                for approval_id in approvals:
                    if isinstance(self.db, MySQLDatabase):
                        cursor = self.db.cursor(dictionary=True)
                        cursor.execute(
                            "SELECT * FROM async_decisions WHERE approval_id = %s",
                            (approval_id,)
                        )
                        decision = cursor.fetchone()
                        if decision:
                            approval_decisions[approval_id] = {
                                "decision_id": decision["decision_id"],
                                "decision": decision["decision"],
                                "form_data": json.loads(decision["form_data"]),
                                "created_at": decision["created_at"]
                            }
                    elif isinstance(self.db, PostgresDatabase):
                        cursor = self.db.execute(
                            "SELECT * FROM async_decisions WHERE approval_id = %s",
                            (approval_id,)
                        )
                        decision = cursor.fetchone()
                        if decision:
                            approval_decisions[approval_id] = {
                                "decision_id": decision["decision_id"],
                                "decision": decision["decision"],
                                "form_data": json.loads(decision["form_data"]),
                                "created_at": decision["created_at"]
                            }
                
                task["approval_decisions"] = approval_decisions
                
                # Cache in memory
                self.tasks[task_id] = task
                
                return task
            
        return None
    
    def check_timeouts(self) -> List[Dict[str, Any]]:
        """
        Check for timed out tasks.
        
        Returns:
            List of timed out tasks
        """
        now = datetime.now()
        timed_out_tasks = []
        
        # Check database first
        if self.db:
            if isinstance(self.db, MySQLDatabase):
                cursor = self.db.cursor(dictionary=True)
                cursor.execute(
                    "SELECT task_id FROM async_tasks WHERE status = 'pending' AND timeout_at < %s",
                    (now,)
                )
                for row in cursor.fetchall():
                    task_id = row["task_id"]
                    task = self.get_task(task_id)  # This will load the full task
                    if task:
                        self.update_task_status(task_id, "timeout")
                        timed_out_tasks.append(task)
            elif isinstance(self.db, PostgresDatabase):
                cursor = self.db.execute(
                    "SELECT task_id FROM async_tasks WHERE status = 'pending' AND timeout_at < %s",
                    (now,)
                )
                for row in cursor.fetchall():
                    task_id = row["task_id"]
                    task = self.get_task(task_id)  # This will load the full task
                    if task:
                        self.update_task_status(task_id, "timeout")
                        timed_out_tasks.append(task)
        
        # Also check in-memory cache
        for task_id, task in self.tasks.items():
            if task["status"] == "pending" and task["timeout_at"] < now:
                self.update_task_status(task_id, "timeout")
                timed_out_tasks.append(task)
        
        return timed_out_tasks
    
    def is_task_complete(self, task_id: str) -> bool:
        """
        Check if a task is complete (all approvals received).
        
        Args:
            task_id: Task ID
            
        Returns:
            True if all approvals are received, False otherwise
        """
        task = self.get_task(task_id)
        if not task:
            return False
            
        # Check if all approvals are received
        for approval_id in task.get("approvals", {}):
            if approval_id not in task.get("approval_decisions", {}):
                return False
                
        return True
    
    def get_task_by_stimulus_id(self, stimulus_id: str) -> Optional[Dict[str, Any]]:
        """
        Get task by stimulus ID.
        
        Args:
            stimulus_id: Stimulus ID
            
        Returns:
            Task dictionary or None if not found
        """
        # Check in-memory cache first
        for task in self.tasks.values():
            if task["stimulus_id"] == stimulus_id:
                return task
                
        # Check database
        if self.db:
            if isinstance(self.db, MySQLDatabase):
                cursor = self.db.cursor(dictionary=True)
                cursor.execute(
                    "SELECT task_id FROM async_tasks WHERE stimulus_id = %s",
                    (stimulus_id,)
                )
                result = cursor.fetchone()
                if result:
                    return self.get_task(result["task_id"])
            elif isinstance(self.db, PostgresDatabase):
                cursor = self.db.execute(
                    "SELECT task_id FROM async_tasks WHERE stimulus_id = %s",
                    (stimulus_id,)
                )
                result = cursor.fetchone()
                if result:
                    return self.get_task(result["task_id"])
                    
        return None