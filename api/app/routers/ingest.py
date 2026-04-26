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

    Calls ocr-service to extract text, then parses as receipt.
    """
    try:
        from app.services.ocr_client import OCRClient
        from app.parsers.receipt_parser import parse_receipt

        # Read image file
        image_bytes = await file.read()

        # Call OCR service
        ocr_client = OCRClient()
        ocr_result = await ocr_client.extract_text(image_bytes)
        ocr_text = ocr_result.get("text", "")

        if not ocr_text:
            return IngestResponse(
                status="rejected",
                user_message="❌ No pude leer la boleta. Intenta con otra imagen.",
                confidence=0.0,
                parse_method="ocr",
            )

        # Parse receipt
        parsed = parse_receipt(ocr_text)

        if not parsed.amount:
            return IngestResponse(
                status="rejected",
                user_message="❌ No logré detectar el total. Intenta con otra boleta.",
                confidence=0.0,
                parse_method="ocr",
            )

        # Create RawMessage audit record
        raw_msg = RawMessage(
            user_id=user_id,
            type="image",
            content=f"OCR: {ocr_text[:200]}...",
            intent="finance",
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
            note=parsed.merchant_hint,
            source="image",
            confidence=Decimal(parsed.confidence),
            raw_msg_id=raw_msg.id,
        )
        db.add(expense)
        db.commit()
        db.refresh(expense)

        # Generate user message
        category_str = category_name or "Otros"
        amount_fmt = f"{parsed.amount:,.0f}".replace(",", ".")
        user_message = f"✅ Boleta registrada: {category_str} — CLP {amount_fmt}"

        return IngestResponse(
            status="registered",
            expense_id=expense.id,
            amount=parsed.amount,
            currency=parsed.currency,
            category=category_name,
            confidence=parsed.confidence,
            user_message=user_message,
            parse_method="ocr",
        )

    except Exception as e:
        return IngestResponse(
            status="rejected",
            user_message=f"❌ Error procesando boleta: {str(e)[:50]}",
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

    Calls whisper-service to transcribe, then parses as text.
    """
    try:
        from app.services.whisper_client import WhisperClient
        from app.parsers.audio_parser import parse_audio_transcript

        # Read audio file
        audio_bytes = await file.read()

        # Call Whisper service
        whisper_client = WhisperClient()
        whisper_result = await whisper_client.transcribe(audio_bytes, language="es")
        transcript = whisper_result.get("text", "")

        if not transcript:
            return IngestResponse(
                status="rejected",
                user_message="❌ No pude entender el audio. Intenta nuevamente.",
                confidence=0.0,
                parse_method="audio",
            )

        # Parse transcript
        parsed = parse_audio_transcript(transcript)

        if not parsed.amount:
            return IngestResponse(
                status="rejected",
                user_message="❌ No detecté un monto en el audio.",
                confidence=0.0,
                parse_method="audio",
            )

        # Create RawMessage audit record
        raw_msg = RawMessage(
            user_id=user_id,
            type="audio",
            transcript=transcript,
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
            note=parsed.note,
            source="audio",
            confidence=Decimal(parsed.confidence),
            raw_msg_id=raw_msg.id,
        )
        db.add(expense)
        db.commit()
        db.refresh(expense)

        # Generate user message
        category_str = category_name or "Otros"
        amount_fmt = f"{parsed.amount:,.0f}".replace(",", ".")
        user_message = f"✅ Audio registrado: {category_str} — CLP {amount_fmt}"

        return IngestResponse(
            status="registered",
            expense_id=expense.id,
            amount=parsed.amount,
            currency=parsed.currency,
            category=category_name,
            confidence=parsed.confidence,
            user_message=user_message,
            parse_method="audio",
        )

    except Exception as e:
        return IngestResponse(
            status="rejected",
            user_message=f"❌ Error procesando audio: {str(e)[:50]}",
            confidence=0.0,
            parse_method="audio",
        )
