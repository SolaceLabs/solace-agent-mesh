import os
import json
import yaml
from solace_ai_connector.common.log import log

_has_initialized_system = False

def initialize():
    global _has_initialized_system
    if not _has_initialized_system:
        _has_initialized_system = True
    else:
        return
    
    try:
        from solace_a2a_agent_enterprise.init_enterprise import initialize_enterprise_features
    except ImportError:
        # Community edition
        # Contact Solace support for enterprise features
        return
    
    enterprise_config = os.getenv("SAM_ENTERPRISE_CONFIG")
    if enterprise_config and isinstance(enterprise_config, str):
        if enterprise_config.endswith('.yaml') or enterprise_config.endswith('.yml'):
            try:
                with open(enterprise_config, 'r', encoding='utf-8') as file:
                    enterprise_config = yaml.safe_load(file)
            except Exception as e:
                log.error("Failed to load YAML config from SAM_ENTERPRISE_CONFIG: %s", e, exc_info=True)
                raise
        elif enterprise_config.endswith('.json'):
            try:
                with open(enterprise_config, 'r', encoding='utf-8') as file:
                    enterprise_config = json.load(file)
            except Exception as e:
                log.error("Failed to load JSON config from SAM_ENTERPRISE_CONFIG: %s", e, exc_info=True)
                raise
        else:
            try:
                enterprise_config = json.loads(enterprise_config)
            except json.JSONDecodeError as e:
                log.error("Invalid JSON in SAM_ENTERPRISE_CONFIG: %s", e, exc_info=True)
                raise
    else:
        enterprise_config = {}
    
    try:
        initialize_enterprise_features(enterprise_config)
    except Exception as e:
        log.error("Failed to initialize enterprise features: %s", e, exc_info=True)
        raise
