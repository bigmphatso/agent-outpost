from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

try:
    import servicemanager
    import win32event
    import win32service
    import win32serviceutil
    import win32timezone  # noqa: F401 - bundled for pywin32 service logging under PyInstaller.
except ImportError as exc:  # pragma: no cover - only exercised on non-Windows hosts.
    raise SystemExit("The OUTPOST Windows service requires pywin32 on Windows.") from exc


class OutpostAgentService(win32serviceutil.ServiceFramework):
    _svc_name_ = "OutpostAgent"
    _svc_display_name_ = "OUTPOST Agent"
    _svc_description_ = "Runs the OUTPOST endpoint monitoring and management agent."

    def __init__(self, args: list[str]) -> None:
        super().__init__(args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.agent_process: subprocess.Popen[bytes] | None = None

    def SvcStop(self) -> None:
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.stop_event)
        self._stop_agent_process()

    def SvcDoRun(self) -> None:
        servicemanager.LogInfoMsg("OUTPOST Agent service starting.")
        self.ReportServiceStatus(win32service.SERVICE_RUNNING)
        self._run_agent_until_stopped()
        servicemanager.LogInfoMsg("OUTPOST Agent service stopped.")

    def _agent_command(self) -> list[str]:
        service_dir = Path(sys.executable).resolve().parent
        packaged_agent = service_dir / "outpost-agent.exe"
        if packaged_agent.exists():
            return [str(packaged_agent)]
        return [sys.executable, "-m", "outpost_agent.main"]

    def _run_agent_until_stopped(self) -> None:
        while win32event.WaitForSingleObject(self.stop_event, 0) == win32event.WAIT_TIMEOUT:
            try:
                self.agent_process = subprocess.Popen(
                    self._agent_command(),
                    cwd=str(Path(sys.executable).resolve().parent),
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                wait_result = win32event.WaitForMultipleObjects(
                    [self.stop_event, int(self.agent_process._handle)],
                    False,
                    win32event.INFINITE,
                )
                if wait_result == win32event.WAIT_OBJECT_0:
                    self._stop_agent_process()
                    return
                exit_code = self.agent_process.poll()
                servicemanager.LogWarningMsg(f"OUTPOST agent process exited with code {exit_code}; restarting.")
                time.sleep(5)
            except Exception as exc:
                servicemanager.LogErrorMsg(f"OUTPOST Agent service error: {exc}")
                time.sleep(10)
            finally:
                self.agent_process = None

    def _stop_agent_process(self) -> None:
        if self.agent_process is None or self.agent_process.poll() is not None:
            return
        self.agent_process.terminate()
        try:
            self.agent_process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            self.agent_process.kill()


def main() -> None:
    win32serviceutil.HandleCommandLine(OutpostAgentService)


if __name__ == "__main__":
    main()
