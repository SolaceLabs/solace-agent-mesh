from datetime import datetime
import json

from solace_ai_connector.common.log import log
from litellm import completion

# Some prompts were imported and modified from mem0
PROMPTS = {
    "EXTRACT_FACTS": f"""You are a Personal Information Organizer, specialized in accurately storing facts, user memories, and preferences. Your primary role is to extract relevant pieces of information from conversations and organize them into distinct, manageable facts. This allows for easy retrieval and personalization in future interactions. Below are the types of information you need to focus on and the detailed instructions on how to handle the input data.

Types of Information to Remember:

1. Store Personal Preferences: Keep track of likes, dislikes, and specific preferences in various categories such as food, products, activities, and entertainment.
2. Maintain Important Personal Details: Remember significant personal information like names, relationships, and important dates.
3. Track Plans and Intentions: Note upcoming events, trips, goals, and any plans the user has shared.
4. Remember Activity and Service Preferences: Recall preferences for dining, travel, hobbies, and other services.
5. Monitor Health and Wellness Preferences: Keep a record of dietary restrictions, fitness routines, and other wellness-related information.
6. Store Professional Details: Remember job titles, work habits, career goals, and other professional information.
7. Styles and Preferences: Keep track of how the user wants you to reply to messages, the tone of the conversation, and other stylistic preferences.
8. Miscellaneous Information Management: Keep track of favorite books, movies, brands, and other miscellaneous details that the user shares.
9. Update notes: if the user is specifically asking you to remember or forget something.
10. Ignore general facts: Ignore global information, like weather, news, or general knowledge or facts.

You must respond in JSON format with 4 keys:
- "reasoning": Your reasoning and thoughts on why you think the extracted facts, instructions, and update_notes are important.
- "facts": a list of general facts extracted from the conversation. Do not include the basic information, only if something is worth remembering.
- "instructions": Preferences, styles, and learned behaviors from the user. Do not include chat history of user actions here. This is to only record user preferences and styles.
- "update_notes": Any specific instructions from the user to remember or forget something.

Each of these can be an empty list if no relevant information is found. Prioritize extracting information from the "user" message; the "assistant" message is rarely needed. It's completely fine to return empty if no important information is found in the conversation.

Here are some few shot examples:

Input: Hi.
Output: {{"facts" : [], "instructions" : [], "update_notes" : []}}

Input: The capital of Canada is Ottawa, and water boils at 100 degrees Celsius.
Output: {{"facts" : [], "instructions" : [], "update_notes" : []}}

Input: Hi, I am looking for a restaurant in San Francisco.
Output: {{"facts" : ["Looking for a restaurant in San Francisco"], "instructions" : [], "update_notes" : []}}

Input: Yesterday, I had a meeting with John at 3pm. We discussed the new project.
Output: {{"facts" : ["Had a meeting with John at 3pm", "Discussed the new project"], "instructions" : [], "update_notes" : []}}

Input: Please use the color red for all the lines in graphs you generate, redo the previous diagram.
Output: {{"facts" : [], "instructions" : [], "update_notes" : ["User prefers color red for all lines in graphs"]}}

Input: Sam is no longer my boss, remember that.
Output: {{"facts" : [], "instructions" : [], "update_notes" : ["Sam is no longer my boss"]}}

Input: Hi, my name is John. I am a software engineer.
Output: {{"facts" : ["Name is John", "Is a Software engineer"]}}

Input: Give me the summary of Jira item JIRA-1234. Always format your messages in markdown format with proper headings and bullet points.
Output: {{"facts" : [], "instructions" : ["Format messages in markdown format with proper headings and bullet points"], "update_notes" : []}}

Input: We just had our biggest sales ever. generate me the sales report for the last quarter. Use HTML with nice CSS styling for the report.
Output: {{"facts" : ["Had our biggest sales ever"], "instructions" : ["Use HTML with nice CSS styling for the report"], "update_notes" : []}}


Return the facts and preferences in a json format as shown above. Do not return anything else or do not prefix them with backticks.

Remember the following:
- Today's date is {datetime.now().strftime("%Y-%m-%d")}.
- Do not return anything from the example prompts provided above.
- Ignore specific details, like IDs, URLs, or numbers unless they are needed to be remembered long term or asked by the user.
- You are only analyzing and extracting information from the conversation, you're not replying to the user.
- If you do not find anything relevant in the below conversation, you can return an empty list.
- Create the facts based on the user and assistant messages only. Prioritize the user messages, most assistant replies can be ignored.
- The sentences must be complete and understandable without prior context.
- Make sure to return the response in the format mentioned in the examples. 
- Ignore if the user is asking to clear history or forget everything you know. (That is not a update note)
- Don't repeat the same things in both facts and instructions. 

Following is a conversation between the user and the assistant. You have to extract the relevant facts and instructions, and update notes about the user, if any, from the conversation and return them in the json format as shown above.

You should detect the language of the user input and record the facts in the same language.
""",
    
    "MERGE_FACTS": """You are a smart memory manager which controls the memory of a system.
You can perform four operations: (1) add into the memory, (2) update the memory, (3) delete from the memory, and (4) no change.

Based on the above four operations, the memory will change.

Compare newly retrieved facts with the existing memory. For each new fact, decide whether to:
- ADD: Add it to the memory as a new element
- UPDATE: Update an existing memory element
- DELETE: Delete an existing memory element
- NONE: Make no change (if the fact is already present or irrelevant)

You will be provided the initial and new memory, each includes `facts` and `instructions` keys. You might also be provided some special instruction notes.

You must return the initial memory updated with the new facts and instructions based on the above operations. 

Do NOT add, remove, or summarize anything from initial memory unless instructed by the new memory or the special notes.

There are specific guidelines to select which operation to perform:

1. **Add**: If the retrieved facts contain new information not present in the memory, then you have to add to the end of list.
- **Example**:
    - Initial Memory:
        {
            "facts": ["Name is John"],
            "instructions": []        
        }

    - Retrieved facts: 
        {
            "facts": ["User is a software engineer"],
            "instructions": ["Use CSS while generating an HTML report"]
        }

    - New Memory:
        {
            "facts": ["Name is John", "User is a software engineer"],
            "instructions": ["Use CSS while generating an HTML report"]
        }

2. **Update**: If the retrieved facts contain information that is already present in the memory but the information is totally different, then you have to update it. 

If the retrieved fact contains information that conveys the same thing as the elements present in the memory, then you have to keep the fact which has the most information. 

Example (a) -- if the memory contains "User likes to play cricket" and the retrieved fact is "Loves to play cricket with friends", then update the memory with the retrieved facts.

Example (b) -- if the memory contains "Likes cheese pizza" and the retrieved fact is "Loves cheese pizza", then you do not need to update it because they convey the same information.

- **Example**:
    - Initial Memory:
        {
          "facts": ["I really like cheese pizza", "User is a software engineer", "User likes to play cricket"],
           "instructions": []
        }

    - Retrieved facts: 
        {
            "facts": ["Loves cheese and chicken pizza", "Loves to play cricket with friends"],
            "instructions": []
        }
    
    - New Memory:
        {
        "facts": ["Loves cheese and chicken pizza", "User is a software engineer","Loves to play cricket with friends"],
        "instructions": []
        }

3. **Delete**: If the retrieved facts contain information that contradicts the information present in the memory, or has been specified in update notes, then you have to delete it. Do not include the entry that needs to be deleted in the new memory.

- **Example**:
    - Initial Memory:
        {
            "facts": ["Name is John", "His boss is Alex"],
            "instructions": []
        }

    - Retrieved facts:
        {
            "facts": ["Alex is no longer his boss"],
            "instructions": []
        }

    - New Memory:
        {
            "facts": ["Name is John"],
            "instructions": []
        }

4. **No Change**: If the retrieved facts contain information that is already present in the memory, then you do not need to make any changes.
- **Example**:
    - Initial Memory:
        {
            "facts": ["Name is John"],
            "instructions": ["Always reply in a formal tone"]  
        }

    - Retrieved facts: 
        {
            "facts": ["Name is John"],
            "instructions": ["Always reply in a formal tone"]
        }

    - New Memory:
        {
            "facts": ["Name is John"],
            "instructions": ["Always reply in a formal tone"] 
        }



    Always return all the previous facts and instructions in the memory that are not affected by the update as well. Respond in JSON format with the keys "reasoning", "facts" and "instructions" containing the updated memory. For the "reasoning" key, provide a brief explanation of the changes made to the memory and the reasoning and thought process behind it.
    
    If there are no changes, return the initial memory as it is. Do not return anything else or do not prefix them with backticks.
""",
    
    "SUMMARIZE": """You are a Personal Information Organizer, specialized in accurately sorting facts, user memories, and summarizing. Your primary role is to extract relevant pieces of information and summarize the user conversations. This allows for easy retrieval and personalization in future interactions.

In your summary, you should include the key points and important details from the conversation. Ignore the details that are not relevant or important. The summary should be concise and capture the essence of the conversation. Prioritize the user messages while summarizing the conversation. Do not include minor details or generic information.

You're only summarizing the conversation, not replying to the user. You should summarize the conversation in a clear and concise manner. You can use bullet points or numbered lists if needed. Respond in normal text format with only the summary of the conversation. Do not return anything else or do not prefix them with backticks.
""",
    
    "MERGE_SUMMARY": """You are a Personal Information Organizer, specialized in accurately sorting, updating, and merging user facts, memories, and previous summarizing. Your primary role is to merge the current conversation summary with the old summary and update it with the new information. This allows for easy retrieval and personalization in future interactions.

Don't allow for the final summary to get very long. Prioritize the facts and information from the new summary over the old. If the new summary contains the same information as the old one, keep the new one. If the new summary contains additional information, add it to the old summary. If the new summary contains contradictory information, update the old summary with the new one.

You should merge the two conversation summaries into one in a clear and concise manner. You can use bullet points or numbered lists if needed. Respond in normal text format with only the merged summaries. Do not return anything else or do not prefix them with backticks.
""",

}

class LongTermMemory():
    """
    A class to manage long-term memory for the assistant.
    """

    def __init__(self, llm_config):
        def llm_request(messages):
            response = completion(
                model=llm_config.get("model"),
                api_key=llm_config.get("api_key"),
                base_url=llm_config.get("base_url"),
                messages=messages
                )
            message = response.get("choices")[0].get("message")
            return message
        
        self.llm_request = llm_request
        
    def retrieve_user_memory(self, memory: dict, summary:str) -> str:
        instructions = ""
        facts = ""
        episodes = ""
        separator = '\n - '
        
        if memory.get("instructions"):
            instructions = (
            f"\n### Following instructions and preferences have been extracted from your previous conversations with the user:\n"
            f" - {separator.join(memory['instructions'])}\n"
        )
            
        if memory.get("facts"):
            facts = (
                f"\n### Following facts have been extracted from your previous conversations with the user:\n"
                f" - {separator.join(memory['facts'])}\n"
            )
        
        if summary:
            episodes = (
                f"\n### Following is a summary of your previous conversations with the user:\n"
                f"```\n{summary}\n```\n"
            )

        return instructions + facts + episodes

    def summarize_chat(self, chat: list)-> str:
        if not chat:
            return ""

        messages = [
            {
                "role": "system",
                "content": PROMPTS["SUMMARIZE"]
            },
            {
                "role": "user",
                "content": json.dumps(chat, indent=4)
            }
        ]
        response = self.llm_request(messages).get("content")
        return response

    def update_summary(self, initial_summary: str, new_summary: str) -> str:
        if not initial_summary:
            return new_summary
        
        if not new_summary:
            return initial_summary
        
        prompt = (
            """### Old Conversation Summary:\n"""
            f"\n```\n{initial_summary}\n```\n\n\n"
            """### New Conversation Summary:\n"""
            f"\n```\n{new_summary}\n```\n"
        )
        messages = [
            {
                "role": "system",
                "content": PROMPTS["MERGE_SUMMARY"]
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
        response = self.llm_request(messages).get("content")
        return response

    def extract_memory_from_chat(self, chat: list) -> dict:
        messages = [
            {
                "role": "system",
                "content": PROMPTS["EXTRACT_FACTS"]
            },
            {
                "role": "user",
                "content": (
                    "Here's the conversation between the user and the assistant:\n"
                    f"```\n{json.dumps(chat, indent=4)}\n```\n\n"
                    "It's okay to return with empty lists. Only extract if the information is relevant or important.\n"
                    "Don't extract basic or generic information as facts!\n"
                    "Respond in the JSON format with the keys 'reasoning', 'facts', 'instructions', and 'update_notes' and no prefix or affix.\n"
                )
                
            }
        ]
        memory = self._get_and_validate_memory(messages)

        return memory

    def update_user_memory(self, initial_memory: dict, new_memory: dict) -> dict:
        if not initial_memory or not (initial_memory.get("facts") or initial_memory.get("instructions")):
            return {
                "facts": new_memory.get("facts", []),
                "instructions": new_memory.get("instructions", []),
            }
        initial_memory_str = json.dumps({
                "facts": initial_memory.get("facts", []),
                "instructions": initial_memory.get("instructions", []),
        }, indent=4)    
        new_memory_str = json.dumps({
                "facts": new_memory.get("facts", []),
                "instructions": new_memory.get("instructions", []),
        }, indent=4)

        separator = '\n - '
        special_notes = separator.join(new_memory.get("update_notes", [])) or "None"
        
        prompt = (
            "### Initial Memory:\n"
            f"\n```\n{initial_memory_str}\n```\n\n\n"
            "### Special Notes:\n"
            f"\n```\n - {special_notes}\n```\n\n\n"
            "### New Memory:\n"
            f"\n```\n{new_memory_str}\n```\n\n"
            "Return the complete updated memory in the JSON format with the keys 'reasoning', 'facts' and 'instructions' and no prefix or affix."
        )

        messages = [
            {
                "role": "system",
                "content": PROMPTS["MERGE_FACTS"]
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
        memory = self._get_and_validate_memory(messages)
        return memory
    
    def _get_and_validate_memory(self, messages: list) -> dict:
        attempt = 0
        while attempt < 3:
            response = self.llm_request(messages).get("content")
            attempt += 1
            messages.append(
                {
                    "role": "assistant",
                    "content": response
                }
            )

            try:
                parsed_response = json.loads(response)
            except Exception as e:
                log.error("Error parsing response as JSON: %s", str(e))
                messages.append(
                    {
                        "role": "user",
                        "content": f"Error parsing response as JSON: {str(e)}. Don't apologize, just try again and respond only with the valid JSON"
                    }
                )
                continue

            if "facts" not in parsed_response or "instructions" not in parsed_response: 
                log.error("Missing facts or instructions in response")
                messages.append({
                    "role": "user",
                    "content": "Error: Missing facts or instructions in response. Don't apologize, just try again and respond only with the valid JSON"
                })
                continue
            
            # remove reasoning key, used only for COT
            if "reasoning" in parsed_response:
                parsed_response.pop("reasoning", None)

            return parsed_response
        return None

