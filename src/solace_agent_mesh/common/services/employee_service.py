"""
Defines the abstract base class and factory for creating Employee Service providers.
"""

import logging
import importlib
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import importlib.metadata as metadata


from ..utils.in_memory_cache import InMemoryCache
import pandas as pd

log = logging.getLogger(__name__)

class BaseEmployeeService(ABC):
    """
    Abstract base class for Employee Service providers.

    This class defines a "thin provider" contract. Implementations should focus
    solely on fetching data from a source system (like an HR platform) and
    mapping it to the canonical format. All complex business logic, such as
    building organizational charts or calculating availability schedules, should
    be handled by the tools that consume this service.

    Canonical Employee Schema
    This schema defines the standard fields that all EmployeeService providers should aim to return.
    - id (string): A unique, stable, and lowercase identifier for the employee (e.g., email, GUID).
    - displayName (string): The employee's full name for display purposes.
    - workEmail (string): The employee's primary work email address.
    - jobTitle (string): The employee's official job title.
    - department (string): The department the employee belongs to.
    - location (string): The physical or regional location of the employee.
    - supervisorId (string): The unique id of the employee's direct manager.
    - hireDate (string): The date the employee was hired (ISO 8601: YYYY-MM-DD).
    - mobilePhone (string): The employee's mobile phone number (optional).

    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initializes the service with its specific configuration block.

        Args:
            config: The dictionary of configuration parameters for this provider.
        """
        self.config = config
        self.log_identifier = f"[{self.__class__.__name__}]"
        self.cache_ttl = config.get("cache_ttl_seconds", 3600)
        self.cache = InMemoryCache() if self.cache_ttl > 0 else None
        log.info(
            "%s Initialized. Cache TTL: %d seconds.",
            self.log_identifier,
            self.cache_ttl,
        )

    @abstractmethod
    async def get_employee_dataframe(self) -> pd.DataFrame:
        """Returns the entire employee directory as a pandas DataFrame."""
        pass

    @abstractmethod
    async def get_employee_profile(self, employee_id: str) -> Optional[Dict[str, Any]]:
        """Fetches the profile for a single employee."""
        pass

    @abstractmethod
    async def get_time_off_data(self, employee_id: str, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Retrieves a list of raw time-off entries for an employee.

        The tool consuming this data is responsible for interpreting it.
        Each dictionary in the list MUST contain the following keys:
        - 'start' (str): The start date of the leave (YYYY-MM-DD).
        - 'end' (str): The end date of the leave (YYYY-MM-DD).
        - 'type' (str): The category of leave (e.g., 'Vacation', 'Sick', 'Holiday').
        - 'amount' (str): The amount of time taken, must be one of 'full_day' or 'half_day'.

        Example:
        [
            {'start': '2025-07-04', 'end': '2025-07-04', 'type': 'Holiday', 'amount': 'full_day'},
            {'start': '2025-08-15', 'end': '2025-08-15', 'type': 'Vacation', 'amount': 'full_day'}
        ]

        Args:
            employee_id: The unique identifier for the employee.

        Returns:
            A list of dictionaries, each representing a time-off entry.
        """
        pass

    @abstractmethod
    async def get_employee_profile_picture(self, employee_id: str) -> Optional[str]:
        """
        Fetches an employee's profile picture and returns it as a data URI.

        Args:
            employee_id: The unique identifier for the employee.

        Returns:
            A string containing the data URI (e.g., 'data:image/jpeg;base64,...')
            or None if not available.
        """
        pass


def create_employee_service(
    config: Optional[Dict[str, Any]],
) -> Optional[BaseEmployeeService]:
    """
    Factory function to create an instance of an Employee Service provider
    based on the provided configuration.
    """
    if not config:
        log.info(
            "[EmployeeFactory] No 'employee_service' configuration found. Skipping creation."
        )
        return None

    provider_type = config.get("type")
    if not provider_type:
        raise ValueError("Employee service config must contain a 'type' key.")

    log.info(
        f"[EmployeeFactory] Attempting to create employee service of type: {provider_type}"
    )

    try:
        entry_points = metadata.entry_points(group="solace_agent_mesh.plugins")
        provider_info_entry = next(
            (ep for ep in entry_points if ep.name == provider_type), None
        )

        if not provider_info_entry:
            raise ValueError(
                f"No plugin provider found for type '{provider_type}' under the 'solace_agent_mesh.plugins' entry point."
            )

        provider_info = provider_info_entry.load()
        class_path = provider_info.get("class_path")
        if not class_path:
            raise ValueError(
                f"Plugin '{provider_type}' is missing 'class_path' in its info dictionary."
            )

        module_path, class_name = class_path.rsplit(".", 1)
        module = importlib.import_module(module_path)
        provider_class = getattr(module, class_name)

        if not issubclass(provider_class, BaseEmployeeService):
            raise TypeError(
                f"Provider class '{class_path}' does not inherit from BaseEmployeeService."
            )

        log.info(f"Successfully loaded employee provider plugin: {provider_type}")
        return provider_class(config)
    except (ImportError, AttributeError, TypeError, ValueError) as e:
        log.exception(
            f"[EmployeeFactory] Failed to load employee provider plugin '{provider_type}'. "
            "Ensure the plugin is installed and the entry point is correct."
        )
        raise ValueError(f"Could not load employee provider plugin: {e}") from e
