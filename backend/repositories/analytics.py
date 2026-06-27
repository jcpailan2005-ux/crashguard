from backend.db import get_connection


def _avg_seconds(start_field: str, end_field: str) -> float | None:
    with get_connection() as conn:
        row = conn.execute(
            f"""
            SELECT AVG((julianday({end_field}) - julianday({start_field})) * 86400.0) AS value
            FROM crash_cases
            WHERE {start_field} IS NOT NULL AND {end_field} IS NOT NULL
            """
        ).fetchone()
    return row["value"] if row and row["value"] is not None else None


def summary() -> dict:
    with get_connection() as conn:
        counts = conn.execute(
            """
            SELECT
              SUM(CASE WHEN strftime('%Y-%m', detectedAt) = strftime('%Y-%m', 'now') THEN 1 ELSE 0 END) AS thisMonth,
              SUM(CASE WHEN strftime('%Y', detectedAt) = strftime('%Y', 'now') THEN 1 ELSE 0 END) AS thisYear,
              SUM(CASE WHEN status IN ('confirmed_crash', 'dispatched', 'resolved') THEN 1 ELSE 0 END) AS confirmedCrashes,
              SUM(CASE WHEN status = 'false_alarm' THEN 1 ELSE 0 END) AS falseAlarms,
              COUNT(*) AS totalCases
            FROM crash_cases
            """
        ).fetchone()
    return {
        "detectionsThisMonth": counts["thisMonth"] or 0,
        "detectionsThisYear": counts["thisYear"] or 0,
        "confirmedCrashes": counts["confirmedCrashes"] or 0,
        "falseAlarms": counts["falseAlarms"] or 0,
        "totalCases": counts["totalCases"] or 0,
        "averageReviewTimeSeconds": _avg_seconds("detectedAt", "reviewedAt"),
        "averageResolveTimeSeconds": _avg_seconds("detectedAt", "resolvedAt"),
    }


def monthly_trend() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
              strftime('%Y-%m', detectedAt) AS month,
              COUNT(*) AS detections,
              SUM(CASE WHEN status IN ('confirmed_crash', 'dispatched', 'resolved') THEN 1 ELSE 0 END) AS confirmedCrashes,
              SUM(CASE WHEN status = 'false_alarm' THEN 1 ELSE 0 END) AS falseAlarms
            FROM crash_cases
            GROUP BY month
            ORDER BY month ASC
            """
        ).fetchall()
    return [dict(row) for row in rows]


def cases_by_area() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT coalesce(areaId, location, 'Unassigned') AS area, COUNT(*) AS cases
            FROM crash_cases
            GROUP BY area
            ORDER BY cases DESC
            """
        ).fetchall()
    return [dict(row) for row in rows]
