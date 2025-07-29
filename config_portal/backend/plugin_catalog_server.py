from flask import Flask, jsonify, request, send_from_directory
import os
import shutil
import logging
from pathlib import Path

from .plugin_catalog.scraper import PluginScraper
from .plugin_catalog.registry_manager import RegistryManager
from .plugin_catalog.constants import PLUGIN_CATALOG_TEMP_DIR

logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

registry_manager = RegistryManager()
plugin_scraper = PluginScraper()


def create_plugin_catalog_app(shared_config=None):
    current_dir = Path(__file__).parent
    static_folder_path = (
        Path(__file__).resolve().parent.parent / "frontend" / "static" / "client"
    )
    app = Flask(__name__, static_folder=str(static_folder_path), static_url_path="")
    app.config["SHARED_CONFIG"] = shared_config

    logger.info("Performing initial plugin scrape on startup...")
    try:
        initial_registries = registry_manager.get_all_registries()
        plugin_scraper.get_all_plugins(initial_registries, force_refresh=True)
        logger.info(
            f"Initial scrape complete. Found {len(plugin_scraper.plugin_cache)} plugins."
        )
    except Exception as e:
        logger.error(f"Error during initial plugin scrape: {e}", exc_info=True)

    @app.route("/")
    def serve_index():
        return send_from_directory(app.static_folder, "index.html")

    @app.route("/assets/<path:filename>")
    def serve_assets(filename):
        assets_dir = Path(app.static_folder) / "assets"
        return send_from_directory(str(assets_dir), filename)

    @app.route("/api/plugin_catalog/plugins", methods=["GET"])
    def get_plugins_api():
        search_query = request.args.get("search", "").lower()

        if not plugin_scraper.is_cache_populated:
            logger.info(
                "Plugin cache not populated, attempting to refresh for /api/plugin_catalog/plugins request."
            )
            all_regs = registry_manager.get_all_registries()
            plugin_scraper.get_all_plugins(all_regs, force_refresh=True)

        plugins_to_filter = plugin_scraper.plugin_cache

        if search_query:
            plugins_to_filter = [
                p
                for p in plugins_to_filter
                if search_query in p.pyproject.name.lower()
                or (
                    p.pyproject.description
                    and search_query in p.pyproject.description.lower()
                )
            ]
        return jsonify([p.model_dump(exclude_none=True) for p in plugins_to_filter])

    @app.route("/api/plugin_catalog/plugins/<plugin_id>/details", methods=["GET"])
    def get_plugin_details_api(plugin_id: str):
        details = plugin_scraper.get_plugin_details(plugin_id)
        if details:
            return jsonify(details.model_dump(exclude_none=True))
        return jsonify({"error": "Plugin not found", "status": "failure"}), 404

    @app.route("/api/plugin_catalog/plugins/install", methods=["POST"])
    def install_plugin_api():
        data = request.json
        if not data:
            return (
                jsonify({"error": "Request body must be JSON", "status": "failure"}),
                400,
            )

        plugin_id = data.get("pluginId")
        component_name = data.get("componentName")

        if not plugin_id or not component_name:
            return (
                jsonify(
                    {
                        "error": "pluginId and componentName are required",
                        "status": "failure",
                    }
                ),
                400,
            )

        plugin_info = plugin_scraper.get_plugin_details(plugin_id)
        if not plugin_info:
            return (
                jsonify({"error": "Plugin not found to install", "status": "failure"}),
                404,
            )

        success, message = plugin_scraper.install_plugin_cli(
            plugin_info, component_name
        )
        if success:
            return jsonify({"message": message, "status": "success"})
        else:
            return jsonify({"error": message, "status": "failure"}), 500

    @app.route("/api/plugin_catalog/registries", methods=["GET"])
    def get_registries_api():
        registries = registry_manager.get_all_registries()
        return jsonify([r.model_dump(exclude_none=True) for r in registries])

    @app.route("/api/plugin_catalog/registries", methods=["POST"])
    def add_registry_api():
        data = request.json
        if not data:
            return (
                jsonify({"error": "Request body must be JSON", "status": "failure"}),
                400,
            )

        path_or_url = data.get("path_or_url")
        name = data.get("name")

        if not path_or_url:
            return (
                jsonify({"error": "path_or_url is required", "status": "failure"}),
                400,
            )

        if registry_manager.add_registry(path_or_url, name=name):
            logger.info(
                f"Registry '{path_or_url}' (Name: {name if name else 'N/A'}) added by user. Refreshing plugins."
            )
            all_regs = registry_manager.get_all_registries()
            plugin_scraper.get_all_plugins(all_regs, force_refresh=True)
            return jsonify(
                {
                    "message": "Registry added and plugins refreshed.",
                    "status": "success",
                }
            )
        else:
            return (
                jsonify(
                    {
                        "error": "Failed to add registry (possibly duplicate, invalid path/URL, or local path issue)"
                    }
                ),
                400,
            )

    @app.route("/api/plugin_catalog/registries/refresh", methods=["POST"])
    def refresh_registries_api():
        logger.info("Refreshing all plugin registries via API call...")
        all_regs = registry_manager.get_all_registries()
        plugin_scraper.get_all_plugins(all_regs, force_refresh=True)
        logger.info(
            f"Refresh complete. Found {len(plugin_scraper.plugin_cache)} plugins."
        )
        return jsonify(
            {
                "message": f"Registries refreshed. Found {len(plugin_scraper.plugin_cache)} plugins.",
                "status": "success",
            }
        )

    @app.route("/api/shutdown", methods=["POST"])
    def shutdown_api():
        shared_config = app.config.get("SHARED_CONFIG")
        if shared_config is not None:
            shared_config["status"] = "shutdown_requested"

        temp_dir_path = Path(os.path.expanduser(PLUGIN_CATALOG_TEMP_DIR))
        if temp_dir_path.exists():
            logger.info(f"Cleaning up temporary directory: {temp_dir_path}")
            try:
                shutil.rmtree(temp_dir_path)
            except Exception as e:
                logger.error(
                    f"Error cleaning up temporary directory {temp_dir_path}: {e}"
                )

        func = request.environ.get("werkzeug.server.shutdown")
        if func is None:
            logger.warning(
                "Werkzeug server shutdown function not found. Attempting os._exit(0)."
            )
            os._exit(0)
        try:
            func()
            logger.info("Server shutdown initiated.")
        except Exception as e:
            logger.error(f"Error during server shutdown: {e}. Forcing exit.")
            os._exit(1)
        return jsonify({"status": "success", "message": "Server shutting down"})

    return app


if __name__ == "__main__":
    app = create_plugin_catalog_app()
    print(
        "Starting Plugin Catalog Flask app directly for testing on http://127.0.0.1:5003"
    )
    app.run(host="127.0.0.1", port=5003, debug=True)
