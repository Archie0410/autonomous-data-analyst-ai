"""
CSV ingestion service.

Responsibilities:
  1. Save uploaded file to disk.
  2. Read with pandas, auto-detect dtypes.
  3. Sanitize column names so they are SQL-safe.
  4. Persist as a dedicated table inside the SQLite database (one table per dataset).
  5. Register metadata in `datasets`.
  6. Add a textual schema description to the FAISS vector store for retrieval.
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import IO, Any, Dict, List

import pandas as pd
from sqlalchemy.orm import Session

from app.config import settings
from app.models.db_models import Dataset
from app.models.schemas import ColumnInfo, DatasetDetail
from app.services.database import get_engine
from app.services.vector_store import vector_store
from app.utils.json_safe import to_json_safe
from app.utils.logger import logger

_SLUG_RE = re.compile(r"[^a-zA-Z0-9_]+")


def _slugify(name: str) -> str:
    cleaned = _SLUG_RE.sub("_", name.strip()).strip("_").lower()
    if not cleaned:
        cleaned = "col"
    if cleaned[0].isdigit():
        cleaned = f"c_{cleaned}"
    return cleaned[:60]


def _unique_table_name(base: str) -> str:
    base = _slugify(base)
    suffix = uuid.uuid4().hex[:6]
    return f"ds_{base}_{suffix}"


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Make column names SQL-safe and unique while preserving order."""
    seen: Dict[str, int] = {}
    new_cols: List[str] = []
    for c in df.columns:
        slug = _slugify(str(c))
        if slug in seen:
            seen[slug] += 1
            slug = f"{slug}_{seen[slug]}"
        else:
            seen[slug] = 0
        new_cols.append(slug)
    df = df.copy()
    df.columns = new_cols
    return df


def _read_csv(file_obj: IO[bytes], filename: str) -> pd.DataFrame:
    """Robust CSV reader that tries multiple encodings and separators."""
    raw = file_obj.read()

    last_err: Exception | None = None
    for encoding in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
        for sep in (None, ",", ";", "\t", "|"):
            try:
                from io import BytesIO

                df = pd.read_csv(
                    BytesIO(raw),
                    encoding=encoding,
                    sep=sep,
                    engine="python" if sep is None else "c",
                    on_bad_lines="skip",
                    low_memory=False,
                )
                if df.shape[1] > 0:
                    logger.info(
                        "Read CSV {} encoding={} sep={!r} shape={}",
                        filename,
                        encoding,
                        sep,
                        df.shape,
                    )
                    return df
            except Exception as e:  # noqa: BLE001
                last_err = e
                continue
    raise ValueError(f"Could not parse CSV file {filename}: {last_err}")


def _column_info(df: pd.DataFrame) -> List[ColumnInfo]:
    out: List[ColumnInfo] = []
    for col in df.columns:
        s = df[col]
        sample_vals = (
            s.dropna().head(5).tolist() if s.dropna().shape[0] > 0 else []
        )
        out.append(
            ColumnInfo(
                name=str(col),
                dtype=str(s.dtype),
                sample_values=to_json_safe(sample_vals),
                null_count=int(s.isna().sum()),
            )
        )
    return out


def ingest_csv(
    db: Session,
    file_obj: IO[bytes],
    filename: str,
    display_name: str | None = None,
) -> DatasetDetail:
    """End-to-end CSV ingestion. Returns a `DatasetDetail` with preview + schema."""
    df = _read_csv(file_obj, filename)
    df = _normalize_columns(df)

    table_name = _unique_table_name(Path(filename).stem)
    name = display_name or Path(filename).stem

    save_path = Path(settings.upload_dir) / f"{table_name}.csv"
    df.to_csv(save_path, index=False)
    logger.info("Saved upload to {}", save_path)

    engine = get_engine()
    df.to_sql(table_name, engine, if_exists="replace", index=False)
    logger.info("Wrote {} rows into table {}", len(df), table_name)

    cols = _column_info(df)
    schema_json = {c.name: c.dtype for c in cols}

    ds = Dataset(
        name=name,
        table_name=table_name,
        original_filename=filename,
        row_count=int(df.shape[0]),
        column_count=int(df.shape[1]),
        schema_json=schema_json,
    )
    db.add(ds)
    db.commit()
    db.refresh(ds)

    schema_doc = _format_schema_doc(name, table_name, cols)
    try:
        vector_store.add_dataset_schema(ds.id, schema_doc)
    except Exception as e:  # noqa: BLE001
        logger.warning("Vector store add failed (non-fatal): {}", e)

    preview = to_json_safe(df.head(10))

    return DatasetDetail(
        id=ds.id,
        name=ds.name,
        table_name=ds.table_name,
        original_filename=ds.original_filename,
        row_count=ds.row_count,
        column_count=ds.column_count,
        created_at=ds.created_at,
        columns=cols,
        preview=preview,
    )


def _format_schema_doc(name: str, table_name: str, cols: List[ColumnInfo]) -> str:
    lines = [f"Dataset: {name}", f"Table: {table_name}", "Columns:"]
    for c in cols:
        sample = ", ".join(repr(v) for v in c.sample_values[:3])
        lines.append(f"  - {c.name} ({c.dtype}) e.g. {sample}")
    return "\n".join(lines)


def get_dataset_detail(db: Session, dataset_id: int) -> DatasetDetail | None:
    ds = db.get(Dataset, dataset_id)
    if not ds:
        return None
    engine = get_engine()
    df = pd.read_sql_table(ds.table_name, engine).head(50)
    cols = _column_info(df)
    return DatasetDetail(
        id=ds.id,
        name=ds.name,
        table_name=ds.table_name,
        original_filename=ds.original_filename,
        row_count=ds.row_count,
        column_count=ds.column_count,
        created_at=ds.created_at,
        columns=cols,
        preview=to_json_safe(df.head(10)),
    )


def list_datasets(db: Session) -> List[Dataset]:
    return db.query(Dataset).order_by(Dataset.created_at.desc()).all()


def get_schema_summary(db: Session, dataset_id: int) -> str:
    """Compact textual schema used in LLM prompts."""
    ds = db.get(Dataset, dataset_id)
    if not ds:
        return ""
    engine = get_engine()
    df = pd.read_sql_table(ds.table_name, engine)
    cols = _column_info(df)
    return _format_schema_doc(ds.name, ds.table_name, cols)
