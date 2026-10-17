"""Small stdlib-only OS adapters; no Codex configuration or model policy here."""
from __future__ import annotations

import base64
import contextlib
import os
from pathlib import Path
import queue
import shlex
import signal
import subprocess
import threading


def configure_stdio():
    import sys
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


@contextlib.contextmanager
def file_lock(path: Path):
    """Nonblocking, process-owned lock. The persistent lock file is never unlinked."""
    with path.open("a+b") as handle:
        if os.name == "nt":
            import msvcrt
            # msvcrt locks a byte range, including when the file was initially empty.
            if not handle.seek(0, os.SEEK_END):
                handle.write(b"\0")
                handle.flush()
            handle.seek(0)
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                # Do not turn permission/disk failures into apparently busy locks.
                if exc.errno not in (13, 11, 36):
                    raise
                raise BlockingIOError("lock busy") from exc
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            if os.name == "nt":
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


def hook_command(python: Path, script: Path) -> str:
    if os.name != "nt":
        return shlex.join([str(python), "-X", "utf8", str(script), "hook"])
    # Codex runs Windows command hooks via cmd.exe /C. Encoding the PowerShell
    # program keeps %, !, &, apostrophes and non-ASCII paths out of cmd's parser.
    # Explicitly forward stdin: PowerShell does not transparently inherit it for
    # native commands. PS 5.1 otherwise also defaults to lossy ASCII pipelines.
    quote = lambda s: "'" + str(s).replace("'", "''") + "'"
    program = (
        "$ErrorActionPreference='Stop'; "
        "$OutputEncoding=[Console]::OutputEncoding=New-Object System.Text.UTF8Encoding($false); "
        "[Console]::InputEncoding=New-Object System.Text.UTF8Encoding($false); "
        "[Console]::In.ReadToEnd() | & " + quote(python) + " -X utf8 " + quote(script) +
        " hook; exit $LASTEXITCODE"
    )
    encoded = base64.b64encode(program.encode("utf-16-le")).decode("ascii")
    return "powershell.exe -NoLogo -NoProfile -NonInteractive -EncodedCommand " + encoded


class _WindowsJob:
    """Kill child descendants on close, including after the direct child exits."""
    def __init__(self, proc):
        import ctypes
        from ctypes import wintypes as w

        class IO_COUNTERS(ctypes.Structure):
            _fields_ = [(name, ctypes.c_ulonglong) for name in
                        ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                         "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

        class BASIC_LIMIT(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_longlong),
                        ("PerJobUserTimeLimit", ctypes.c_longlong), ("LimitFlags", w.DWORD),
                        ("MinimumWorkingSetSize", ctypes.c_size_t),
                        ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", w.DWORD),
                        ("Affinity", ctypes.c_size_t), ("PriorityClass", w.DWORD),
                        ("SchedulingClass", w.DWORD)]

        class EXTENDED_LIMIT(ctypes.Structure):
            _fields_ = [("BasicLimitInformation", BASIC_LIMIT), ("IoInfo", IO_COUNTERS),
                        ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                        ("PeakProcessMemoryUsed", ctypes.c_size_t),
                        ("PeakJobMemoryUsed", ctypes.c_size_t)]

        self.api = ctypes.WinDLL("kernel32", use_last_error=True)
        self.api.CreateJobObjectW.argtypes = [ctypes.c_void_p, w.LPCWSTR]
        self.api.CreateJobObjectW.restype = w.HANDLE
        self.api.SetInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD]
        self.api.SetInformationJobObject.restype = w.BOOL
        self.api.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
        self.api.AssignProcessToJobObject.restype = w.BOOL
        self.api.CloseHandle.argtypes = [w.HANDLE]
        self.api.CloseHandle.restype = w.BOOL
        self.handle = self.api.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        limits = EXTENDED_LIMIT()
        limits.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if (not self.api.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits))
                or not self.api.AssignProcessToJobObject(self.handle, w.HANDLE(int(proc._handle)))):
            error = ctypes.WinError(ctypes.get_last_error())
            self.close()
            raise error

    def close(self):
        if self.handle:
            self.api.CloseHandle(self.handle)
            self.handle = None


def spawn(argv, **kwargs):
    """Create an isolated process tree; never invoke a shell for Codex arguments."""
    options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {"start_new_session": True}
    proc = subprocess.Popen(argv, **kwargs, **options)
    if os.name == "nt":
        try:
            proc._updater_job = _WindowsJob(proc)
        except BaseException:
            # Fail closed if the OS cannot give us ownership of the child tree.
            if proc.poll() is None:
                proc.kill()
            proc.wait(timeout=3)
            for pipe in (proc.stdin, proc.stdout, proc.stderr):
                if pipe:
                    pipe.close()
            raise
    return proc


def stop_process(proc):
    """Idempotent bounded cleanup on success, EOF, timeout or exception."""
    if os.name == "nt":
        job = getattr(proc, "_updater_job", None)
        if job:
            job.close()
        elif proc.poll() is None:
            proc.kill()
    else:
        # Kill the whole group even if its original leader has already exited.
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except PermissionError:
            # Some macOS sandboxes deny killpg for an already exited child with
            # no remaining accessible group. Never ignore this for a live child.
            if proc.poll() is None:
                raise
    proc.wait(timeout=3)


def communicate(proc, data: bytes, timeout: float):
    """Include blocked stdin writes in the timeout on Windows as well as POSIX."""
    result = queue.Queue()

    def worker():
        try:
            result.put((True, proc.communicate(data)))
        except BaseException as exc:
            result.put((False, exc))

    thread = threading.Thread(target=worker, daemon=True, name="title-review-io")
    thread.start()
    try:
        try:
            ok, value = result.get(timeout=timeout)
        except queue.Empty:
            raise subprocess.TimeoutExpired(proc.args, timeout) from None
        if not ok:
            raise value
        return value
    finally:
        stop_process(proc)
        thread.join(timeout=3)
        for pipe in (proc.stdin, proc.stdout, proc.stderr):
            if pipe:
                pipe.close()
