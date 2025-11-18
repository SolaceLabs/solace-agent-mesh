#!/usr/bin/env python3
'''
Unit tests for uvicorn configuration in WebUIBackendComponent.

Tests ensure that:
1. log_config is explicitly set to None
'''

from unittest.mock import MagicMock, patch

from solace_agent_mesh.gateway.http_sse.component import WebUIBackendComponent


class TestUvicornConfig:
    '''Test suite for uvicorn configuration.'''

    @patch('solace_agent_mesh.gateway.http_sse.component.uvicorn.Server')
    @patch('solace_agent_mesh.gateway.http_sse.component.uvicorn.Config')
    @patch('solace_agent_mesh.gateway.http_sse.component.threading.Thread')
    @patch('solace_agent_mesh.gateway.http_sse.component.TaskLoggerService')
    def test_log_config_is_none(
        self, mock_task_logger_service, mock_thread, mock_uvicorn_config, mock_uvicorn_server
    ):
        '''Test that log_config is explicitly set to None in uvicorn configuration.'''
        mock_config_instance = MagicMock()
        mock_uvicorn_config.return_value = mock_config_instance
        mock_thread.return_value = MagicMock()

        # Create a minimal mock component instance
        component = MagicMock()
        component.fastapi_app = None
        component.fastapi_thread = None
        component.fastapi_host = '127.0.0.1'
        component.fastapi_port = 8000
        component.fastapi_https_port = 8443
        component.ssl_keyfile = ''
        component.ssl_certfile = ''
        component.ssl_keyfile_password = ''
        component.log_identifier = '[test]'
        component.database_url = None
        component.platform_database_url = None
        component.get_config = MagicMock(return_value={})
        
        with patch('solace_agent_mesh.gateway.http_sse.component.dependencies') as mock_deps:
            with patch('solace_agent_mesh.gateway.http_sse.component.log'):
                mock_main = MagicMock()
                mock_main.app = MagicMock()
                mock_main.setup_dependencies = MagicMock()
                
                mock_deps.SessionLocal = None
                
                with patch('builtins.__import__', side_effect=lambda name, *args, **kwargs: mock_main if 'main' in name else __import__(name, *args, **kwargs)):
                    WebUIBackendComponent._start_fastapi_server(component)

                    assert mock_uvicorn_config.called, 'uvicorn.Config should have been called'
                    
                    call_args = mock_uvicorn_config.call_args
                    kwargs = call_args.kwargs if call_args.kwargs else call_args[1]
                    
                    assert 'log_config' in kwargs, 'log_config not found in uvicorn.Config arguments'
                    assert kwargs['log_config'] is None, (
                        'log_config should be None, but got ' + str(kwargs['log_config'])
                    )
