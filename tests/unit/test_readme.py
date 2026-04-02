from pathlib import Path


def test_readme_includes_local_development_section():
    readme = Path(__file__).resolve().parents[2] / "README.md"
    content = readme.read_text(encoding="utf-8")

    assert "### 🛠️ Developing Locally" in content
    assert "git clone https://github.com/SolaceLabs/solace-agent-mesh.git" in content
    assert "pip install -e .[test]" in content
    assert "sam run" in content
    assert "pytest" in content
