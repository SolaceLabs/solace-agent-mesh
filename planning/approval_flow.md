# Feature Description

I am planning a new feature that I want to add to this repo. The actors involved in the flow of this feature are the user, slack interface, gateway, gateway DB, orchestrator, Agent Action, AsyncService, AsyncServiceDB. Help me plan this feature. The flow I want to capture is like this:

## Slack flow

### Assumptions

- approver is the stimulus originator

### Flow

- the user enters a request in slack
- it's received by the slack interface which forwards it to gateway
- gateway forwards it to the orchestrator
- the orchestrator chooses an agent action
- the orchestrator forwards the request to the agent action
- the agent action processes the request, but then hits a point where approval is required. Here is an example of an action: create_image.py. This one doesn't have an approval requirement, but you can use it as an example to understand how actions are constructed.
- the agent action creates a form schema with the details of the form to present to the user (using something like RJFS) and adds it in the ActionResponse in the approval object. The ActionResponse is defined in action_response.py. It would be nice to have an async sub object that would contain the information on the approval. I'm thinking that the async sub object could also be used to return early from long running action tasks. In the approval case however, the object needs to contain the form that will be sent to the user. I'm thinking RJFS would be a nice format. It would be nice to have some utility methods available that would take some data related to the approval (in dict form) and fill out a RFJS form and then add Approve and Reject buttons for the end user to click.
- the ActionResponse is returned to the orchestrator. The response handling is in the orchestrator_action_response_component.py.
- the orchestrator waits for all inflight agent action requests to complete (in OrchestratorActionResponseComponent.invoke)
- when all of the agent actions complete, if any of the responses contain the approval object, then all of session history (gateway history), stimulus history (orchestrator history), the agent_list state and stimulus state are put in an event and sent to the Async Service. After the message is sent to the Async Service, the orchestrator clears it's memory of the stimulus history and agent responses.
- The Async Service is a new service that manages asyncronous tasks in a stimulus. Each asynchronous task gets a UUID and the state is stored against that UUID. The state can be stored in memory, on disk or in a database. After the state is stored, the timer is started, and a message is sent to the originating gateway.
  Exception handling: There is a configurable timeout for the Async Service. When a timeout occurs, an event is emitted to the gateway stating that a timeout occurred for the UUID.
  now back to the regular flow:
- the gateway receives the event from the Async Service and forwards it on to the slack interface.
- the slack interface uses a form renderer to create blocks from the form schema and then posts the blocks to the user's SAM app channel for approval. The slack interface will require a RFJS to blocks converter to render the form in slack.
  .... time passes ....
- the user fills out the form in slack and then submits it.
- the form data is then sent to the slack interface, where a decoder extracts the data fields adds it to the event data. This requires extracting the data from the blocks and building a data structure that represents the input from the user (in this case just an approve or reject with the associated form data).
- info: the stimulus id and async service uuid are passed along with the form data so that it can be correlated with the response.
- the slack interface creates an approval event and forwards it to gateway.
- the gateway forwards the event to the orchestrator
- the orchestrator recognizes the event as an Async response (by the Async Service UUID perhaps) and forwards the event to the Async Service (no llm interaction required).
- the async service waits for all approvals to be received for the stimulus id before proceeding
- once all approvals are receive the async service finds the state related to the paused stimulus, and sends a resume message to the orchestrator including all of the stored state.
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
