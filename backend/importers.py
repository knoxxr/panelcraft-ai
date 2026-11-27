"""Zero-dependency importers for Excel (.xlsx), CSV, and RFP PDF/TXT files."""

from __future__ import annotations

import csv
import io
import re
import uuid
import zipfile
import zlib
import xml.etree.ElementTree as ET
from typing import Any

from backend.models import CustomCatalogItem, LoadUnit


# ---------------------------------------------------------------------------
# Generic Excel (.xlsx) & CSV Tabular Reader
# ---------------------------------------------------------------------------

def _col_letters_to_index(col_ref: str) -> int:
    letters = "".join(ch for ch in col_ref if ch.isalpha()).upper()
    idx = 0
    for ch in letters:
        idx = idx * 26 + (ord(ch) - ord("A") + 1)
    return max(0, idx - 1)


def read_xlsx_rows(data: bytes) -> list[list[str]]:
    """Parse first worksheet of an .xlsx file using Python standard library only."""
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in zf.namelist():
            root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
            for si in root.findall("m:si", ns):
                texts = [t.text or "" for t in si.iter() if t.tag.endswith("}t")]
                shared_strings.append("".join(texts))

        sheet_candidates = sorted(
            n for n in zf.namelist() if n.startswith("xl/worksheets/sheet") and n.endswith(".xml")
        )
        if not sheet_candidates:
            return []

        sheet_root = ET.fromstring(zf.read(sheet_candidates[0]))
        rows: list[list[str]] = []
        for row_el in sheet_root.iter():
            if not row_el.tag.endswith("}row"):
                continue
            row_map: dict[int, str] = {}
            max_col = -1
            for c_el in row_el:
                if not c_el.tag.endswith("}c"):
                    continue
                ref = c_el.attrib.get("r", "")
                col_idx = _col_letters_to_index(ref) if ref else (max_col + 1)
                max_col = max(max_col, col_idx)
                cell_type = c_el.attrib.get("t", "")

                val = ""
                if cell_type == "inlineStr":
                    val = "".join(t.text or "" for t in c_el.iter() if t.tag.endswith("}t"))
                else:
                    v_el = next((ch for ch in c_el if ch.tag.endswith("}v")), None)
                    if v_el is not None and v_el.text is not None:
                        if cell_type == "s":
                            s_idx = int(v_el.text)
                            val = shared_strings[s_idx] if 0 <= s_idx < len(shared_strings) else ""
                        else:
                            val = v_el.text
                row_map[col_idx] = val.strip()

            if max_col >= 0:
                row_vals = [row_map.get(i, "") for i in range(max_col + 1)]
                if any(cell != "" for cell in row_vals):
                    rows.append(row_vals)
        return rows


def read_tabular_rows(filename: str, data: bytes) -> list[list[str]]:
    """Read rows from .xlsx or .csv (UTF-8 / UTF-8-BOM / CP949)."""
    lower = filename.lower()
    if lower.endswith(".xlsx") or data[:2] == b"PK":
        return read_xlsx_rows(data)

    text: str | None = None
    for enc in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
        try:
            text = data.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        text = data.decode("utf-8", errors="replace")

    reader = csv.reader(io.StringIO(text))
    return [[cell.strip() for cell in row] for row in reader if any(c.strip() for c in row)]


# ---------------------------------------------------------------------------
# Load Schedule Importer (Excel / CSV -> list[LoadUnit])
# ---------------------------------------------------------------------------

LOAD_TYPE_ALIASES: dict[str, str] = {
    "motor_inv": "motor_inv",
    "inv": "motor_inv",
    "vfd": "motor_inv",
    "인버터": "motor_inv",
    "인버터모터": "motor_inv",
    "motor_dol": "motor_dol",
    "dol": "motor_dol",
    "motor": "motor_dol",
    "직입": "motor_dol",
    "직입모터": "motor_dol",
    "모터": "motor_dol",
    "servo": "servo",
    "서보": "servo",
    "서보축": "servo",
    "heater": "heater",
    "히터": "heater",
    "solenoid_group": "solenoid_group",
    "solenoid": "solenoid_group",
    "솔레노이드": "solenoid_group",
    "밸브": "solenoid_group",
    "sensor_group": "sensor_group",
    "sensor": "sensor_group",
    "센서": "sensor_group",
    "safety_circuit": "safety_circuit",
    "safety": "safety_circuit",
    "안전": "safety_circuit",
    "안전회로": "safety_circuit",
    "비상정지": "safety_circuit",
}


def _find_col(headers: list[str], candidates: list[str]) -> int:
    norm = [h.lower().replace(" ", "").replace("_", "") for h in headers]
    for cand in candidates:
        c = cand.lower().replace(" ", "").replace("_", "")
        for i, h in enumerate(norm):
            if c in h:
                return i
    return -1


def _to_float(val: str, default: float) -> float:
    cleaned = re.sub(r"[^0-9.\-]", "", val or "")
    try:
        return float(cleaned) if cleaned else default
    except ValueError:
        return default


def _to_int(val: str, default: int) -> int:
    return int(round(_to_float(val, float(default))))


def parse_loads_file(filename: str, data: bytes) -> tuple[list[LoadUnit], int, list[str]]:
    """Parse an Excel/CSV load schedule into SSOT LoadUnit records."""
    rows = read_tabular_rows(filename, data)
    if len(rows) < 2:
        return [], 0, ["헤더와 데이터 행이 최소 2줄 이상 필요합니다."]

    headers = rows[0]
    i_tag = _find_col(headers, ["tag", "태그", "기기태그", "unit"])
    i_name = _find_col(headers, ["name", "부하명", "유닛명", "명칭", "설명"])
    i_type = _find_col(headers, ["type", "loadtype", "유형", "구분", "종류"])
    i_kw = _find_col(headers, ["kw", "power", "용량"])
    i_qty = _find_col(headers, ["qty", "quantity", "수량", "대수", "점수"])
    i_volt = _find_col(headers, ["volt", "전압"])
    i_cable = _find_col(headers, ["cable", "length", "케이블", "거리"])
    i_saf = _find_col(headers, ["safety", "pl", "안전등급"])

    units: list[LoadUnit] = []
    skipped = 0
    warnings: list[str] = []

    for r_idx, row in enumerate(rows[1:], start=2):
        def cell(idx: int) -> str:
            return row[idx].strip() if 0 <= idx < len(row) else ""

        raw_type = cell(i_type).lower().replace(" ", "")
        mapped_type = LOAD_TYPE_ALIASES.get(raw_type)
        if not mapped_type:
            # Fuzzy fallback on Korean keywords
            for k, v in LOAD_TYPE_ALIASES.items():
                if k in raw_type or k in cell(i_name).lower():
                    mapped_type = v
                    break
        if not mapped_type:
            skipped += 1
            warnings.append(f"{r_idx}행 건너뜀: 인식할 수 없는 부하 유형 '{cell(i_type)}'")
            continue

        tag = cell(i_tag) or f"UNIT_{r_idx - 1:02d}"
        name = cell(i_name) or tag
        qty = max(1, _to_int(cell(i_qty), 1))
        kw = max(0.0, _to_float(cell(i_kw), 0.0 if mapped_type in ("solenoid_group", "sensor_group", "safety_circuit") else 1.5))
        cable = max(1.0, _to_float(cell(i_cable), 15.0))

        if mapped_type in ("solenoid_group", "sensor_group", "safety_circuit"):
            volt, phases = 24, 0
        elif mapped_type == "servo":
            volt = _to_int(cell(i_volt), 220)
            phases = 3 if kw >= 1.5 else 1
        else:
            volt = _to_int(cell(i_volt), 380)
            phases = 1 if volt == 220 and kw < 1.5 else 3

        saf_raw = cell(i_saf).upper()
        safety_level = None
        if mapped_type == "safety_circuit":
            safety_level = "PLe" if "PLE" in saf_raw else ("PLc" if "PLC" in saf_raw else "PLd")

        units.append(
            LoadUnit(
                id=f"imp_{uuid.uuid4().hex[:6]}",
                tag=tag,
                name=name,
                load_type=mapped_type,  # type: ignore[arg-type]
                power_kw=kw,
                quantity=qty,
                voltage=volt,
                phases=phases,
                cable_length_m=cable,
                power_factor=1.0 if mapped_type == "heater" else 0.85,
                efficiency=1.0 if mapped_type == "heater" else 0.88,
                safety_level=safety_level,  # type: ignore[arg-type]
            )
        )

    return units, skipped, warnings


# ---------------------------------------------------------------------------
# Company Custom Component Catalog Importer (Excel / CSV)
# ---------------------------------------------------------------------------

CAT_ALIASES: dict[str, str] = {
    "mccb": "MCCB",
    "차단기": "MCCB",
    "breaker": "MCCB",
    "mc": "MC",
    "접촉기": "MC",
    "전자접촉기": "MC",
    "contactor": "MC",
    "inverter": "INVERTER",
    "vfd": "INVERTER",
    "인버터": "INVERTER",
    "servo": "SERVO",
    "서보": "SERVO",
    "smps": "SMPS",
    "전원공급기": "SMPS",
}


def parse_catalog_file(filename: str, data: bytes) -> tuple[list[CustomCatalogItem], list[str]]:
    """Parse an Excel/CSV company parts database into CustomCatalogItem list."""
    rows = read_tabular_rows(filename, data)
    if len(rows) < 2:
        return [], ["헤더와 부품 데이터 행이 최소 2줄 이상 필요합니다."]

    headers = rows[0]
    i_cat = _find_col(headers, ["category", "분류", "카테고리", "품목"])
    i_mfr = _find_col(headers, ["manufacturer", "vendor", "제조사", "메이커"])
    i_pn = _find_col(headers, ["partnumber", "partno", "pn", "파트넘버", "형명", "모델명"])
    i_rate = _find_col(headers, ["rated", "정격", "용량", "전류", "kw", "amp"])
    i_spec = _find_col(headers, ["spec", "규격", "사양", "설명"])
    i_price = _find_col(headers, ["price", "단가", "가격", "krw"])
    i_lead = _find_col(headers, ["lead", "납기"])

    items: list[CustomCatalogItem] = []
    warnings: list[str] = []

    for r_idx, row in enumerate(rows[1:], start=2):
        def cell(idx: int) -> str:
            return row[idx].strip() if 0 <= idx < len(row) else ""

        raw_cat = cell(i_cat).lower().replace(" ", "")
        cat = CAT_ALIASES.get(raw_cat)
        if not cat:
            for k, v in CAT_ALIASES.items():
                if k in raw_cat:
                    cat = v
                    break
        pn = cell(i_pn)
        if not cat or not pn:
            warnings.append(f"{r_idx}행 건너뜀: 분류({cell(i_cat)}) 또는 파트넘버({pn}) 누락")
            continue

        rated = _to_float(cell(i_rate), 0.0)
        if rated <= 0:
            warnings.append(f"{r_idx}행 건너뜀: 정격값(A 또는 kW)이 0 이하입니다 ({pn})")
            continue

        mfr = cell(i_mfr) or "사내표준"
        spec = cell(i_spec) or f"{mfr} {cat} {rated}"
        price = max(0, _to_int(cell(i_price), 50000))
        lead = max(0, _to_int(cell(i_lead), 3))

        items.append(
            CustomCatalogItem(
                id=f"CUST-{cat}-{re.sub(r'[^A-Za-z0-9]', '', pn)[:16]}",
                category=cat,  # type: ignore[arg-type]
                manufacturer=mfr,
                part_number=pn,
                rated_value=rated,
                spec=spec,
                unit_price_krw=price,
                lead_time_days=lead,
            )
        )

    return items, warnings


# ---------------------------------------------------------------------------
# Pure-Python RFP PDF & Text Extractor
# ---------------------------------------------------------------------------

def _decode_pdf_literal(raw: bytes) -> str:
    """Decode PDF string literal bytes handling basic escapes and UTF-16BE BOM."""
    out = bytearray()
    i = 0
    n = len(raw)
    while i < n:
        b = raw[i]
        if b == 92 and i + 1 < n:  # backslash
            nxt = raw[i + 1]
            if nxt in (ord("n"), ord("r"), ord("t")):
                out.append(ord(" "))
                i += 2
                continue
            if nxt in (ord("("), ord(")"), 92):
                out.append(nxt)
                i += 2
                continue
            i += 2
            continue
        out.append(b)
        i += 1
    if out.startswith(b"\xfe\xff"):
        return out[2:].decode("utf-16-be", errors="ignore")
    try:
        return out.decode("utf-8")
    except UnicodeDecodeError:
        return out.decode("cp949", errors="ignore")


def extract_pdf_text(data: bytes) -> str:
    """Extract readable text from PDF streams (uncompressed & FlateDecode) without external libraries."""
    if not data.lstrip().startswith(b"%PDF"):
        # Plain text / markdown RFP file
        for enc in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
            try:
                return data.decode(enc)
            except UnicodeDecodeError:
                continue
        return data.decode("utf-8", errors="ignore")

    chunks: list[str] = []

    # 1. Inspect every stream ... endstream block
    for m in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", data, re.DOTALL):
        stream_bytes = m.group(1)
        candidates = [stream_bytes]
        try:
            candidates.insert(0, zlib.decompress(stream_bytes))
        except zlib.error:
            pass

        for content in candidates:
            if b"Tj" not in content and b"TJ" not in content:
                continue
            # Extract parenthesized text tokens inside Tj / TJ operators
            for lit in re.finditer(rb"\(([^()\\]*(?:\\.[^()\\]*)*)\)", content):
                txt = _decode_pdf_literal(lit.group(1)).strip()
                if txt:
                    chunks.append(txt)
            # Extract UTF-16BE hex strings <FEFF...>
            for hx in re.finditer(rb"<([0-9A-Fa-f]{4,})>", content):
                try:
                    raw_hex = bytes.fromhex(hx.group(1).decode("ascii"))
                    if raw_hex.startswith(b"\xfe\xff"):
                        txt = raw_hex[2:].decode("utf-16-be", errors="ignore").strip()
                    else:
                        txt = raw_hex.decode("utf-8", errors="ignore").strip()
                    if txt and any(ch.isalnum() for ch in txt):
                        chunks.append(txt)
                except Exception:
                    continue
            break

    extracted = " ".join(chunks)
    extracted = re.sub(r"\s+", " ", extracted).strip()
    return extracted


# ---------------------------------------------------------------------------
# Downloadable CSV Templates
# ---------------------------------------------------------------------------

def export_load_template_csv() -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["태그(Tag)", "부하명(Name)", "유형(Type)", "용량(kW)", "수량(Qty)", "전압(V)", "케이블길이(m)", "안전등급(PL)"])
    w.writerow(["CONV_01", "메인 컨베이어 인버터", "인버터", "1.5", "4", "380", "20", ""])
    w.writerow(["LIFT_01", "리프트 서보 축", "서보", "0.75", "2", "220", "15", ""])
    w.writerow(["PUMP_01", "순환 펌프 모터", "직입모터", "2.2", "1", "380", "18", ""])
    w.writerow(["HTR_01", "예열 히터 존", "히터", "3.0", "1", "380", "12", ""])
    w.writerow(["SOL_01", "공압 솔레노이드 그룹", "솔레노이드", "0", "12", "24", "10", ""])
    w.writerow(["SEN_01", "근접/광전 센서 그룹", "센서", "0", "16", "24", "12", ""])
    w.writerow(["SAFETY_01", "라인 비상정지 회로", "안전회로", "0", "2", "24", "10", "PLd"])
    return "\ufeff" + buf.getvalue()


def export_catalog_template_csv() -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["분류(Category)", "제조사(Manufacturer)", "파트넘버(PartNumber)", "정격값(A 또는 kW)", "규격(Spec)", "단가(KRW)", "납기(Days)"])
    w.writerow(["MCCB", "LS Electric", "ABS50c-CUST-30A", "30", "사내표준 MCCB 3P 50AF/30AT", "49000", "2"])
    w.writerow(["MC", "LS Electric", "MC-18b-STD-24V", "18", "사내표준 전자접촉기 18A DC24V", "26500", "1"])
    w.writerow(["INVERTER", "LS Electric", "LSLV0015G100-STD", "1.5", "사내표준 인버터 3P 380V 1.5kW", "295000", "3"])
    w.writerow(["SERVO", "Mitsubishi Electric", "MR-J5-70G-STD", "0.75", "사내표준 서보 드라이브 750W", "590000", "5"])
    w.writerow(["SMPS", "MeanWell", "NDR-240-24-STD", "10", "사내표준 SMPS DC24V 10A", "61000", "2"])
    return "\ufeff" + buf.getvalue()
