"""Tests for SandboxRunner."""

import os
import resource
import shutil
import stat
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from solace_agent_mesh.sandbox.sandbox_runner import (
    SANDBOX_PROFILES,
    SandboxRunner,
    SandboxRunnerConfig,
    STATUS_PIPE_FILENAME,
)


def _make_runner(tmp_path: Path, **overrides) -> SandboxRunner:
    config = {
        "mode": "direct",
        "work_base_dir": str(tmp_path / "work"),
        "tools_python_dir": str(tmp_path / "tools"),
        "max_concurrent_executions": 2,
        **overrides,
    }
    (tmp_path / "work").mkdir(exist_ok=True)
    (tmp_path / "tools").mkdir(exist_ok=True)
    return SandboxRunner(config)


class TestSafeFilenameRejectsTraversal:
    def test_rejects_dotdot(self, tmp_path: Path):
        with pytest.raises(ValueError, match="Unsafe"):
            SandboxRunner._safe_filename("../etc/passwd", tmp_path)

    def test_rejects_dotdot_mid_path(self, tmp_path: Path):
        with pytest.raises(ValueError, match="Unsafe"):
            SandboxRunner._safe_filename("subdir/../../etc/passwd", tmp_path)


class TestSafeFilenameRejectsAbsolute:
    def test_rejects_leading_slash(self, tmp_path: Path):
        with pytest.raises(ValueError, match="Unsafe"):
            SandboxRunner._safe_filename("/etc/passwd", tmp_path)

    def test_rejects_leading_backslash(self, tmp_path: Path):
        with pytest.raises(ValueError, match="Unsafe"):
            SandboxRunner._safe_filename("\\etc\\passwd", tmp_path)


class TestSafeFilenameRejectsEmpty:
    def test_rejects_empty_string(self, tmp_path: Path):
        with pytest.raises(ValueError, match="Empty"):
            SandboxRunner._safe_filename("", tmp_path)


class TestSafeFilenameAcceptsValid:
    def test_simple_filename(self, tmp_path: Path):
        result = SandboxRunner._safe_filename("data.csv", tmp_path)
        assert result == (tmp_path / "data.csv").resolve()

    def test_subdirectory_filename(self, tmp_path: Path):
        sub = tmp_path / "sub"
        sub.mkdir()
        result = SandboxRunner._safe_filename("sub/data.csv", tmp_path)
        assert str(result).startswith(str(tmp_path.resolve()))


class TestGetProfile:
    def test_known_profile(self, tmp_path: Path):
        runner = _make_runner(tmp_path)
        profile = runner._get_profile("restrictive")
        assert profile["rlimit_as_mb"] == 512

    def test_standard_profile(self, tmp_path: Path):
        runner = _make_runner(tmp_path)
        profile = runner._get_profile("standard")
        assert profile["rlimit_cpu_sec"] == 300

    def test_unknown_falls_back_to_standard(self, tmp_path: Path):
        runner = _make_runner(tmp_path)
        profile = runner._get_profile("nonexistent")
        assert profile == SANDBOX_PROFILES["standard"]


class TestMakePreexecFnSetsLimits:
    def test_sets_rlimit_nproc(self):
        profile = {"rlimit_nproc": 64}
        preexec = SandboxRunner._make_preexec_fn(profile)

        with patch("solace_agent_mesh.sandbox.sandbox_runner.resource.setrlimit") as mock_set:
            preexec()

        calls = {c[0][0]: c[0][1] for c in mock_set.call_args_list}
        assert calls[resource.RLIMIT_NPROC] == (64, 64)

    def test_sets_core_to_zero(self):
        profile = {}
        preexec = SandboxRunner._make_preexec_fn(profile)

        with patch("solace_agent_mesh.sandbox.sandbox_runner.resource.setrlimit") as mock_set:
            preexec()

        calls = {c[0][0]: c[0][1] for c in mock_set.call_args_list}
        assert calls[resource.RLIMIT_CORE] == (0, 0)

    def test_sets_nofile(self):
        profile = {"rlimit_nofile": 256}
        preexec = SandboxRunner._make_preexec_fn(profile)

        with patch("solace_agent_mesh.sandbox.sandbox_runner.resource.setrlimit") as mock_set:
            preexec()

        calls = {c[0][0]: c[0][1] for c in mock_set.call_args_list}
        assert calls[resource.RLIMIT_NOFILE] == (256, 256)

    def test_sets_all_limits_for_full_profile(self):
        profile = SANDBOX_PROFILES["standard"]
        preexec = SandboxRunner._make_preexec_fn(profile)

        with patch("solace_agent_mesh.sandbox.sandbox_runner.resource.setrlimit") as mock_set:
            preexec()

        set_resources = {c[0][0] for c in mock_set.call_args_list}
        assert resource.RLIMIT_AS in set_resources
        assert resource.RLIMIT_CPU in set_resources
        assert resource.RLIMIT_FSIZE in set_resources
        assert resource.RLIMIT_NOFILE in set_resources
        assert resource.RLIMIT_NPROC in set_resources
        assert resource.RLIMIT_CORE in set_resources


class TestProfilesContainNproc:
    def test_restrictive_has_nproc(self):
        assert SANDBOX_PROFILES["restrictive"]["rlimit_nproc"] == 32

    def test_standard_has_nproc(self):
        assert SANDBOX_PROFILES["standard"]["rlimit_nproc"] == 128

    def test_permissive_has_nproc(self):
        assert SANDBOX_PROFILES["permissive"]["rlimit_nproc"] == 512


class TestSetupWorkDirectory:
    def test_creates_structure(self, tmp_path: Path):
        runner = _make_runner(tmp_path)
        work_dir = runner._setup_work_directory("task-001")

        assert (work_dir / "input").is_dir()
        assert (work_dir / "output").is_dir()
        assert (work_dir / STATUS_PIPE_FILENAME).exists()

    def test_pipe_permissions(self, tmp_path: Path):
        runner = _make_runner(tmp_path)
        work_dir = runner._setup_work_directory("task-002")

        pipe_path = work_dir / STATUS_PIPE_FILENAME
        mode = pipe_path.stat().st_mode
        assert stat.S_ISFIFO(mode)
        perms = stat.S_IMODE(mode)
        assert perms == 0o600


class TestCleanupWorkDirectory:
    def test_removes_directory(self, tmp_path: Path):
        runner = _make_runner(tmp_path)
        work_dir = runner._setup_work_directory("task-003")
        assert work_dir.exists()

        runner._cleanup_work_directory(work_dir)
        assert not work_dir.exists()

    def test_nonexistent_dir_no_error(self, tmp_path: Path):
        runner = _make_runner(tmp_path)
        runner._cleanup_work_directory(tmp_path / "nonexistent")


class TestCleanupStaleWorkDirs:
    def test_removes_old_keeps_recent(self, tmp_path: Path):
        runner = _make_runner(tmp_path)
        work_base = tmp_path / "work"

        old_dir = work_base / "old-task"
        old_dir.mkdir()
        old_time = time.time() - 7200
        os.utime(old_dir, (old_time, old_time))

        new_dir = work_base / "new-task"
        new_dir.mkdir()

        removed = runner._cleanup_stale_work_dirs(max_age_hours=1.0)
        assert removed == 1
        assert not old_dir.exists()
        assert new_dir.exists()

    def test_empty_base_returns_zero(self, tmp_path: Path):
        runner = _make_runner(tmp_path)
        removed = runner._cleanup_stale_work_dirs()
        assert removed == 0


class TestCheckDiskSpace:
    def test_sufficient_space(self, tmp_path: Path):
        assert SandboxRunner._check_disk_space(str(tmp_path), min_free_mb=1) is True

    def test_low_space(self, tmp_path: Path):
        assert SandboxRunner._check_disk_space(str(tmp_path), min_free_mb=999_999_999) is False

    def test_error_fails_open(self):
        assert SandboxRunner._check_disk_space("/nonexistent/path/xyz", min_free_mb=1) is True


class TestBuildBwrapCommand:
    def test_key_flags_present(self, tmp_path: Path):
        runner = _make_runner(tmp_path)
        params = MagicMock()
        params.task_id = "t1"
        params.tool_name = "tool"
        params.args = {}
        params.tool_config = {}
        params.timeout_seconds = 60
        params.sandbox_profile = "standard"
        params.app_name = "app"
        params.user_id = "u"
        params.session_id = "s"

        manifest_entry = MagicMock()
        manifest_entry.module = "mod"
        manifest_entry.function = "fn"
        manifest_entry.class_name = None
        manifest_entry.sandbox_profile = None

        work_dir = runner._setup_work_directory("t1")
        profile = SANDBOX_PROFILES["standard"]

        runner._config.mode = "bwrap"
        cmd = runner._build_bwrap_command(
            work_dir, params, manifest_entry, {}, {}, profile,
        )

        cmd_str = " ".join(cmd)
        assert "--die-with-parent" in cmd_str
        assert "--unshare-pid" in cmd_str
        assert "--unshare-user" in cmd_str
        assert "--uid 65534" in cmd_str
        assert "--gid 65534" in cmd_str
        assert "--ro-bind" in cmd_str
        assert "--clearenv" in cmd_str

    def test_network_isolation(self, tmp_path: Path):
        runner = _make_runner(tmp_path)
        params = MagicMock()
        params.task_id = "t2"
        params.tool_name = "tool"
        params.args = {}
        params.tool_config = {}
        params.timeout_seconds = 60
        params.sandbox_profile = "restrictive"
        params.app_name = "app"
        params.user_id = "u"
        params.session_id = "s"

        manifest_entry = MagicMock()
        manifest_entry.module = "mod"
        manifest_entry.function = "fn"
        manifest_entry.class_name = None
        manifest_entry.sandbox_profile = None

        work_dir = runner._setup_work_directory("t2")
        profile = SANDBOX_PROFILES["restrictive"]

        runner._config.mode = "bwrap"
        cmd = runner._build_bwrap_command(
            work_dir, params, manifest_entry, {}, {}, profile,
        )
        assert "--unshare-net" in cmd


class TestBuildDirectCommand:
    def test_structure(self, tmp_path: Path):
        runner = _make_runner(tmp_path)
        params = MagicMock()
        params.task_id = "t3"
        params.tool_name = "tool"
        params.args = {}
        params.tool_config = {}
        params.timeout_seconds = 60
        params.sandbox_profile = "standard"
        params.app_name = "app"
        params.user_id = "u"
        params.session_id = "s"

        manifest_entry = MagicMock()
        manifest_entry.module = "mod"
        manifest_entry.function = "fn"
        manifest_entry.class_name = None

        work_dir = runner._setup_work_directory("t3")
        cmd = runner._build_direct_command(
            work_dir, params, manifest_entry, {}, {},
        )

        assert cmd[0] == runner._config.python_bin
        assert "-m" in cmd
        assert "solace_agent_mesh.sandbox.tool_runner" in cmd


class TestSemaphoreValue:
    def test_matches_config(self, tmp_path: Path):
        runner = _make_runner(tmp_path, max_concurrent_executions=7)
        assert runner._execution_semaphore._value == 7


def _build_bwrap_cmd(tmp_path: Path, profile_name: str = "standard") -> list:
    """Helper to build a bwrap command for testing mount assertions."""
    runner = _make_runner(tmp_path)
    params = MagicMock()
    params.task_id = "sec-test"
    params.tool_name = "tool"
    params.args = {}
    params.tool_config = {}
    params.timeout_seconds = 60
    params.sandbox_profile = profile_name
    params.app_name = "app"
    params.user_id = "u"
    params.session_id = "s"

    manifest_entry = MagicMock()
    manifest_entry.module = "mod"
    manifest_entry.function = "fn"
    manifest_entry.class_name = None
    manifest_entry.sandbox_profile = None

    work_dir = runner._setup_work_directory("sec-test")
    profile = SANDBOX_PROFILES[profile_name]
    runner._config.mode = "bwrap"
    return runner._build_bwrap_command(work_dir, params, manifest_entry, {}, {}, profile)


class TestBwrapCommandHidesSecrets:
    def test_no_var_run_secrets_bind(self, tmp_path: Path):
        cmd = _build_bwrap_cmd(tmp_path)
        pairs = list(zip(cmd, cmd[1:]))
        for flag, src in pairs:
            if flag == "--ro-bind" and "/var/run/secrets" in src:
                pytest.fail("--ro-bind exposes /var/run/secrets")

    def test_tmpfs_over_var_run_secrets(self, tmp_path: Path):
        cmd = _build_bwrap_cmd(tmp_path)
        pairs = list(zip(cmd, cmd[1:]))
        assert ("--tmpfs", "/var/run/secrets") in pairs

    def test_no_etc_shadow_bind(self, tmp_path: Path):
        cmd = _build_bwrap_cmd(tmp_path)
        pairs = list(zip(cmd, cmd[1:]))
        for flag, src in pairs:
            if flag == "--ro-bind" and src == "/etc/shadow":
                pytest.fail("--ro-bind exposes /etc/shadow")

    def test_no_app_dir_bind(self, tmp_path: Path):
        cmd = _build_bwrap_cmd(tmp_path)
        pairs = list(zip(cmd, cmd[1:]))
        for flag, src in pairs:
            if flag == "--ro-bind" and src == "/app":
                pytest.fail("--ro-bind exposes /app")


class TestBwrapCommandWhitelistMounts:
    def test_no_root_bind(self, tmp_path: Path):
        cmd = _build_bwrap_cmd(tmp_path)
        pairs = list(zip(cmd, cmd[1:], cmd[2:]))
        for flag, src, dst in pairs:
            if flag == "--ro-bind" and src == "/" and dst == "/":
                pytest.fail("Found --ro-bind / / — should use whitelist mounts")

    def test_mounts_usr_readonly(self, tmp_path: Path):
        cmd = _build_bwrap_cmd(tmp_path)
        pairs = list(zip(cmd, cmd[1:], cmd[2:]))
        assert ("--ro-bind", "/usr", "/usr") in pairs

    def test_mounts_etc_resolv_conf(self, tmp_path: Path):
        cmd = _build_bwrap_cmd(tmp_path)
        pairs = list(zip(cmd, cmd[1:], cmd[2:]))
        assert ("--ro-bind", "/etc/resolv.conf", "/etc/resolv.conf") in pairs

    def test_mounts_etc_ssl(self, tmp_path: Path):
        cmd = _build_bwrap_cmd(tmp_path)
        pairs = list(zip(cmd, cmd[1:], cmd[2:]))
        assert ("--ro-bind", "/etc/ssl", "/etc/ssl") in pairs

    def test_mounts_tools_readonly(self, tmp_path: Path):
        cmd = _build_bwrap_cmd(tmp_path)
        tools_dir = str(tmp_path / "tools")
        pairs = list(zip(cmd, cmd[1:], cmd[2:]))
        assert ("--ro-bind", tools_dir, tools_dir) in pairs


class TestBwrapCommandProcMount:
    def test_proc_mount_present(self, tmp_path: Path):
        cmd = _build_bwrap_cmd(tmp_path)
        pairs = list(zip(cmd, cmd[1:]))
        assert ("--proc", "/proc") in pairs


class TestBuildFilesystemMounts:
    def test_mounts_usr(self, tmp_path: Path):
        mounts = SandboxRunner._build_filesystem_mounts(str(tmp_path / "tools"))
        assert "--ro-bind" in mounts
        idx = mounts.index("/usr")
        assert mounts[idx - 1] == "--ro-bind"

    def test_handles_lib_symlink(self, tmp_path: Path):
        with patch("os.path.islink") as mock_islink, \
             patch("os.readlink", return_value="usr/lib") as mock_readlink, \
             patch("os.path.exists", return_value=True):
            mock_islink.side_effect = lambda p: p in ("/lib", "/lib64", "/bin", "/sbin")
            mounts = SandboxRunner._build_filesystem_mounts(str(tmp_path / "tools"))

        assert "--symlink" in mounts
        sym_pairs = [(mounts[i], mounts[i + 1], mounts[i + 2])
                     for i in range(len(mounts) - 2)
                     if mounts[i] == "--symlink"]
        targets = {t[2] for t in sym_pairs}
        assert "/lib" in targets

    def test_handles_lib_directory(self, tmp_path: Path):
        with patch("os.path.islink", return_value=False), \
             patch("os.path.exists", return_value=True):
            mounts = SandboxRunner._build_filesystem_mounts(str(tmp_path / "tools"))

        pairs = list(zip(mounts, mounts[1:], mounts[2:]))
        assert ("--ro-bind", "/lib", "/lib") in pairs

    def test_optional_files_skipped_when_missing(self, tmp_path: Path):
        def fake_exists(path):
            if path in ("/etc/ld.so.cache", "/etc/localtime", "/etc/nsswitch.conf", "/etc/hosts"):
                return False
            if path in ("/lib", "/lib64", "/bin", "/sbin"):
                return False
            return True

        with patch("os.path.islink", return_value=False), \
             patch("os.path.exists", side_effect=fake_exists):
            mounts = SandboxRunner._build_filesystem_mounts(str(tmp_path / "tools"))

        assert "/etc/ld.so.cache" not in mounts
        assert "/etc/localtime" not in mounts
        assert "/etc/nsswitch.conf" not in mounts
        assert "/etc/hosts" not in mounts
