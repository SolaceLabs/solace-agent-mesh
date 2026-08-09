"""
Regression tests verifying that OS-level CVE pins in the Dockerfile actually
produce a patched image, rather than just asserting the Dockerfile text looks
right.

These tests build a real container from the runtime stage's apt-get RUN
instruction (extracted verbatim from the Dockerfile) and inspect the
installed dpkg package versions, using `dpkg --compare-versions` for
Debian-correct version comparison (handles epochs and `+debNNuM` suffixes,
which plain string/semver comparison gets wrong).

They intentionally build only that one RUN instruction standalone rather than
`docker build --target runtime`, which would also force-build the UI and
Python wheel stages the runtime stage COPYs from -- unnecessary and slow for
verifying an OS package version.

Excluded from the default test run (see pyproject.toml addopts) because they
require Docker and network access and take longer than the unit suite. Run
explicitly with:

    make test-security
"""

import re
import subprocess
import tempfile
from pathlib import Path

import pytest

pytestmark = pytest.mark.slow

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE = REPO_ROOT / "Dockerfile"

_APT_RUN_PATTERN = re.compile(
    r"FROM python:3\.13\.11-slim-trixie AS runtime\b.*?"
    r"(RUN echo \"deb http://deb\.debian\.org/debian unstable main\".*?"
    r"rm -rf /var/lib/apt/lists/\* /etc/apt/sources\.list\.d/unstable\.list /etc/apt/preferences\.d/99pin-libtasn1)",
    re.DOTALL,
)


def _extract_runtime_apt_install_instruction() -> str:
    """Pulls the runtime stage's apt-get RUN instruction verbatim out of the Dockerfile."""
    text = DOCKERFILE.read_text()
    match = _APT_RUN_PATTERN.search(text)
    assert match, (
        "Could not locate the runtime stage's apt-get install RUN instruction "
        "in Dockerfile -- did its structure change?"
    )
    return match.group(1)


def _build_image_from_apt_instruction(apt_run_instruction: str) -> str:
    tag = "sam-cve-pin-test:runtime-apt-layer"
    dockerfile_content = f"FROM python:3.13.11-slim-trixie\n{apt_run_instruction}\n"
    with tempfile.TemporaryDirectory() as build_context:
        Path(build_context, "Dockerfile").write_text(dockerfile_content)
        proc = subprocess.run(
            ["docker", "build", "-t", tag, build_context],
            capture_output=True,
            timeout=300,
        )
    assert proc.returncode == 0, f"Docker build failed:\n{proc.stderr.decode()}"
    return tag


def _installed_dpkg_version_satisfies(image_tag: str, package: str, minimum_version: str) -> bool:
    result = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            image_tag,
            "sh",
            "-c",
            f"dpkg --compare-versions \"$(dpkg-query -W -f='${{Version}}' {package} 2>/dev/null)\" ge \"{minimum_version}\"",
        ],
        capture_output=True,
        timeout=60,
    )
    return result.returncode == 0


@pytest.fixture(scope="module")
def runtime_apt_image():
    apt_run_instruction = _extract_runtime_apt_install_instruction()
    tag = _build_image_from_apt_instruction(apt_run_instruction)
    yield tag
    subprocess.run(["docker", "rmi", "-f", tag], capture_output=True)


def test_libnss3_meets_debian_security_fix_for_cve_2026_16389(runtime_apt_image):
    # https://security-tracker.debian.org/tracker/CVE-2026-16389 -- trixie fixed in 2:3.110-1+deb13u4
    assert _installed_dpkg_version_satisfies(runtime_apt_image, "libnss3", "2:3.110-1+deb13u4"), (
        "libnss3 in the runtime image is missing or older than the version that "
        "fixes CVE-2026-16389 (DATAGO-146589)"
    )
