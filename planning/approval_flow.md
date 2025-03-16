# Feature Description

I am planning a new feature that I need to add to this repo. At this point I just want to capture what the new flow will be, maybe in a mermaid diagram. The actors are the user, slack interface, gateway, gateway DB, orchestrator, Agent Action, AsyncService, AsyncServiceDB. The flow I want to capture is like this:

## Slack flow

### Assumptions

- approver is the stimulus originator

### Flow

- the user enters a request in slack
- it's received by the slack interface which forwards it to gateway
- gateway forwards it to the orchestrator
- the orchestrator chooses an agent action
- the orchestrator forwards the request to the agent action
- the agent action processes the request, but then hits a point where approval is required.
- the agent action creates a form schema with the details of the form to present to the user (using something like RJFS) and adds it in the ActionResponse in the approval object
- the ActionResponse is returned to the orchestrator
- the orchestrator waits for all inflight agent action requests to complete (in OrchestratorActionResponseComponent.invoke)
- when all of the agent actions complete, if any of the responses contain the approval object, then all of session history (gateway history), stimulus history (orchestrator history), the agent_list state and stimulus state put in an event and sent to the async service
- the orchestrator clears it's memory of this stimulus (or marks it as pending)
- the async service creates a uuid for the approval and stores the state in the AsyncServiceDB, sets a timer and then creates a set of form requests, one for each agent that requires approval
- the form request events are sent to the gateway
- the gateway updates the session history associated with the stimulus with a note saying that there are outstanding items.
- the slack interface uses a form renderer to create blocks from the form schema and then posts the blocks to the user's SAM app channel for approval
.... time passes ....
- the user fills out the form in slack and then submits it
- the form data is then sent to the slack interface, where a decoder extracts the data fields adds it to the event data.
- info: the stimulus id and async service uuid are passed along with the form data so that it can be correlated with the response.
- the slack interface creates an approval event and forwards it to gateway.
- the gateway forwards the event to the orchestrator
- the event is forwarded to the orchestrator
- the orchestator sees the async service uuid and forwards the event to the async service (no llm interaction required)
- the async service waits for all approvals to be received for the stimulus id before proceeding
- once all approvals are receive the async service finds the state related to the paused stimulus, and sends a resume message to the orchestrator.
- the orchestrator re-populates the session state, stimulus state, previous action responses and re-sends updated requests to the agent action with the additional data.
- a status message is returned to the user saying that processing on the request has resumed
- the agent action processes the new request and returns an ActionResponse
- the orchestrator waits for all outstanding action responses to be received and then processes the responses
- normal processing continues

### Error Scenarios

Consider these in the future:

- The agent no longer exists or has been upgraded
- The resource that required approval is no longer relevent
- The user takes too long to respond