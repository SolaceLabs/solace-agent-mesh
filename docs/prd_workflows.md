# PRD: Prescriptive Workflows for SAM

**Version:** 1.0  
**Status:** Draft  
**Author:** SAM Team  
**Last Updated:** 2025-01-13

---

## 1. Executive Summary

This PRD defines **Prescriptive Workflows**, a new feature for the Solace Agent Mesh (SAM) that enables users to define structured, DAG-based agent orchestration with guaranteed data integrity and schema validation. Workflows appear as regular agents to external systems while internally executing a predefined sequence of agent personas with validated data flow between stages.

**Key Value Proposition:**
- **Reliability:** Schema validation at every workflow edge ensures type safety and predictable behavior
- **Data Integrity:** Value reference system prevents LLM hallucination of critical data (IDs, keys, etc.)
- **Composability:** Workflows are agents, enabling workflows to call other workflows
- **Observability:** Clear execution traces with status updates at each workflow stage
- **Backward Compatible:** Existing agents and orchestration patterns continue to work unchanged

**Success Metrics:**
- Schema validation catches 100% of type mismatches at workflow edges
- Zero breaking changes to existing SAM functionality

---

## 2. Problem Statement

### Current State
SAM currently supports **free-form agent collaboration** where:
- Agents communicate via natural language requests and responses
- Data is passed through LLM context (risk of hallucination)
- No guarantees about output structure or data integrity
- Orchestration logic is embedded in agent instructions (flexible but unpredictable)

### Pain Points

**1. Data Integrity Issues**
When critical data (customer IDs, order numbers, API keys) passes through an LLM, there's risk of:
- Hallucination (inventing plausible but incorrect values)
- Truncation (partial IDs)
- Formatting errors (case changes, typos)
- Confusion with similar values in context

**Example:**
```
Agent A returns: {"package_id": "PKG-12345"}
Agent B receives context with this ID
Agent B calls: track_package("PKG-12346")  ← LLM hallucinated wrong ID!
```

**2. Unpredictable Output Structure**
Without schemas, downstream agents must handle variability:
- Missing fields
- Unexpected types
- Inconsistent naming
- Nested structure changes

**3. Difficult to Debug**
When a multi-agent workflow fails:
- Hard to identify which agent produced invalid output
- No clear contract violations to point to
- Requires manual inspection of conversation history

**4. No Reusable Patterns**
Complex orchestration logic is embedded in agent instructions, making it:
- Hard to reuse across similar workflows
- Difficult to test in isolation
- Challenging to version and maintain

### User Needs

**Workflow Designers need:**
- Ability to define reliable, repeatable agent orchestration
- Guarantees about data flow and structure
- Clear failure modes and error messages
- Reusable workflow patterns

**Agent Developers need:**
- Clear contracts (input/output schemas) for their agents
- Confidence that data they receive is valid
- Ability to create specialized agents for specific workflow steps

**System Operators need:**
- Visibility into workflow execution
- Ability to monitor and debug failures
- Graceful upgrade paths for workflow changes

---

## 3. Goals & Non-Goals

### Goals

**G1: Enable Structured Workflows**
- Define workflows as DAGs of agent personas
- Support sequential, conditional, and parallel execution
- Validate data flow at every workflow edge

**G2: Ensure Data Integrity**
- Prevent LLM manipulation of critical data values
- Provide value reference system for pass-through data
- Validate all data against schemas

**G3: Maintain "Workflows as Agents" Abstraction**
- Workflows appear identical to regular agents externally
- Workflows can call other workflows
- Workflows can be discovered and delegated to via A2A protocol

**G4: Support Flow Control**
- Conditional branching (if/else, case/switch)
- Parallel execution (fork/join)
- Iteration (loops with max iteration limits)
- Retry logic for transient failures

**G5: Provide Observability**
- Status updates at each workflow stage
- Clear error messages for validation failures
- Execution traces for debugging

**G6: Backward Compatibility**
- No breaking changes to existing SAM functionality
- Existing agents continue to work unchanged
- Workflows are opt-in, not required

### Non-Goals

**NG1: Replace Free-Form Agent Collaboration**
- Free-form orchestration remains valuable for exploratory tasks
- Workflows complement, not replace, existing patterns

**NG2: Visual Workflow Designer**
- MVP uses YAML configuration only
- Visual designer is a future enhancement

**NG3: Long-Running Workflow Orchestration (Hours/Days)**
- While the architecture supports long-running workflows, MVP focuses on workflows that complete in minutes
- Advanced features like pause/resume, checkpointing are future enhancements

**NG4: Workflow Versioning**
- MVP supports only latest version of agent personas
- Versioning and schema evolution are future enhancements

**NG5: Complex Error Recovery**
- MVP supports basic retry logic
- Advanced error handling (compensation, rollback) are future enhancements

---

## 4. Use Cases

### UC1: Customer Onboarding Pipeline

**Actor:** Customer service system  
**Preconditions:** Customer submits onboarding form with document  
**Flow:**
1. System sends onboarding request to CustomerOnboardingWorkflow
2. Workflow extracts customer info from document (ExtractInfoAgent)
3. Workflow validates extracted data (ValidateInfoAgent)
4. If valid, workflow creates account (CreateAccountAgent)
5. Workflow sends welcome email (SendEmailAgent)
6. Workflow returns account ID and confirmation

**Postconditions:** Customer account created, welcome email sent  
**Success Criteria:** 
- All customer data extracted correctly (no hallucinated values)
- Account creation only happens if validation passes
- Workflow completes in < 2 minutes

### UC2: Data Processing Pipeline

**Actor:** Data analytics system  
**Preconditions:** Raw CSV file uploaded  
**Flow:**
1. System sends processing request to DataProcessingWorkflow
2. Workflow extracts and cleans CSV (CSVExtractorAgent)
3. Workflow analyzes data (DataAnalyzerAgent)
4. Workflow generates visualizations (ChartGeneratorAgent)
5. Workflow creates summary report (ReportGeneratorAgent)
6. Workflow returns report artifact

**Postconditions:** Analysis complete, report generated  
**Success Criteria:**
- Data integrity maintained through pipeline (no corrupted values)
- Each stage validates input before processing
- Workflow handles large datasets (up to 100MB)

### UC3: Multi-Step Approval Workflow

**Actor:** Business process automation system  
**Preconditions:** Purchase request submitted  
**Flow:**
1. System sends approval request to ApprovalWorkflow
2. Workflow validates request (ValidationAgent)
3. If amount < $1000, auto-approve
4. If amount >= $1000, route to manager approval (NotificationAgent)
5. Wait for manager response (external input)
6. If approved, create purchase order (PurchaseOrderAgent)
7. Workflow returns approval status and PO number

**Postconditions:** Purchase request processed, PO created if approved  
**Success Criteria:**
- Conditional routing works correctly
- Workflow can wait for external input
- All financial data (amounts, PO numbers) handled without LLM manipulation

### UC4: Parallel Data Enrichment

**Actor:** Customer data platform  
**Preconditions:** Customer record needs enrichment  
**Flow:**
1. System sends enrichment request to EnrichmentWorkflow
2. Workflow forks into parallel branches:
   - Branch A: Enrich billing info (BillingEnricherAgent)
   - Branch B: Enrich shipping info (ShippingEnricherAgent)
   - Branch C: Enrich preferences (PreferencesEnricherAgent)
3. Workflow joins results from all branches
4. Workflow merges enriched data (MergeAgent)
5. Workflow returns complete customer profile

**Postconditions:** Customer record fully enriched  
**Success Criteria:**
- Parallel execution reduces total time by ~3x
- All branches complete successfully or workflow fails
- Merged data conforms to expected schema

---

## 5. User Stories

**US1:** As a workflow designer, I want to define a DAG of agent personas so that I can create reliable, repeatable orchestration patterns.

**US2:** As a workflow designer, I want to specify input/output schemas for each workflow stage so that I can guarantee data integrity between stages.

**US3:** As a workflow designer, I want to use value references for critical data so that LLMs cannot hallucinate or corrupt important values like IDs and keys.

**US4:** As a workflow designer, I want to define conditional branches so that workflows can adapt to different scenarios.

**US5:** As a workflow designer, I want to execute workflow stages in parallel so that I can reduce total execution time.

**US6:** As an agent developer, I want to create agent personas with clear input/output contracts so that my agents can be reliably used in workflows.

**US7:** As an agent developer, I want my agent to explicitly signal success or failure so that workflows can handle errors appropriately.

**US8:** As a system operator, I want to monitor workflow execution in real-time so that I can identify and debug failures quickly.

**US9:** As a system operator, I want to gracefully upgrade workflows without disrupting in-flight executions so that I can deploy changes safely.

**US10:** As an external system, I want to interact with workflows exactly like regular agents so that I don't need special integration logic.

---

## 6. Requirements

### 6.1 Functional Requirements

#### FR1: Workflow Definition via YAML
**Priority:** P0 (Must Have)  
**Description:** Users can define workflows in YAML configuration files with:
- Workflow metadata (name, description)
- Input/output schemas (optional at workflow level)
- DAG of nodes (agent personas, flow control)
- Node dependencies and input mappings

**Acceptance Criteria:**
- Workflow YAML follows documented schema
- Workflow loads successfully at startup
- Invalid YAML produces clear error messages

#### FR2: Schema Validation at Workflow Edges
**Priority:** P0 (Must Have)  
**Description:** System validates data against schemas at every workflow edge:
- Workflow input validated against workflow input schema (if defined)
- Node input validated against persona input schema (mandatory)
- Node output validated against persona output schema (mandatory)
- Workflow output validated against workflow output schema (if defined)

**Acceptance Criteria:**
- Schema validation catches type mismatches
- Validation errors include clear messages with expected vs. actual data
- Validation failures trigger retry logic (up to max retries)

#### FR3: Value Reference System
**Priority:** P0 (Must Have)  
**Description:** Agents can reference data values without LLM manipulation using `«value:artifact:path»` syntax:
- References resolved by framework before tool execution
- Supports JSON path notation for nested data
- Works with artifacts from previous nodes, workflow input, or any accessible artifact

**Acceptance Criteria:**
- Value references resolve correctly to actual values
- Invalid references produce clear error messages
- References work in tool arguments (any depth of nesting)

#### FR4: Result Artifact Marking
**Priority:** P0 (Must Have)  
**Description:** Agents explicitly mark their output artifact using `«result:artifact=name status=success|failure [message=text]»` syntax:
- Success status requires artifact name
- Failure status requires message, artifact optional
- Framework uses marked artifact for schema validation and passing to next node

**Acceptance Criteria:**
- Result embed correctly parsed from agent response
- Missing result embed produces clear error
- Failure status skips schema validation
- Success status triggers schema validation

#### FR5: Flow Control Nodes
**Priority:** P0 (Must Have)  
**Description:** Workflows support flow control nodes:
- **if/else:** Conditional branching based on previous node output
- **case/switch:** Multi-way branching based on expression
- **fork:** Parallel execution of multiple branches
- **join:** Wait for parallel branches to complete and merge results
- **loop:** Iteration with max iteration limit

**Acceptance Criteria:**
- Conditional expressions evaluate correctly
- Parallel branches execute concurrently
- Join merges branch outputs correctly
- Loops respect max iteration limits
- Flow control nodes don't require agent personas

#### FR6: Workflow as Agent
**Priority:** P0 (Must Have)  
**Description:** Workflows appear as regular agents to external systems:
- Publish agent card to discovery topic
- Receive A2A tasks on agent request topic
- Return A2A responses
- Can be discovered and delegated to by other agents

**Acceptance Criteria:**
- Workflow agent card published successfully
- External systems cannot distinguish workflow from regular agent
- Workflows can call other workflows
- Workflows can be called by orchestrator agents

#### FR7: Workflow Execution State Persistence
**Priority:** P0 (Must Have)  
**Description:** Workflow execution state persisted in ADK session storage:
- Current node being executed
- Completed nodes and their outputs
- Pending nodes
- Error state and retry counts

**Acceptance Criteria:**
- State persisted if session service configured for persistence
- Workflow can resume after restart (if state persisted)
- State includes sufficient information for debugging

#### FR8: Graceful Workflow Upgrades
**Priority:** P1 (Should Have)  
**Description:** Workflows support graceful upgrades without disrupting in-flight executions:
- Old workflow instance enters "shutdown mode"
- Old instance unbinds from queue
- New instance binds to queue and handles new requests
- Old instance completes in-flight workflows within timeout
- After timeout, old instance force-stops

**Acceptance Criteria:**
- In-flight workflows complete successfully during upgrade
- New requests routed to new workflow instance
- Shutdown timeout configurable
- Clear logging of shutdown process

#### FR9: Workflow Monitoring via A2A Status Updates
**Priority:** P1 (Should Have)  
**Description:** Workflows publish A2A status updates for observability:
- Workflow started
- Node started (with node ID)
- Node completed (with node ID, duration)
- Node failed (with node ID, error)
- Workflow completed
- Workflow failed

**Acceptance Criteria:**
- Status updates published to correct A2A topic
- Updates include metadata only (not intermediate data)
- Updates follow existing A2A status update format
- Updates enable real-time monitoring

#### FR10: Nested Workflow Support
**Priority:** P1 (Should Have)  
**Description:** Workflows can call other workflows:
- Child workflow receives augmented session ID
- Child workflow can access parent session artifacts
- Child workflow errors bubble up to parent
- Parent workflow handles child errors like node failures

**Acceptance Criteria:**
- Nested workflows execute correctly
- Session ID augmentation works (e.g., `session_123:child_456`)
- Artifact access works across workflow boundaries
- Error propagation works correctly

### 6.2 Non-Functional Requirements

#### NFR1: Performance
**Description:** Workflow execution overhead must be minimal:
- Workflow execution latency < 2x sequential agent calls
- Schema validation adds < 100ms per node
- Value reference resolution adds < 50ms per reference

**Acceptance Criteria:**
- Performance benchmarks meet targets
- No significant degradation with workflow size (up to 50 nodes)

#### NFR2: Scalability
**Description:** System must support:
- Workflows up to 50 nodes
- Up to 10 parallel branches in fork/join
- Concurrent execution of 100+ workflow instances

**Acceptance Criteria:**
- Large workflows execute successfully
- Parallel execution works correctly
- System remains stable under load

#### NFR3: Usability
**Description:** Workflows must be easy to define and debug:
- Schema validation errors are clear and actionable
- Workflow YAML is intuitive and well-documented
- Error messages include context (node ID, expected vs. actual)

**Acceptance Criteria:**
- User testing shows < 30 minutes to create simple workflow
- Error messages rated as "helpful" by developers
- Documentation includes complete examples

#### NFR4: Backward Compatibility
**Description:** No breaking changes to existing SAM functionality:
- Existing agents work unchanged
- Existing orchestrator patterns continue to work
- New features are opt-in

**Acceptance Criteria:**
- All existing integration tests pass
- No changes required to existing agent configurations
- Workflows are optional feature

---

## 7. Key Design Decisions

### Decision 1: Workflows are Agents

**Rationale:**
- Unified abstraction simplifies mental model
- Enables composability (workflows calling workflows)
- Reuses existing A2A protocol and discovery
- No special integration logic needed for external systems

**Alternatives Considered:**
- Separate workflow service (rejected: adds complexity, breaks abstraction)
- Workflows as special message type (rejected: requires protocol changes)

**Trade-offs:**
- Slightly more complex component model (WorkflowExecutorComponent vs. SamAgentComponent)
- Workflows must publish agent cards and handle A2A protocol

**Impact:** Medium implementation complexity, high conceptual simplicity

---

### Decision 2: Schemas Belong with Agent Personas

**Rationale:**
- Single source of truth for agent contracts
- Instructions and schemas stay in sync
- Reusable across multiple workflows
- Enables validation at persona discovery time

**Alternatives Considered:**
- Schemas in workflow definition (rejected: duplication, inconsistency)
- Implicit schemas from examples (rejected: unreliable)

**Trade-offs:**
- Requires persona discovery before workflow validation
- Schema changes affect all workflows using that persona

**Impact:** High maintainability, medium implementation complexity

---

### Decision 3: Value References for Data Integrity

**Rationale:**
- Prevents LLM hallucination of critical data
- Guarantees data integrity through workflows
- Reduces LLM context size (schemas instead of data)
- Enables auditability (clear data provenance)

**Alternatives Considered:**
- Pass data through LLM (rejected: hallucination risk)
- Encrypted data tokens (rejected: complex, limited flexibility)

**Trade-offs:**
- New embed syntax to learn
- Requires framework support for resolution
- LLM must use references correctly (instruction injection needed)

**Impact:** High reliability improvement, medium learning curve

---

### Decision 4: Explicit Result Artifact Marking

**Rationale:**
- Clear output semantics (no guessing which artifact is "the output")
- Supports tool-created artifacts (agent doesn't need to re-save)
- Enables explicit success/failure signaling
- Simplifies validation logic

**Alternatives Considered:**
- Flag on save_artifact (rejected: doesn't work for tool-created artifacts)
- Implicit detection (last artifact created) (rejected: fragile, ambiguous)

**Trade-offs:**
- Requires LLM to use new embed syntax
- Additional instruction injection needed

**Impact:** High clarity, low implementation complexity

**Syntax:** `«result:artifact=name[:version] status=success|failure [message=text]»`

---

### Decision 5: Specialized WorkflowExecutorComponent

**Rationale:**
- Clean separation of concerns (orchestration vs. agent execution)
- Enables workflow-specific optimizations (parallelism, state management)
- Avoids polluting SamAgentComponent with orchestration logic
- Easier to test and maintain

**Alternatives Considered:**
- Mode in SamAgentComponent (rejected: mixing concerns, complex conditionals)
- Separate workflow service (rejected: breaks "workflows as agents" abstraction)

**Trade-offs:**
- New component type to maintain
- Slightly more complex deployment model

**Impact:** High maintainability, medium implementation complexity

---

### Decision 6: Fork/Join Output Merging with Explicit Keys

**Rationale:**
- Clear semantics for accessing branch outputs
- Prevents key collisions between branches
- Enables schema validation on merged result
- Workflow designer has full control over output structure

**Alternatives Considered:**
- Automatic merging by key (rejected: collision risk)
- List of branch outputs (rejected: harder to access specific branch)

**Trade-offs:**
- Requires workflow designer to specify merge keys
- Slightly more verbose workflow definitions

**Impact:** High clarity, low implementation complexity

**Example:**
```yaml
- id: parallel_enrichment
  type: fork
  branches:
    - id: enrich_billing
      agent_persona: BillingEnricher
      output_key: billing  # Merged result will have 'billing' key
    - id: enrich_shipping
      agent_persona: ShippingEnricher
      output_key: shipping  # Merged result will have 'shipping' key

- id: next_step
  agent_persona: NextAgent
  depends_on: [parallel_enrichment]
  # Input will be: {billing: {...}, shipping: {...}}
```

---

### Decision 7: Conditional Expressions Reference Node Outputs by ID

**Rationale:**
- Explicit and clear (no ambiguity about which node's output)
- Supports referencing any previous node (not just immediate predecessor)
- Consistent with input mapping syntax

**Alternatives Considered:**
- `previous` keyword (rejected: only works for immediate predecessor)
- Value references in conditionals (rejected: can't guarantee artifact names)

**Trade-offs:**
- Slightly more verbose
- Requires knowing node IDs

**Impact:** High clarity, low implementation complexity

**Example:**
```yaml
- id: validate_customer
  agent_persona: ValidationAgent
  # output: {is_valid: boolean, error_message: string}

- id: routing
  type: if
  condition: "{{validate_customer.output.is_valid}} == true"
  then: [...]
  else: [...]
```

---

### Decision 8: Runtime Schema Validation (MVP)

**Rationale:**
- Simpler implementation (no dependency on agent discovery timing)
- Clear failure mode (workflow fails on first execution if schemas incompatible)
- Enables faster iteration during development

**Alternatives Considered:**
- Startup validation (rejected: requires all personas discovered before workflow starts)
- Delayed workflow card publishing (future enhancement)

**Trade-offs:**
- First workflow execution might fail due to schema incompatibility
- Requires good error messages to guide user to fix

**Impact:** Low implementation complexity, medium user experience impact

**Future Enhancement:** Workflow waits to publish agent card until all dependency schemas validated

---

### Decision 9: Standardized Retry Logic

**Rationale:**
- Consistent behavior across all workflows
- Simpler for users (no per-workflow retry configuration)
- Easier to test and maintain

**Alternatives Considered:**
- Configurable retry logic per workflow (future enhancement)
- No automatic retries (rejected: reduces reliability)

**Trade-offs:**
- Less flexibility for advanced users
- One-size-fits-all approach may not suit all use cases

**Impact:** Low implementation complexity, high consistency

**Retry Behavior:**
- Schema validation failure: Retry with validation error in prompt (max 3 attempts)
- Value reference resolution failure: Retry with resolution error in prompt (max 3 attempts)
- Node returns failure status: No retry (explicit failure)
- Tool execution error: Agent decides whether to retry (existing behavior)

---

### Decision 10: Workflow and Node Timeouts

**Rationale:**
- Prevents runaway workflows
- Provides clear failure mode for stuck executions
- Enables resource management

**Alternatives Considered:**
- No timeouts (rejected: risk of infinite execution)
- Only workflow-level timeout (rejected: doesn't catch stuck nodes)

**Trade-offs:**
- Requires timeout configuration
- May need tuning for different workflow types

**Impact:** Medium implementation complexity, high reliability improvement

**Timeout Strategy:**
- Per-node timeout (configurable per node, default 5 minutes)
- Workflow-level timeout (configurable per workflow, default 30 minutes)
- Loop max iterations (configurable per loop, default 100)

---

## 8. Success Metrics

### Primary Metrics

**M1: Schema Validation Effectiveness**
- **Target:** 100% of type mismatches caught
- **Measurement:** Manual review of validation failures
- **Rationale:** Schema validation is core value proposition

**M2: Zero Breaking Changes**
- **Target:** 100% of existing integration tests pass
- **Measurement:** Automated test suite
- **Rationale:** Backward compatibility is hard requirement

### Secondary Metrics

**M5: Workflow Definition Time**
- **Target:** < 30 minutes for simple workflows (5-10 nodes)
- **Measurement:** User testing with workflow designers
- **Rationale:** Usability indicator

**M6: Workflow Execution Performance**
- **Target:** < 2x sequential agent call latency
- **Measurement:** Automated benchmarks
- **Rationale:** Performance overhead must be acceptable

---

## 9. Dependencies

### Internal Dependencies

**D1: Agent Executor Implementation**
- **Status:** Parallel development (see PRD: Agent Executors)
- **Impact:** Workflows can initially use single-agent deployments, but agent executors enable efficient multi-persona hosting
- **Mitigation:** Workflows designed to work with both deployment models

**D2: Embed Resolution Enhancements**
- **Status:** Requires implementation
- **Impact:** Value references and result artifact marking depend on embed resolution
- **Mitigation:** Extend existing embed resolution framework

**D3: ADK Session Storage**
- **Status:** Exists, may need minor enhancements
- **Impact:** Workflow state persistence uses session storage
- **Mitigation:** Use existing `state` field in session

### External Dependencies

**D4: JSON Schema Validation Library**
- **Library:** `jsonschema` (Python)
- **Status:** Mature, stable
- **Impact:** Schema validation depends on this library
- **Mitigation:** Well-established library with good support

**D5: Solace Broker**
- **Status:** Existing infrastructure
- **Impact:** Workflow communication uses Solace messaging
- **Mitigation:** No changes needed to broker

---

## 10. Risks & Mitigations

### Risk 1: LLMs Don't Reliably Use Value References

**Likelihood:** Medium  
**Impact:** High  
**Description:** LLMs might not consistently use `«value:...»` syntax, leading to data integrity issues.

**Mitigation:**
- Strong instruction injection explaining value references
- Clear examples in system prompts
- Validation that catches missing references (e.g., if tool arg looks like an ID but isn't a reference)
- Retry logic with corrective feedback

**Contingency:** If adoption is poor, consider automatic reference injection for known ID patterns

---

### Risk 2: Schema Validation Too Strict

**Likelihood:** Medium  
**Impact:** Medium  
**Description:** Schema validation might block valid workflows due to overly strict rules.

**Mitigation:**
- Clear, actionable error messages
- Schema compatibility checker tool (future)
- Documentation with common patterns
- Support for `additionalProperties: true` for flexible schemas

**Contingency:** Add schema relaxation options if needed

---

### Risk 3: Performance Overhead of Schema Validation

**Likelihood:** Low  
**Impact:** Medium  
**Description:** Schema validation at every edge might add significant latency.

**Mitigation:**
- Cache parsed schemas
- Validate only at workflow edges (not within agent execution)
- Use efficient validation library
- Benchmark and optimize hot paths

**Contingency:** Make validation optional for performance-critical workflows (not recommended)

---

### Risk 4: Complex Workflows Hard to Debug

**Likelihood:** Medium  
**Impact:** Medium  
**Description:** Large workflows with many nodes might be difficult to debug when failures occur.

**Mitigation:**
- Comprehensive status updates at each stage
- Clear error messages with node ID and context
- Execution trace in workflow state
- Future: Workflow visualization tool

**Contingency:** Provide debugging guide and best practices

---

### Risk 5: Graceful Upgrade Complexity

**Likelihood:** Medium  
**Impact:** Medium  
**Description:** Implementing graceful shutdown for workflow upgrades might be complex.

**Mitigation:**
- Start with simple timeout-based approach
- Clear documentation of upgrade process
- Monitoring and logging of shutdown process
- Test with long-running workflows

**Contingency:** Accept brief downtime during upgrades if graceful shutdown proves too complex

---

### Risk 6: Fork/Join Merge Conflicts

**Likelihood:** Low  
**Impact:** Low  
**Description:** Parallel branches might produce conflicting outputs that can't be merged.

**Mitigation:**
- Require explicit output keys for each branch
- Validate merge compatibility at workflow definition time (future)
- Clear error messages if merge fails

**Contingency:** Provide merge conflict resolution strategies in documentation

---

## 11. Open Questions

### OQ1: Workflow Versioning Strategy
**Question:** How do we handle workflow versioning when schemas change?  
**Options:**
- A) Lock workflows to specific persona versions (complex)
- B) Always use latest persona versions (simpler, may break workflows)
- C) Graceful shutdown allows old workflows to complete (chosen for MVP)

**Decision:** Option C for MVP, revisit versioning in future

---

### OQ2: Workflow State Persistence Strategy
**Question:** Should workflow state be persisted by default, or opt-in?  
**Options:**
- A) Always persist (reliable, but requires storage)
- B) Opt-in via configuration (flexible, but users might forget)
- C) Follow session service configuration (consistent with existing behavior)

**Decision:** Option C - if session service is configured for persistence, workflow state is persisted

---

### OQ3: Workflow Visualization
**Question:** Should we provide a tool to visualize workflow execution?  
**Options:**
- A) Build visualization tool (high value, high effort)
- B) Provide execution trace data, let users build tools (lower effort)
- C) Defer to future (MVP focuses on core functionality)

**Decision:** Option C for MVP, Option A for future enhancement

---

### OQ4: Workflow Testing Strategy
**Question:** How should users test workflows before deployment?  
**Options:**
- A) Dry-run mode (validates without executing)
- B) Test environment with mock agents
- C) Unit test individual nodes, integration test full workflow

**Decision:** Defer to future, provide testing best practices in documentation

---

### OQ5: Error Recovery Strategies
**Question:** Should workflows support advanced error recovery (compensation, rollback)?  
**Options:**
- A) Build compensation framework (complex, high value for certain use cases)
- B) Provide error handling nodes (medium complexity)
- C) Rely on retry logic and manual intervention (simpler)

**Decision:** Option C for MVP, Option B for future enhancement

---

## 13. Appendix

### A. Example Workflow Definition

```yaml
# customer_onboarding_workflow.yaml
apps:
  - name: customer_onbo arding_workflow
    app_module: solace_agent_mesh.workflow.workflow_app
    broker:
      broker_type: solace
      broker_url: ${SOLACE_BROKER_URL}
      broker_vpn: ${SOLACE_BROKER_VPN}
      broker_username: ${SOLACE_BROKER_USERNAME}
      broker_password: ${SOLACE_BROKER_PASSWORD}
    
    app_config:
      namespace: ${NAMESPACE}
      agent_name: "CustomerOnboardingWorkflow"
      agent_type: "workflow"
      
      workflow:
        # Optional workflow-level schemas
        input_schema:
          type: object
          properties:
            document_filename: {type: string}
          required: [document_filename]
        
        output_schema:
          type: object
          properties:
            account_id: {type: string}
            welcome_email_sent: {type: boolean}
          required: [account_id, welcome_email_sent]
        
        # Workflow DAG
        nodes:
          - id: extract_info
            agent_persona: "ExtractInfoAgent"
            input:
              document_filename: "{{workflow.input.document_filename}}"
            timeout_seconds: 60
          
          - id: validate_info
            agent_persona: "ValidateInfoAgent"
            depends_on: [extract_info]
            input:
              customer_name: "{{extract_info.output.customer_name}}"
              email: "{{extract_info.output.email}}"
            timeout_seconds: 30
          
          - id: routing
            type: if
            condition: "{{validate_info.output.is_valid}} == true"
            then:
              - id: create_account
                agent_persona: "CreateAccountAgent"
                input:
                  customer_name: "{{extract_info.output.customer_name}}"
                  email: "{{extract_info.output.email}}"
                timeout_seconds: 45
              
              - id: send_welcome
                agent_persona: "SendEmailAgent"
                depends_on: [create_account]
                input:
                  recipient: "{{extract_info.output.email}}"
                  template: "welcome"
                  account_id: "{{create_account.output.account_id}}"
                timeout_seconds: 30
            else:
              - id: send_rejection
                agent_persona: "SendEmailAgent"
                input:
                  recipient: "{{extract_info.output.email}}"
                  template: "rejection"
                  reason: "{{validate_info.output.error_message}}"
                timeout_seconds: 30
        
        # Map final output
        output_mapping:
          account_id: "{{create_account.output.account_id}}"
          welcome_email_sent: true
      
      # Agent card
      agent_card:
        description: "Complete customer onboarding workflow from document to account"
        input_schema:
          type: object
          properties:
            document_filename: {type: string}
        output_schema:
          type: object
          properties:
            account_id: {type: string}
            welcome_email_sent: {type: boolean}
      
      agent_card_publishing:
        interval_seconds: 10
      
      session_service:
        type: sql
        database_url: ${DATABASE_URL}
      
      artifact_service:
        type: filesystem
        base_path: /tmp/artifacts
```

### B. Example Agent Persona Definition

```yaml
# agent_executor.yaml
apps:
  - name: customer_service_executor
    app_module: solace_agent_mesh.agent.sac.executor_app
    broker:
      broker_type: solace
      broker_url: ${SOLACE_BROKER_URL}
      broker_vpn: ${SOLACE_BROKER_VPN}
      broker_username: ${SOLACE_BROKER_USERNAME}
      broker_password: ${SOLACE_BROKER_PASSWORD}
    
    app_config:
      namespace: ${NAMESPACE}
      executor_mode: true
      
      executor_config:
        executor_id: "customer_service_001"
        
        personas:
          - agent_name: "ExtractInfoAgent"
            instruction: |
              Extract customer information from the provided document.
              
              You will receive a document filename as input.
              Load the document and extract:
              - Customer name
              - Email address
              - Phone number (if present)
              
              Use the create_structured_output tool to save your results.
            
            input_schema:
              type: object
              properties:
                document_filename:
                  type: string
                  description: "Name of the document artifact to process"
              required: [document_filename]
            
            output_schema:
              type: object
              properties:
                customer_name:
                  type: string
                  description: "Extracted customer name"
                email:
                  type: string
                  description: "Extracted email address"
                phone:
                  type: string
                  description: "Extracted phone number"
              required: [customer_name, email]
            
            tools:
              - tool_type: builtin
                tool_name: load_artifact
              - tool_type: builtin
                tool_name: convert_file_to_markdown
              - tool_type: builtin
                tool_name: create_structured_output
          
          - agent_name: "ValidateInfoAgent"
            instruction: |
              Validate the provided customer information.
              
              Check that:
              - Email address is valid format
              - Customer name is not empty
              - Phone number is valid format (if provided)
              
              Use the create_structured_output tool to save your validation results.
            
            input_schema:
              type: object
              properties:
                customer_name: {type: string}
                email: {type: string}
                phone: {type: string}
            
            output_schema:
              type: object
              properties:
                is_valid:
                  type: boolean
                  description: "Whether all validation checks passed"
                error_message:
                  type: string
                  description: "Error message if validation failed"
              required: [is_valid]
            
            tools:
              - tool_type: python
                function_name: validate_email
              - tool_type: python
                function_name: validate_phone
              - tool_type: builtin
                tool_name: create_structured_output
```

### C. Example Value Reference Usage

```python
# In agent's response (generated by LLM):

# Tool call with value reference
{
  "tool_calls": [
    {
      "name": "create_account",
      "args": {
        "customer_name": "«value:customer_info.json:customer_name»",
        "email": "«value:customer_info.json:email»",
        "phone": "«value:customer_info.json:phone»"
      }
    }
  ]
}

# Framework resolves references before calling tool:
{
  "customer_name": "John Doe",
  "email": "john.doe@example.com",
  "phone": "+1-555-0123"
}

# Tool executes with actual values (no LLM manipulation)
```

### D. Example Result Artifact Marking

```python
# Agent's response after creating output:

# Success case
"""
I have successfully extracted the customer information from the document.

«result:artifact=customer_info.json status=success message=Extracted 3 fields»
"""

# Failure case
"""
I was unable to extract customer information from the document.
The document appears to be corrupted or in an unsupported format.

«result:status=failure message=Document format not supported»
"""

# Framework parses result embed:
# - Success: Loads customer_info.json, validates against output schema
# - Failure: Skips validation, propagates error to workflow
```

---

**End of PRD**
