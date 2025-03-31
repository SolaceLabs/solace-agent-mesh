import unittest

# Comment the import statements to prevent running the tests

from tests.test_history_service import TestHistoryService
from tests.services.file_service.test_file_service import TestFileServiceRegex, TestFileService, TestFileUtils
from tests.services.history_service.test_history_service import TestHistoryService
from tests.test_action_manager import TestActionManger
from tests.test_parser import TestParser
from tests.test_orchestrator_streaming_output import TestOrchestratorStreamingOutput
from tests.test_form_utils import TestFormUtils
from tests.services.async_service.test_async_service_component import TestAsyncServiceComponent


def run_tests():
    unittest.main()


if __name__ == "__main__":
    run_tests()
