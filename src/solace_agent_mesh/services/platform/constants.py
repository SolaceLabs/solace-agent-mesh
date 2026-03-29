"""Constants for Platform Service model_configurations."""

# Column length constraints for model_configurations table
MODEL_CONFIGURATION_CONSTRAINTS = {
    "ALIAS_MIN_LENGTH": 1,
    "ALIAS_MAX_LENGTH": 100,
    "PROVIDER_MAX_LENGTH": 50,
    "MODEL_NAME_MAX_LENGTH": 255,
    "API_BASE_MAX_LENGTH": 2048,
    "MODEL_AUTH_TYPE_MAX_LENGTH": 50,
    "CREATED_BY_MAX_LENGTH": 255,
    "UPDATED_BY_MAX_LENGTH": 255,
}
