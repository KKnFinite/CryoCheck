"""Read-only Neon control-plane efficiency monitoring for administrators."""

from __future__ import annotations

import calendar
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


NEON_API_BASE = "https://console.neon.tech/api/v2"
NEON_MINIMUM_CU = Decimal("0.25")
_PROJECT_ID_PATTERN = re.compile(r"^[a-z0-9-]{1,60}$")


@dataclass(frozen=True)
class NeonEfficiency:
    """Sanitized Neon efficiency values safe for the admin template."""

    state: str
    message: str
    min_cu: Decimal | None = None
    max_cu: Decimal | None = None
    suspend_timeout: str | None = None
    last_compute_activity: str | None = None
    consumption_period: str | None = None
    consumption_plan: str | None = None
    cu_hours_month_to_date: Decimal | None = None
    projected_cu_hours: Decimal | None = None
    history_state: str = "unavailable"
    configuration_status: str | None = None
    configuration_reason: str | None = None


class _NeonAPIError(Exception):
    """Sanitized internal API failure carrying only an HTTP status."""

    def __init__(self, status: int | None = None):
        super().__init__("Neon API request failed.")
        self.status = status


def fetch_neon_efficiency(
    api_key: str | None,
    project_id: str | None,
    *,
    now: datetime | None = None,
    opener: Callable = urlopen,
) -> NeonEfficiency:
    """Fetch one project snapshot without querying or waking Postgres compute."""
    clean_key = api_key.strip() if isinstance(api_key, str) else ""
    clean_project_id = (
        project_id.strip() if isinstance(project_id, str) else ""
    )
    if not clean_key or not clean_project_id:
        return NeonEfficiency(
            state="setup",
            message=(
                "Set NEON_API_KEY and NEON_PROJECT_ID to enable database "
                "efficiency monitoring."
            ),
        )
    if _PROJECT_ID_PATTERN.fullmatch(clean_project_id) is None:
        return NeonEfficiency(
            state="unavailable",
            message="Neon efficiency data is unavailable. Check the project configuration.",
        )

    reference_time = _aware_utc(now or datetime.now(timezone.utc))
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {clean_key}",
        "User-Agent": "CryoCheck-Neon-Efficiency/1.0",
    }
    try:
        project_payload = _get_json(
            f"{NEON_API_BASE}/projects/{quote(clean_project_id, safe='')}",
            headers,
            opener,
        )
        project = project_payload.get("project")
        if not isinstance(project, dict):
            raise _NeonAPIError()
        efficiency = _project_efficiency(project)
    except _NeonAPIError:
        return NeonEfficiency(
            state="unavailable",
            message="Neon efficiency data is temporarily unavailable.",
        )

    org_id = project.get("org_id")
    if not isinstance(org_id, str) or not org_id:
        return _with_history_unavailable(
            efficiency,
            "CU-hour history is unavailable for this Neon project.",
        )

    month_start = reference_time.replace(
        day=1,
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    query = urlencode(
        {
            "project_ids": clean_project_id,
            "from": _iso_z(month_start),
            "to": _iso_z(reference_time),
            "granularity": "daily",
            "org_id": org_id,
            "metrics": "compute_unit_seconds",
            "limit": 1,
        }
    )
    try:
        history = _get_json(
            f"{NEON_API_BASE}/consumption_history/v2/projects?{query}",
            headers,
            opener,
        )
    except _NeonAPIError as error:
        if error.status == 403:
            return _with_history_unavailable(
                efficiency,
                "CU-hour history unavailable for this Neon plan.",
                history_state="unsupported",
            )
        return _with_history_unavailable(
            efficiency,
            "CU-hour history is temporarily unavailable.",
        )

    try:
        cu_seconds, history_through, plans = _sum_compute_unit_seconds(
            history,
            clean_project_id,
        )
        cu_hours = cu_seconds / Decimal(3600)
        projection_through = history_through or reference_time
        projected = _project_month_end(
            cu_hours,
            month_start=month_start,
            through=projection_through,
        )
    except (InvalidOperation, TypeError, ValueError):
        return _with_history_unavailable(
            efficiency,
            "CU-hour history is temporarily unavailable.",
        )

    return NeonEfficiency(
        **{
            **efficiency.__dict__,
            "cu_hours_month_to_date": cu_hours,
            "projected_cu_hours": projected,
            "history_state": "available",
            "consumption_plan": ", ".join(plans) if plans else None,
        }
    )


def _project_efficiency(project: dict) -> NeonEfficiency:
    settings = project.get("default_endpoint_settings")
    settings = settings if isinstance(settings, dict) else {}
    min_cu = _decimal_or_none(settings.get("autoscaling_limit_min_cu"))
    max_cu = _decimal_or_none(settings.get("autoscaling_limit_max_cu"))
    timeout_seconds = _integer_or_none(settings.get("suspend_timeout_seconds"))
    status, reason = configuration_status(min_cu, timeout_seconds)
    return NeonEfficiency(
        state="available",
        message="Neon project configuration loaded.",
        min_cu=min_cu,
        max_cu=max_cu,
        suspend_timeout=_format_suspend_timeout(timeout_seconds),
        last_compute_activity=_format_timestamp(project.get("compute_last_active_at")),
        consumption_period=_format_period(
            project.get("consumption_period_start"),
            project.get("consumption_period_end"),
        ),
        configuration_status=status,
        configuration_reason=reason,
    )


def configuration_status(
    min_cu: Decimal | None,
    suspend_timeout_seconds: int | None,
) -> tuple[str, str]:
    """Return the deterministic scale-to-zero configuration sanity status."""
    reasons: list[str] = []
    if suspend_timeout_seconds is None:
        reasons.append("Neon did not return a scale-to-zero timeout.")
    elif suspend_timeout_seconds == -1:
        reasons.append("Scale-to-zero is disabled, so idle compute stays active.")

    if min_cu is None:
        reasons.append("Neon did not return a minimum compute setting.")
    elif min_cu != NEON_MINIMUM_CU:
        reasons.append(
            f"Minimum compute is {_format_decimal(min_cu)} CU; Neon's minimum "
            "practical setting is 0.25 CU."
        )

    if reasons:
        return "Review", " ".join(reasons)
    return (
        "Good",
        "Scale-to-zero is enabled and minimum compute is set to Neon's 0.25 CU minimum.",
    )


def _get_json(url: str, headers: dict[str, str], opener: Callable) -> dict:
    request = Request(url, headers=headers, method="GET")
    try:
        with opener(request, timeout=5) as response:
            payload = json.load(response)
    except HTTPError as error:
        raise _NeonAPIError(error.code) from None
    except (OSError, URLError, ValueError, json.JSONDecodeError):
        raise _NeonAPIError() from None
    if not isinstance(payload, dict):
        raise _NeonAPIError()
    return payload


def _sum_compute_unit_seconds(
    payload: dict,
    project_id: str,
) -> tuple[Decimal, datetime | None, tuple[str, ...]]:
    total = Decimal(0)
    latest: datetime | None = None
    plans: list[str] = []
    projects = payload.get("projects", [])
    if not isinstance(projects, list):
        raise ValueError("Invalid consumption response.")
    for project in projects:
        if not isinstance(project, dict) or project.get("project_id") != project_id:
            continue
        periods = project.get("periods", [])
        if not isinstance(periods, list):
            raise ValueError("Invalid consumption periods.")
        for period in periods:
            if not isinstance(period, dict):
                raise ValueError("Invalid consumption period.")
            plan = period.get("period_plan")
            if isinstance(plan, str) and plan and plan not in plans:
                plans.append(plan)
            consumption = period.get("consumption", [])
            if not isinstance(consumption, list):
                raise ValueError("Invalid consumption records.")
            for timeframe in consumption:
                if not isinstance(timeframe, dict):
                    raise ValueError("Invalid consumption timeframe.")
                timeframe_end = _parse_timestamp(timeframe.get("timeframe_end"))
                if timeframe_end is not None and (
                    latest is None or timeframe_end > latest
                ):
                    latest = timeframe_end
                metrics = timeframe.get("metrics", [])
                if not isinstance(metrics, list):
                    raise ValueError("Invalid consumption metrics.")
                for metric in metrics:
                    if (
                        isinstance(metric, dict)
                        and metric.get("metric_name") == "compute_unit_seconds"
                    ):
                        value = Decimal(str(metric.get("value")))
                        if not value.is_finite() or value < 0:
                            raise ValueError("Invalid compute consumption.")
                        total += value
    return total, latest, tuple(plans)


def _project_month_end(
    cu_hours: Decimal,
    *,
    month_start: datetime,
    through: datetime,
) -> Decimal | None:
    through = _aware_utc(through)
    elapsed_seconds = Decimal(str((through - month_start).total_seconds()))
    if elapsed_seconds <= 0:
        return None
    days_in_month = calendar.monthrange(month_start.year, month_start.month)[1]
    month_end = month_start.replace(day=days_in_month) + timedelta(days=1)
    month_seconds = Decimal(str((month_end - month_start).total_seconds()))
    return cu_hours * month_seconds / elapsed_seconds


def _with_history_unavailable(
    efficiency: NeonEfficiency,
    message: str,
    *,
    history_state: str = "unavailable",
) -> NeonEfficiency:
    return NeonEfficiency(
        **{
            **efficiency.__dict__,
            "message": message,
            "history_state": history_state,
        }
    )


def _format_suspend_timeout(value: int | None) -> str | None:
    if value is None:
        return None
    if value == -1:
        return "Disabled (never suspends)"
    if value == 0:
        return "Plan default (5 minutes)"
    if value % 3600 == 0:
        hours = value // 3600
        return f"{hours} hour{'s' if hours != 1 else ''}"
    if value % 60 == 0:
        minutes = value // 60
        return f"{minutes} minute{'s' if minutes != 1 else ''}"
    return f"{value} seconds"


def _format_period(start, end) -> str | None:
    start_value = _format_timestamp(start)
    end_value = _format_timestamp(end)
    if start_value and end_value:
        return f"{start_value} – {end_value}"
    return start_value or end_value


def _format_timestamp(value) -> str | None:
    parsed = _parse_timestamp(value)
    return parsed.strftime("%Y-%m-%d %H:%M UTC") if parsed else None


def _parse_timestamp(value) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return _aware_utc(datetime.fromisoformat(value.replace("Z", "+00:00")))
    except ValueError:
        return None


def _decimal_or_none(value) -> Decimal | None:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return result if result.is_finite() else None


def _integer_or_none(value) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _format_decimal(value: Decimal) -> str:
    return format(value.normalize(), "f")


def _iso_z(value: datetime) -> str:
    return _aware_utc(value).isoformat().replace("+00:00", "Z")


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


__all__ = [
    "NEON_MINIMUM_CU",
    "NeonEfficiency",
    "configuration_status",
    "fetch_neon_efficiency",
]
