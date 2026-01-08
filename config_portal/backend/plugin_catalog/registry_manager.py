import json
import os
import hashlib
from pathlib import Path
from typing import List, Optional, Dict, Any
from pydantic import ValidationError

from .models import Registry
from .constants import (
    DEFAULT_OFFICIAL_REGISTRY_URL,
    USER_REGISTRIES_PATH,
    OFFICIAL_REGISTRY_GIT_BRANCH,
)


class RegistryManager:
    def __init__(self):
        self.user_registries_file = Path(os.path.expanduser(USER_REGISTRIES_PATH))
        self.user_registries_file.parent.mkdir(parents=True, exist_ok=True)

    def _generate_registry_id(self, path_or_url: str) -> str:
        """Generates a consistent ID for a registry based on its path or URL."""
        return hashlib.md5(path_or_url.encode("utf-8")).hexdigest()

    def get_all_registries(self) -> List[Registry]:
        default_id = self._generate_registry_id(DEFAULT_OFFICIAL_REGISTRY_URL)
        default_official_registry = Registry(
            id=default_id,
            path_or_url=DEFAULT_OFFICIAL_REGISTRY_URL,
            name="official_sam_plugins",
            type=(
                "git"
                if DEFAULT_OFFICIAL_REGISTRY_URL.startswith(
                    ("http://", "https://", "git@")
                )
                else "local"
            ),
            is_default=True,
            is_official_source=True,
            git_branch=OFFICIAL_REGISTRY_GIT_BRANCH,
        )

        registries_map: Dict[str, Registry] = {
            default_official_registry.id: default_official_registry
        }

        if self.user_registries_file.exists():
            try:
                with open(self.user_registries_file, "r", encoding="utf-8") as f:
                    loaded_data = json.load(f)
                    if isinstance(loaded_data, list):
                        for reg_dict in loaded_data:
                            if isinstance(reg_dict, dict):
                                try:
                                    registry_obj = Registry(**reg_dict)
                                    if registry_obj.id not in registries_map:
                                        registries_map[registry_obj.id] = registry_obj
                                except ValidationError as ve:
                                    print(
                                        f"Warning: Invalid registry data in user registries file: {reg_dict}. Error: {ve}"
                                    )
                                except Exception as e_parse:
                                    print(
                                        f"Warning: Could not parse registry item '{reg_dict}' from user registries: {e_parse}"
                                    )
                            else:
                                print(
                                    f"Warning: Non-dictionary item found in user registries list: {reg_dict}"
                                )
                    else:
                        print(
                            f"Warning: User registries file ({self.user_registries_file}) does not contain a list. Ignoring."
                        )
            except json.JSONDecodeError:
                print(
                    f"Error decoding user registries file: {self.user_registries_file}. A new file will be created if a registry is added."
                )
            except Exception as e:
                print(
                    f"An unexpected error occurred while reading {self.user_registries_file}: {e}"
                )

        return list(registries_map.values())

    def add_registry(self, path_or_url: str, name: Optional[str] = None) -> bool:
        original_path_or_url = path_or_url

        if path_or_url.startswith(("http://", "https://", "git@")):
            registry_type = "git"
        else:
            registry_type = "local"
            try:
                expanded_path = Path(os.path.expanduser(path_or_url))
                if not expanded_path.exists() or not expanded_path.is_dir():
                    print(
                        f"Error: Local path for registry does not exist or is not a directory: {expanded_path}"
                    )
                    return False
                path_or_url = str(expanded_path.resolve())
            except Exception as e_path:
                print(f"Error processing local path '{original_path_or_url}': {e_path}")
                return False

        registry_id = self._generate_registry_id(path_or_url)
   
        final_name = name
        if not final_name:
            if registry_type == "git":
                final_name = Path(original_path_or_url).name.replace(".git", "")
            else:
                final_name = Path(path_or_url).name

        # Sanitize name to be filesystem-friendly
        final_name = "".join(c if c.isalnum() else '_' for c in final_name)
        is_official_src = path_or_url == DEFAULT_OFFICIAL_REGISTRY_URL

        try:
            new_registry = Registry(
                id=registry_id,
                path_or_url=path_or_url,
                name=final_name,
                type=registry_type,
                is_default=False,
                is_official_source=is_official_src,
            )
        except ValidationError as ve:
            print(f"Invalid registry data for '{path_or_url}': {ve}")
            return False

        current_registries_data: List[Dict[str, Any]] = []
        if self.user_registries_file.exists():
            try:
                with open(self.user_registries_file, "r", encoding="utf-8") as f:
                    loaded_data = json.load(f)
                    if isinstance(loaded_data, list):
                        current_registries_data = [
                            item for item in loaded_data if isinstance(item, dict)
                        ]
            except json.JSONDecodeError:
                print(
                    f"Warning: User registries file {self.user_registries_file} is corrupted. It will be overwritten."
                )
            except Exception as e:
                print(
                    f"An unexpected error occurred while reading {self.user_registries_file} before adding: {e}"
                )

        if any(
            r_data.get("id") == new_registry.id for r_data in current_registries_data
        ):
            print(
                f"Registry with path/URL '{path_or_url}' (ID: {new_registry.id}) already exists."
            )
            return False

        current_registries_data.append(new_registry.model_dump())

        try:
            with open(self.user_registries_file, "w", encoding="utf-8") as f:
                json.dump(current_registries_data, f, indent=2)
            return True
        except Exception as e:
            print(
                f"Error writing to user registries file {self.user_registries_file}: {e}"
            )
            return False
