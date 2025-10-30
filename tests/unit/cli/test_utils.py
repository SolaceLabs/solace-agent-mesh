from pathlib import Path
from unittest.mock import MagicMock
import click
import pytest


@pytest.fixture
def mock_click_confirm(mocker):
    """Mock click.confirm for yes/no questions"""
    return mocker.patch("cli.utils.click.confirm")


@pytest.fixture
def mock_click_prompt(mocker):
    """Mock click.prompt for general questions"""
    return mocker.patch("cli.utils.click.prompt")


@pytest.fixture
def mock_click_echo(mocker):
    """Mock click.echo for output"""
    return mocker.patch("cli.utils.click.echo")


class TestAskYesNoQuestion:
    """Tests for ask_yes_no_question function"""

    def test_ask_yes_no_question_default_false(self, mock_click_confirm):
        """Test yes/no question with default False"""
        from cli.utils import ask_yes_no_question

        mock_click_confirm.return_value = False
        result = ask_yes_no_question("Continue?", default=False)

        assert result is False
        mock_click_confirm.assert_called_once_with("Continue?", default=False)

    def test_ask_yes_no_question_default_true(self, mock_click_confirm):
        """Test yes/no question with default True"""
        from cli.utils import ask_yes_no_question

        mock_click_confirm.return_value = True
        result = ask_yes_no_question("Proceed?", default=True)

        assert result is True
        mock_click_confirm.assert_called_once_with("Proceed?", default=True)

    def test_ask_yes_no_question_user_response(self, mock_click_confirm):
        """Test yes/no question with user response"""
        from cli.utils import ask_yes_no_question

        mock_click_confirm.return_value = True
        result = ask_yes_no_question("Are you sure?")

        assert result is True
        mock_click_confirm.assert_called_once_with("Are you sure?", default=False)


class TestAskQuestion:
    """Tests for ask_question function"""

    def test_ask_question_basic(self, mock_click_prompt):
        """Test basic question asking"""
        from cli.utils import ask_question

        mock_click_prompt.return_value = "test_answer"
        result = ask_question("What is your name?")

        assert result == "test_answer"
        mock_click_prompt.assert_called_once_with(
            "What is your name?",
            default=None,
            hide_input=False,
            type=None,
            show_choices=None,
        )

    def test_ask_question_with_default(self, mock_click_prompt):
        """Test question with default value"""
        from cli.utils import ask_question

        mock_click_prompt.return_value = "default_value"
        result = ask_question("Enter value:", default="default_value")

        assert result == "default_value"
        mock_click_prompt.assert_called_once_with(
            "Enter value:",
            default="default_value",
            hide_input=False,
            type=None,
            show_choices=None,
        )

    def test_ask_question_hide_input(self, mock_click_prompt):
        """Test question with hidden input (password)"""
        from cli.utils import ask_question

        mock_click_prompt.return_value = "secret"
        result = ask_question("Enter password:", hide_input=True)

        assert result == "secret"
        mock_click_prompt.assert_called_once_with(
            "Enter password:",
            default=None,
            hide_input=True,
            type=None,
            show_choices=None,
        )

    def test_ask_question_with_type(self, mock_click_prompt):
        """Test question with type parameter"""
        from cli.utils import ask_question

        mock_click_prompt.return_value = 42
        result = ask_question("Enter number:", type=int)

        assert result == 42
        mock_click_prompt.assert_called_once_with(
            "Enter number:",
            default=None,
            hide_input=False,
            type=int,
            show_choices=None,
        )

    def test_ask_question_with_show_choices(self, mock_click_prompt):
        """Test question with show_choices parameter"""
        from cli.utils import ask_question

        mock_click_prompt.return_value = "option1"
        result = ask_question("Select option:", show_choices=True)

        assert result == "option1"
        mock_click_prompt.assert_called_once_with(
            "Select option:",
            default=None,
            hide_input=False,
            type=None,
            show_choices=True,
        )


class TestAskIfNotProvided:
    """Tests for ask_if_not_provided function"""

    def test_key_exists_returns_value(self, mock_click_prompt):
        """Test when key exists in options, returns existing value"""
        from cli.utils import ask_if_not_provided

        options = {"name": "existing_value"}
        result = ask_if_not_provided(options, "name", "Enter name:")

        assert result == "existing_value"
        mock_click_prompt.assert_not_called()

    def test_key_missing_interactive_regular_question(self, mock_click_prompt):
        """Test when key is missing, asks question in interactive mode"""
        from cli.utils import ask_if_not_provided

        mock_click_prompt.return_value = "new_value"
        options = {}
        result = ask_if_not_provided(options, "name", "Enter name:")

        assert result == "new_value"
        assert options["name"] == "new_value"
        mock_click_prompt.assert_called_once()

    def test_key_missing_non_interactive_uses_default(self, mock_click_prompt):
        """Test when key is missing in non-interactive mode, uses default"""
        from cli.utils import ask_if_not_provided

        options = {}
        result = ask_if_not_provided(
            options, "name", "Enter name:", default="default_name", none_interactive=True
        )

        assert result == "default_name"
        assert options["name"] == "default_name"
        mock_click_prompt.assert_not_called()

    def test_key_missing_bool_question(self, mock_click_confirm):
        """Test when key is missing and is_bool=True"""
        from cli.utils import ask_if_not_provided

        mock_click_confirm.return_value = True
        options = {}
        result = ask_if_not_provided(
            options, "enabled", "Enable feature?", default=True, is_bool=True
        )

        assert result is True
        assert options["enabled"] is True
        mock_click_confirm.assert_called_once_with("Enable feature?", default=True)

    def test_key_missing_bool_question_default_false(self, mock_click_confirm):
        """Test bool question with non-bool default falls back to False"""
        from cli.utils import ask_if_not_provided

        mock_click_confirm.return_value = False
        options = {}
        result = ask_if_not_provided(
            options, "enabled", "Enable feature?", default="not_bool", is_bool=True
        )

        assert result is False
        assert options["enabled"] is False
        mock_click_confirm.assert_called_once_with("Enable feature?", default=False)

    def test_key_missing_with_choices(self, mock_click_prompt):
        """Test when key is missing with choices parameter"""
        from cli.utils import ask_if_not_provided

        mock_click_prompt.return_value = "option2"
        options = {}
        choices = ["option1", "option2", "option3"]
        result = ask_if_not_provided(
            options, "choice", "Select option:", choices=choices
        )

        assert result == "option2"
        assert options["choice"] == "option2"
        mock_click_prompt.assert_called_once()
        # Verify that click.Choice was used
        call_args = mock_click_prompt.call_args
        assert call_args[1]["show_choices"] is True

    def test_key_missing_with_hide_input(self, mock_click_prompt):
        """Test when key is missing with hide_input parameter"""
        from cli.utils import ask_if_not_provided

        mock_click_prompt.return_value = "secret"
        options = {}
        result = ask_if_not_provided(
            options, "password", "Enter password:", hide_input=True
        )

        assert result == "secret"
        assert options["password"] == "secret"
        mock_click_prompt.assert_called_once()
        call_args = mock_click_prompt.call_args
        assert call_args[1]["hide_input"] is True

    def test_key_none_value_asks_question(self, mock_click_prompt):
        """Test when key exists but value is None, asks question"""
        from cli.utils import ask_if_not_provided

        mock_click_prompt.return_value = "new_value"
        options = {"name": None}
        result = ask_if_not_provided(options, "name", "Enter name:")

        assert result == "new_value"
        assert options["name"] == "new_value"
        mock_click_prompt.assert_called_once()


class TestGetCliRootDir:
    """Tests for get_cli_root_dir function"""

    def test_get_cli_root_dir_returns_path(self):
        """Test that get_cli_root_dir returns a valid Path"""
        from cli.utils import get_cli_root_dir

        result = get_cli_root_dir()

        assert isinstance(result, Path)
        assert result.exists()

    def test_get_cli_root_dir_is_parent_of_cli(self):
        """Test that returned path is parent of cli directory"""
        from cli.utils import get_cli_root_dir

        result = get_cli_root_dir()
        cli_dir = result / "cli"

        assert cli_dir.exists()
        assert cli_dir.is_dir()


class TestLoadTemplate:
    """Tests for load_template function"""

    def test_load_template_success(self, tmp_path, mocker):
        """Test successful template loading"""
        from cli.utils import load_template

        # Mock get_cli_root_dir to return tmp_path
        mocker.patch("cli.utils.get_cli_root_dir", return_value=tmp_path)

        # Create a template file
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        template_file = templates_dir / "test_template.txt"
        template_file.write_text("Hello, World!")

        result = load_template("test_template.txt")

        assert result == "Hello, World!"

    def test_load_template_file_not_found(self, tmp_path, mocker):
        """Test FileNotFoundError when template doesn't exist"""
        from cli.utils import load_template

        mocker.patch("cli.utils.get_cli_root_dir", return_value=tmp_path)

        with pytest.raises(FileNotFoundError) as exc_info:
            load_template("nonexistent.txt")

        assert "does not exist" in str(exc_info.value)

    def test_load_template_with_parser(self, tmp_path, mocker):
        """Test template loading with parser function"""
        from cli.utils import load_template

        mocker.patch("cli.utils.get_cli_root_dir", return_value=tmp_path)

        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        template_file = templates_dir / "test_template.txt"
        template_file.write_text("hello world")

        def uppercase_parser(content, suffix):
            return content.upper() + suffix

        result = load_template("test_template.txt", uppercase_parser, "!!!")

        assert result == "HELLO WORLD!!!"

    def test_load_template_without_parser(self, tmp_path, mocker):
        """Test template loading without parser returns raw content"""
        from cli.utils import load_template

        mocker.patch("cli.utils.get_cli_root_dir", return_value=tmp_path)

        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        template_file = templates_dir / "test_template.txt"
        template_file.write_text("Raw content\nMultiple lines")

        result = load_template("test_template.txt")

        assert result == "Raw content\nMultiple lines"


class TestGetFormattedNames:
    """Tests for get_formatted_names function"""

    def test_get_formatted_names_camel_case(self):
        """Test formatting from camelCase"""
        from cli.utils import get_formatted_names

        result = get_formatted_names("myTestName")

        assert result["KEBAB_CASE_NAME"] == "my-test-name"
        assert result["PASCAL_CASE_NAME"] == "MyTestName"
        assert result["SNAKE_CASE_NAME"] == "my_test_name"
        assert result["SNAKE_UPPER_CASE_NAME"] == "MY_TEST_NAME"
        assert result["SPACED_NAME"] == "my test name"
        assert result["SPACED_CAPITALIZED_NAME"] == "My Test Name"

    def test_get_formatted_names_snake_case(self):
        """Test formatting from snake_case"""
        from cli.utils import get_formatted_names

        result = get_formatted_names("my_test_name")

        assert result["KEBAB_CASE_NAME"] == "my-test-name"
        assert result["PASCAL_CASE_NAME"] == "MyTestName"
        assert result["SNAKE_CASE_NAME"] == "my_test_name"
        assert result["SNAKE_UPPER_CASE_NAME"] == "MY_TEST_NAME"
        assert result["SPACED_NAME"] == "my test name"
        assert result["SPACED_CAPITALIZED_NAME"] == "My Test Name"

    def test_get_formatted_names_kebab_case(self):
        """Test formatting from kebab-case"""
        from cli.utils import get_formatted_names

        result = get_formatted_names("my-test-name")

        assert result["KEBAB_CASE_NAME"] == "my-test-name"
        assert result["PASCAL_CASE_NAME"] == "MyTestName"
        assert result["SNAKE_CASE_NAME"] == "my_test_name"
        assert result["SNAKE_UPPER_CASE_NAME"] == "MY_TEST_NAME"
        assert result["SPACED_NAME"] == "my test name"
        assert result["SPACED_CAPITALIZED_NAME"] == "My Test Name"

    def test_get_formatted_names_spaces(self):
        """Test formatting from spaced name"""
        from cli.utils import get_formatted_names

        result = get_formatted_names("my test name")

        assert result["KEBAB_CASE_NAME"] == "my-test-name"
        assert result["PASCAL_CASE_NAME"] == "MyTestName"
        assert result["SNAKE_CASE_NAME"] == "my_test_name"
        assert result["SNAKE_UPPER_CASE_NAME"] == "MY_TEST_NAME"
        assert result["SPACED_NAME"] == "my test name"
        assert result["SPACED_CAPITALIZED_NAME"] == "My Test Name"

    def test_get_formatted_names_acronym(self):
        """Test formatting with acronyms like API"""
        from cli.utils import get_formatted_names

        result = get_formatted_names("APIKey")

        assert result["KEBAB_CASE_NAME"] == "api-key"
        assert result["PASCAL_CASE_NAME"] == "ApiKey"
        assert result["SNAKE_CASE_NAME"] == "api_key"
        assert result["SNAKE_UPPER_CASE_NAME"] == "API_KEY"
        assert result["SPACED_NAME"] == "api key"
        assert result["SPACED_CAPITALIZED_NAME"] == "API Key"

    def test_get_formatted_names_all_caps_acronym(self):
        """Test formatting with all caps acronym"""
        from cli.utils import get_formatted_names

        result = get_formatted_names("API")

        assert result["KEBAB_CASE_NAME"] == "api"
        assert result["PASCAL_CASE_NAME"] == "Api"
        assert result["SNAKE_CASE_NAME"] == "api"
        assert result["SNAKE_UPPER_CASE_NAME"] == "API"
        assert result["SPACED_NAME"] == "api"
        assert result["SPACED_CAPITALIZED_NAME"] == "API"

    def test_get_formatted_names_mixed_separators(self):
        """Test formatting with mixed separators"""
        from cli.utils import get_formatted_names

        result = get_formatted_names("my-test_name")

        assert result["KEBAB_CASE_NAME"] == "my-test-name"
        assert result["PASCAL_CASE_NAME"] == "MyTestName"
        assert result["SNAKE_CASE_NAME"] == "my_test_name"

    def test_get_formatted_names_pascal_case(self):
        """Test formatting from PascalCase"""
        from cli.utils import get_formatted_names

        result = get_formatted_names("MyTestName")

        assert result["KEBAB_CASE_NAME"] == "my-test-name"
        assert result["PASCAL_CASE_NAME"] == "MyTestName"
        assert result["SNAKE_CASE_NAME"] == "my_test_name"
        assert result["SPACED_CAPITALIZED_NAME"] == "My Test Name"


class TestGetModulePath:
    """Tests for get_module_path function"""

    def test_get_module_path_valid_module(self, mocker):
        """Test getting path for a valid module"""
        from cli.utils import get_module_path

        mock_module = MagicMock()
        mock_module.__path__ = ["/path/to/module"]
        mock_import = mocker.patch("cli.utils.importlib.import_module", return_value=mock_module)

        result = get_module_path("test_module")

        assert result == "/path/to/module"
        mock_import.assert_called_once_with("test_module")


class TestErrorExit:
    """Tests for error_exit function"""

    def test_error_exit_with_message(self, mock_click_echo):
        """Test error_exit with a message"""
        from cli.utils import error_exit

        with pytest.raises(click.Abort):
            error_exit("Something went wrong")

        mock_click_echo.assert_called_once()
        call_args = mock_click_echo.call_args
        assert "Something went wrong" in str(call_args)
        assert call_args[1]["err"] is True

    def test_error_exit_without_message(self, mock_click_echo):
        """Test error_exit without a message"""
        from cli.utils import error_exit

        with pytest.raises(click.Abort):
            error_exit()

        mock_click_echo.assert_not_called()


class TestGetSamCliHomeDir:
    """Tests for get_sam_cli_home_dir function"""

    def test_get_sam_cli_home_dir_with_absolute_env_var(self, tmp_path, monkeypatch):
        """Test with SAM_CLI_HOME set to absolute path"""
        from cli.utils import get_sam_cli_home_dir

        sam_home = tmp_path / "sam_home"
        monkeypatch.setenv("SAM_CLI_HOME", str(sam_home))

        result = get_sam_cli_home_dir()

        assert result == sam_home.resolve()
        assert sam_home.exists()

    def test_get_sam_cli_home_dir_with_relative_env_var(self, tmp_path, monkeypatch):
        """Test with SAM_CLI_HOME set to relative path"""
        from cli.utils import get_sam_cli_home_dir

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("SAM_CLI_HOME", "relative/sam")

        result = get_sam_cli_home_dir()

        expected = (tmp_path / "relative" / "sam").resolve()
        assert result == expected
        assert result.exists()

    def test_get_sam_cli_home_dir_without_env_var(self, tmp_path, monkeypatch):
        """Test without SAM_CLI_HOME env var (uses default .sam)"""
        from cli.utils import get_sam_cli_home_dir

        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("SAM_CLI_HOME", raising=False)

        result = get_sam_cli_home_dir()

        expected = (tmp_path / ".sam").resolve()
        assert result == expected
        assert result.exists()

    def test_get_sam_cli_home_dir_creates_directory(self, tmp_path, monkeypatch):
        """Test that directory is created if it doesn't exist"""
        from cli.utils import get_sam_cli_home_dir

        sam_home = tmp_path / "new" / "sam" / "home"
        monkeypatch.setenv("SAM_CLI_HOME", str(sam_home))

        result = get_sam_cli_home_dir()

        assert result == sam_home.resolve()
        assert sam_home.exists()
        assert sam_home.is_dir()

    def test_get_sam_cli_home_dir_oserror_handling(self, tmp_path, monkeypatch, mocker):
        """Test OSError handling when directory creation fails"""
        from cli.utils import get_sam_cli_home_dir

        sam_home = tmp_path / "sam_home"
        monkeypatch.setenv("SAM_CLI_HOME", str(sam_home))

        mock_path = mocker.patch("cli.utils.Path")
        mock_instance = MagicMock()
        mock_instance.mkdir.side_effect = OSError("Permission denied")
        mock_path.return_value = mock_instance
        mock_path.cwd.return_value = tmp_path

        with pytest.raises(click.Abort):
            get_sam_cli_home_dir()


class TestIndentMultilineString:
    """Tests for indent_multiline_string function"""

    def test_indent_multiline_string_default_indent(self):
        """Test with default 4-space indent"""
        from cli.utils import indent_multiline_string

        text = "line1\nline2\nline3"
        result = indent_multiline_string(text)

        assert result == "line1\n    line2\n    line3"

    def test_indent_multiline_string_custom_indent(self):
        """Test with custom indent level"""
        from cli.utils import indent_multiline_string

        text = "line1\nline2"
        result = indent_multiline_string(text, indent=2)

        assert result == "line1\n  line2"

    def test_indent_multiline_string_with_initial_indent(self):
        """Test with initial_indent=True"""
        from cli.utils import indent_multiline_string

        text = "line1\nline2"
        result = indent_multiline_string(text, indent=4, initial_indent=True)

        assert result == "\n    line1\n    line2"

    def test_indent_multiline_string_single_line(self):
        """Test with single line"""
        from cli.utils import indent_multiline_string

        text = "single line"
        result = indent_multiline_string(text)

        assert result == "single line"


class TestWaitForServer:
    """Tests for wait_for_server function"""

    def test_wait_for_server_success(self, mocker):
        """Test successful server connection"""
        from cli.utils import wait_for_server

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get = mocker.patch("cli.utils.requests.get", return_value=mock_response)

        result = wait_for_server("http://localhost:8000", timeout=5)

        assert result is True
        mock_get.assert_called_with("http://localhost:8000")

    def test_wait_for_server_timeout(self, mocker):
        """Test server connection timeout"""
        from cli.utils import wait_for_server

        mock_get = mocker.patch("cli.utils.requests.get", side_effect=Exception("Connection refused"))
        mocker.patch("cli.utils.sleep")

        result = wait_for_server("http://localhost:8000", timeout=1)

        assert result is False
        assert mock_get.call_count >= 2


class TestCreateAndValidateDatabase:
    """Tests for create_and_validate_database function"""

    def test_create_and_validate_database_sqlite(self, tmp_path, mocker, mock_click_echo):
        """Test SQLite database creation and validation"""
        from cli.utils import create_and_validate_database

        db_file = tmp_path / "test.db"
        database_url = f"sqlite:///{db_file}"

        mock_engine = MagicMock()
        mock_connection = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = mock_connection
        mock_create_engine = mocker.patch("cli.utils.create_engine", return_value=mock_engine)
        mocker.patch("cli.utils.event")

        result = create_and_validate_database(database_url, "test_db")

        assert result is True
        mock_create_engine.assert_called_once_with(database_url)
        mock_engine.dispose.assert_called_once()
        assert db_file.parent.exists()

    def test_create_and_validate_database_postgresql_with_psycopg2(self, mocker, mock_click_echo):
        """Test PostgreSQL database with psycopg2 available"""
        from cli.utils import create_and_validate_database

        database_url = "postgresql://user:pass@localhost/db"

        mock_engine = MagicMock()
        mock_connection = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = mock_connection
        mock_create_engine = mocker.patch("cli.utils.create_engine", return_value=mock_engine)
        mocker.patch.dict("sys.modules", {"psycopg2": MagicMock()})

        result = create_and_validate_database(database_url, "postgres_db")

        assert result is True
        mock_create_engine.assert_called_once_with(database_url)
        mock_engine.dispose.assert_called_once()

    def test_create_and_validate_database_postgresql_without_psycopg2(self, mocker, mock_click_echo):
        """Test PostgreSQL database without psycopg2 raises ValueError"""
        from cli.utils import create_and_validate_database

        database_url = "postgresql://user:pass@localhost/db"

        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "psycopg2":
                raise ImportError("No module named psycopg2")
            return real_import(name, *args, **kwargs)

        mocker.patch("builtins.__import__", side_effect=mock_import)

        with pytest.raises(ValueError) as exc_info:
            create_and_validate_database(database_url, "postgres_db")

        assert "psycopg2" in str(exc_info.value)

    def test_create_and_validate_database_generic(self, mocker, mock_click_echo):
        """Test generic database URL"""
        from cli.utils import create_and_validate_database

        database_url = "mysql://user:pass@localhost/db"

        mock_engine = MagicMock()
        mock_connection = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = mock_connection
        mock_create_engine = mocker.patch("cli.utils.create_engine", return_value=mock_engine)

        result = create_and_validate_database(database_url, "mysql_db")

        assert result is True
        mock_create_engine.assert_called_once_with(database_url)
        mock_engine.dispose.assert_called_once()

    def test_create_and_validate_database_connection_failure(self, mocker, mock_click_echo):
        """Test database connection failure"""
        from cli.utils import create_and_validate_database

        database_url = "sqlite:///test.db"

        mock_engine = MagicMock()
        mock_engine.connect.side_effect = Exception("Connection failed")
        mocker.patch("cli.utils.create_engine", return_value=mock_engine)
        mocker.patch("cli.utils.event")

        with pytest.raises(ValueError) as exc_info:
            create_and_validate_database(database_url, "test_db")

        assert "Connection failed" in str(exc_info.value)
