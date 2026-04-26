"""Ingest endpoints for expenses (text, image, audio)."""

from decimal import Decimal

from fastapi import APIRouter, Depends, File, Form, Header, UploadFile, HTTPException
from sqlalchemy.orm import Session

from app.classifiers.intent_detector import is_finance_intent
from app.db import get_db
from app.deps import verify_internal_key
from app.models import Category, Expense, RawMessage
from app.parsers.text_parser import parse_expense_text
from app.schemas.expense import IngestResponse, IntentCheckRequest, IntentCheckResponse

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("/intent/check", response_model=IntentCheckResponse)
async def check_intent(
    request: IntentCheckRequest,
    x_internal_key: str = Depends(verify_internal_key),
) -> IntentCheckResponse:
    """
    Check if text contains financial intent.

    Used by Kraken to decide whether to delegate to Fortunia.
    """
    result = is_finance_intent(request.text)
    return IntentCheckResponse(
        is_finance=result.is_finance,
        confidence=result.confidence,
        needs_llm=result.needs_llm,
        reason=result.reason,
    )


@router.post("/text", response_model=IngestResponse)
async def ingest_text(
    text: str = Form(...),
    user_id: str = Form(default="user"),
    msg_id: str = Form(default=None),
    db: Session = Depends(get_db),
    x_internal_key: str = Depends(verify_internal_key),
) -> IngestResponse:
    """
    Ingest expense from text.

    Example:
        POST /ingest/text
        text=gasté 15 lucas en ropa
        user_id=user
        msg_id=tg_123456
    """
    # Parse text
    parsed = parse_expense_text(text)

    if not parsed.amount:
        return IngestResponse(
            status="rejected",
            user_message="❌ No logré detectar un monto. Ej: 'gasté 15 lucas en ropa'",
            confidence=0.0,
        )

    # Create RawMessage audit record
    raw_msg = RawMessage(
        user_id=user_id,
        telegram_id=msg_id,
        type="text",
        content=text,
        intent="finance" if parsed.amount else "unknown",
        intent_conf=Decimal(parsed.confidence),
        used_llm=False,
    )
    db.add(raw_msg)
    db.flush()

    # Resolve category
    category_id = None
    category_name = None
    if parsed.category_hint:
        category = db.query(Category).filter_by(name=parsed.category_hint).first()
        if category:
            category_id = category.id
            category_name = category.name

    # Create Expense
    expense = Expense(
        user_id=user_id,
        amount=parsed.amount,
        currency=parsed.currency,
        category_id=category_id,
        spent_at=None,  # Use current time
        note=parsed.note,
        source="text",
        confidence=Decimal(parsed.confidence),
        raw_msg_id=raw_msg.id,
    )
    db.add(expense)
    db.commit()
    db.refresh(expense)

    # Generate user message for Telegram
    category_str = category_name or "Otros"
    amount_fmt = f"{parsed.amount:,.0f}".replace(",", ".")
    user_message = f"✅ Registrado: {category_str} — CLP {amount_fmt}"

    return IngestResponse(
        status="registered",
        expense_id=expense.id,
        amount=parsed.amount,
        currency=parsed.currency,
        category=category_name,
        confidence=parsed.confidence,
        user_message=user_message,
        parse_method=parsed.parse_method,
    )


@router.post("/image", response_model=IngestResponse)
async def ingest_image(
    file: UploadFile = File(...),
    user_id: str = Form(default="user"),
    caption: str = Form(default=None),
    db: Session = Depends(get_db),
    x_internal_key: str = Depends(verify_internal_key),
) -> IngestResponse:
    """
    Ingest expense from receipt image (OCR + parse).

    Currently a stub; in ETAPA 6 integrate with ocr-service.
    """
    return IngestResponse(
        status="needs_confirmation",
        user_message="📸 Procesando boleta... (función en desarrollo)",
        confidence=0.0,
        parse_method="ocr",
    )


@router.post("/audio", response_model=IngestResponse)
async def ingest_audio(
    file: UploadFile = File(...),
    user_id: str = Form(default="user"),
    db: Session = Depends(get_db),
    x_internal_key: str = Depends(verify_internal_key),
) -> IngestResponse:
    """
    Ingest expense from audio (Whisper STT + parse).

    Currently a stub; in ETAPA 6 integrate with whisper-service.
    """
    return IngestResponse(
        status="needs_confirmation",
        user_message="🎙️ Procesando audio... (función en desarrollo)",
        confidence=0.0,
        parse_method="audio",
    )
