import os
import shutil
import subprocess
from sys import stdout, exit as sys_exit

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version, build_data):
        super().initialize(version, build_data)
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
            log("### npm install")
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
            log("### npm install")
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
            log("### npm install")
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
