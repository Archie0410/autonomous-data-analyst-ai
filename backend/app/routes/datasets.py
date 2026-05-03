"""Dataset upload + browse endpoints."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.models.schemas import DatasetDetail, DatasetSummary
from app.services import ingestion
from app.services.database import get_session
from app.utils.logger import logger

router = APIRouter(prefix="/api/datasets", tags=["datasets"])


@router.post("/upload", response_model=DatasetDetail)
async def upload_dataset(
    file: UploadFile = File(...),
    name: str | None = Form(default=None),
    db: Session = Depends(get_session),
) -> DatasetDetail:
    if not file.filename or not file.filename.lower().endswith((".csv", ".tsv", ".txt")):
        raise HTTPException(400, "Only CSV/TSV files are supported.")
    try:
        detail = ingestion.ingest_csv(
            db=db, file_obj=file.file, filename=file.filename, display_name=name,
        )
    except Exception as e:  # noqa: BLE001
        logger.exception("Upload failed")
        raise HTTPException(400, f"Failed to ingest CSV: {e}")
    return detail


@router.get("", response_model=List[DatasetSummary])
def list_datasets(db: Session = Depends(get_session)) -> List[DatasetSummary]:
    rows = ingestion.list_datasets(db)
    return [
        DatasetSummary(
            id=r.id,
            name=r.name,
            table_name=r.table_name,
            original_filename=r.original_filename,
            row_count=r.row_count,
            column_count=r.column_count,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.get("/{dataset_id}", response_model=DatasetDetail)
def get_dataset(dataset_id: int, db: Session = Depends(get_session)) -> DatasetDetail:
    detail = ingestion.get_dataset_detail(db, dataset_id)
    if not detail:
        raise HTTPException(404, "Dataset not found")
    return detail
