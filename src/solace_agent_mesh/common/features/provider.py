"""
OpenFeature provider that delegates to FeatureChecker.

This provider implements the OpenFeature AbstractProvider interface so that
flag evaluation throughout SAM is expressed in standard OpenFeature terms.
Swapping the backend (e.g. to a remote flag service) only requires replacing
this provider — all call sites remain unchanged.

Only boolean flag evaluation is supported because SAM feature flags are
on/off switches. String, integer, float, and object evaluation methods are
provided as required by the interface but always return the default value.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional, Union

from openfeature.evaluation_context import EvaluationContext
from openfeature.flag_evaluation import FlagResolutionDetails, Reason
from openfeature.provider import AbstractProvider
from openfeature.provider.metadata import Metadata

if TYPE_CHECKING:
    from .checker import FeatureChecker

logger = logging.getLogger(__name__)

_PROVIDER_NAME = "SAMFeatureProvider"


class SamFeatureProvider(AbstractProvider):
    """
    OpenFeature provider backed by FeatureChecker.

    Parameters
    ----------
    checker:
        A configured FeatureChecker instance that performs the two-tier
        evaluation (env var → registry default).
    """

    def __init__(self, checker: "FeatureChecker") -> None:
        self._checker = checker

    def get_metadata(self) -> Metadata:
        return Metadata(name=_PROVIDER_NAME)

    def get_provider_hooks(self):
        return []

    def resolve_boolean_details(
        self,
        flag_key: str,
        default_value: bool,
        evaluation_context: Optional[EvaluationContext] = None,  # pylint: disable=unused-argument
    ) -> FlagResolutionDetails[bool]:
        if not self._checker.is_known_flag(flag_key):
            logger.warning(
                "resolve_boolean_details() called for unregistered flag '%s';"
                " returning default %s",
                flag_key,
                default_value,
            )
            return FlagResolutionDetails(value=default_value, reason=Reason.DEFAULT)
        try:
            value = self._checker.is_enabled(flag_key)
            return FlagResolutionDetails(value=value, reason=Reason.STATIC)
        except Exception:  # pylint: disable=broad-except
            logger.exception(
                "Error resolving boolean flag '%s'; returning default %s",
                flag_key,
                default_value,
            )
            return FlagResolutionDetails(value=default_value, reason=Reason.ERROR)

    def resolve_string_details(
        self,
        flag_key: str,  # pylint: disable=unused-argument
        default_value: str,
        evaluation_context: Optional[EvaluationContext] = None,  # pylint: disable=unused-argument
    ) -> FlagResolutionDetails[str]:
        return FlagResolutionDetails(value=default_value, reason=Reason.DEFAULT)

    def resolve_integer_details(
        self,
        flag_key: str,  # pylint: disable=unused-argument
        default_value: int,
        evaluation_context: Optional[EvaluationContext] = None,  # pylint: disable=unused-argument
    ) -> FlagResolutionDetails[int]:
        return FlagResolutionDetails(value=default_value, reason=Reason.DEFAULT)

    def resolve_float_details(
        self,
        flag_key: str,  # pylint: disable=unused-argument
        default_value: float,
        evaluation_context: Optional[EvaluationContext] = None,  # pylint: disable=unused-argument
    ) -> FlagResolutionDetails[float]:
        return FlagResolutionDetails(value=default_value, reason=Reason.DEFAULT)

    def resolve_object_details(
        self,
        flag_key: str,  # pylint: disable=unused-argument
        default_value: Union[dict, list],
        evaluation_context: Optional[EvaluationContext] = None,  # pylint: disable=unused-argument
    ) -> FlagResolutionDetails[Union[dict, list]]:
        return FlagResolutionDetails(value=default_value, reason=Reason.DEFAULT)

    def all_flags(self) -> dict[str, bool]:
        """Return evaluated state of every registered flag."""
        return self._checker.all_flags()

    def load_flags_from_yaml(self, yaml_path) -> None:
        """Load additional flag definitions from a YAML file into the registry."""
        self._checker.load_from_yaml(yaml_path)
