from solace_ai_connector.components import timer_input

import importlib
import pkgutil

importlib.import_module("solace_ai_connector.components.general")


def import_submodules(package_name):
    package = importlib.import_module(package_name)

    for loader, module_name, is_pkg in pkgutil.walk_packages(package.__path__):
        if is_pkg:
            import_submodules(package_name + "." + module_name)
        else:
            importlib.import_module(package_name + "." + module_name)


def import_submodule(package_name, submodule_name, max_depth=3, current_depth=0):
    """Import a submodule from a package with error handling and depth limiting."""
    if current_depth >= max_depth:
        return  # Limit recursion depth
    
    try:
        package = importlib.import_module(package_name)
    except ImportError as e:
        print(f"Error importing {package_name}: {e}")
        return
    
    try:
        for loader, module_name, is_pkg in pkgutil.walk_packages(package.__path__):
            print(f"package_name: {package_name}, module_name: {module_name}")
            full_module_name = package_name + "." + module_name
            print(f"full_module_name: {full_module_name}, is_pkg: {is_pkg}")
            if is_pkg:
                import_submodule(full_module_name, submodule_name, max_depth, current_depth + 1)
            # elif full_module_name == submodule_name:
            #     importlib.import_module(full_module_name)
    except Exception as e:
        print(f"Error walking packages in {package_name}: {e}")


import_submodule(
    "solace_ai_connector.components", "solace_ai_connector.components.timer_input"
)

# module = importlib.import_module(
#     "solace_ai_connector.components.inputs_outputs.timer_input"
# )
# print(module)

# import_submodules('solace_ai_connector.components')

# module = importlib.import_module("solace_ai_connector.components.timer_input")
# print(module)
# print(timer_input)
