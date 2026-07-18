# =================================================================================
# The MIT License 
# MIT许可证
# 
# <https://opensource.org/license/mit>
# 
# SPDX short identifier / SPDX 短标识符：MIT 
# 
# Copyright (c) 2026 autoMBD
# 版权所有 (c) 2026 autoMBD
#
# Permission is hereby granted, free of charge, to any person obtaining a 
# copy of this software and associated documentation files (the "Software"), 
# to deal in the Software without restriction, including without limitation 
# the rights to use, copy, modify, merge, publish, distribute, sublicense, 
# and/or sell copies of the Software, and to permit persons to whom the 
# Software is furnished to do so, subject to the following conditions:
# 特此向获得本软件及相关文档（合称"本软件"）副本的任何人免费授予不受限制地利用本软
# 件的许可，包括而不限于：使用、复制、修改、合并、发布、分发、分许可和/或销售本软
# 件副本，并允许本软件的接收者也获得前述许可，但须遵守以下条件：
# 
# The above copyright notice and this permission notice shall be included 
# in all copies or substantial portions of the Software.
# 以上版权声明及本许可声明应包含在本软件的所有副本或主要部分中。
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, 
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF 
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND 
# NONINFRINGEMENT. IN NO EVENT SHALLTHE AUTHORS OR COPYRIGHT 
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER 
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN 
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE 
# SOFTWARE.
# 本软件系"按原样"提供，不包含任何形式的明示或默示保证，包括但不限于适销性、特定
# 目的适用性及不侵权的保证。在任何情况下，无论是在合同、侵权或其他案件中，作者或版
# 权持有人均不对因本软件、或因本软件的使用或其他利用而引起的、引发的或与之相关的任
# 何权利主张、损害赔偿或其他责任承担责任。
# =================================================================================
# Project:     RTD CfgFile CLI <https://github.com/autoMBD/autombd-rtd-config>
# File:        process_tree.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-07-13
# Version:     0.1.0
# Description: Run validator process trees with bounded output and fail-closed cleanup.
# =================================================================================

from __future__ import annotations

from dataclasses import dataclass
import codecs
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
from typing import BinaryIO, Mapping

from ...errors import CliFailure


@dataclass(frozen=True)
class ProcessOutputLimits:
    max_bytes: int = 256 * 1024
    max_lines: int = 4000

    def __post_init__(self) -> None:
        if self.max_bytes <= 0 or self.max_lines <= 0:
            raise ValueError("process output limits must be positive")


@dataclass(frozen=True)
class ProcessTreeResult:
    exit_code: int
    stdout: str
    stderr: str
    code: str
    timed_out: bool = False
    stdout_truncated: bool = False
    stderr_truncated: bool = False
    severe_problems: tuple[str, ...] = ()
    output_faults: tuple[str, ...] = ()


class _BoundedTail:
    def __init__(self, limits: ProcessOutputLimits) -> None:
        self._limits = limits
        self._data = bytearray()
        self.truncated = False

    def append(self, chunk: bytes) -> None:
        self._data.extend(chunk)
        if len(self._data) > self._limits.max_bytes:
            del self._data[: len(self._data) - self._limits.max_bytes]
            self.truncated = True
        line_count = self._data.count(b"\n")
        if line_count > self._limits.max_lines:
            remove = line_count - self._limits.max_lines
            offset = 0
            for _ in range(remove):
                offset = self._data.find(b"\n", offset) + 1
            del self._data[:offset]
            self.truncated = True

    def text(self) -> str:
        return bytes(self._data).decode("utf-8", errors="replace")


def _is_qualifying_severe(line: str) -> bool:
    return (
        ("[TOOL]" in line and "has the following error" in line)
        or ("From Problems view:" in line and "Tool problem issue:" in line)
    )


class _OutputCollector:
    """Bound the display tail while retaining streamed validation verdicts."""

    def __init__(self, limits: ProcessOutputLimits) -> None:
        self.tail = _BoundedTail(limits)
        self._decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        self._pending = ""
        self.severe: list[str] = []
        self.faults: list[str] = []

    def append(self, chunk: bytes) -> None:
        self.tail.append(chunk)
        self._consume(self._decoder.decode(chunk))

    def finish(self) -> None:
        self._consume(self._decoder.decode(b"", final=True), final=True)

    def fault(self, _exc: BaseException) -> None:
        # Exception text can contain paths or vendor data. Only the stable fault
        # class crosses the process boundary.
        self.faults.append("process_output_read_failed")

    def _consume(self, text: str, *, final: bool = False) -> None:
        self._pending += text
        lines = self._pending.split("\n")
        self._pending = "" if final else lines.pop()
        if final and self._pending:
            lines.append(self._pending)
            self._pending = ""
        for line in lines:
            candidate = line.rstrip("\r").strip()
            if _is_qualifying_severe(candidate) and candidate not in self.severe:
                self.severe.append(candidate)
        # A hostile no-newline stream must not turn verdict extraction into an
        # unbounded allocation. Detect a complete sentinel before retaining only
        # the bounded suffix; truncation itself remains a fail-closed condition.
        if len(self._pending) > self.tail._limits.max_bytes:
            candidate = self._pending.strip()
            if _is_qualifying_severe(candidate) and candidate not in self.severe:
                self.severe.append(candidate)
            self._pending = self._pending[-self.tail._limits.max_bytes :]

    @property
    def truncated(self) -> bool:
        return self.tail.truncated

    def text(self) -> str:
        return self.tail.text()


def _drain(stream: BinaryIO, sink: _OutputCollector) -> None:
    try:
        while chunk := stream.read(64 * 1024):
            sink.append(chunk)
        sink.finish()
    except BaseException as exc:
        sink.fault(exc)
    finally:
        try:
            stream.close()
        except BaseException as exc:
            sink.fault(exc)


if os.name == "nt":
    import ctypes
    from ctypes import wintypes

    _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
    _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS = 9

    class _IO_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_ulonglong),
            ("WriteOperationCount", ctypes.c_ulonglong),
            ("OtherOperationCount", ctypes.c_ulonglong),
            ("ReadTransferCount", ctypes.c_ulonglong),
            ("WriteTransferCount", ctypes.c_ulonglong),
            ("OtherTransferCount", ctypes.c_ulonglong),
        ]

    class _JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_longlong),
            ("PerJobUserTimeLimit", ctypes.c_longlong),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class _JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", _JOBOBJECT_BASIC_LIMIT_INFORMATION),
            ("IoInfo", _IO_COUNTERS),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _CreateJobObjectW = _kernel32.CreateJobObjectW
    _CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
    _CreateJobObjectW.restype = wintypes.HANDLE
    _SetInformationJobObject = _kernel32.SetInformationJobObject
    _SetInformationJobObject.argtypes = [
        wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD,
    ]
    _SetInformationJobObject.restype = wintypes.BOOL
    _AssignProcessToJobObject = _kernel32.AssignProcessToJobObject
    _AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    _AssignProcessToJobObject.restype = wintypes.BOOL
    _TerminateJobObject = _kernel32.TerminateJobObject
    _TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
    _TerminateJobObject.restype = wintypes.BOOL
    _CloseHandle = _kernel32.CloseHandle
    _CloseHandle.argtypes = [wintypes.HANDLE]
    _CloseHandle.restype = wintypes.BOOL
    _NtResumeProcess = ctypes.WinDLL("ntdll").NtResumeProcess
    _NtResumeProcess.argtypes = [wintypes.HANDLE]
    _NtResumeProcess.restype = ctypes.c_long


class _WindowsJob:
    def __init__(self) -> None:
        self.handle = _CreateJobObjectW(None, None)
        if not self.handle:
            raise OSError("job creation failed")
        limits = _JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        limits.BasicLimitInformation.LimitFlags = _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not _SetInformationJobObject(
            self.handle,
            _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS,
            ctypes.byref(limits),
            ctypes.sizeof(limits),
        ):
            self.close()
            raise OSError("job configuration failed")

    def assign_and_resume(self, process: subprocess.Popen[bytes]) -> None:
        if not _AssignProcessToJobObject(self.handle, process._handle):
            raise OSError("job assignment failed")
        if _NtResumeProcess(process._handle) != 0:
            raise OSError("suspended process resume failed")

    def terminate(self) -> None:
        if self.handle and not _TerminateJobObject(self.handle, 125):
            raise OSError("job termination failed")

    def close(self) -> None:
        if self.handle:
            if not _CloseHandle(self.handle):
                raise OSError("job close failed")
            self.handle = None


class ProcessTreeRunner:
    """Launch an argv-only process inside an owned whole-tree kill boundary."""

    def __init__(self, limits: ProcessOutputLimits | None = None) -> None:
        self.limits = limits or ProcessOutputLimits()

    def run(
        self,
        argv: list[str],
        *,
        cwd: Path,
        env: Mapping[str, str],
        timeout_s: float,
    ) -> ProcessTreeResult:
        if not argv or not all(isinstance(item, str) and item for item in argv):
            raise CliFailure(
                "validation_command_invalid",
                "Validator commands must be non-empty argv string lists.",
                module="backend",
            )
        if timeout_s <= 0:
            raise CliFailure(
                "validation_timeout_invalid",
                "Validator timeout must be positive.",
                module="backend",
            )
        if os.name != "nt" and os.name != "posix":
            raise CliFailure(
                "validation_process_isolation_unavailable",
                "This platform cannot isolate the validator process tree safely.",
                module="backend",
            )

        job = None
        process: subprocess.Popen[bytes] | None = None
        creationflags = 0
        start_new_session = os.name == "posix"
        try:
            if os.name == "nt":
                job = _WindowsJob()
                creationflags = (
                    getattr(subprocess, "CREATE_SUSPENDED", 0x00000004)
                    | getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
                )
            process = subprocess.Popen(
                argv,
                cwd=str(cwd),
                env=dict(env),
                shell=False,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=creationflags,
                start_new_session=start_new_session,
            )
            if job is not None:
                job.assign_and_resume(process)
        except (OSError, ValueError, subprocess.SubprocessError):
            cleanup_ok = True
            if process is not None:
                cleanup_ok = self._terminate_tree(process, job)
            if job is not None:
                try:
                    job.close()
                except OSError:
                    cleanup_ok = False
            if not cleanup_ok:
                return ProcessTreeResult(
                    125, "", "Validator process tree cleanup failed.",
                    "process_tree_kill_failed",
                )
            return ProcessTreeResult(
                127, "", "Validator process could not be launched.",
                "process_spawn_failed",
            )

        assert process.stdout is not None and process.stderr is not None
        stdout = _OutputCollector(self.limits)
        stderr = _OutputCollector(self.limits)
        readers = [
            threading.Thread(target=_drain, args=(process.stdout, stdout), daemon=True),
            threading.Thread(target=_drain, args=(process.stderr, stderr), daemon=True),
        ]
        for reader in readers:
            reader.start()

        timed_out = False
        interrupted: BaseException | None = None
        try:
            self._interruptible_wait(process, timeout_s)
        except subprocess.TimeoutExpired:
            timed_out = True
        except BaseException as exc:
            interrupted = exc

        # This is deliberately unconditional: a successful parent exit does not
        # prove that children which inherited stdout/stderr have exited.
        cleanup_ok = self._terminate_tree(process, job)
        if not cleanup_ok:
            # Last-resort parent cleanup is still bounded. It cannot restore
            # confidence in descendant cleanup, so the final result remains
            # process_tree_kill_failed even when this reap succeeds.
            try:
                process.kill()
            except OSError:
                pass
            try:
                process.wait(timeout=2)
            except (OSError, subprocess.TimeoutExpired):
                pass
        if job is not None:
            try:
                job.close()
            except OSError:
                cleanup_ok = False
            job = None
        for pipe in (process.stdout, process.stderr):
            if pipe is not None and not getattr(pipe, "closed", False):
                try:
                    pipe.close()
                except (OSError, ValueError):
                    pass
        for reader in readers:
            reader.join(timeout=2)
            if reader.is_alive():
                cleanup_ok = False
        if not cleanup_ok:
            if interrupted is not None:
                raise CliFailure(
                    "process_tree_kill_failed",
                    "The validator process tree could not be terminated safely.",
                    module="backend",
                ) from interrupted
            return ProcessTreeResult(
                125, stdout.text(), stderr.text(), "process_tree_kill_failed",
                timed_out=timed_out,
                stdout_truncated=stdout.truncated,
                stderr_truncated=stderr.truncated,
                severe_problems=tuple(stdout.severe + stderr.severe),
                output_faults=tuple(stdout.faults + stderr.faults),
            )
        if interrupted is not None:
            raise interrupted
        faults = tuple(stdout.faults + stderr.faults)
        truncated = stdout.truncated or stderr.truncated
        code = (
            "process_timeout" if timed_out
            else "process_output_fault" if faults
            else "process_output_truncated" if truncated
            else "process_exit"
        )
        return ProcessTreeResult(
            124 if timed_out else int(process.returncode or 0),
            stdout.text(), stderr.text(),
            code,
            timed_out=timed_out,
            stdout_truncated=stdout.truncated,
            stderr_truncated=stderr.truncated,
            severe_problems=tuple(stdout.severe + stderr.severe),
            output_faults=faults,
        )

    @staticmethod
    def _interruptible_wait(
        process: subprocess.Popen[bytes], timeout_s: float
    ) -> None:
        deadline = time.monotonic() + timeout_s
        while process.poll() is None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(process.args, timeout_s)
            try:
                process.wait(timeout=min(0.1, remaining))
            except subprocess.TimeoutExpired:
                continue

    @staticmethod
    def _terminate_tree(
        process: subprocess.Popen[bytes], job: _WindowsJob | None
    ) -> bool:
        deadline = time.monotonic() + 4.0
        try:
            if job is not None:
                job.terminate()
            else:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
            try:
                process.wait(timeout=min(2.0, max(0.01, deadline - time.monotonic())))
            except subprocess.TimeoutExpired:
                if job is not None:
                    job.terminate()
                else:
                    os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=min(2.0, max(0.01, deadline - time.monotonic())))
            if job is None:
                # The parent may already be reaped while a signal-ignoring
                # descendant remains in the dedicated process group.
                try:
                    os.killpg(process.pid, 0)
                except ProcessLookupError:
                    return True
                os.killpg(process.pid, signal.SIGKILL)
                while time.monotonic() < deadline:
                    try:
                        os.killpg(process.pid, 0)
                    except ProcessLookupError:
                        return True
                    time.sleep(0.02)
                return False
            return process.poll() is not None
        except (OSError, ProcessLookupError, subprocess.TimeoutExpired):
            return False
