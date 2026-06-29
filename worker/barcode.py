"""SII TED PDF417 barcode decode (token-free ground truth).

zxing-cpp for PDF417 (pyzbar/zbar CANNOT read PDF417). Returns verified header
fields parsed from the <TED>/<DD> XML, or None. See docs/02-chile-sii-dte.md.
"""
from __future__ import annotations

from dataclasses import dataclass

from normalize import format_rut


@dataclass
class TED:
    rut_emisor: str | None = None      # RE
    tipo_dte: int | None = None        # TD (39/41/33/34)
    folio: str | None = None           # F
    issued_date: str | None = None     # FE (YYYY-MM-DD)
    rut_receptor: str | None = None    # RR
    merchant_name: str | None = None   # RSR
    total: int | None = None           # MNT
    first_item: str | None = None      # IT1


def _text(dd, tag):
    el = dd.find(tag)
    return el.text.strip() if el is not None and el.text else None


def parse_ted_xml(xml: str) -> TED | None:
    from lxml import etree

    data = xml.encode() if isinstance(xml, str) else xml
    # TED payload is untrusted (decoded from a user-submitted photo). SII TED
    # never contains a DTD/entities, so harden the parser against XXE and reject
    # any DOCTYPE/ENTITY outright.
    if b"<!DOCTYPE" in data or b"<!ENTITY" in data:
        return None
    parser = etree.XMLParser(
        resolve_entities=False, no_network=True, load_dtd=False,
        dtd_validation=False, huge_tree=False,
    )
    try:
        root = etree.fromstring(data, parser=parser)
    except etree.XMLSyntaxError:
        return None
    dd = root.find("DD")
    if dd is None:
        return None
    re_ = _text(dd, "RE")
    rr_ = _text(dd, "RR")
    td = _text(dd, "TD")
    mnt = _text(dd, "MNT")
    return TED(
        rut_emisor=format_rut(re_) if re_ else None,
        rut_receptor=format_rut(rr_) if rr_ else None,
        tipo_dte=int(td) if td and td.isdigit() else None,
        folio=_text(dd, "F"),
        issued_date=_text(dd, "FE"),
        merchant_name=_text(dd, "RSR"),
        total=int(mnt) if mnt and mnt.isdigit() else None,
        first_item=_text(dd, "IT1"),
    )


def decode_ted(gray_image) -> TED | None:
    """Find the PDF417 timbre and parse it. gray_image = numpy uint8."""
    try:
        import zxingcpp
    except Exception:
        return None
    try:
        results = zxingcpp.read_barcodes(gray_image)
    except Exception:
        return None
    for r in results:
        if r.format == zxingcpp.BarcodeFormat.PDF417 and r.text:
            ted = parse_ted_xml(r.text)
            if ted:
                return ted
    return None
