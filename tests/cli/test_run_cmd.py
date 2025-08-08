import unittest
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from cli.commands.run_cmd import run


class TestRunCmd(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()
        self.project_root = Path.cwd()
        self.configs_dir = self.project_root / "configs"
        self.configs_dir.mkdir(exist_ok=True)

    def tearDown(self):
        if self.configs_dir.exists():
            for f in self.configs_dir.glob("*.yaml"):
                f.unlink()
            for f in self.configs_dir.glob("*.yml"):
                f.unlink()
            self.configs_dir.rmdir()

    @patch("cli.commands.run_cmd._execute_with_solace_ai_connector")
    def test_run_with_specific_files(self, mock_execute):
        """Test running the command with specific file paths."""
        mock_execute.return_value = 0
        with self.runner.isolated_filesystem():
            with open("test1.yaml", "w") as f:
                f.write("key: value1")
            with open("test2.yml", "w") as f:
                f.write("key: value2")

            result = self.runner.invoke(run, ["test1.yaml", "test2.yml"])
            self.assertEqual(result.exit_code, 0)
            mock_execute.assert_called_once()
            call_args = mock_execute.call_args[0][0]
            self.assertIn(str(Path("test1.yaml").resolve()), call_args)
            self.assertIn(str(Path("test2.yml").resolve()), call_args)

    @patch("cli.commands.run_cmd._execute_with_solace_ai_connector")
    def test_run_with_discovery(self, mock_execute):
        """Test running the command with file discovery."""
        mock_execute.return_value = 0
        with self.runner.isolated_filesystem():
            configs_dir = Path("configs")
            configs_dir.mkdir()
            (configs_dir / "test1.yaml").touch()
            (configs_dir / "test2.yml").touch()
            (configs_dir / "_hidden.yaml").touch()
            (configs_dir / "shared_config.yaml").touch()

            result = self.runner.invoke(run)
            self.assertEqual(result.exit_code, 0)
            mock_execute.assert_called_once()
            call_args = mock_execute.call_args[0][0]
            self.assertIn(str((configs_dir / "test1.yaml").resolve()), call_args)
            self.assertIn(str((configs_dir / "test2.yml").resolve()), call_args)
            self.assertNotIn(str((configs_dir / "_hidden.yaml").resolve()), call_args)
            self.assertNotIn(
                str((configs_dir / "shared_config.yaml").resolve()), call_args
            )

    @patch("cli.commands.run_cmd._execute_with_solace_ai_connector")
    def test_run_with_skip(self, mock_execute):
        """Test the --skip option."""
        mock_execute.return_value = 0
        with self.runner.isolated_filesystem():
            with open("test1.yaml", "w") as f:
                f.write("key: value1")
            with open("test2.yml", "w") as f:
                f.write("key: value2")

            result = self.runner.invoke(
                run, ["test1.yaml", "test2.yml", "--skip", "test1.yaml"]
            )
            self.assertEqual(result.exit_code, 0)
            mock_execute.assert_called_once()
            call_args = mock_execute.call_args[0][0]
            self.assertNotIn(str(Path("test1.yaml").resolve()), call_args)
            self.assertIn(str(Path("test2.yml").resolve()), call_args)

    @patch("cli.commands.run_cmd.load_dotenv")
    @patch("cli.commands.run_cmd._execute_with_solace_ai_connector")
    def test_run_with_system_env(self, mock_execute, mock_load_dotenv):
        """Test the --system-env option."""
        mock_execute.return_value = 0
        with self.runner.isolated_filesystem():
            with open("test1.yaml", "w") as f:
                f.write("key: value1")

            result = self.runner.invoke(run, ["test1.yaml", "--system-env"])
            self.assertEqual(result.exit_code, 0)
            mock_load_dotenv.assert_not_called()

    @patch("cli.commands.run_cmd._execute_with_solace_ai_connector")
    def test_run_no_configs_dir(self, mock_execute):
        """Test running with discovery when configs directory is missing."""
        with self.runner.isolated_filesystem():
            result = self.runner.invoke(run)
            self.assertNotEqual(result.exit_code, 0)
            self.assertIn("Error: Configuration directory ", result.output)
            self.assertIn(
                "not found. Please run 'init' first or provide specific config files.",
                result.output,
            )
            mock_execute.assert_not_called()

    @patch("cli.commands.run_cmd._execute_with_solace_ai_connector")
    def test_run_no_files_found(self, mock_execute):
        """Test running with discovery when no config files are found."""
        with self.runner.isolated_filesystem():
            configs_dir = Path("configs")
            configs_dir.mkdir()
            result = self.runner.invoke(run)
            self.assertEqual(result.exit_code, 0)
            self.assertIn(
                "No configuration files to run after filtering. Exiting.", result.output
            )
            mock_execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
