# noqa: INP001
import os
import shutil
import subprocess
from sys import stderr

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version, build_data):
        super().initialize(version, build_data)
        stderr.write(">>> Building Solace Agent Mesh frontend\n")
        npm = shutil.which("npm")
        if npm is None:
            raise RuntimeError(
                "NodeJS `npm` is required for building Solace Agent Mesh frontend but it was not found"
            )

        os.chdir("config_portal/frontend")
        try:
            stderr.write("### npm install\n")
            subprocess.run([npm, "install"], check=True)
            stderr.write("\n### npm run build\n")
            subprocess.run([npm, "run", "build"], check=True)
        finally:
            os.chdir("..")
