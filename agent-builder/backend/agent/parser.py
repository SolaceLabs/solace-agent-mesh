import xml.etree.ElementTree as ET

from typing import Dict, List, Any

def parse_agent_xml(agent_xml):
    """
    Parse the agent XML and extract relevant information.
    """
    try:
        # Parse the XML string
        root = ET.fromstring(agent_xml)

        # Extract the agent information
        agent_dict = {
            "name": root.find("name").text.strip(),
            "description": root.find("description").text.strip(),
            "actions": []
        }

        # Extract actions
        actions_element = root.find("actions")
        if actions_element is not None:
            for action_elem in actions_element.findall("action"):
                action_dict = {
                    "name": action_elem.find("name").text.strip(),
                    "description": action_elem.find("description").text.strip(),
                    "parameters": [],
                    "returns": action_elem.find("returns").text.strip()
                }

                # Extract parameters
                parameters_element = action_elem.find("parameters")
                if parameters_element is not None:
                    for parameter_elem in parameters_element.findall("parameter"):
                        param_dict = {
                            "name": parameter_elem.find("name").text.strip(),
                            "type": parameter_elem.find("type").text.strip(),
                            "description": parameter_elem.find("description").text.strip()
                        }
                        action_dict["parameters"].append(param_dict)

                agent_dict["actions"].append(action_dict)
        return agent_dict
    
    except ET.ParseError as e:
        print(f"Error parsing XML: {e}")
        return {"error": f"Error parsing XML: {e}"}
    except Exception as e:
        print(f"Unexpected error: {e}")
        return {"error": f"Unexpected error: {e}"}
    