import os
import shutil
import subprocess
from sys import exit as sys_exit
from sys import stdout

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version, build_data):
        super().initialize(version, build_data)

        # Check if we should skip UI builds (static assets already present)
        skip_ui_build = os.environ.get("SAM_SKIP_UI_BUILD", "").lower() in (
            "true",
            "1",
            "yes",
        )

        if skip_ui_build:
            self.app.display_info("SAM_SKIP_UI_BUILD is set, skipping UI build steps\n")
            self.app.display_info("Verifying static assets exist...\n")

            required_paths = [
                "config_portal/frontend/static",
                "client/webui/frontend/static",
                "docs/build",
            ]

            missing = [p for p in required_paths if not os.path.exists(p)]
            if missing:
                raise RuntimeError(
                    f"SAM_SKIP_UI_BUILD is set but required static assets are missing: {', '.join(missing)}"
                )

            self.app.display_info(
                "All required static assets found, proceeding with Python build only\n"
            )
            return

        npm = shutil.which("npm")
        if npm is None:
            raise RuntimeError(
                "NodeJS `npm` is required for building Solace Agent Mesh but it was not found"
            )
        build_log_file = "build.log"
        log_file = open(build_log_file, "w", encoding="utf-8")

        def log(message):
            stdout.write(message)
            log_file.write(message)

        def build_failed(message):
            log(f"\nError during build: {message}\n")
            log(
                f"Build failed. Please check the logs for details at {os.path.abspath(log_file.name)}\n"
            )
            if log_file:
                log_file.close()
            sys_exit(1)

        log(f"Build logs will be written to {os.path.abspath(log_file.name)}\n")
        log(">>> Building Solace Agent Mesh Config Portal\n")
        os.chdir("config_portal/frontend")
        try:
            log("### npm ci")
            subprocess.run(
                [npm, "ci"], check=True, stdout=log_file, stderr=subprocess.STDOUT
            )
            log("\n### npm run build\n")
            subprocess.run(
                [npm, "run", "build"],
                check=True,
                stdout=log_file,
                stderr=subprocess.STDOUT,
            )
        except subprocess.CalledProcessError:
            build_failed("Config Portal build failed with error")
        finally:
            os.chdir("../..")

        log(">>> Building Solace Agent Mesh Web UI\n")
        os.chdir("client/webui/frontend")
        try:
            log("### npm ci")
            subprocess.run(
                [npm, "ci"], check=True, stdout=log_file, stderr=subprocess.STDOUT
            )
            log("\n### npm run build\n")
            subprocess.run(
                [npm, "run", "build"],
                check=True,
                stdout=log_file,
                stderr=subprocess.STDOUT,
            )
        except subprocess.CalledProcessError:
            build_failed(
                "Web UI build failed with error",
            )
        finally:
            os.chdir("../../..")

        log(">>> Building Solace Agent Mesh Documentation\n")
        os.chdir("docs")
        try:
            log("### npm ci")
            subprocess.run(
                [npm, "ci"], check=True, stdout=log_file, stderr=subprocess.STDOUT
            )
            log("\n### npm run build\n")
            subprocess.run(
                [npm, "run", "build"],
                check=True,
                stdout=log_file,
                stderr=subprocess.STDOUT,
            )
        except subprocess.CalledProcessError:
            build_failed("Documentation build failed with error")
        finally:
            os.chdir("..")

        log(">>> Build completed successfully\n")
        log_file.close()
