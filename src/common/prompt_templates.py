from typing import List
import yaml


def FilterLocationsSystemPrompt(locations: List[str]) -> str:
    return f"""
You will use your geographical knowledge to filter the following list of locations
into a list of locations that fall within the user's request. Those locations
must be returned in a yaml array of the following schema:

<response-schema-yaml>
matching_locations:
  - <location1>
  - <location2>
  ...
</response-schema-yaml>

<locations>
{yaml.dump(locations)}
"""


def FilterLocationsUserPrompt(location_filter: str) -> str:
    return f"""
<user-location-filter>
{location_filter}
</user-location-filter>
"""
