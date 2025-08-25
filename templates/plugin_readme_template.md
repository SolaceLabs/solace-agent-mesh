# __PLUGIN_KEBAB_CASE_NAME__ SAM Plugin

__PLUGIN_DESCRIPTION__

This is a plugin for Solace Agent Mesh (SAM).

## Configuration (`config.yaml`)

The `config.yaml` in this plugin serves as a template. When you use `sam plugin add <component_name> --plugin __PLUGIN_KEBAB_CASE_NAME__`, the following placeholders in the YAML structure will be replaced with variations of `<component_name>`:
- `__COMPONENT_UPPER_SNAKE_CASE_NAME__`
- `__COMPONENT_KEBAB_CASE_NAME__`
- `__COMPONENT_PASCAL_CASE_NAME__`

Customize the `config.yaml` in this plugin directory to define the base configuration for components created from it.

## Source Code (`src/`)
The `src/` directory contains the Python source code for your plugin.

## Installation (as a developer of this plugin)

To build and install this plugin locally for testing:
```bash
sam plugin build
pip install dist/*.whl 
```
(Or `pip install .` if preferred, `sam plugin build` is for creating the distributable wheel)

## Usage (as a user of this plugin)

Once the plugin is installed (e.g., from PyPI or a local wheel file):
```bash
sam plugin add <your-new-component-name> --plugin __PLUGIN_KEBAB_CASE_NAME__
```
This will create a new component configuration at `configs/plugins/<your-new-component-name-kebab-case>.yaml`.