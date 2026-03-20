BOOTSTRAP_SUBSCRIBE_TOPIC = "{namespace}configuration/model/bootstrap/>"
BOOTSTRAP_REQUEST_TOPIC = "{namespace}configuration/model/bootstrap/{model_id}"
BOOTSTRAP_RESPONSE_TOPIC = "{namespace}configuration/model/response/{model_id}/{component_id}"
MODEL_CONFIG_UPDATE_TOPIC = "{namespace}configuration/model/{model_id}"

def get_bootstrap_subscribe_topic(namespace: str) -> str:
    """
    Get the A2A topic to subscribe to for model configuration bootstrap requests.

    Returns:
        The topic string to subscribe to for model config bootstrap requests.
    """
    return BOOTSTRAP_SUBSCRIBE_TOPIC.format(namespace=namespace)

def get_bootstrap_request_topic(namespace: str, model_id: str) -> str:
    """
    Get the A2A topic to publish model configuration requests to.

    Returns:
        The topic string to publish model config requests to.
    """

    return BOOTSTRAP_REQUEST_TOPIC.format(
        namespace=namespace,
        model_id=model_id,
    )

def get_bootstrap_response_topic(namespace: str, model_id: str, component_id: str) -> str:
    """
    Get the A2A topic to listen for model configuration request responses.

    Returns:
        The topic string to listen for model config request responses on.
    """
    return BOOTSTRAP_RESPONSE_TOPIC.format(
        namespace=namespace,
        model_id=model_id,
        component_id=component_id
        )

def get_model_config_update_topic(namespace: str, model_id: str) -> str:
    """
    Get the A2A topic to listen for model configuration updates on.

    Returns:
        The topic string to listen for model config updates on.
    """
    return MODEL_CONFIG_UPDATE_TOPIC.format(
        namespace=namespace,
        model_id=model_id,
    )