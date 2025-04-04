import os
from ruamel.yaml import YAML

# Initialize a YAML object
yaml = YAML()
yaml.preserve_quotes = True  # To preserve quotes in the YAML

from cli.utils import merge_dicts, load_template, remove_duplicate


class Config:
    default_config_file = "solace-agent-mesh-default.yaml"
    user_config_file = "solace-agent-mesh.yaml"
    user_plugin_config_file = "solace-agent-mesh-plugin.yaml"
    default_plugin_config_file = "solace-agent-mesh-plugin-default.yaml"

    @staticmethod
    def get_default_config():
        loaded_config = load_template(Config.default_config_file)
        return yaml.load(loaded_config)

    @staticmethod
    def get_default_plugin_config():
        loaded_config = load_template(Config.default_plugin_config_file)
        return yaml.load(loaded_config)

    @staticmethod
    def get_user_config(config_file=None):
        config_file_path = config_file or Config.user_config_file
        if os.path.exists(config_file_path):
            with open(config_file_path, "r", encoding="utf-8") as f:
                return yaml.load(f) or {}
        return {}

    @staticmethod
    def get_user_plugin_config(config_file=None):
        config_file_path = config_file or Config.user_plugin_config_file
        if os.path.exists(config_file_path):
            with open(config_file_path, "r", encoding="utf-8") as f:
                return yaml.load(f) or {}
        return {}

    @staticmethod
    def get_config(config_file=None):
        user_config = Config.get_user_config(config_file)
        default_config = Config.get_default_config()
        # Merge user config with default config
        merged_config = merge_dicts(default_config, user_config)
        merged_config["solace_agent_mesh"]["built_in"]["agents"] = remove_duplicate(
            merged_config["solace_agent_mesh"]["built_in"]["agents"],
            lambda agent: agent.get("name"),
        )
        return merged_config

    @staticmethod
    def get_plugin_config(config_file=None):
        user_config = Config.get_user_plugin_config(config_file)
        default_config = Config.get_default_plugin_config()
        # Merge user config with default config
        merged_config = merge_dicts(default_config, user_config)
        return merged_config

    @staticmethod
    def is_plugin_project():
        return os.path.exists(Config.user_plugin_config_file)

    @staticmethod
    @staticmethod
    def write_config(config, path=None):
        if not path:
            path = Config.user_config_file
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(config, f)

    @staticmethod
    def load_config(path=None):
        if not path:
            path = Config.user_config_file
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return yaml.load(f)
            
    @staticmethod
    def get_yaml_parser():
        return yaml.load
