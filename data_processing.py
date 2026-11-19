"""Lectura y normalización de CSV exportados desde Grafana/InfluxDB."""
from __future__ import annotations

from pathlib import Path
import re
from typing import Iterable

import pandas as pd

ALIASES = {
    "temperature_c": {
        "temperature_c", "temperature", "temperatura", "temp", "temp_c", "temperatura_c"
    },
    "humidity_pct": {
        "humidity_pct", "humidity", "humedad", "relative_humidity", "humedad_relativa", "rh"
    },
    "illumination_lux": {
        "illumination_lux", "illumination", "light_lux", "lux", "iluminacion", "iluminacion_lux", "ldr_lux"
    },
}


def clean_col(value: object) -> str:
    text = str(value).strip().replace(" ", "_").replace("%", "pct")
    text = text.replace("°", "")
    return re.sub(r"[^a-zA-Z0-9_áéíóúÁÉÍÓÚñÑ]+", "", text).lower()


def canonical_field(value: object) -> str | None:
    cleaned = clean_col(value)
    for canonical, aliases in ALIASES.items():
        if cleaned in aliases:
            return canonical
    return None


def find_time_column(df: pd.DataFrame) -> str | None:
    for col in df.columns:
        if clean_col(col) in {"_time", "time", "timestamp", "datetime", "date", "fecha"}:
            return col
    return None


def normalize_one(uploaded_file) -> pd.DataFrame:
    """Normaliza un CSV ancho, largo de InfluxDB o Time/Value de Grafana."""
    raw = pd.read_csv(uploaded_file)
    raw.columns = [str(c).strip() for c in raw.columns]
    if raw.empty:
        return pd.DataFrame(columns=["timestamp"])

    normalized_columns = {clean_col(c): c for c in raw.columns}
    time_col = find_time_column(raw)
    if time_col is None:
        return pd.DataFrame(columns=["timestamp"])

    field_col = normalized_columns.get("_field") or normalized_columns.get("field")
    value_col = normalized_columns.get("_value") or normalized_columns.get("value")

    # Formato largo de InfluxDB: _time, _field, _value.
    if field_col and value_col:
        work = raw[[time_col, field_col, value_col]].copy()
        work[time_col] = pd.to_datetime(work[time_col], errors="coerce", utc=True)
        work[value_col] = pd.to_numeric(work[value_col], errors="coerce")
        work["canonical_field"] = work[field_col].map(canonical_field)
        work = work.dropna(subset=[time_col, value_col, "canonical_field"])
        if work.empty:
            return pd.DataFrame(columns=["timestamp"])
        wide = work.pivot_table(
            index=time_col, columns="canonical_field", values=value_col, aggfunc="mean"
        ).reset_index()
        wide.columns.name = None
        return wide.rename(columns={time_col: "timestamp"})

    frame = raw.copy()
    frame = frame.rename(columns={time_col: "timestamp"})
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="coerce", utc=True)

    # CSV de un panel de Grafana: columnas Time y Value. Inferir la variable
    # únicamente cuando el nombre del archivo lo identifique explícitamente.
    normalized = {clean_col(c): c for c in frame.columns}
    if value_col and not any(canonical_field(c) for c in frame.columns):
        stem = clean_col(Path(getattr(uploaded_file, "name", "")).stem)
        target = None
        if any(token in stem for token in ("temperatura", "temperature", "temp")):
            target = "temperature_c"
        elif any(token in stem for token in ("humedad", "humidity")):
            target = "humidity_pct"
        elif any(token in stem for token in ("iluminacion", "illumination", "light", "ldr", "lux")):
            target = "illumination_lux"
        if target:
            frame[target] = pd.to_numeric(frame[value_col], errors="coerce")

    # Formato ancho: Time + columnas con nombres reales/alias.
    rename: dict[str, str] = {}
    for col in frame.columns:
        target = canonical_field(col)
        if target:
            rename[col] = target
    frame = frame.rename(columns=rename)

    # Evitar nombres duplicados por variaciones de mayúsculas/alias.
    frame = frame.loc[:, ~frame.columns.duplicated()]
    keep = ["timestamp"] + [c for c in ALIASES if c in frame.columns]
    frame = frame[keep]
    for col in keep:
        if col != "timestamp":
            frame[col] = pd.to_numeric(frame[col], errors="coerce")
    return frame.dropna(subset=["timestamp"])


def load_files(files: Iterable) -> pd.DataFrame:
    frames = [normalize_one(file) for file in files]
    frames = [frame for frame in frames if not frame.empty and "timestamp" in frame.columns]
    if not frames:
        return pd.DataFrame(columns=["timestamp"])

    indexed = [frame.set_index("timestamp") for frame in frames]
    # Si varios CSV contienen la misma variable, conserva el primer valor no nulo.
    result = pd.concat(indexed, axis=1).sort_index()
    result = result.T.groupby(level=0, sort=False).first().T
    result = result.reset_index()
    result.columns.name = None
    for col in ALIASES:
        if col in result.columns:
            result[col] = pd.to_numeric(result[col], errors="coerce")
    return result.dropna(subset=["timestamp"])
