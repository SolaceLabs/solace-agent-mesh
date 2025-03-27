"""Grab-bag of common utility functions."""

import re
import yaml
import xml.etree.ElementTree as ET
from solace_ai_connector.common.log import log

from ..services.file_service import FileService


def escape_special_characters(xml_string):
    """
    Escapes special characters in an XML string.
    """
    # Escape & if it's not part of an entity like &amp;
    xml_string = re.sub(r"&(?!amp;|lt;|gt;|apos;|quot;)", "&amp;", xml_string)
    return xml_string


def extract_and_ignore_tag_content(xml_string, tag):
    """
    Extracts a tag and ignores its content.
    """
    # Find the first <data> tag and the last </data> tag
    start_index = xml_string.find(f"<{tag}")
    end_index = xml_string.rfind(f"</{tag}>")

    if start_index == -1 or end_index == -1:
        # If no <data> or </data> is found, return the original string and empty data content
        return xml_string, {}

    # Extract attributes of the first <data> tag
    open_tag_end = xml_string.find(">", start_index) + 1
    data_open_tag = xml_string[start_index:open_tag_end]

    # Extract the content of the first <data> tag
    open_tag_xml_string = data_open_tag + f"</{tag}>"
    data_attributes = xml_to_dict(open_tag_xml_string, None)[tag]

    # Extract content between the first <data> and the last </data>
    data_content = xml_string[open_tag_end:end_index].strip()

    # Remove the <data>...</data> section from the XML string
    xml_string = xml_string[:start_index] + xml_string[end_index + len(f"</{tag}>") :]

    data_attributes[tag] = data_content

    return xml_string, data_attributes


def xml_to_dict(xml_string, ignore_content_tags=[], strip_uniquifier_tag_prefix=False):
    """
    Converts an XML string to a dictionary.

    Parameters:
    - xml_string (str): The XML string.
    - ignore_content_tags (list): A list of tags whose content should be ignored (content is returned as a string).
    """
    # Extract the <data> block, its content, and its attributes
    ignore_contents = {}
    if ignore_content_tags and len(ignore_content_tags) > 0:
        for escape_tag in ignore_content_tags:
            xml_string, data_content = extract_and_ignore_tag_content(
                xml_string, escape_tag
            )
            ignore_contents[escape_tag] = data_content

    # Escape special characters in the XML string
    xml_string = escape_special_characters(xml_string)

    def parse_element(element):
        parsed_dict = {}

        # Get the tag of the element
        element_tag = element.tag
        if strip_uniquifier_tag_prefix:
            element_tag = element_tag.split("_", 1)[-1]

        # Add element attributes
        if element.attrib:
            parsed_dict.update(element.attrib)

        # If the element has children, recursively parse them
        if list(element):
            for child in element:
                tag = child.tag
                if strip_uniquifier_tag_prefix:
                    tag = tag.split("_", 1)[-1]
                child_dict = parse_element(child)
                if tag in parsed_dict:
                    # If tag already exists, convert it into a list of values
                    if not isinstance(parsed_dict[tag], list):
                        parsed_dict[tag] = [parsed_dict[tag]]
                    parsed_dict[tag].append(child_dict[tag])
                else:
                    parsed_dict[tag] = child_dict[tag]

        # If the element contains text, store it
        if element.text and element.text.strip():
            parsed_dict[element_tag] = element.text.strip()

        return {element_tag: parsed_dict}

    # Parse the remaining XML string
    root = ET.fromstring(xml_string)

    # Convert the root element to dictionary
    parsed_dict = parse_element(root)

    # Add the ignored <data> content and attributes back into the dictionary
    if ignore_contents:
        parsed_dict.update(ignore_contents)

    return parsed_dict


def parse_yaml_response(response: str) -> dict:
    """Parse a YAML response that came back from an LLM."""
    # Need to deal with the possibility of a None response or the
    # yaml is surrounded by ```yaml...```
    if not response:
        return {}
    if "<response" in response:
        tag_name = re.search(r"<response[^>]*>", response).group(0)
        response = response.split(tag_name, 1)[1]
        response = response.rsplit(f"</{tag_name[1:]}", 1)[0]
    if "```yaml" in response:
        response = response.split("```yaml", 1)[1]
        response = response.rsplit("```", 1)[0]
    return yaml.safe_load(response)


def split_text(text, max_len=2000):
    pattern = r".{1,%d}(?:\n|\.|\s|$)" % max_len
    return re.findall(pattern, text, re.DOTALL)


def parse_file_content(file_xml: str) -> dict:
    """
    Parse the xml tags in the content and return a dictionary of the content.
    """
    try:
        ignore_content_tags = ["data"]
        file_dict = xml_to_dict(file_xml, ignore_content_tags)
        dict_keys = list(file_dict.keys())
        top_key = [key for key in dict_keys if key not in ignore_content_tags][0]

        return {
            "data": file_dict.get("data", {}).get("data", ""),
            "url": file_dict.get(top_key, {}).get("url", {}).get("url", ""),
            "mime_type": file_dict.get(top_key, {}).get("mime_type", ""),
            "name": file_dict.get(top_key, {}).get("name", ""),
        }
    except Exception as e:
        result = {"data": "", "url": "", "mime_type": "", "name": ""}
        log.error("Error parsing file content: %s", e)
        return result


def parse_llm_output(llm_output: str) -> dict:
    # The response has <<< and >>> around the parameter string values
    # We want to replace these strings with placeholders that we will
    # replace with the actual values later. This removes long strings from the
    # yaml that might cause parsing issues.
    # We need to save all the strings that we replace so that we can put them back
    # after we parse the yaml. Use a sequence number to create a unique placeholder
    # for each string.
    string_placeholders = {}
    string_count = 0
    sanity = 100
    while "<<<" in llm_output and sanity > 0:
        sanity -= 1
        start = llm_output.index("<<<")
        if not ">>>" in llm_output:
            # set the end to the end of the string
            end = len(llm_output)
        else:
            end = llm_output.index(">>>")
        string = llm_output[start + 3 : end]
        llm_output = (
            llm_output[:start] + f"___STRING{string_count}___" + llm_output[end + 3 :]
        )
        # Also replace an newline characters in the string with a real newline
        string = string.replace("\\n", "\n")
        string_placeholders[f"___STRING{string_count}___"] = string
        string_count += 1

    # Sometimes the response comes back surrounded by <response-schema> tags
    if "<response-schema>" in llm_output:
        llm_output = llm_output.split("<response-schema>", 1)[1]
        llm_output = llm_output.rsplit("</response-schema>", 1)[0]

    if "<response>" in llm_output:
        llm_output = llm_output.split("<response>", 1)[1]
        llm_output = llm_output.rsplit("</response>", 1)[0]

    if "<response-yaml>" in llm_output:
        llm_output = llm_output.split("<response-yaml>", 1)[1]
        llm_output = llm_output.rsplit("</response-yaml>", 1)[0]

    # The llm_output should be yaml - it might be contained in ```yaml``` tags
    if "```yaml" in llm_output:
        # Get the text between the ```yaml and the final ```
        # Note that there might be nesting of ``` tags, so don't
        # just go to the next ```, but instead find the last one
        llm_output = llm_output.split("```yaml", 1)[1]
        llm_output = llm_output.rsplit("```", 1)[0]

    obj = None
    try:
        obj = yaml.safe_load(llm_output)
    except Exception:
        # Remove the last line and try again
        llm_output = llm_output.split("\n")[:-1]
        try:
            obj = yaml.safe_load("\n".join(llm_output))
        except Exception:
            return None

    def replace_placeholder(value):
        # Find all the placeholders in the string and replace them
        def replace(match):
            placeholder = match.group(0)
            if placeholder in string_placeholders:
                return string_placeholders[placeholder]
            return match.group(0)

        return re.sub(r"___STRING\d+___", replace, value)

    # Replace the string placeholders in obj with the actual strings
    def replace_strings(obj):
        if isinstance(obj, dict):
            for key, value in obj.items():
                if isinstance(value, str):
                    obj[key] = replace_placeholder(value)
                else:
                    replace_strings(value)
        elif isinstance(obj, list):
            for i, value in enumerate(obj):
                if isinstance(value, str):
                    obj[i] = replace_placeholder(value)
                else:
                    replace_strings(value)

    replace_strings(obj)
    return obj


def parse_orchestrator_response(response, last_chunk=False, tag_prefix=""):
    tp = tag_prefix
    parsed_data = {
        "actions": [],
        "current_subject_starting_id": None,
        "errors": [],
        "reasoning": None,
        "content": [],
        "status_updates": [],
        "send_last_status_update": False,
    }

    if not response:
        return parsed_data

    if not tp:
        # Learn the tag prefix from the response
        match = re.search(r"<(t[\d]+_)", response)
        if match:
            tp = match.group(1)
        else:
            tp = ""

    if not last_chunk:
        response = remove_incomplete_tags_at_end(response)

    # Parse out the <reasoning> tag - they are always first, so just do a
    # simple search and remove them from the response
    reasoning_match = re.search(
        "<" + tp + r"reasoning>(.*?)</" + tp + "reasoning>", response, re.DOTALL
    )
    if reasoning_match:
        parsed_data["reasoning"] = reasoning_match.group(1).strip()
        response = re.sub(
            "<" + tp + r"reasoning>.*?</" + tp + "reasoning>",
            "",
            response,
            flags=re.DOTALL,
        )
    elif f"<{tp}reasoning>" in response:
        parsed_data["errors"].append("Incomplete <reasoning> tag")
        return parsed_data
    else:
        parsed_data["reasoning"] = None

    # Get all the <{tp}status_update> tags
    status_updates = []
    status_matches = re.finditer(
        f"<{tp}status_update>(.*?)</{tp}status_update>", response, re.DOTALL
    )
    for match in status_matches:
        status_updates.append(match.group(1).strip())
        response = response.replace(match.group(0), "", 1)

    # Remove all complete status_update tags
    response = re.sub(
        f"<{tp}status_update>.*?</{tp}status_update>" + r"\s*",
        "",
        response,
        flags=re.DOTALL,
    )

    # Remove any incomplete status_update tags
    response = re.sub(f"<{tp}status_update>.*?($|<)", "", response, flags=re.DOTALL)

    if status_updates:
        parsed_data["status_updates"] = status_updates

    # Parse out <file> tags and other elements
    in_file = False
    current_file = {}
    file_content = []
    current_action = {}
    in_invoke_action = False
    current_param_name = None
    current_param_value = []
    open_tags = []
    current_text = []

    for line in response.split("\n"):

        if f"<{tp}current_subject" in line:
            id_match = re.search(r'starting_id\s*=\s*[\'"](\w+)[\'"]\s*\/?>', line)
            if id_match:
                parsed_data["current_subject_starting_id"] = id_match.group(1)

        elif f"<{tp}file" in line:
            in_file = True
            # We can't guarantee the order of the attributes, so we need to parse them separately
            name_match = re.search(r'name\s*=\s*[\'"]([^\'"]+)[\'"]', line)
            mime_type_match = re.search(r'mime_type\s*=\s*[\'"]([^\'"]+)[\'"]', line)
            current_file = {
                "name": name_match.group(1) if name_match else "",
                "mime_type": mime_type_match.group(1) if mime_type_match else "",
                "url": "",
                "data": "",
            }
            file_start_index = line.index(f"<{tp}file")
            file_line = line[file_start_index:]
            if f"</{tp}file>" in line:
                file_end_index = line.index(f"</{tp}file>")
                file_line = line[: file_end_index + len(f"</{tp}file>")]
                file_content = [file_line]
                current_file = parse_file_content("\n".join(file_content))
                add_content_entry(parsed_data["content"], "file", current_file)
                in_file = False
                current_file = {}
                file_content = []
            else:
                file_content.append(file_line)

        elif f"</{tp}file>" in line:
            if in_file:
                if current_text:
                    add_content_entry(
                        parsed_data["content"], "text", current_text, add_newline=True
                    )
                    current_text = []
                file_end_index = line.index(f"</{tp}file>")
                file_line = line[: file_end_index + len(f"</{tp}file>")]
                file_content.append(file_line)
                current_file = parse_file_content("\n".join(file_content))
                add_content_entry(parsed_data["content"], "file", current_file)
                in_file = False
                current_file = {}
                file_content = []
            else:
                parsed_data["errors"].append("Unmatched </file> tag")
        elif in_file:
            file_content.append(line)

        elif f"<{tp}invoke_action" in line:
            if in_invoke_action:
                parsed_data["errors"].append("Nested <invoke_action> tags")
            in_invoke_action = True
            open_tags.append("invoke_action")
            current_action = {
                "agent": None,
                "action": None,
                "parameters": {},
            }

            for attr in ["agent", "action"]:
                attr_match = re.search(rf'{attr}\s*=\s*[\'"]([_\-\.\w]+)[\'"]', line)
                if attr_match:
                    current_action[attr] = attr_match.group(1)

        elif f"</{tp}invoke_action>" in line:
            if not in_invoke_action:
                parsed_data["errors"].append("Unmatched </invoke_action> tag")
            else:
                in_invoke_action = False
                if "invoke_action" in open_tags:
                    open_tags.remove("invoke_action")
                if current_param_name:
                    current_action["parameters"][current_param_name] = "\n".join(
                        current_param_value
                    ).strip()
                parsed_data["actions"].append(current_action)
                current_action = {}
                current_param_name = None
                current_param_value = []

        elif in_invoke_action and f"<{tp}parameter" in line:
            if current_param_name:
                current_action["parameters"][current_param_name] = "\n".join(
                    current_param_value
                ).strip()
                current_param_value = []

            param_name_match = re.search(r'name\s*=\s*[\'"](\w+)[\'"]', line)
            if param_name_match:
                current_param_name = param_name_match.group(1)
                open_tags.append("parameter")

                # Handle content on the same line as opening tag
                content_after_open = re.search(
                    r">(.*?)(?:</" + tp + "parameter>|$)", line
                )
                if content_after_open:
                    initial_content = content_after_open.group(1).strip()
                    if initial_content:
                        current_param_value.append(initial_content)

                # Check if parameter closes on same line
                if f"</{tp}parameter>" in line:
                    current_action["parameters"][current_param_name] = "\n".join(
                        current_param_value
                    ).strip()
                    current_param_name = None
                    current_param_value = []
                    if "parameter" in open_tags:
                        open_tags.remove("parameter")
                elif line.endswith("/>"):
                    current_action["parameters"][current_param_name] = ""
                    current_param_name = None
                    if "parameter" in open_tags:
                        open_tags.remove("parameter")
                elif not ">" in line:
                    parsed_data["errors"].append("Incomplete <parameter> tag")

        elif in_invoke_action and current_param_name:
            if f"</{tp}parameter>" in line:
                # Handle content before closing tag on final line
                content_before_close = re.sub(f"</{tp}parameter>.*", "", line)
                if content_before_close.strip():
                    current_param_value.append(content_before_close.strip())
                current_action["parameters"][current_param_name] = "\n".join(
                    current_param_value
                ).strip()
                current_param_name = None
                current_param_value = []
                if "parameter" in open_tags:
                    open_tags.remove("parameter")
            else:
                current_param_value.append(line.strip())

        else:
            current_text.append(line)

    if open_tags:
        parsed_data["errors"].append(f"Unclosed tags: {', '.join(open_tags)}")

    if in_file:
        content = "\n".join(file_content)
        # Add a status update for this
        parsed_data["status_updates"].append(
            f"File {current_file['name']} loading ({len(content)} characters)..."
        )
        parsed_data["send_last_status_update"] = True
        parsed_data["errors"].append("Unclosed <file> tag")

    if len(current_text) > 0:
        add_content_entry(parsed_data["content"], "text", current_text)

    return parsed_data


def remove_incomplete_tags_at_end(text):
    """If the end of the text is in the middle of a <tag> or </tag> then remove it."""
    # remove any open tags at the end
    last_open_tag = text.rfind("<")
    last_open_end_tag = text.rfind("</")
    last_close_tag = text.rfind(">")
    if last_close_tag >= last_open_tag and last_close_tag >= last_open_end_tag:
        return text
    # Knock off the last line
    return text.rsplit("\n", 1)[0]


def add_content_entry(content_list, entry_type, body, add_newline=False):
    if body:
        if entry_type == "text":
            body = clean_text(body)
            if add_newline:
                body += "\n"
        content_list.append({"type": entry_type, "body": body})


def match_solace_topic_level(pattern: str, topic_level: str) -> bool:
    """Match a single topic level with potential * wildcard prefix matching"""
    if pattern == "*":
        return True
    if pattern.endswith("*"):
        return topic_level.startswith(pattern[:-1])
    return pattern == topic_level


def match_solace_topic(subscription: str, topic: str) -> bool:
    """
    Match a Solace topic against a subscription pattern.
    Handles * for prefix matching within a level and > for matching one or more levels.
    Case sensitive matching.

    Examples:
        match_solace_topic("a/b*/c", "a/bob/c") -> True
        match_solace_topic("a/*/c", "a/b/c") -> True
        match_solace_topic("a/>", "a/b") -> True
        match_solace_topic("a/>", "a/b/c") -> True
        match_solace_topic("a/>", "a") -> False
    """
    if not subscription or not topic:
        return False

    sub_levels = subscription.split("/")
    topic_levels = topic.split("/")

    # Handle > wildcard
    if sub_levels[-1] == ">":
        # > must match at least one level
        if len(topic_levels) <= len(sub_levels) - 1:
            return False
        # Match all levels before the >
        return all(
            match_solace_topic_level(sub_levels[i], topic_levels[i])
            for i in range(len(sub_levels) - 1)
        )

    # Without >, levels must match exactly
    if len(sub_levels) != len(topic_levels):
        return False

    # Match each level
    return all(
        match_solace_topic_level(sub_levels[i], topic_levels[i])
        for i in range(len(sub_levels))
    )


def clean_text(text_array):
    # Any leading blank lines are removed
    while text_array and not text_array[0]:
        text_array.pop(0)

    # Look for multiple blank lines in a row and collapse them into a single blank line
    i = 0
    while i < len(text_array) - 1:
        if not text_array[i] and not text_array[i + 1]:
            text_array.pop(i)
        else:
            i += 1

    return "\n".join(text_array)


def files_to_block_text(files):
    blocks = []
    text = ""
    if files:
        for file in files:
            try:
                block = FileService.get_file_block_by_metadata(file)
                blocks.append(block)
            except Exception as e:
                log.warning("Could not get file block: %s", e)
    if blocks:
        text += (
            "\n\nAttached files:\n\n" if len(blocks) > 1 else "\n\nAttached file:\n\n"
        )
        text += "\n\n".join(blocks)
    return text


def remove_config_parameter(info, parameter_name):
    """
    Remove a parameter from the config of a component.
    """
    if "config_parameters" in info:
        index = info["config_parameters"].index(
            next(
                (
                    item
                    for item in info["config_parameters"]
                    if item.get("name") == parameter_name
                ),
                None,
            )
        )

        # Remove the parameter from the list
        if index is not None:
            info["config_parameters"].pop(index)

    return info


def format_agent_response(actions):
    """Format the action response for the AI"""
    ai_response = (
        "Results for the requested actions. NOTE: these are generated internally in the "
        "system. A user was not involved, so there is no need to respond to them or thank them.\n"
    )
    found_ai_response = False
    files = []
    for action in actions:
        found_ai_response = True
        ai_response += f"\n  {action.get('action_idx')}: {action.get('agent_name')}.{action.get('action_name')}:\n"
        params = action.get("action_params", {})
        response_files = action.get("response", {}).get("files", [])
        for param, value in params.items():
            if isinstance(value, str):
                ai_response += f"    {param}: {value[:100]}\n"
            else:
                ai_response += f"    {param}: {value}\n"
        ai_response += "  Response:\n"
        ai_response += f"    <<<{action.get('response', {'text':'<No response>'}).get('text')}>>>\n"
        if response_files:
            ai_response += "  Files:\n"
            for file in response_files:
                ai_response += f"    {file.get('url')}\n"
        files.extend(action.get("response", {}).get("files", []))

    if not found_ai_response:
        return None
    return ai_response, files
