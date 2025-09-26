# Implementation Plan: Agent Side Quests                                                                                                                          
                                                                                                                                                                  
This plan outlines the necessary steps to implement the "Agent Side Quests" feature as described in the design documents. It focuses on reusing existing          
infrastructure to ensure a robust and maintainable solution.                                                                                                      
                                                                                                                                                                  
---                                                                                                                                                               
                                                                                                                                                                  
### **Part 1: Core Tool and Configuration**                                                                                                                       
                                                                                                                                                                  
This part focuses on creating the `self_side_quest` tool and the configuration required to enable it.                                                             
                                                                                                                                                                  
1.  **Add Configuration Flag:**                                                                                                                                   
    *   **Task:** Introduce a new configuration flag in `src/solace_agent_mesh/agent/sac/app.py` to enable or disable the side quest feature.                     
    *   **Details:** Add a new field `enable_side_quests: bool = Field(default=False, ...)` to the `SamAgentAppConfig` Pydantic model. This ensures the feature is
off by default for backward compatibility.                                                                                                                        
                                                                                                                                                                  
2.  **Create the `SelfSideQuestTool`:**                                                                                                                           
    *   **Task:** Create a new file: `src/solace_agent_mesh/agent/tools/self_side_quest_tool.py`.                                                                 
    *   **Details:**                                                                                                                                              
        *   Define a `SelfSideQuestTool` class that inherits from `google.adk.tools.BaseTool`.                                                                    
        *   This tool will be very similar in structure to the existing `PeerAgentTool`.                                                                          
        *   It will be a long-running tool (`is_long_running = True`).                                                                                            
        *   Its `_get_declaration` method will define the tool's parameters for the LLM: `task_description` (required) and `artifacts` (optional).                
        *   The `run_async` method will be the core of the tool. It will:                                                                                         
            *   Construct an A2A message containing the `task_description`.                                                                                       
            *   Add special metadata to the message: `is_side_quest: True`, `parent_session_id` (from the current context), and `invoked_with_artifacts`.         
            *   Set `sessionBehavior: "RUN_BASED"` in the metadata to signal the required session type.                                                           
            *   Call `self.host_component.submit_a2a_task`, targeting the agent's own name.                                                                       
            *   It will reuse the existing patterns from `PeerAgentTool` for creating a unique sub-task ID, registering the parallel call, and setting up a       
timeout in the cache service.                                                                                                                                     
                                                                                                                                                                  
3.  **Register the New Tool:**                                                                                                                                    
    *   **Task:** Update the tool loading mechanism in `src/solace_agent_mesh/agent/adk/setup.py`.                                                                
    *   **Details:** In the `load_adk_tools` function, add logic to check if `enable_side_quests` is true in the component's configuration. If it is,             
programmatically create an instance of `SelfSideQuestTool` and add it to the list of enabled built-in tools for the agent.                                        
                                                                                                                                                                  
---                                                                                                                                                               
                                                                                                                                                                  
### **Part 2: Event Handling and Context Management**                                                                                                             
                                                                                                                                                                  
This part covers the modifications needed to make the agent's core event handler recognize and manage side quest tasks.                                           
                                                                                                                                                                  
4.  **Update A2A Request Handler for Side Quests:**                                                                                                               
    *   **Task:** Modify the `handle_a2a_request` function in `src/solace_agent_mesh/agent/protocol/event_handlers.py`.                                           
    *   **Details:**                                                                                                                                              
        *   After parsing the incoming `A2ARequest`, inspect the message metadata for `is_side_quest: True`.                                                      
        *   The existing logic that checks for `sessionBehavior: "RUN_BASED"` will correctly handle creating a temporary session and copying the parent's history.
The new tool will set this metadata, so this part should work as-is.                                                                                              
        *   The key change will be to handle artifact pre-loading.                                                                                                
                                                                                                                                                                  
5.  **Implement Artifact Pre-loading for Side Quests:**                                                                                                           
    *   **Task:** Add new logic within `handle_a2a_request` in `src/solace_agent_mesh/agent/protocol/event_handlers.py`.                                          
    *   **Details:**                                                                                                                                              
        *   If a request is identified as a side quest and its metadata contains `invoked_with_artifacts`, the handler must construct a rich initial prompt.      
        *   It will bypass the standard `translate_a2a_to_adk_content` function for this case.                                                                    
        *   Instead, it will use the `generate_artifact_metadata_summary` helper to create a text summary of the specified artifacts.                             
        *   This summary will be prepended to the `task_description` from the tool call.                                                                          
        *   The combined text will be used to create a new `adk_types.Content` object, which is then passed to the ADK runner. This saves an LLM turn by providing
all necessary context in the very first prompt of the side quest.                                                                                                 
                                                                                                                                                                  
---                                                                                                                                                               
                                                                                                                                                                  
### **Part 3: Agent Instruction and Finalization**                                                                                                                
                                                                                                                                                                  
This part ensures the LLM knows how to use the new feature and that the results are handled correctly.                                                            
                                                                                                                                                                  
6.  **Update LLM Instructions:**                                                                                                                                  
    *   **Task:** Modify the `_generate_tool_instructions_from_registry` function in `src/solace_agent_mesh/agent/adk/callbacks.py`.                              
    *   **Details:** The `self_side_quest` tool will be automatically included by the tool registry. We just need to ensure its `description` field in the tool's 
`FunctionDeclaration` is clear and instructive for the LLM, explaining its purpose for isolated, complex sub-tasks. A good description is critical for the LLM to 
use the tool effectively.                                                                                                                                         
                                                                                                                                                                  
7.  **Verify Result Handling:**                                                                                                                                   
    *   **Task:** No code changes are anticipated, but this is a critical step for verification.                                                                  
    *   **Details:** Confirm that the existing logic in `handle_a2a_response` correctly processes the final `Task` object returned by the completed side quest.   
The logic that handles responses from `PeerAgentTool` (claiming the sub-task, recording the result, and re-triggering the main agent) should apply directly to the
`SelfSideQuestTool` as well, since both are long-running tools managed via the same sub-task mechanism.                                                           
                                                                                                                                                                  
8.  **Verify Automatic Cleanup:**                                                                                                                                 
    *   **Task:** No code changes are anticipated, but this is another critical verification step.                                                                
    *   **Details:** Confirm that the `finalize_task_with_cleanup` method in `src/solace_agent_mesh/agent/sac/component.py` correctly identifies the completed    
side quest as a `RUN_BASED` session and calls `session_service.delete_session` on the temporary session ID. This ensures the isolated context is properly         
discarded.                                                                                                                                                        
                                                                                                                                                                  
---                                                                                                                                                               
                                                                                                                                                                  
### **Part 4: Documentation**                                                                                                                                     
                                                                                                                                                                  
9.  **Update Documentation:**                                                                                                                                     
    *   **Task:** Update the design documents (`docs/proposals/agent_side_quests.md` and `docs/designs/agent_side_quests.md`).                                    
    *   **Details:** Add a section to the documentation explaining how to enable the feature using the `enable_side_quests` flag in the agent's YAML configuration
file and provide a simple example of an LLM prompt that would trigger its use.       
