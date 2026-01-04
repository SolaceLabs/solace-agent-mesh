"""
Unit tests for src/solace_agent_mesh/agent/skills/loader.py

Tests the skill loading functionality including:
- YAML frontmatter parsing
- Skill metadata extraction
- Directory scanning for skills
- Skill catalog instruction generation
"""

import os
import tempfile
from pathlib import Path

import pytest

from src.solace_agent_mesh.agent.skills.loader import (
    parse_yaml_frontmatter,
    extract_skill_metadata,
    scan_skill_directories,
    generate_skill_catalog_instructions,
)
from src.solace_agent_mesh.agent.skills.types import SkillCatalogEntry


class TestParseYamlFrontmatter:
    """Tests for parse_yaml_frontmatter function"""

    def test_valid_frontmatter(self):
        """Test parsing valid YAML frontmatter"""
        content = """---
name: test-skill
description: A test skill for unit testing
allowed-tools: tool1, tool2
---

# Test Skill

This is the body content.
"""
        metadata, body = parse_yaml_frontmatter(content)

        assert metadata is not None
        assert metadata["name"] == "test-skill"
        assert metadata["description"] == "A test skill for unit testing"
        assert metadata["allowed-tools"] == "tool1, tool2"
        assert "# Test Skill" in body
        assert "This is the body content." in body

    def test_no_frontmatter(self):
        """Test content without frontmatter returns None metadata"""
        content = """# Test Skill

This is just markdown without frontmatter.
"""
        metadata, body = parse_yaml_frontmatter(content)

        assert metadata is None
        assert "# Test Skill" in body

    def test_unclosed_frontmatter(self):
        """Test unclosed frontmatter returns None metadata"""
        content = """---
name: test-skill
description: Missing closing delimiter

# Body content
"""
        metadata, body = parse_yaml_frontmatter(content)

        assert metadata is None

    def test_empty_frontmatter(self):
        """Test empty frontmatter returns None"""
        content = """---
---

# Body content
"""
        metadata, body = parse_yaml_frontmatter(content)

        # Empty YAML returns None
        assert metadata is None

    def test_frontmatter_with_complex_values(self):
        """Test frontmatter with complex YAML values"""
        content = """---
name: complex-skill
description: |
  A multi-line
  description
allowed-tools: tool1, tool2, tool3
extra_field: some_value
---

# Complex Skill
"""
        metadata, body = parse_yaml_frontmatter(content)

        assert metadata is not None
        assert metadata["name"] == "complex-skill"
        assert "multi-line" in metadata["description"]
        assert metadata["extra_field"] == "some_value"

    def test_frontmatter_preserves_body(self):
        """Test that body content is preserved correctly after frontmatter"""
        content = """---
name: test
description: test
---

## Section 1

Content here.

## Section 2

More content.
"""
        metadata, body = parse_yaml_frontmatter(content)

        assert metadata is not None
        assert "## Section 1" in body
        assert "## Section 2" in body
        assert "Content here." in body
        assert "More content." in body


class TestExtractSkillMetadata:
    """Tests for extract_skill_metadata function"""

    def test_valid_skill_directory(self, tmp_path):
        """Test extracting metadata from a valid skill directory"""
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()

        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text("""---
name: my-skill
description: A skill for doing things
---

# My Skill Instructions
""")

        entry = extract_skill_metadata(str(skill_dir))

        assert entry is not None
        assert entry.name == "my-skill"
        assert entry.description == "A skill for doing things"
        assert entry.path == str(skill_dir)
        assert entry.has_sam_tools is False

    def test_skill_with_sam_tools(self, tmp_path):
        """Test that has_sam_tools is True when skill.sam.yaml exists"""
        skill_dir = tmp_path / "tool-skill"
        skill_dir.mkdir()

        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text("""---
name: tool-skill
description: A skill with tools
---

# Tool Skill
""")

        sam_yaml = skill_dir / "skill.sam.yaml"
        sam_yaml.write_text("""
tools:
  - name: my_tool
    description: A tool
""")

        entry = extract_skill_metadata(str(skill_dir))

        assert entry is not None
        assert entry.has_sam_tools is True

    def test_skill_with_allowed_tools_string(self, tmp_path):
        """Test parsing allowed-tools as comma-separated string"""
        skill_dir = tmp_path / "allowed-skill"
        skill_dir.mkdir()

        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text("""---
name: allowed-skill
description: Skill with allowed tools
allowed-tools: tool1, tool2, tool3
---

# Skill
""")

        entry = extract_skill_metadata(str(skill_dir))

        assert entry is not None
        assert entry.allowed_tools == ["tool1", "tool2", "tool3"]

    def test_skill_with_allowed_tools_list(self, tmp_path):
        """Test parsing allowed-tools as YAML list"""
        skill_dir = tmp_path / "list-skill"
        skill_dir.mkdir()

        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text("""---
name: list-skill
description: Skill with list tools
allowed-tools:
  - tool1
  - tool2
---

# Skill
""")

        entry = extract_skill_metadata(str(skill_dir))

        assert entry is not None
        assert entry.allowed_tools == ["tool1", "tool2"]

    def test_missing_skill_md(self, tmp_path):
        """Test that missing SKILL.md returns None"""
        skill_dir = tmp_path / "empty-skill"
        skill_dir.mkdir()

        entry = extract_skill_metadata(str(skill_dir))

        assert entry is None

    def test_missing_name_field(self, tmp_path):
        """Test that missing name field returns None"""
        skill_dir = tmp_path / "no-name-skill"
        skill_dir.mkdir()

        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text("""---
description: Skill without name
---

# Skill
""")

        entry = extract_skill_metadata(str(skill_dir))

        assert entry is None

    def test_missing_description_field(self, tmp_path):
        """Test that missing description field returns None"""
        skill_dir = tmp_path / "no-desc-skill"
        skill_dir.mkdir()

        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text("""---
name: no-desc-skill
---

# Skill
""")

        entry = extract_skill_metadata(str(skill_dir))

        assert entry is None

    def test_no_frontmatter(self, tmp_path):
        """Test that SKILL.md without frontmatter returns None"""
        skill_dir = tmp_path / "no-frontmatter"
        skill_dir.mkdir()

        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text("""# Skill Without Frontmatter

Just markdown content.
""")

        entry = extract_skill_metadata(str(skill_dir))

        assert entry is None


class TestScanSkillDirectories:
    """Tests for scan_skill_directories function"""

    def test_scan_single_skill(self, tmp_path):
        """Test scanning a directory with a single skill"""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        skill1 = skills_dir / "skill1"
        skill1.mkdir()
        (skill1 / "SKILL.md").write_text("""---
name: skill1
description: First skill
---

# Skill 1
""")

        catalog = scan_skill_directories([str(skills_dir)])

        assert len(catalog) == 1
        assert "skill1" in catalog
        assert catalog["skill1"].description == "First skill"

    def test_scan_multiple_skills(self, tmp_path):
        """Test scanning a directory with multiple skills"""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        for i in range(3):
            skill = skills_dir / f"skill{i}"
            skill.mkdir()
            (skill / "SKILL.md").write_text(f"""---
name: skill{i}
description: Skill number {i}
---

# Skill {i}
""")

        catalog = scan_skill_directories([str(skills_dir)])

        assert len(catalog) == 3
        assert "skill0" in catalog
        assert "skill1" in catalog
        assert "skill2" in catalog

    def test_scan_multiple_paths(self, tmp_path):
        """Test scanning multiple directory paths"""
        path1 = tmp_path / "path1"
        path1.mkdir()
        skill1 = path1 / "skill-a"
        skill1.mkdir()
        (skill1 / "SKILL.md").write_text("""---
name: skill-a
description: Skill A
---
""")

        path2 = tmp_path / "path2"
        path2.mkdir()
        skill2 = path2 / "skill-b"
        skill2.mkdir()
        (skill2 / "SKILL.md").write_text("""---
name: skill-b
description: Skill B
---
""")

        catalog = scan_skill_directories([str(path1), str(path2)])

        assert len(catalog) == 2
        assert "skill-a" in catalog
        assert "skill-b" in catalog

    def test_scan_nested_skills_auto_discover(self, tmp_path):
        """Test recursive scanning finds nested skills"""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        nested = skills_dir / "category" / "subcategory"
        nested.mkdir(parents=True)

        skill = nested / "nested-skill"
        skill.mkdir()
        (skill / "SKILL.md").write_text("""---
name: nested-skill
description: A nested skill
---
""")

        catalog = scan_skill_directories([str(skills_dir)], auto_discover=True)

        assert len(catalog) == 1
        assert "nested-skill" in catalog

    def test_scan_no_auto_discover(self, tmp_path):
        """Test non-recursive scanning only finds immediate subdirectories"""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        # Immediate child
        immediate = skills_dir / "immediate-skill"
        immediate.mkdir()
        (immediate / "SKILL.md").write_text("""---
name: immediate-skill
description: Immediate skill
---
""")

        # Nested child
        nested = skills_dir / "nested" / "nested-skill"
        nested.mkdir(parents=True)
        (nested / "SKILL.md").write_text("""---
name: nested-skill
description: Nested skill
---
""")

        catalog = scan_skill_directories([str(skills_dir)], auto_discover=False)

        assert len(catalog) == 1
        assert "immediate-skill" in catalog
        assert "nested-skill" not in catalog

    def test_scan_relative_path_with_base(self, tmp_path):
        """Test resolving relative paths with base_path"""
        base = tmp_path / "project"
        base.mkdir()

        skills_dir = base / "skills"
        skills_dir.mkdir()

        skill = skills_dir / "rel-skill"
        skill.mkdir()
        (skill / "SKILL.md").write_text("""---
name: rel-skill
description: Relative skill
---
""")

        catalog = scan_skill_directories(["./skills"], base_path=str(base))

        assert len(catalog) == 1
        assert "rel-skill" in catalog

    def test_scan_nonexistent_path(self, tmp_path):
        """Test that nonexistent paths are skipped gracefully"""
        catalog = scan_skill_directories(["/nonexistent/path"])

        assert len(catalog) == 0

    def test_scan_duplicate_skill_names(self, tmp_path):
        """Test that duplicate skill names use first occurrence"""
        path1 = tmp_path / "path1"
        path1.mkdir()
        skill1 = path1 / "dupe"
        skill1.mkdir()
        (skill1 / "SKILL.md").write_text("""---
name: duplicate-skill
description: First occurrence
---
""")

        path2 = tmp_path / "path2"
        path2.mkdir()
        skill2 = path2 / "dupe2"
        skill2.mkdir()
        (skill2 / "SKILL.md").write_text("""---
name: duplicate-skill
description: Second occurrence
---
""")

        catalog = scan_skill_directories([str(path1), str(path2)])

        assert len(catalog) == 1
        assert catalog["duplicate-skill"].description == "First occurrence"

    def test_scan_empty_directory(self, tmp_path):
        """Test scanning empty directory returns empty catalog"""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        catalog = scan_skill_directories([str(empty_dir)])

        assert len(catalog) == 0


class TestGenerateSkillCatalogInstructions:
    """Tests for generate_skill_catalog_instructions function"""

    def test_empty_catalog(self):
        """Test that empty catalog returns empty string"""
        result = generate_skill_catalog_instructions({})

        assert result == ""

    def test_single_skill(self):
        """Test generating instructions for a single skill"""
        catalog = {
            "test-skill": SkillCatalogEntry(
                name="test-skill",
                description="A test skill for testing",
                path="/path/to/skill",
            )
        }

        result = generate_skill_catalog_instructions(catalog)

        assert "## Available Skills" in result
        assert "activate_skill" in result
        assert "### `test-skill`" in result
        assert "A test skill for testing" in result

    def test_multiple_skills_sorted(self):
        """Test that skills are sorted alphabetically"""
        catalog = {
            "zebra-skill": SkillCatalogEntry(
                name="zebra-skill",
                description="Z skill",
                path="/path",
            ),
            "alpha-skill": SkillCatalogEntry(
                name="alpha-skill",
                description="A skill",
                path="/path",
            ),
            "middle-skill": SkillCatalogEntry(
                name="middle-skill",
                description="M skill",
                path="/path",
            ),
        }

        result = generate_skill_catalog_instructions(catalog)

        # Check ordering - alpha should come before middle, middle before zebra
        alpha_pos = result.index("alpha-skill")
        middle_pos = result.index("middle-skill")
        zebra_pos = result.index("zebra-skill")

        assert alpha_pos < middle_pos < zebra_pos

    def test_instructions_contain_activation_guidance(self):
        """Test that instructions explain how to activate skills"""
        catalog = {
            "any-skill": SkillCatalogEntry(
                name="any-skill",
                description="Any skill",
                path="/path",
            )
        }

        result = generate_skill_catalog_instructions(catalog)

        assert "activate_skill" in result
        assert "skill_name" in result or "context" in result.lower()


class TestParseSamToolsYaml:
    """Tests for parse_sam_tools_yaml function"""

    def test_parses_valid_tools_yaml(self, tmp_path):
        """Test parsing a valid skill.sam.yaml with tools"""
        from unittest.mock import Mock
        from src.solace_agent_mesh.agent.skills.loader import parse_sam_tools_yaml

        sam_yaml = tmp_path / "skill.sam.yaml"
        sam_yaml.write_text("""
tools:
  - tool_type: python
    component_module: tests.integration.test_support.tools
    function_name: echo_tool
    name: echo_tool
    description: Echoes a message
    parameters:
      properties:
        message:
          type: string
          description: Message to echo
      required:
        - message
""")

        mock_component = Mock()
        mock_component.log_identifier = "[Test]"

        tools, declarations = parse_sam_tools_yaml(
            str(sam_yaml), "test-skill", mock_component
        )

        assert len(tools) == 1
        assert len(declarations) == 1
        assert tools[0].name == "echo_tool_test-skill"
        assert declarations[0].name == "echo_tool_test-skill"

    def test_empty_tools_section(self, tmp_path):
        """Test parsing a YAML with empty tools section"""
        from unittest.mock import Mock
        from src.solace_agent_mesh.agent.skills.loader import parse_sam_tools_yaml

        sam_yaml = tmp_path / "skill.sam.yaml"
        sam_yaml.write_text("""
tools: []
""")

        mock_component = Mock()
        mock_component.log_identifier = "[Test]"

        tools, declarations = parse_sam_tools_yaml(
            str(sam_yaml), "test-skill", mock_component
        )

        assert len(tools) == 0
        assert len(declarations) == 0

    def test_no_tools_key(self, tmp_path):
        """Test parsing a YAML without tools key"""
        from unittest.mock import Mock
        from src.solace_agent_mesh.agent.skills.loader import parse_sam_tools_yaml

        sam_yaml = tmp_path / "skill.sam.yaml"
        sam_yaml.write_text("""
other_config: value
""")

        mock_component = Mock()
        mock_component.log_identifier = "[Test]"

        tools, declarations = parse_sam_tools_yaml(
            str(sam_yaml), "test-skill", mock_component
        )

        assert len(tools) == 0
        assert len(declarations) == 0

    def test_skips_invalid_tool_configs(self, tmp_path):
        """Test that invalid tool configs are skipped gracefully"""
        from unittest.mock import Mock
        from src.solace_agent_mesh.agent.skills.loader import parse_sam_tools_yaml

        sam_yaml = tmp_path / "skill.sam.yaml"
        sam_yaml.write_text("""
tools:
  - tool_type: python
    component_module: tests.integration.test_support.tools
    function_name: echo_tool
    name: valid_tool
    description: Valid tool
  - tool_type: python
    name: invalid_tool
    description: Missing module and function
  - tool_type: python
    component_module: tests.integration.test_support.tools
    function_name: nonexistent_function
    name: missing_func
    description: Function doesn't exist
""")

        mock_component = Mock()
        mock_component.log_identifier = "[Test]"

        tools, declarations = parse_sam_tools_yaml(
            str(sam_yaml), "test-skill", mock_component
        )

        # Only the valid tool should be loaded
        assert len(tools) == 1
        assert tools[0].name == "valid_tool_test-skill"


class TestLoadFullSkill:
    """Tests for load_full_skill function"""

    def test_loads_skill_with_sam_tools(self, tmp_path):
        """Test loading a full skill that has SAM tools"""
        from unittest.mock import Mock
        from src.solace_agent_mesh.agent.skills.loader import load_full_skill
        from src.solace_agent_mesh.agent.skills.types import SkillCatalogEntry

        skill_dir = tmp_path / "tool-skill"
        skill_dir.mkdir()

        (skill_dir / "SKILL.md").write_text("""---
name: tool-skill
description: Skill with tools
---

# Tool Skill

Use the tool to do things.
""")

        (skill_dir / "skill.sam.yaml").write_text("""
tools:
  - tool_type: python
    component_module: tests.integration.test_support.tools
    function_name: echo_tool
    name: echo
    description: Echoes messages
    parameters:
      properties:
        message:
          type: string
          description: Message
      required:
        - message
""")

        catalog_entry = SkillCatalogEntry(
            name="tool-skill",
            description="Skill with tools",
            path=str(skill_dir),
            has_sam_tools=True,
        )

        mock_component = Mock()
        mock_component.log_identifier = "[Test]"

        activated = load_full_skill(catalog_entry, mock_component)

        assert activated.name == "tool-skill"
        assert "# Tool Skill" in activated.full_content
        assert len(activated.tools) == 1
        assert len(activated.tool_declarations) == 1
        assert activated.tools[0].name == "echo_tool-skill"

    def test_loads_skill_without_sam_tools(self, tmp_path):
        """Test loading a full skill without SAM tools"""
        from unittest.mock import Mock
        from src.solace_agent_mesh.agent.skills.loader import load_full_skill
        from src.solace_agent_mesh.agent.skills.types import SkillCatalogEntry

        skill_dir = tmp_path / "basic-skill"
        skill_dir.mkdir()

        (skill_dir / "SKILL.md").write_text("""---
name: basic-skill
description: Basic skill
---

# Basic Skill

Instructions here.
""")

        catalog_entry = SkillCatalogEntry(
            name="basic-skill",
            description="Basic skill",
            path=str(skill_dir),
            has_sam_tools=False,
        )

        mock_component = Mock()
        mock_component.log_identifier = "[Test]"

        activated = load_full_skill(catalog_entry, mock_component)

        assert activated.name == "basic-skill"
        assert "# Basic Skill" in activated.full_content
        assert len(activated.tools) == 0
        assert len(activated.tool_declarations) == 0

    def test_full_content_strips_frontmatter(self, tmp_path):
        """Test that full_content contains body without frontmatter"""
        from unittest.mock import Mock
        from src.solace_agent_mesh.agent.skills.loader import load_full_skill
        from src.solace_agent_mesh.agent.skills.types import SkillCatalogEntry

        skill_dir = tmp_path / "strip-test"
        skill_dir.mkdir()

        (skill_dir / "SKILL.md").write_text("""---
name: strip-test
description: Test frontmatter stripping
allowed-tools: tool1, tool2
---

# Actual Content

This should be in full_content.
The frontmatter should not be.
""")

        catalog_entry = SkillCatalogEntry(
            name="strip-test",
            description="Test",
            path=str(skill_dir),
            has_sam_tools=False,
        )

        mock_component = Mock()
        mock_component.log_identifier = "[Test]"

        activated = load_full_skill(catalog_entry, mock_component)

        assert "# Actual Content" in activated.full_content
        assert "This should be in full_content" in activated.full_content
        # Frontmatter should not appear in full_content
        assert "name: strip-test" not in activated.full_content
        assert "allowed-tools:" not in activated.full_content
