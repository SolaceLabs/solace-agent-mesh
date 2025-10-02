# Feature: Configurable Data Retention and Automatic Cleanup

**Version:** 1.0
**Status:** Proposed

## 1. Background

The WebUI Gateway currently stores tasks, task events, and user feedback in a persistent database. This data accumulates indefinitely, which can lead to:

- **Storage Growth**: Unbounded database growth over time
- **Performance Degradation**: Queries become slower as tables grow
- **Compliance Issues**: Inability to enforce data retention policies
- **Operational Overhead**: Manual intervention required to manage database size

Without an automated cleanup mechanism, operators must manually delete old data or risk running out of storage space.

## 2. Goals and Purpose

The primary goal is to implement a configurable, automated data retention system that:

- **Prevents Unbounded Growth**: Automatically removes data older than a configured threshold
- **Maintains Performance**: Keeps database tables at a manageable size
- **Supports Compliance**: Enables enforcement of data retention policies
- **Operates Autonomously**: Requires no manual intervention once configured
- **Provides Flexibility**: Allows different retention periods for different data types

## 3. Requirements

### R1: Configuration Schema

- **R1.1:** A new `data_retention` configuration block shall be added to the WebUI Gateway's app configuration schema
- **R1.2:** The configuration shall include an `enabled` flag (default: `true`) to enable/disable automatic cleanup
- **R1.3:** The configuration shall include `task_retention_days` (default: `90`) to specify how long to retain task records
- **R1.4:** The configuration shall include `feedback_retention_days` (default: `90`) to specify how long to retain feedback records
- **R1.5:** The configuration shall include `cleanup_interval_hours` (default: `24`) to specify how often cleanup runs
- **R1.6:** The configuration shall include `batch_size` (default: `1000`) to control how many records are deleted per transaction
- **R1.7:** The system shall enforce a minimum retention period of 7 days to prevent accidental data loss

### R2: Data Retention Service

- **R2.1:** A new `DataRetentionService` class shall be created in `src/solace_agent_mesh/gateway/http_sse/services/`
- **R2.2:** The service shall accept a database session factory and configuration dictionary in its constructor
- **R2.3:** The service shall provide a `cleanup_old_data()` method that orchestrates the cleanup process
- **R2.4:** The service shall provide a `_cleanup_old_tasks()` method that deletes tasks older than the configured retention period
- **R2.5:** The service shall provide a `_cleanup_old_feedback()` method that deletes feedback older than the configured retention period
- **R2.6:** The service shall use batch deletion (configurable batch size) to avoid long-running transactions
- **R2.7:** The service shall log the number of records deleted and time taken for each cleanup operation
- **R2.8:** The service shall handle database errors gracefully and log warnings without crashing the gateway

### R3: Timer Integration

- **R3.1:** The `WebUIBackendComponent` shall initialize a cleanup timer in its `__init__()` method
- **R3.2:** The timer shall be configured with an interval based on `cleanup_interval_hours` converted to milliseconds
- **R3.3:** The timer shall be assigned a unique ID (e.g., `data_retention_cleanup_{gateway_id}`)
- **R3.4:** The component's `handle_timer_event()` method shall be extended to handle the cleanup timer
- **R3.5:** When the cleanup timer fires, it shall call the `DataRetentionService.cleanup_old_data()` method
- **R3.6:** The cleanup timer shall be cancelled during component cleanup to prevent resource leaks

### R4: Database Optimizations

- **R4.1:** A new Alembic migration shall be created to add performance indexes
- **R4.2:** An index shall be added on `tasks.start_time` to optimize TTL queries
- **R4.3:** An index shall be added on `feedback.created_time` to optimize TTL queries
- **R4.4:** The migration shall be reversible (include a `downgrade()` function)

### R5: Repository Methods

- **R5.1:** The `TaskRepository` shall provide a `delete_tasks_older_than(cutoff_time_ms, batch_size)` method
- **R5.2:** The `FeedbackRepository` shall provide a `delete_feedback_older_than(cutoff_time_ms, batch_size)` method
- **R5.3:** Both methods shall return the total number of records deleted
- **R5.4:** Both methods shall use batch deletion with LIMIT clauses to control transaction size
- **R5.5:** Both methods shall commit after each batch to release locks incrementally

### R6: Dependency Injection

- **R6.1:** A new `get_data_retention_service()` dependency function shall be added to `dependencies.py`
- **R6.2:** The dependency shall instantiate the service with the session factory and configuration
- **R6.3:** The dependency shall return `None` if the database is not configured (graceful degradation)

### R7: Monitoring and Observability

- **R7.1:** The service shall log at INFO level when cleanup starts and completes
- **R7.2:** The service shall log the number of tasks deleted, feedback deleted, and total time taken
- **R7.3:** The service shall log at WARNING level if cleanup is disabled via configuration
- **R7.4:** The service shall log at ERROR level if database operations fail
- **R7.5:** The service shall log at WARNING level if no records are found to delete (possible misconfiguration)

### R8: Safety and Validation

- **R8.1:** The service shall validate that retention periods are at least 7 days
- **R8.2:** The service shall validate that batch size is at least 1 and at most 10,000
- **R8.3:** The service shall validate that cleanup interval is at least 1 hour
- **R8.4:** If validation fails, the service shall log an error and use safe default values

## 4. Implementation Checklist

### Phase 1: Configuration and Schema (Files to Modify)

- [x] **Step 1.1**: Add `data_retention` configuration block to `WebUIBackendApp.SPECIFIC_APP_SCHEMA_PARAMS` in `src/solace_agent_mesh/gateway/http_sse/app.py`
  - Include all 6 configuration parameters with proper types, defaults, and descriptions
  - Add validation rules in the schema

- [x] **Step 1.2**: Update example configuration file `examples/gateways/webui_example.yaml`
  - Add commented-out `data_retention` block showing all available options
  - Include explanatory comments about what each option does

### Phase 2: Database Migrations (New Files)

- [x] **Step 2.1**: Create new Alembic migration file
  - File: `src/solace_agent_mesh/gateway/http_sse/alembic/versions/20250102_add_retention_indexes.py`
  - Add index on `tasks.start_time`
  - Add index on `feedback.created_time`
  - Include proper `upgrade()` and `downgrade()` functions

### Phase 3: Repository Layer (Files to Modify)

- [ ] **Step 3.1**: Extend `TaskRepository` in `src/solace_agent_mesh/gateway/http_sse/repository/task_repository.py`
  - Add `delete_tasks_older_than(cutoff_time_ms: int, batch_size: int) -> int` method
  - Implement batch deletion logic with proper transaction handling
  - Return total count of deleted records

- [ ] **Step 3.2**: Extend `FeedbackRepository` in `src/solace_agent_mesh/gateway/http_sse/repository/feedback_repository.py`
  - Add `delete_feedback_older_than(cutoff_time_ms: int, batch_size: int) -> int` method
  - Implement batch deletion logic with proper transaction handling
  - Return total count of deleted records

- [ ] **Step 3.3**: Update repository interfaces in `src/solace_agent_mesh/gateway/http_sse/repository/interfaces.py`
  - Add method signatures to `ITaskRepository` interface
  - Add method signatures to `IFeedbackRepository` interface (if interface exists)

### Phase 4: Service Layer (New File)

- [ ] **Step 4.1**: Create `DataRetentionService` class
  - File: `src/solace_agent_mesh/gateway/http_sse/services/data_retention_service.py`
  - Implement `__init__(session_factory, config)` constructor
  - Implement `cleanup_old_data()` main orchestration method
  - Implement `_cleanup_old_tasks(retention_days: int)` private method
  - Implement `_cleanup_old_feedback(retention_days: int)` private method
  - Implement `_validate_config()` private method for safety checks
  - Add comprehensive logging at all key points
  - Add error handling for database failures

### Phase 5: Component Integration (Files to Modify)

- [ ] **Step 5.1**: Modify `WebUIBackendComponent.__init__()` in `src/solace_agent_mesh/gateway/http_sse/component.py`
  - Retrieve `data_retention` configuration block
  - Initialize `DataRetentionService` instance and store as `self.data_retention_service`
  - Create cleanup timer with unique ID
  - Calculate timer interval from `cleanup_interval_hours` config
  - Add timer using `self.add_timer()`

- [ ] **Step 5.2**: Extend `WebUIBackendComponent.handle_timer_event()` in `src/solace_agent_mesh/gateway/http_sse/component.py`
  - Add conditional check for data retention timer ID
  - Call `self.data_retention_service.cleanup_old_data()` when timer fires
  - Wrap in try/except to prevent timer errors from crashing component

- [ ] **Step 5.3**: Modify `WebUIBackendComponent.cleanup()` in `src/solace_agent_mesh/gateway/http_sse/component.py`
  - Cancel the data retention timer using `self.cancel_timer()`
  - Set `self.data_retention_service = None`

### Phase 6: Dependency Injection (Files to Modify)

- [ ] **Step 6.1**: Add dependency function to `src/solace_agent_mesh/gateway/http_sse/dependencies.py`
  - Create `get_data_retention_service()` function
  - Return service instance from component
  - Handle case where database is not configured (return None)
  - Add proper type hints and docstring

### Phase 7: Documentation (Files to Modify/Create)

- [ ] **Step 7.1**: Update main README or configuration guide
  - Document the new `data_retention` configuration block
  - Explain what each parameter does
  - Provide examples of common configurations

- [ ] **Step 7.2**: Add inline code documentation
  - Ensure all new methods have comprehensive docstrings
  - Add comments explaining complex logic (especially batch deletion)

### Phase 8: Testing Considerations (Future Work)

- [ ] **Step 8.1**: Unit tests for `DataRetentionService`
  - Test cleanup with various retention periods
  - Test batch deletion logic
  - Test configuration validation
  - Test error handling

- [ ] **Step 8.2**: Integration tests
  - Test timer triggering cleanup
  - Test actual database deletion
  - Test with no database configured

- [ ] **Step 8.3**: Manual testing checklist
  - Verify cleanup runs on schedule
  - Verify correct records are deleted
  - Verify indexes improve query performance
  - Verify logs are informative

## 5. Implementation Order

The recommended implementation order is:

1. **Configuration** (Phase 1) - Establishes the contract
2. **Database Migrations** (Phase 2) - Prepares the database
3. **Repository Layer** (Phase 3) - Provides data access methods
4. **Service Layer** (Phase 4) - Implements business logic
5. **Component Integration** (Phase 5) - Wires everything together
6. **Dependency Injection** (Phase 6) - Enables future API access if needed
7. **Documentation** (Phase 7) - Helps users configure the feature

## 6. Rollout Strategy

### Initial Deployment
- Deploy with `enabled: false` by default in production
- Monitor logs to ensure no errors
- Enable on a staging environment first

### Gradual Enablement
- Start with a short retention period (e.g., 30 days) to test
- Monitor database size and performance
- Gradually increase retention period to desired value (e.g., 90 days)

### Monitoring
- Watch for cleanup timer logs
- Monitor database size trends
- Check for any error logs related to cleanup

## 7. Future Enhancements (Out of Scope)

- **Dry-run mode**: Add a flag to log what would be deleted without actually deleting
- **Metrics endpoint**: Expose cleanup statistics via API
- **Configurable retention by user**: Allow different retention periods for different users
- **Archive before delete**: Option to export old data before deletion
- **Session cleanup**: Extend to also clean up old session records

## 8. Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Accidental data loss | Enforce minimum 7-day retention period |
| Long-running transactions | Use batch deletion with configurable batch size |
| Database locks | Commit after each batch to release locks |
| Timer failures | Wrap cleanup in try/except, log errors |
| Configuration errors | Validate all config values, use safe defaults |
| Performance impact | Run cleanup during off-peak hours (configurable interval) |

## 9. Success Criteria

The feature will be considered successful when:

- ✅ Database size stabilizes and does not grow indefinitely
- ✅ Cleanup runs automatically on schedule without manual intervention
- ✅ No performance degradation during cleanup operations
- ✅ Logs clearly show cleanup activity and results
- ✅ Configuration is intuitive and well-documented
- ✅ System handles edge cases gracefully (no database, errors, etc.)
