# 06 — References

Sources gathered during discovery (2026-06-27). Licenses/maintenance verified against PyPI + GitHub.

## Parsing libraries
- invoice2data — https://github.com/invoice-x/invoice2data
- invoice2data lines parser — https://raw.githubusercontent.com/invoice-x/invoice2data/master/src/invoice2data/extract/parsers/lines.py
- invoice2data migration 1.0 — https://raw.githubusercontent.com/invoice-x/invoice2data/master/docs/migration-1.0.md
- receipt-parser — https://github.com/mre/receipt-parser
- receipt-parser-server — https://github.com/ReceiptManager/receipt-parser-server
- Camelot — https://github.com/camelot-dev/camelot
- tabula-py — https://github.com/chezou/tabula-py

## OCR engines
- PaddleOCR — https://github.com/PaddlePaddle/PaddleOCR
- ocrmac (Apple Vision) — https://github.com/straussmaximilian/ocrmac
- EasyOCR — https://github.com/JaidedAI/EasyOCR · https://www.jaided.ai/easyocr/
- docTR — https://github.com/mindee/doctr
- Tesseract — https://github.com/tesseract-ocr/tesseract
- Tesseract ImproveQuality — https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html
- OCRmyPDF — https://github.com/ocrmypdf/OCRmyPDF

## Extraction helpers
- price-parser — https://github.com/scrapinghub/price-parser
- dateparser — https://dateparser.readthedocs.io/en/latest/
- Tesseract+OpenCV invoice OCR — https://pyimagesearch.com/2020/09/07/ocr-a-document-form-or-invoice-with-tesseract-opencv-and-python/
- OCR with Tesseract (Nanonets) — https://nanonets.com/blog/ocr-with-tesseract/

## Image preprocessing
- pyimagesearch document scanner — https://pyimagesearch.com/2014/09/01/build-kick-ass-mobile-document-scanner-just-5-minutes/
- 4-point perspective transform — https://pyimagesearch.com/2014/08/25/4-point-opencv-getperspective-transform-example/
- sbrunner/deskew — https://github.com/sbrunner/deskew
- jdeskew — https://github.com/phamquiluan/jdeskew
- Sauvola/Niblack thresholding — https://scikit-image.org/docs/stable/auto_examples/segmentation/plot_niblack_sauvola.html
- OpenCV histogram equalization (CLAHE) — https://docs.opencv.org/4.x/d5/daf/tutorial_py_histogram_equalization.html

## Local models
- Donut (CORD-v2) — https://huggingface.co/naver-clova-ix/donut-base-finetuned-cord-v2 · https://github.com/clovaai/donut
- Donut in Transformers — https://huggingface.co/docs/transformers/en/model_doc/donut
- LayoutLMv3 — https://huggingface.co/microsoft/layoutlmv3-base
- Table Transformer — https://huggingface.co/microsoft/table-transformer-structure-recognition
- Ollama vision models — https://ollama.com/library/qwen2.5vl · https://ollama.com/library/deepseek-ocr · https://ollama.com/library/minicpm-v

## Chile SII / DTE / barcode
- PDF417 — https://en.wikipedia.org/wiki/PDF417
- zxing-cpp — https://pypi.org/project/zxing-cpp/ · https://github.com/zxing-cpp/zxing-cpp
- pdf417decoder — https://pypi.org/project/pdf417decoder/
- pyzbar — https://github.com/NaturalHistoryMuseum/pyzbar
- zbar (cannot decode PDF417) — https://github.com/mchehab/zbar
- cl-sii — https://pypi.org/project/cl-sii/ · https://github.com/fyntex/lib-cl-sii-python
- cl-sii DTE parse — https://raw.githubusercontent.com/fyntex/lib-cl-sii-python/develop/src/cl_sii/dte/parse.py

## Personal-finance schema references
- Actual Budget schema — https://raw.githubusercontent.com/actualbudget/actual/master/packages/loot-core/src/server/aql/schema/index.ts
- Maybe Finance schema — https://raw.githubusercontent.com/maybe-finance/maybe/main/db/schema.rb
- Maybe models — transaction.rb / merchant.rb / category.rb / rule/condition.rb (same repo)
- Firefly III TransactionJournal — https://raw.githubusercontent.com/firefly-iii/firefly-iii/main/app/Models/TransactionJournal.php

## Infra
- python:3.12-slim-bookworm (avoid alpine for OpenCV/numpy wheels)
- postgres:16 · pgAdmin 4 · Metabase (optional)
- python-telegram-bot · FastAPI · uvicorn · httpx · psycopg
