"""
Unit tests for src/solace_agent_mesh/agent/tools/time_tools.py

Tests the time tools functionality including:
- Getting current time in user's timezone
- Timezone handling and validation
- Error handling for missing context
- Time formatting and calculations
- Edge cases and error conditions
"""

from unittest.mock import Mock, MagicMock, patch
from datetime import datetime
from zoneinfo import ZoneInfo
import pytest

from src.solace_agent_mesh.agent.tools.time_tools import (
    get_current_time,
    get_current_time_tool_def,
    CATEGORY_NAME,
    CATEGORY_DESCRIPTION,
)


class TestGetCurrentTime:
    """Tests for get_current_time function"""

    @pytest.mark.asyncio
    async def test_get_current_time_missing_context(self):
        """Test error when tool context is missing"""
        result = await get_current_time(tool_context=None)
        
        assert result["status"] == "error"
        assert "ToolContext is missing" in result["message"]

    @pytest.mark.asyncio
    async def test_get_current_time_missing_invocation_context(self):
        """Test error when invocation context is not available"""
        mock_context = Mock()
        mock_context._invocation_context = None
        
        result = await get_current_time(tool_context=mock_context)
        
        assert result["status"] == "error"
        assert "InvocationContext is not available" in result["message"]

    @pytest.mark.asyncio
    async def test_get_current_time_success_utc(self):
        """Test successful time retrieval with UTC timezone"""
        mock_context = Mock()
        mock_inv_context = Mock()
        mock_inv_context.user_timezone = "UTC"
        mock_context._invocation_context = mock_inv_context
        
        with patch('src.solace_agent_mesh.agent.tools.time_tools.get_user_timezone') as mock_get_tz:
            mock_get_tz.return_value = "UTC"
            
            result = await get_current_time(tool_context=mock_context)
            
            assert result["status"] == "success"
            assert result["timezone"] == "UTC"
            assert "current_time" in result
            assert "formatted_time" in result
            assert "timestamp" in result
            assert "date" in result
            assert "time" in result
            assert "day_of_week" in result
            assert "timezone_offset" in result
            assert "timezone_abbreviation" in result

    @pytest.mark.asyncio
    async def test_get_current_time_success_america_toronto(self):
        """Test successful time retrieval with America/Toronto timezone"""
        mock_context = Mock()
        mock_inv_context = Mock()
        mock_inv_context.user_timezone = "America/Toronto"
        mock_context._invocation_context = mock_inv_context
        
        with patch('src.solace_agent_mesh.agent.tools.time_tools.get_user_timezone') as mock_get_tz:
            mock_get_tz.return_value = "America/Toronto"
            
            result = await get_current_time(tool_context=mock_context)
            
            assert result["status"] == "success"
            assert result["timezone"] == "America/Toronto"
            assert "current_time" in result
            assert "formatted_time" in result
            assert ":" in result["timezone_offset"]
            assert result["timezone_offset"].startswith(("+", "-"))

    @pytest.mark.asyncio
    async def test_get_current_time_invalid_timezone_fallback(self):
        """Test fallback to UTC when invalid timezone is provided"""
        mock_context = Mock()
        mock_inv_context = Mock()
        mock_inv_context.user_timezone = "Invalid/Timezone"
        mock_context._invocation_context = mock_inv_context
        
        with patch('src.solace_agent_mesh.agent.tools.time_tools.get_user_timezone') as mock_get_tz:
            mock_get_tz.return_value = "Invalid/Timezone"
            
            result = await get_current_time(tool_context=mock_context)
            
            assert result["status"] == "success"
            assert result["timezone"] == "UTC"
            assert "current_time" in result

    @pytest.mark.asyncio
    async def test_get_current_time_timezone_offset_format(self):
        """Test that timezone offset is properly formatted"""
        mock_context = Mock()
        mock_inv_context = Mock()
        mock_context._invocation_context = mock_inv_context
        
        with patch('src.solace_agent_mesh.agent.tools.time_tools.get_user_timezone') as mock_get_tz:
            mock_get_tz.return_value = "America/New_York"
            
            result = await get_current_time(tool_context=mock_context)
            
            assert result["status"] == "success"
            offset = result["timezone_offset"]
            assert len(offset) == 6
            assert offset[0] in ["+", "-"]
            assert offset[3] == ":"
            assert offset[1:3].isdigit()
            assert offset[4:6].isdigit()

    @pytest.mark.asyncio
    async def test_get_current_time_iso_format(self):
        """Test that current_time is in ISO format"""
        mock_context = Mock()
        mock_inv_context = Mock()
        mock_context._invocation_context = mock_inv_context
        
        with patch('src.solace_agent_mesh.agent.tools.time_tools.get_user_timezone') as mock_get_tz:
            mock_get_tz.return_value = "UTC"
            
            result = await get_current_time(tool_context=mock_context)
            
            assert result["status"] == "success"
            current_time_str = result["current_time"]
            parsed_time = datetime.fromisoformat(current_time_str)
            assert isinstance(parsed_time, datetime)

    @pytest.mark.asyncio
    async def test_get_current_time_date_format(self):
        """Test that date is in YYYY-MM-DD format"""
        mock_context = Mock()
        mock_inv_context = Mock()
        mock_context._invocation_context = mock_inv_context
        
        with patch('src.solace_agent_mesh.agent.tools.time_tools.get_user_timezone') as mock_get_tz:
            mock_get_tz.return_value = "UTC"
            
            result = await get_current_time(tool_context=mock_context)
            
            assert result["status"] == "success"
            date_str = result["date"]
            assert len(date_str) == 10
            assert date_str[4] == "-"
            assert date_str[7] == "-"
            datetime.strptime(date_str, "%Y-%m-%d")

    @pytest.mark.asyncio
    async def test_get_current_time_time_format(self):
        """Test that time is in HH:MM:SS format"""
        mock_context = Mock()
        mock_inv_context = Mock()
        mock_context._invocation_context = mock_inv_context
        
        with patch('src.solace_agent_mesh.agent.tools.time_tools.get_user_timezone') as mock_get_tz:
            mock_get_tz.return_value = "UTC"
            
            result = await get_current_time(tool_context=mock_context)
            
            assert result["status"] == "success"
            time_str = result["time"]
            assert len(time_str) == 8
            assert time_str[2] == ":"
            assert time_str[5] == ":"
            datetime.strptime(time_str, "%H:%M:%S")

    @pytest.mark.asyncio
    async def test_get_current_time_day_of_week(self):
        """Test that day_of_week is a valid day name"""
        mock_context = Mock()
        mock_inv_context = Mock()
        mock_context._invocation_context = mock_inv_context
        
        with patch('src.solace_agent_mesh.agent.tools.time_tools.get_user_timezone') as mock_get_tz:
            mock_get_tz.return_value = "UTC"
            
            result = await get_current_time(tool_context=mock_context)
            
            assert result["status"] == "success"
            day = result["day_of_week"]
            valid_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            assert day in valid_days

    @pytest.mark.asyncio
    async def test_get_current_time_timestamp_is_integer(self):
        """Test that timestamp is an integer"""
        mock_context = Mock()
        mock_inv_context = Mock()
        mock_context._invocation_context = mock_inv_context
        
        with patch('src.solace_agent_mesh.agent.tools.time_tools.get_user_timezone') as mock_get_tz:
            mock_get_tz.return_value = "UTC"
            
            result = await get_current_time(tool_context=mock_context)
            
            assert result["status"] == "success"
            assert isinstance(result["timestamp"], int)
            assert result["timestamp"] > 1577836800
            assert result["timestamp"] < 4102444800

    @pytest.mark.asyncio
    async def test_get_current_time_message_format(self):
        """Test that message contains timezone and formatted time"""
        mock_context = Mock()
        mock_inv_context = Mock()
        mock_context._invocation_context = mock_inv_context
        
        with patch('src.solace_agent_mesh.agent.tools.time_tools.get_user_timezone') as mock_get_tz:
            mock_get_tz.return_value = "America/Toronto"
            
            result = await get_current_time(tool_context=mock_context)
            
            assert result["status"] == "success"
            message = result["message"]
            assert "America/Toronto" in message
            assert "Current time" in message

    @pytest.mark.asyncio
    async def test_get_current_time_with_tool_config(self):
        """Test that tool_config parameter is accepted"""
        mock_context = Mock()
        mock_inv_context = Mock()
        mock_context._invocation_context = mock_inv_context
        
        tool_config = {"some_config": "value"}
        
        with patch('src.solace_agent_mesh.agent.tools.time_tools.get_user_timezone') as mock_get_tz:
            mock_get_tz.return_value = "UTC"
            
            result = await get_current_time(
                tool_context=mock_context,
                tool_config=tool_config
            )
            
            assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_get_current_time_exception_handling(self):
        """Test exception handling for unexpected errors"""
        mock_context = Mock()
        mock_inv_context = Mock()
        mock_context._invocation_context = mock_inv_context
        
        with patch('src.solace_agent_mesh.agent.tools.time_tools.get_user_timezone', side_effect=Exception("Unexpected error")):
            result = await get_current_time(tool_context=mock_context)
            
            assert result["status"] == "error"
            assert "unexpected error" in result["message"].lower()


class TestToolDefinition:
    """Tests for get_current_time_tool_def"""

    def test_tool_definition_exists(self):
        """Test that tool definition is properly defined"""
        assert get_current_time_tool_def is not None
        assert get_current_time_tool_def.name == "get_current_time"
        assert get_current_time_tool_def.implementation == get_current_time

    def test_tool_definition_category(self):
        """Test that tool has correct category"""
        assert get_current_time_tool_def.category == "time"
        assert get_current_time_tool_def.category_name == CATEGORY_NAME
        assert get_current_time_tool_def.category_description == CATEGORY_DESCRIPTION

    def test_tool_definition_description(self):
        """Test that tool has a description"""
        assert get_current_time_tool_def.description is not None
        assert len(get_current_time_tool_def.description) > 0
        assert "current" in get_current_time_tool_def.description.lower()
        assert "time" in get_current_time_tool_def.description.lower()

    def test_tool_definition_required_scopes(self):
        """Test that tool has required scopes"""
        assert get_current_time_tool_def.required_scopes is not None
        assert "tool:time:read" in get_current_time_tool_def.required_scopes

    def test_tool_definition_parameters(self):
        """Test that tool has parameters schema"""
        assert get_current_time_tool_def.parameters is not None
        assert get_current_time_tool_def.parameters.required == []


class TestConstants:
    """Tests for module constants"""

    def test_category_name(self):
        """Test CATEGORY_NAME constant"""
        assert CATEGORY_NAME == "Time & Date"

    def test_category_description(self):
        """Test CATEGORY_DESCRIPTION constant"""
        assert CATEGORY_DESCRIPTION is not None
        assert len(CATEGORY_DESCRIPTION) > 0
        assert "time" in CATEGORY_DESCRIPTION.lower()