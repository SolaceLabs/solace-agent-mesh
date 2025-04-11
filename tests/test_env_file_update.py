import os
import tempfile
import unittest
from cli.commands.init.create_other_project_files_step import update_or_add_pairs_to_file


class TestEnvFileUpdate(unittest.TestCase):
    def setUp(self):
        # Create a temporary file for testing
        self.temp_file = tempfile.NamedTemporaryFile(delete=False)
        self.temp_file.close()

    def tearDown(self):
        # Clean up the temporary file
        if os.path.exists(self.temp_file.name):
            os.unlink(self.temp_file.name)

    def test_update_or_add_pairs_to_file_empty_file(self):
        """Test updating an empty file."""
        pairs = [
            ("KEY1", "=value1"),
            ("KEY2", "=value2"),
        ]
        update_or_add_pairs_to_file(self.temp_file.name, pairs)

        with open(self.temp_file.name, "r") as f:
            content = f.read()

        self.assertIn("KEY1=value1", content)
        self.assertIn("KEY2=value2", content)

    def test_update_or_add_pairs_to_file_existing_keys(self):
        """Test updating existing keys in a file."""
        # Create a file with existing keys
        with open(self.temp_file.name, "w") as f:
            f.write("KEY1=old_value1\n")
            f.write("KEY2=old_value2\n")
            f.write("KEY3=value3\n")

        pairs = [
            ("KEY1", "=new_value1"),
            ("KEY2", "=new_value2"),
            ("KEY4", "=value4"),
        ]
        update_or_add_pairs_to_file(self.temp_file.name, pairs)

        with open(self.temp_file.name, "r") as f:
            content = f.read()

        # Check that keys were updated
        self.assertIn("KEY1=new_value1", content)
        self.assertIn("KEY2=new_value2", content)
        # Check that untouched keys remain
        self.assertIn("KEY3=value3", content)
        # Check that new keys were added
        self.assertIn("KEY4=value4", content)
        # Check that old values are gone
        self.assertNotIn("old_value1", content)
        self.assertNotIn("old_value2", content)

    def test_update_or_add_pairs_to_file_with_comments(self):
        """Test updating a file with comments."""
        # Create a file with comments and existing keys
        with open(self.temp_file.name, "w") as f:
            f.write("# This is a comment\n")
            f.write("KEY1=old_value1\n")
            f.write("\n")  # Empty line
            f.write("# Another comment\n")
            f.write("KEY2=old_value2\n")

        pairs = [
            ("KEY1", "=new_value1"),
            ("KEY3", "=value3"),
        ]
        update_or_add_pairs_to_file(self.temp_file.name, pairs)

        with open(self.temp_file.name, "r") as f:
            content = f.read()

        # Check that comments are preserved
        self.assertIn("# This is a comment", content)
        self.assertIn("# Another comment", content)
        # Check that keys were updated
        self.assertIn("KEY1=new_value1", content)
        # Check that untouched keys remain
        self.assertIn("KEY2=old_value2", content)
        # Check that new keys were added
        self.assertIn("KEY3=value3", content)


if __name__ == "__main__":
    unittest.main()