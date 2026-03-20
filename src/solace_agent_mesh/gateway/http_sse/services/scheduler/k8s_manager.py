"""
Kubernetes CronJob manager for scheduled tasks.

This service manages the lifecycle of Kubernetes CronJobs that execute scheduled tasks.
Each scheduled task in the database corresponds to a K8S CronJob.
"""

import logging
import re
from typing import Dict, Optional

from kubernetes import client, config
from kubernetes.client.rest import ApiException

from ...repository.models import ScheduledTaskModel, ScheduleType

log = logging.getLogger(__name__)


class K8SCronJobManager:
    """
    Manages Kubernetes CronJobs for scheduled tasks.
    
    This service creates, updates, and deletes K8S CronJobs based on
    scheduled task definitions in the database.
    """

    def __init__(
        self,
        namespace: str,
        executor_image: str,
        database_url_secret: str,
        broker_config_secret: str,
        a2a_namespace: str,
    ):
        """
        Initialize K8S CronJob manager.

        Args:
            namespace: Kubernetes namespace for CronJobs
            executor_image: Docker image for scheduler executor
            database_url_secret: Name of K8S secret containing database URL
            broker_config_secret: Name of K8S secret containing broker config
            a2a_namespace: A2A namespace for messaging
        """
        self.namespace = namespace
        self.executor_image = executor_image
        self.database_url_secret = database_url_secret
        self.broker_config_secret = broker_config_secret
        self.a2a_namespace = a2a_namespace
        
        # Load K8S configuration
        try:
            config.load_incluster_config()
            log.info("Loaded in-cluster Kubernetes configuration")
        except config.ConfigException:
            try:
                config.load_kube_config()
                log.info("Loaded kubeconfig from local environment")
            except config.ConfigException as e:
                log.error(f"Failed to load Kubernetes configuration: {e}")
                raise
        
        self.batch_v1 = client.BatchV1Api()
        log.info(f"K8SCronJobManager initialized for namespace '{namespace}'")

    async def sync_task(self, task: ScheduledTaskModel) -> bool:
        """
        Sync a task to K8S (create or update CronJob/Job).
        
        ONE_TIME tasks create K8S Jobs, recurring tasks create CronJobs.

        Args:
            task: Scheduled task model

        Returns:
            True if successful, False otherwise
        """
        # ONE_TIME tasks use K8S Jobs, not CronJobs
        if task.schedule_type == ScheduleType.ONE_TIME:
            return await self.sync_one_time_job(task)
        
        # Recurring tasks use CronJobs
        cronjob_name = self._get_cronjob_name(task.id)
        
        try:
            # Check if CronJob exists
            try:
                existing = self.batch_v1.read_namespaced_cron_job(
                    name=cronjob_name,
                    namespace=self.namespace
                )
                # Update existing CronJob
                return await self.update_cronjob(task)
            except ApiException as e:
                if e.status == 404:
                    # CronJob doesn't exist, create it
                    return await self.create_cronjob(task)
                else:
                    raise
        except Exception as e:
            log.error(f"Failed to sync task {task.id} to K8S: {e}", exc_info=True)
            return False

    async def create_cronjob(self, task: ScheduledTaskModel) -> bool:
        """
        Create a K8S CronJob for a scheduled task.

        Args:
            task: Scheduled task model

        Returns:
            True if successful, False otherwise
        """
        cronjob_name = self._get_cronjob_name(task.id)
        log.info(f"Creating K8S CronJob '{cronjob_name}' for task {task.id}")
        
        try:
            cronjob_spec = self._build_cronjob_spec(task)
            
            self.batch_v1.create_namespaced_cron_job(
                namespace=self.namespace,
                body=cronjob_spec
            )
            
            log.info(f"Successfully created CronJob '{cronjob_name}'")
            return True
            
        except ApiException as e:
            log.error(f"K8S API error creating CronJob: {e.status} - {e.reason}")
            return False
        except Exception as e:
            log.error(f"Failed to create CronJob: {e}", exc_info=True)
            return False

    async def update_cronjob(self, task: ScheduledTaskModel) -> bool:
        """
        Update an existing K8S CronJob.

        Args:
            task: Scheduled task model

        Returns:
            True if successful, False otherwise
        """
        cronjob_name = self._get_cronjob_name(task.id)
        log.info(f"Updating K8S CronJob '{cronjob_name}' for task {task.id}")
        
        try:
            cronjob_spec = self._build_cronjob_spec(task)
            
            self.batch_v1.replace_namespaced_cron_job(
                name=cronjob_name,
                namespace=self.namespace,
                body=cronjob_spec
            )
            
            log.info(f"Successfully updated CronJob '{cronjob_name}'")
            return True
            
        except ApiException as e:
            log.error(f"K8S API error updating CronJob: {e.status} - {e.reason}")
            return False
        except Exception as e:
            log.error(f"Failed to update CronJob: {e}", exc_info=True)
            return False

    async def sync_one_time_job(self, task: ScheduledTaskModel) -> bool:
        """
        Sync a ONE_TIME task to K8S Job.
        
        ONE_TIME tasks are scheduled to run at a specific time once.
        We create a K8S Job that will be executed at the scheduled time.

        Args:
            task: Scheduled task model (must be ONE_TIME type)

        Returns:
            True if successful, False otherwise
        """
        from datetime import datetime
        
        job_name = self._get_job_name(task.id)
        log.info(f"Syncing ONE_TIME task {task.id} as K8S Job '{job_name}'")
        
        try:
            # Parse schedule_expression as ISO 8601 datetime
            scheduled_time = datetime.fromisoformat(task.schedule_expression)
            current_time = datetime.now(scheduled_time.tzinfo or None)
            
            # Check if task should run now or has already passed
            if scheduled_time <= current_time:
                # Time has passed or is now - create/update Job immediately
                log.info(f"ONE_TIME task {task.id} scheduled time has passed, creating Job now")
                return await self.create_one_time_job(task)
            else:
                # Future execution - we'll need to create the Job when the time comes
                # For now, just log that it's scheduled
                log.info(f"ONE_TIME task {task.id} scheduled for {scheduled_time}, will create Job at that time")
                # TODO: Implement delayed Job creation (could use a watcher or timer)
                # For MVP, we'll create the Job immediately and let K8S handle it
                return await self.create_one_time_job(task)
                
        except Exception as e:
            log.error(f"Failed to sync ONE_TIME task {task.id}: {e}", exc_info=True)
            return False

    async def create_one_time_job(self, task: ScheduledTaskModel) -> bool:
        """
        Create a K8S Job for a ONE_TIME scheduled task.

        Args:
            task: Scheduled task model (must be ONE_TIME type)

        Returns:
            True if successful, False otherwise
        """
        job_name = self._get_job_name(task.id)
        log.info(f"Creating K8S Job '{job_name}' for ONE_TIME task {task.id}")
        
        try:
            # Check if Job already exists
            try:
                existing = self.batch_v1.read_namespaced_job(
                    name=job_name,
                    namespace=self.namespace
                )
                log.info(f"Job '{job_name}' already exists, skipping creation")
                return True
            except ApiException as e:
                if e.status != 404:
                    raise
            
            # Build Job spec
            job_spec = self._build_job_spec(task)
            
            self.batch_v1.create_namespaced_job(
                namespace=self.namespace,
                body=job_spec
            )
            
            log.info(f"Successfully created Job '{job_name}'")
            return True
            
        except ApiException as e:
            log.error(f"K8S API error creating Job: {e.status} - {e.reason}")
            return False
        except Exception as e:
            log.error(f"Failed to create Job: {e}", exc_info=True)
            return False

    async def delete_one_time_job(self, task_id: str) -> bool:
        """
        Delete a K8S Job for a ONE_TIME task.

        Args:
            task_id: Scheduled task ID

        Returns:
            True if successful, False otherwise
        """
        job_name = self._get_job_name(task_id)
        log.info(f"Deleting K8S Job '{job_name}' for task {task_id}")
        
        try:
            self.batch_v1.delete_namespaced_job(
                name=job_name,
                namespace=self.namespace,
                propagation_policy='Foreground'  # Delete Pods
            )
            
            log.info(f"Successfully deleted Job '{job_name}'")
            return True
            
        except ApiException as e:
            if e.status == 404:
                log.warning(f"Job '{job_name}' not found, already deleted")
                return True
            log.error(f"K8S API error deleting Job: {e.status} - {e.reason}")
            return False
        except Exception as e:
            log.error(f"Failed to delete Job: {e}", exc_info=True)
            return False

    async def delete_cronjob(self, task_id: str, schedule_type: ScheduleType = None) -> bool:
        """
        Delete a K8S CronJob or Job.

        Args:
            task_id: Scheduled task ID
            schedule_type: Schedule type (to determine if it's a Job or CronJob)

        Returns:
            True if successful, False otherwise
        """
        # If it's a ONE_TIME task, delete the Job instead
        if schedule_type == ScheduleType.ONE_TIME:
            return await self.delete_one_time_job(task_id)
        """
        Delete a K8S CronJob.

        Args:
            task_id: Scheduled task ID

        Returns:
            True if successful, False otherwise
        """
        cronjob_name = self._get_cronjob_name(task_id)
        log.info(f"Deleting K8S CronJob '{cronjob_name}' for task {task_id}")
        
        try:
            self.batch_v1.delete_namespaced_cron_job(
                name=cronjob_name,
                namespace=self.namespace,
                propagation_policy='Foreground'  # Delete Jobs and Pods
            )
            
            log.info(f"Successfully deleted CronJob '{cronjob_name}'")
            return True
            
        except ApiException as e:
            if e.status == 404:
                log.warning(f"CronJob '{cronjob_name}' not found, already deleted")
                return True
            log.error(f"K8S API error deleting CronJob: {e.status} - {e.reason}")
            return False
        except Exception as e:
            log.error(f"Failed to delete CronJob: {e}", exc_info=True)
            return False

    async def suspend_cronjob(self, task_id: str) -> bool:
        """
        Suspend a K8S CronJob (disable without deleting).

        Args:
            task_id: Scheduled task ID

        Returns:
            True if successful, False otherwise
        """
        cronjob_name = self._get_cronjob_name(task_id)
        log.info(f"Suspending K8S CronJob '{cronjob_name}'")
        
        try:
            # Patch the CronJob to set suspend=True
            body = {"spec": {"suspend": True}}
            
            self.batch_v1.patch_namespaced_cron_job(
                name=cronjob_name,
                namespace=self.namespace,
                body=body
            )
            
            log.info(f"Successfully suspended CronJob '{cronjob_name}'")
            return True
            
        except ApiException as e:
            log.error(f"K8S API error suspending CronJob: {e.status} - {e.reason}")
            return False
        except Exception as e:
            log.error(f"Failed to suspend CronJob: {e}", exc_info=True)
            return False

    async def resume_cronjob(self, task_id: str) -> bool:
        """
        Resume a suspended K8S CronJob.

        Args:
            task_id: Scheduled task ID

        Returns:
            True if successful, False otherwise
        """
        cronjob_name = self._get_cronjob_name(task_id)
        log.info(f"Resuming K8S CronJob '{cronjob_name}'")
        
        try:
            # Patch the CronJob to set suspend=False
            body = {"spec": {"suspend": False}}
            
            self.batch_v1.patch_namespaced_cron_job(
                name=cronjob_name,
                namespace=self.namespace,
                body=body
            )
            
            log.info(f"Successfully resumed CronJob '{cronjob_name}'")
            return True
            
        except ApiException as e:
            log.error(f"K8S API error resuming CronJob: {e.status} - {e.reason}")
            return False
        except Exception as e:
            log.error(f"Failed to resume CronJob: {e}", exc_info=True)
            return False

    def _get_cronjob_name(self, task_id: str) -> str:
        """
        Generate K8S CronJob name from task ID.
        
        K8S names must be DNS-1123 compliant (lowercase alphanumeric + hyphens).
        """
        # Replace underscores and other invalid chars with hyphens
        safe_id = re.sub(r'[^a-z0-9-]', '-', task_id.lower())
        return f"scheduled-task-{safe_id}"

    def _get_job_name(self, task_id: str) -> str:
        """
        Generate K8S Job name from task ID (for ONE_TIME tasks).
        
        K8S names must be DNS-1123 compliant (lowercase alphanumeric + hyphens).
        """
        # Replace underscores and other invalid chars with hyphens
        safe_id = re.sub(r'[^a-z0-9-]', '-', task_id.lower())
        return f"scheduled-job-{safe_id}"

    def _build_cronjob_spec(self, task: ScheduledTaskModel) -> client.V1CronJob:
        """
        Build K8S CronJob specification from task model.

        Args:
            task: Scheduled task model

        Returns:
            V1CronJob specification
        """
        cronjob_name = self._get_cronjob_name(task.id)
        
        # Convert schedule to cron format
        schedule = self._convert_schedule(task)
        
        # Build container spec
        container = client.V1Container(
            name="task-executor",
            image=self.executor_image,
            image_pull_policy="IfNotPresent",
            env=[
                client.V1EnvVar(name="TASK_ID", value=task.id),
                client.V1EnvVar(name="NAMESPACE", value=self.a2a_namespace),
                # Database URL from secret
                client.V1EnvVar(
                    name="DATABASE_URL",
                    value_from=client.V1EnvVarSource(
                        secret_key_ref=client.V1SecretKeySelector(
                            name=self.database_url_secret,
                            key="url"
                        )
                    )
                ),
                # Broker config from secret
                client.V1EnvVar(
                    name="BROKER_URL",
                    value_from=client.V1EnvVarSource(
                        secret_key_ref=client.V1SecretKeySelector(
                            name=self.broker_config_secret,
                            key="url"
                        )
                    )
                ),
                client.V1EnvVar(
                    name="BROKER_USERNAME",
                    value_from=client.V1EnvVarSource(
                        secret_key_ref=client.V1SecretKeySelector(
                            name=self.broker_config_secret,
                            key="username",
                            optional=True
                        )
                    )
                ),
                client.V1EnvVar(
                    name="BROKER_PASSWORD",
                    value_from=client.V1EnvVarSource(
                        secret_key_ref=client.V1SecretKeySelector(
                            name=self.broker_config_secret,
                            key="password",
                            optional=True
                        )
                    )
                ),
                client.V1EnvVar(
                    name="BROKER_VPN",
                    value_from=client.V1EnvVarSource(
                        secret_key_ref=client.V1SecretKeySelector(
                            name=self.broker_config_secret,
                            key="vpn"
                        )
                    )
                ),
            ],
            resources=client.V1ResourceRequirements(
                requests={"memory": "128Mi", "cpu": "100m"},
                limits={"memory": "512Mi", "cpu": "500m"}
            )
        )
        
        # Build pod template
        pod_template = client.V1PodTemplateSpec(
            metadata=client.V1ObjectMeta(
                labels={
                    "app": "sam-scheduler",
                    "task-id": task.id,
                    "component": "executor"
                }
            ),
            spec=client.V1PodSpec(
                restart_policy="Never",
                containers=[container]
            )
        )
        
        # Build job template
        job_template = client.V1JobTemplateSpec(
            metadata=client.V1ObjectMeta(
                labels={
                    "app": "sam-scheduler",
                    "task-id": task.id
                }
            ),
            spec=client.V1JobSpec(
                backoff_limit=0,  # No automatic retries (handle in app layer)
                template=pod_template
            )
        )
        
        # Build CronJob spec
        cronjob_spec = client.V1CronJobSpec(
            schedule=schedule,
            time_zone=task.timezone,
            concurrency_policy="Forbid",  # Prevent overlapping executions
            successful_jobs_history_limit=3,
            failed_jobs_history_limit=3,
            job_template=job_template,
            suspend=not task.enabled  # Suspend if task is disabled
        )
        
        # Build CronJob
        cronjob = client.V1CronJob(
            api_version="batch/v1",
            kind="CronJob",
            metadata=client.V1ObjectMeta(
                name=cronjob_name,
                namespace=self.namespace,
                labels={
                    "app": "sam-scheduler",
                    "task-id": task.id,
                    "task-name": task.name,
                    "sam-namespace": task.namespace,
                    "managed-by": "sam-scheduler"
                },
                annotations={
                    "sam.scheduler/task-id": task.id,
                    "sam.scheduler/task-name": task.name,
                    "sam.scheduler/target-agent": task.target_agent_name,
                    "sam.scheduler/schedule-type": task.schedule_type.value
                }
            ),
            spec=cronjob_spec
        )
        
        return cronjob

    def _build_job_spec(self, task: ScheduledTaskModel) -> client.V1Job:
        """
        Build K8S Job specification for ONE_TIME task.

        Args:
            task: Scheduled task model (must be ONE_TIME type)

        Returns:
            V1Job specification
        """
        job_name = self._get_job_name(task.id)
        
        # Build container spec (same as CronJob)
        container = client.V1Container(
            name="task-executor",
            image=self.executor_image,
            image_pull_policy="IfNotPresent",
            env=[
                client.V1EnvVar(name="TASK_ID", value=task.id),
                client.V1EnvVar(name="NAMESPACE", value=self.a2a_namespace),
                # Database URL from secret
                client.V1EnvVar(
                    name="DATABASE_URL",
                    value_from=client.V1EnvVarSource(
                        secret_key_ref=client.V1SecretKeySelector(
                            name=self.database_url_secret,
                            key="url"
                        )
                    )
                ),
                # Broker config from secret
                client.V1EnvVar(
                    name="BROKER_URL",
                    value_from=client.V1EnvVarSource(
                        secret_key_ref=client.V1SecretKeySelector(
                            name=self.broker_config_secret,
                            key="url"
                        )
                    )
                ),
                client.V1EnvVar(
                    name="BROKER_USERNAME",
                    value_from=client.V1EnvVarSource(
                        secret_key_ref=client.V1SecretKeySelector(
                            name=self.broker_config_secret,
                            key="username",
                            optional=True
                        )
                    )
                ),
                client.V1EnvVar(
                    name="BROKER_PASSWORD",
                    value_from=client.V1EnvVarSource(
                        secret_key_ref=client.V1SecretKeySelector(
                            name=self.broker_config_secret,
                            key="password",
                            optional=True
                        )
                    )
                ),
                client.V1EnvVar(
                    name="BROKER_VPN",
                    value_from=client.V1EnvVarSource(
                        secret_key_ref=client.V1SecretKeySelector(
                            name=self.broker_config_secret,
                            key="vpn"
                        )
                    )
                ),
            ],
            resources=client.V1ResourceRequirements(
                requests={"memory": "128Mi", "cpu": "100m"},
                limits={"memory": "512Mi", "cpu": "500m"}
            )
        )
        
        # Build pod template
        pod_template = client.V1PodTemplateSpec(
            metadata=client.V1ObjectMeta(
                labels={
                    "app": "sam-scheduler",
                    "task-id": task.id,
                    "component": "executor",
                    "schedule-type": "one-time"
                }
            ),
            spec=client.V1PodSpec(
                restart_policy="Never",
                containers=[container]
            )
        )
        
        # Build Job spec
        job_spec = client.V1JobSpec(
            backoff_limit=0,  # No automatic retries
            template=pod_template,
            ttl_seconds_after_finished=3600  # Clean up after 1 hour
        )
        
        # Build Job
        job = client.V1Job(
            api_version="batch/v1",
            kind="Job",
            metadata=client.V1ObjectMeta(
                name=job_name,
                namespace=self.namespace,
                labels={
                    "app": "sam-scheduler",
                    "task-id": task.id,
                    "task-name": task.name,
                    "sam-namespace": task.namespace,
                    "schedule-type": "one-time",
                    "managed-by": "sam-scheduler"
                },
                annotations={
                    "sam.scheduler/task-id": task.id,
                    "sam.scheduler/task-name": task.name,
                    "sam.scheduler/target-agent": task.target_agent_name,
                    "sam.scheduler/schedule-type": "one_time",
                    "sam.scheduler/scheduled-time": task.schedule_expression
                }
            ),
            spec=job_spec
        )
        
        return job

    def _convert_schedule(self, task: ScheduledTaskModel) -> str:
        """
        Convert task schedule to K8S cron format.

        Args:
            task: Scheduled task model

        Returns:
            Cron schedule string

        Raises:
            ValueError: If schedule type is not supported or invalid
        """
        if task.schedule_type == ScheduleType.CRON:
            # Already in cron format
            return task.schedule_expression
        
        elif task.schedule_type == ScheduleType.INTERVAL:
            # Convert interval to cron
            # Format: "30s", "5m", "1h", "1d"
            return self._interval_to_cron(task.schedule_expression)
        
        elif task.schedule_type == ScheduleType.ONE_TIME:
            # ONE_TIME tasks should not call this method
            # They use _build_job_spec() instead
            raise ValueError(
                f"ONE_TIME schedule type should not use _convert_schedule(). "
                f"Task {task.id} should use _build_job_spec() instead."
            )
        
        else:
            raise ValueError(f"Unsupported schedule type: {task.schedule_type}")

    def _interval_to_cron(self, interval_str: str) -> str:
        """
        Convert interval string to cron expression.

        Args:
            interval_str: Interval string (e.g., "30s", "5m", "1h")

        Returns:
            Cron expression

        Raises:
            ValueError: If interval cannot be converted to cron
        """
        interval_str = interval_str.strip().lower()
        
        # Parse interval
        if interval_str.endswith("s"):
            seconds = int(interval_str[:-1])
        elif interval_str.endswith("m"):
            seconds = int(interval_str[:-1]) * 60
        elif interval_str.endswith("h"):
            seconds = int(interval_str[:-1]) * 3600
        elif interval_str.endswith("d"):
            seconds = int(interval_str[:-1]) * 86400
        else:
            seconds = int(interval_str)
        
        # Convert to cron
        if seconds < 60:
            raise ValueError(
                f"Intervals less than 1 minute not supported in K8S CronJobs: {interval_str}"
            )
        elif seconds == 60:
            return "* * * * *"  # Every minute
        elif seconds % 3600 == 0:
            hours = seconds // 3600
            if hours == 1:
                return "0 * * * *"  # Every hour
            elif hours == 24:
                return "0 0 * * *"  # Every day
            elif 24 % hours == 0:
                return f"0 */{hours} * * *"  # Every N hours
            else:
                raise ValueError(f"Cannot convert interval to cron: {interval_str}")
        elif seconds % 60 == 0:
            minutes = seconds // 60
            if minutes < 60:
                return f"*/{minutes} * * * *"  # Every N minutes
            else:
                raise ValueError(f"Cannot convert interval to cron: {interval_str}")
        else:
            raise ValueError(f"Cannot convert interval to cron: {interval_str}")