from __future__ import annotations

import os
import shutil

from outpost_agent.linux_platform import is_linux, linux_antivirus_status, linux_pending_update_count, linux_suspicious_process_count


def collect_health_report() -> dict:
    disk = shutil.disk_usage(os.path.abspath(os.sep))
    disk_free_percent = round((disk.free / disk.total) * 100, 2)
    if is_linux():
        antivirus_present, antivirus_enabled, signature_age_days = linux_antivirus_status()
        return {
            "os_updates_pending": linux_pending_update_count(),
            "antivirus_present": antivirus_present,
            "antivirus_enabled": antivirus_enabled,
            "antivirus_signature_age_days": signature_age_days,
            "disk_free_percent": disk_free_percent,
            "suspicious_process_count": linux_suspicious_process_count(),
        }

    return {
        "os_updates_pending": 0,
        "antivirus_present": True,
        "antivirus_enabled": True,
        "antivirus_signature_age_days": 0,
        "disk_free_percent": disk_free_percent,
        "suspicious_process_count": 0,
    }
