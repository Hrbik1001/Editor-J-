[exports.py](https://github.com/user-attachments/files/27099967/exports.py)
from __future__ import annotations

import math
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from xml.dom import minidom
from xml.etree.ElementTree import Element, SubElement, tostring

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from models import Database, Line, Stop, Trip


PDF_FONT_REGULAR = "Helvetica"
PDF_FONT_BOLD = "Helvetica-Bold"
PDF_FONT_ITALIC = "Helvetica-Oblique"
_PDF_FONTS_READY = False


def _register_pdf_fonts():
    global _PDF_FONTS_READY, PDF_FONT_REGULAR, PDF_FONT_BOLD, PDF_FONT_ITALIC
    if _PDF_FONTS_READY:
        return

    candidates = [
        (
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/ariali.ttf",
        ),
        (
            "C:/Windows/Fonts/calibri.ttf",
            "C:/Windows/Fonts/calibrib.ttf",
            "C:/Windows/Fonts/calibrii.ttf",
        ),
        (
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
        ),
        (
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Italic.ttf",
        ),
    ]

    for regular, bold, italic in candidates:
        if os.path.exists(regular) and os.path.exists(bold):
            try:
                pdfmetrics.registerFont(TTFont("JRRegular", regular))
                pdfmetrics.registerFont(TTFont("JRBold", bold))
                if os.path.exists(italic):
                    pdfmetrics.registerFont(TTFont("JRItalic", italic))
                    PDF_FONT_ITALIC = "JRItalic"
                else:
                    PDF_FONT_ITALIC = "JRRegular"
                PDF_FONT_REGULAR = "JRRegular"
                PDF_FONT_BOLD = "JRBold"
                _PDF_FONTS_READY = True
                return
            except Exception:
                pass

    _PDF_FONTS_READY = True


def sort_stops(stops: list[Stop], mode: str):
    if mode == "alpha":
        return sorted(stops, key=lambda s: s.name.lower())
    return sorted(stops, key=lambda s: s.stop_number)


def _safe_int(value, fallback):
    try:
        return int(value)
    except Exception:
        return fallback


def _safe_filename(name: str) -> str:
    invalid = '<>:"/\\|?*'
    return "".join("_" if c in invalid else c for c in name).replace("\n", " ").strip()


def _to_hms(text: str) -> str:
    value = text.strip()
    if not value:
        return ""
    if len(value) == 5 and ":" in value:
        return f"{value}:00"
    return value


def _to_iso_date(text: str) -> str:
    dt = datetime.strptime(text.replace(" ", ""), "%d.%m.%Y")
    return dt.strftime("%Y-%m-%d")


def _prettify_xml(root: Element) -> str:
    rough = tostring(root, encoding="utf-8")
    reparsed = minidom.parseString(rough)
    pretty = reparsed.toprettyxml(indent="  ", encoding=None)
    lines = [line for line in pretty.splitlines() if line.strip()]
    return "\n".join(lines)


def _parse_km(text: str) -> float | None:
    text = (text or "").strip().replace(",", ".")
    if not text:
        return None
    try:
        return float(text)
    except Exception:
        return None


def _parse_time_to_minutes(value: str):
    value = (value or "").strip()
    if not value or ":" not in value:
        return None
    try:
        hh, mm_ = value.split(":")
        return int(hh) * 60 + int(mm_)
    except Exception:
        return None


def _going_text_from_time_codes(trip: Trip, tc_lookup: dict) -> str:
    symbols = []
    for tc_id in trip.time_code_ids:
        tc = tc_lookup.get(tc_id)
        if tc and tc.symbol:
            symbols.append(tc.symbol)

    if not symbols:
        return "denně"

    s = set(symbols)
    if s == {"X"}:
        return "X"
    if s == {"†"}:
        return "†"
    if s == {"7"}:
        return "7"

    ordered = [x for x in ["1", "2", "3", "4", "5", "6", "7", "X", "†"] if x in s]
    return ",".join(ordered) if ordered else "denně"


def _trip_cell_text(sr, first_used_index, last_used_index, idx):
    if sr is None:
        if first_used_index is not None and idx < first_used_index:
            return "...."
        if last_used_index is not None and idx > last_used_index:
            return "...."
        return ""
    if sr.goes_other_way:
        return "|"
    if sr.does_not_stop:
        return "⸾"
    if sr.departure or sr.arrival:
        return sr.departure or sr.arrival
    if first_used_index is not None and idx < first_used_index:
        return "...."
    if last_used_index is not None and idx > last_used_index:
        return "...."
    return ""


def _legend_lines(symbols: set):
    mapping = {
        "†": "† - spoj jede jen v neděle a svátky",
        "X": "X - spoj jede v pracovní dny",
        "7": "7 - spoj jede jen v neděli",
        "1": "1 - spoj jede v pondělí",
        "2": "2 - spoj jede v úterý",
        "3": "3 - spoj jede ve středu",
        "4": "4 - spoj jede ve čtvrtek",
        "5": "5 - spoj jede v pátek",
        "6": "6 - spoj jede v sobotu",
        "x": "x - zastávka na znamení",
        "⸾": "⸾ - spoj zastávkou projíždí",
        "|": "| - spoj jede jinudy",
        "....": ".... - spoj zde nezačíná / zde nekončí",
        "🚂": "🚂 - přestup na linky S a další vlakové spoje",
    }
    order = ["†", "X", "7", "1", "2", "3", "4", "5", "6", "x", "⸾", "|", "....", "🚂"]
    return [mapping[s] for s in order if s in symbols]


def _make_trip_header(trip: Trip, time_code_lookup, used_symbols: set):
    symbols = []
    for tc_id in trip.time_code_ids:
        tc = time_code_lookup.get(tc_id)
        if tc and tc.symbol:
            symbols.append(tc.symbol)
            used_symbols.add(tc.symbol)
    return {"number": trip.trip_number, "codes": symbols}


def _split_trip_groups(line: Line, max_per_side: int = 7):
    odd = sorted(
        [t for t in line.trips if t.trip_number.isdigit() and int(t.trip_number) % 2 == 1],
        key=lambda t: int(t.trip_number),
    )
    even = sorted(
        [t for t in line.trips if t.trip_number.isdigit() and int(t.trip_number) % 2 == 0],
        key=lambda t: int(t.trip_number),
    )
    others = [t for t in line.trips if not t.trip_number.isdigit()]
    odd.extend(others)

    count = max(
        math.ceil(len(odd) / max_per_side) if odd else 1,
        math.ceil(len(even) / max_per_side) if even else 1,
    )

    out = []
    for i in range(count):
        out.append((
            odd[i * max_per_side:(i + 1) * max_per_side],
            even[i * max_per_side:(i + 1) * max_per_side],
        ))
    return out


def _find_trip_used_range(trip: Trip):
    first_idx = None
    last_idx = None
    for idx, sr in enumerate(trip.stop_records):
        if sr.goes_other_way:
            continue
        if sr.departure or sr.arrival or sr.does_not_stop:
            if first_idx is None:
                first_idx = idx
            last_idx = idx
    return first_idx, last_idx


def _prepare_block_data(line, odd_trips, even_trips, stop_lookup, fixed_lookup, time_code_lookup, carrier_lookup):
    used_symbols = set()
    rows = []

    odd_ranges = {t.id: _find_trip_used_range(t) for t in odd_trips}
    even_ranges = {t.id: _find_trip_used_range(t) for t in even_trips}

    for row_index, rs in enumerate(line.route):
        stop = stop_lookup.get(rs.stop_id)
        if not stop:
            continue

        stop_symbols = []
        for code_id in stop.fixed_code_ids:
            fc = fixed_lookup.get(code_id)
            if fc:
                stop_symbols.append(fc.symbol)
                used_symbols.add(fc.symbol)

        odd_cells = []
        for trip in odd_trips:
            rec = next((r for r in trip.stop_records if r.stop_id == stop.id), None)
            first_idx, last_idx = odd_ranges[trip.id]
            txt = _trip_cell_text(rec, first_idx, last_idx, row_index)
            odd_cells.append(txt)
            if txt in {"⸾", "|", "...."}:
                used_symbols.add(txt)

        even_cells = []
        for trip in even_trips:
            rec = next((r for r in trip.stop_records if r.stop_id == stop.id), None)
            first_idx, last_idx = even_ranges[trip.id]
            txt = _trip_cell_text(rec, first_idx, last_idx, row_index)
            even_cells.append(txt)
            if txt in {"⸾", "|", "...."}:
                used_symbols.add(txt)

        rows.append({
            "stop_name": stop.name,
            "stop_symbols": stop_symbols,
            "odd_cells": odd_cells,
            "even_cells": even_cells,
        })

    odd_headers = [_make_trip_header(t, time_code_lookup, used_symbols) for t in odd_trips]
    even_headers = [_make_trip_header(t, time_code_lookup, used_symbols) for t in even_trips]

    carrier = carrier_lookup.get(line.carrier_id)
    company = carrier.name if carrier else ""
    contact = ""
    if carrier:
        contact = carrier.phone or carrier.web or carrier.email or carrier.seat or ""

    return {
        "line_number": line.line_number,
        "line_name": line.name.strip(),
        "valid_from": line.validity_from.strip(),
        "company": company,
        "contact": contact,
        "odd_headers": odd_headers,
        "even_headers": even_headers,
        "rows": rows,
        "used_symbols": used_symbols,
    }


def _pdf_fit_font_size(text: str, font_name: str, max_width: float, start_size: float, min_size: float = 6.0) -> float:
    size = start_size
    while size >= min_size:
        if pdfmetrics.stringWidth(text, font_name, size) <= max_width:
            return size
        size -= 0.5
    return min_size


def _pdf_ellipsize(text: str, font_name: str, font_size: float, max_width: float) -> str:
    if pdfmetrics.stringWidth(text, font_name, font_size) <= max_width:
        return text
    suffix = "…"
    out = text
    while out:
        out = out[:-1]
        candidate = out + suffix
        if pdfmetrics.stringWidth(candidate, font_name, font_size) <= max_width:
            return candidate
    return suffix


def _max_stop_text_width(rows, font_name, font_size):
    max_w = 0
    for row in rows:
        text = row["stop_name"]
        if row["stop_symbols"]:
            text += "   " + " ".join(row["stop_symbols"])
        w = pdfmetrics.stringWidth(text, font_name, font_size)
        max_w = max(max_w, w)
    return max_w


def _compute_block_width(data: dict):
    odd_cols = len(data["odd_headers"])
    even_cols = len(data["even_headers"])
    line_w = 16 * mm
    time_cell_w = 9 * mm

    longest = _max_stop_text_width(data["rows"], PDF_FONT_REGULAR, 9)
    stop_w = max(46 * mm, min(longest + 8 * mm, 64 * mm))

    left_times = odd_cols * time_cell_w
    right_times = even_cols * time_cell_w

    if even_cols == 0 and odd_cols > 0:
        return line_w + left_times + stop_w
    if odd_cols == 0 and even_cols > 0:
        return line_w + stop_w + right_times
    return line_w + left_times + stop_w + right_times


def _layout_blocks(page_w, page_h, blocks):
    margin_x = 8 * mm
    margin_y = 8 * mm
    gap_x = 6 * mm

    if not blocks:
        return []

    pages = []
    i = 0
    usable_w = page_w - 2 * margin_x

    while i < len(blocks):
        current_w = _compute_block_width(blocks[i])

        if i + 1 < len(blocks):
            next_w = _compute_block_width(blocks[i + 1])
            if current_w + gap_x + next_w <= usable_w:
                pages.append([
                    {"x": margin_x, "y_top": page_h - margin_y, "data": blocks[i]},
                    {"x": margin_x + current_w + gap_x, "y_top": page_h - margin_y, "data": blocks[i + 1]},
                ])
                i += 2
                continue

        pages.append([
            {"x": margin_x, "y_top": page_h - margin_y, "data": blocks[i]},
        ])
        i += 1

    return pages


def _split_rows_for_height(data, page_h):
    header_top_h = 11 * mm
    trip_header_h = 6 * mm
    row_h = 7.2 * mm
    footer_h = 18 * mm
    margin_top = 8 * mm
    margin_bottom = 10 * mm
    usable = page_h - margin_top - margin_bottom - header_top_h - trip_header_h - footer_h
    max_rows = max(4, int(usable // row_h))

    rows = data["rows"]
    if len(rows) <= max_rows:
        return [data]

    chunks = []
    part = 1
    total = math.ceil(len(rows) / max_rows)
    for i in range(0, len(rows), max_rows):
        chunk = dict(data)
        chunk["rows"] = rows[i:i + max_rows]
        chunk["continued_from_prev"] = i > 0
        chunk["continued_to_next"] = i + max_rows < len(rows)
        chunk["part"] = part
        chunk["part_total"] = total
        chunks.append(chunk)
        part += 1
    return chunks


def _draw_text_center_fit(c: canvas.Canvas, text: str, center_x: float, baseline_y: float, max_width: float, font_name: str, start_size: float, min_size: float = 6.0):
    size = _pdf_fit_font_size(text, font_name, max_width, start_size, min_size)
    text2 = _pdf_ellipsize(text, font_name, size, max_width)
    c.setFont(font_name, size)
    c.drawCentredString(center_x, baseline_y, text2)


def _draw_line_block(c: canvas.Canvas, x: float, y_top: float, data: dict):
    odd_cols = len(data["odd_headers"])
    even_cols = len(data["even_headers"])

    line_w = 16 * mm
    time_cell_w = 9 * mm
    header_top_h = 11 * mm
    trip_header_h = 6 * mm
    row_h = 7.2 * mm

    longest = _max_stop_text_width(data["rows"], PDF_FONT_REGULAR, 9)
    stop_w = max(46 * mm, min(longest + 8 * mm, 64 * mm))

    odd_w = odd_cols * time_cell_w
    even_w = even_cols * time_cell_w

    x1 = x + line_w
    if even_cols == 0 and odd_cols > 0:
        x2 = x1 + odd_w
        x3 = x2 + stop_w
        x4 = x3
    elif odd_cols == 0 and even_cols > 0:
        x2 = x1
        x3 = x2 + stop_w
        x4 = x3 + even_w
    else:
        x2 = x1 + odd_w
        x3 = x2 + stop_w
        x4 = x3 + even_w

    total_w = x4 - x
    legend = _legend_lines(data["used_symbols"])
    table_h = header_top_h + trip_header_h + len(data["rows"]) * row_h

    c.setLineWidth(1.0)
    c.rect(x, y_top - table_h, total_w, table_h)

    c.line(x1, y_top - table_h, x1, y_top)
    if odd_cols > 0:
        c.line(x2, y_top - table_h, x2, y_top)
    c.line(x3, y_top - table_h, x3, y_top)

    y1 = y_top - header_top_h
    y2 = y1 - trip_header_h

    c.line(x, y1, x4, y1)
    c.line(x, y2, x4, y2)

    if odd_cols > 0:
        for i in range(1, odd_cols):
            xx = x1 + i * time_cell_w
            c.line(xx, y_top - table_h, xx, y1)

    if even_cols > 0:
        for i in range(1, even_cols):
            xx = x3 + i * time_cell_w
            c.line(xx, y_top - table_h, xx, y1)

    yy = y2
    for _ in data["rows"]:
        yy -= row_h
        c.line(x, yy, x4, yy)

    c.setFont(PDF_FONT_BOLD, 18)
    c.drawCentredString(x + line_w / 2, y_top - 8.2 * mm, str(data["line_number"]))

    if data["valid_from"]:
        c.setFont(PDF_FONT_REGULAR, 7.0)
        c.drawCentredString((x2 + x3) / 2, y_top - 2.5 * mm, "platí od:")
        _draw_text_center_fit(
            c,
            data["valid_from"],
            (x2 + x3) / 2,
            y_top - 7.4 * mm,
            stop_w - 2 * mm,
            PDF_FONT_BOLD,
            11,
            7,
        )

    if data["company"] and even_cols > 0:
        _draw_text_center_fit(
            c,
            data["company"],
            (x3 + x4) / 2,
            y_top - 5.0 * mm,
            max(14 * mm, even_w - 2 * mm),
            PDF_FONT_BOLD,
            11,
            7,
        )
    if data["contact"] and even_cols > 0:
        _draw_text_center_fit(
            c,
            data["contact"],
            (x3 + x4) / 2,
            y_top - 8.8 * mm,
            max(14 * mm, even_w - 2 * mm),
            PDF_FONT_REGULAR,
            7.5,
            6,
        )

    for i in range(odd_cols):
        cell_x = x1 + i * time_cell_w
        cx = cell_x + time_cell_w / 2
        head = data["odd_headers"][i]
        c.setFont(PDF_FONT_BOLD, 8.5)
        c.drawCentredString(cx, y1 - 3.5 * mm, head["number"])
        if head["codes"]:
            c.setFont(PDF_FONT_ITALIC, 5.5)
            c.drawRightString(cell_x + time_cell_w - 0.4 * mm, y1 - 1.8 * mm, "".join(head["codes"]))

    for i in range(even_cols):
        cell_x = x3 + i * time_cell_w
        cx = cell_x + time_cell_w / 2
        head = data["even_headers"][i]
        c.setFont(PDF_FONT_BOLD, 8.5)
        c.drawCentredString(cx, y1 - 3.5 * mm, head["number"])
        if head["codes"]:
            c.setFont(PDF_FONT_ITALIC, 5.5)
            c.drawRightString(cell_x + time_cell_w - 0.4 * mm, y1 - 1.8 * mm, "".join(head["codes"]))

    current_y = y2

    for idx, row in enumerate(data["rows"]):
        mid_y = current_y - row_h / 2 + 1

        for i in range(odd_cols):
            txt = row["odd_cells"][i] if i < len(row["odd_cells"]) else ""
            cx = x1 + i * time_cell_w + time_cell_w / 2
            c.setFont(PDF_FONT_REGULAR, 8.0)
            c.drawCentredString(cx, mid_y, txt)

        stop_text = row["stop_name"]
        if row["stop_symbols"]:
            stop_text += "   " + " ".join(row["stop_symbols"])

        stop_size = _pdf_fit_font_size(stop_text, PDF_FONT_REGULAR, stop_w - 6 * mm, 8.5, 6.0)
        stop_text = _pdf_ellipsize(stop_text, PDF_FONT_REGULAR, stop_size, stop_w - 6 * mm)
        c.setFont(PDF_FONT_REGULAR, stop_size)
        c.drawCentredString((x2 + x3) / 2, mid_y, stop_text)

        if idx % 2 == 0:
            c.setFont(PDF_FONT_REGULAR, 10)
            c.drawString(x2 + 0.8 * mm, mid_y - 1.0, "↓")
            c.drawRightString(x3 - 0.8 * mm, mid_y - 1.0, "↑")

        for i in range(even_cols):
            txt = row["even_cells"][i] if i < len(row["even_cells"]) else ""
            cx = x3 + i * time_cell_w + time_cell_w / 2
            c.setFont(PDF_FONT_REGULAR, 8.0)
            c.drawCentredString(cx, mid_y, txt)

        current_y -= row_h

    footer_y = y_top - table_h - 2.5 * mm

    if data.get("continued_to_next"):
        c.setFont(PDF_FONT_REGULAR, 8)
        c.drawString(x, footer_y, f"pokračování na straně č.{data['part'] + 1}")
        footer_y -= 4 * mm

    if legend:
        c.setFont(PDF_FONT_REGULAR, 7.5)
        for line in legend:
            c.drawString(x, footer_y, line)
            footer_y -= 3.6 * mm


def export_stops_pdf(db: Database, path: str) -> None:
    _register_pdf_fonts()
    c = canvas.Canvas(path, pagesize=A4)
    _, height = A4
    y = height - 20 * mm

    c.setFont(PDF_FONT_BOLD, 16)
    c.drawString(15 * mm, y, "Seznam zastávek")
    y -= 10 * mm

    c.setFont(PDF_FONT_BOLD, 10)
    c.drawString(15 * mm, y, "Číslo")
    c.drawString(45 * mm, y, "Název")
    c.drawString(115 * mm, y, "IDS")
    c.drawString(150 * mm, y, "Zóna")
    y -= 6 * mm

    c.setFont(PDF_FONT_REGULAR, 10)
    for stop in sort_stops(db.stops, db.settings.stop_sort_mode):
        if y < 20 * mm:
            c.showPage()
            _, height = A4
            y = height - 20 * mm
            c.setFont(PDF_FONT_REGULAR, 10)

        c.drawString(15 * mm, y, stop.stop_number)
        c.drawString(45 * mm, y, stop.name)
        c.drawString(115 * mm, y, stop.integrated_system)
        c.drawString(150 * mm, y, stop.tariff_zone)
        y -= 5 * mm

    c.save()


def export_duties_pdf(db: Database, path: str) -> None:
    _register_pdf_fonts()
    c = canvas.Canvas(path, pagesize=A4)
    _, height = A4

    trip_lookup = {}
    for line in db.lines:
        for trip in line.trips:
            trip_lookup[trip.id] = (line, trip)

    for idx, duty in enumerate(sorted(db.duties, key=lambda d: (d.duty_number, d.name))):
        if idx > 0:
            c.showPage()

        y = height - 20 * mm
        c.setFont(PDF_FONT_BOLD, 14)
        c.drawString(15 * mm, y, f"{duty.name} | {duty.duty_number}")
        y -= 10 * mm

        c.setFont(PDF_FONT_BOLD, 11)
        c.drawString(15 * mm, y, "Název spoje")
        c.drawString(95 * mm, y, "Začátek")
        c.drawString(135 * mm, y, "Konec")
        y -= 6 * mm

        c.setFont(PDF_FONT_REGULAR, 10)
        for item in duty.items:
            if y < 20 * mm:
                c.showPage()
                _, height = A4
                y = height - 20 * mm
                c.setFont(PDF_FONT_REGULAR, 10)

            if item.kind == "trip" and item.ref_trip_id in trip_lookup:
                line, trip = trip_lookup[item.ref_trip_id]
                begin = ""
                end = ""
                if trip.stop_records:
                    first = trip.stop_records[0]
                    last = trip.stop_records[-1]
                    begin = first.departure or first.arrival
                    end = last.arrival or last.departure

                c.drawString(15 * mm, y, f"Linka {line.line_number} / spoj {trip.trip_number}")
                c.drawString(95 * mm, y, begin)
                c.drawString(135 * mm, y, end)
            else:
                c.drawString(15 * mm, y, item.title)
                c.drawString(95 * mm, y, item.time_from)
                c.drawString(135 * mm, y, item.time_to)

            y -= 5 * mm

    c.save()


def export_lines_pdf(db: Database, path: str) -> None:
    _register_pdf_fonts()
    c = canvas.Canvas(path, pagesize=landscape(A4))
    page_w, page_h = landscape(A4)

    stop_lookup = {s.id: s for s in db.stops}
    fixed_lookup = {f.id: f for f in db.fixed_codes}
    time_code_lookup = {t.id: t for t in db.time_codes}
    carrier_lookup = {c.id: c for c in db.carriers}

    first_page = True

    for line in sorted(db.lines, key=lambda x: _safe_int(x.line_number, x.line_number)):
        groups = _split_trip_groups(line, max_per_side=7)
        if not groups:
            groups = [([], [])]

        blocks = []
        for odd_trips, even_trips in groups:
            prepared = _prepare_block_data(
                line=line,
                odd_trips=odd_trips,
                even_trips=even_trips,
                stop_lookup=stop_lookup,
                fixed_lookup=fixed_lookup,
                time_code_lookup=time_code_lookup,
                carrier_lookup=carrier_lookup,
            )
            blocks.extend(_split_rows_for_height(prepared, page_h))

        pages = _layout_blocks(page_w, page_h, blocks)

        for page_blocks in pages:
            if not first_page:
                c.showPage()
            first_page = False

            for block in page_blocks:
                _draw_line_block(c, block["x"], block["y_top"], block["data"])

    c.save()


def export_timetable_xml(db: Database, path: str) -> None:
    root = Element("Trains")
    tc_lookup = {t.id: t for t in db.time_codes}

    for line in sorted(db.lines, key=lambda x: _safe_int(x.line_number, x.line_number)):
        grouped = {}
        for trip in line.trips:
            train_number = f"{line.line_number}{trip.trip_number}"
            grouped.setdefault(train_number, []).append(trip)

        for train_number, trips in grouped.items():
            train_el = SubElement(root, "Train", {"number": train_number})

            for idx, trip in enumerate(sorted(trips, key=lambda t: _safe_int(t.trip_number, t.trip_number)), start=1):
                variant_attrs = {"id": str(idx)}
                if line.name.strip():
                    variant_attrs["name"] = line.name.strip()
                variant_el = SubElement(train_el, "Variant", variant_attrs)

                validity_el = SubElement(variant_el, "validity")
                datesdef_attrs = {}
                if line.validity_from.strip():
                    datesdef_attrs["from"] = _to_iso_date(line.validity_from.strip())
                if line.validity_to.strip():
                    datesdef_attrs["to"] = _to_iso_date(line.validity_to.strip())

                going = _going_text_from_time_codes(trip, tc_lookup)
                if going:
                    datesdef_attrs["going"] = going

                SubElement(validity_el, "datesdef", datesdef_attrs)

                languages_el = SubElement(variant_el, "languages")
                SubElement(languages_el, "language").text = "CZ"

                stops_el = SubElement(variant_el, "stops")

                stop_records = [sr for sr in trip.stop_records if not sr.goes_other_way]
                if not stop_records:
                    continue

                for sidx, sr in enumerate(stop_records):
                    stop_obj = next((s for s in db.stops if s.id == sr.stop_id), None)
                    sr70 = stop_obj.stop_number.strip() if stop_obj and stop_obj.stop_number.strip() else sr.stop_id

                    attrs = {"SR70": sr70, "lineIDS": str(line.line_number)}
                    arr = sr.arrival.strip()
                    dep = sr.departure.strip()

                    if sidx == 0:
                        if not dep and arr:
                            dep = arr
                        attrs["category"] = "Os"
                        if dep:
                            attrs["deptime"] = _to_hms(dep)
                    elif sidx == len(stop_records) - 1:
                        if not arr and dep:
                            arr = dep
                        if arr:
                            attrs["arrtime"] = _to_hms(arr)
                    else:
                        if not arr and dep:
                            arr = dep
                        if not dep and arr:
                            dep = arr
                        attrs["arrtime"] = _to_hms(arr) if arr else ""
                        attrs["deptime"] = _to_hms(dep) if dep else ""

                    SubElement(stops_el, "Stop", attrs)

    pretty_xml = _prettify_xml(root)
    with open(path, "w", encoding="utf-8") as f:
        f.write(pretty_xml)


def export_stations_xml(db: Database, path: str) -> None:
    root = Element("Stations")
    for stop in sort_stops(db.stops, db.settings.stop_sort_mode):
        attrs = {
            "SR70": stop.stop_number,
            "name": stop.name,
        }
        if stop.integrated_system:
            attrs["integratedSystem"] = stop.integrated_system
        if stop.tariff_zone:
            attrs["tariffZone"] = stop.tariff_zone
        if stop.coordinates:
            attrs["gps"] = stop.coordinates
        SubElement(root, "Station", attrs)

    pretty_xml = _prettify_xml(root)
    with open(path, "w", encoding="utf-8") as f:
        f.write(pretty_xml)


def export_stop_line_timetable_pdf(db: Database, stop_id: str, path: str) -> None:
    _register_pdf_fonts()
    stop = next((s for s in db.stops if s.id == stop_id), None)
    if not stop:
        raise ValueError("Zastávka neexistuje.")

    c = canvas.Canvas(path, pagesize=landscape(A4))
    page_w, page_h = landscape(A4)
    stop_lookup = {s.id: s for s in db.stops}

    relevant_lines = []
    for line in sorted(db.lines, key=lambda l: _safe_int(l.line_number, l.line_number)):
        if any(rs.stop_id == stop_id for rs in line.route):
            relevant_lines.append(line)

    if not relevant_lines:
        c.setFont(PDF_FONT_BOLD, 16)
        c.drawString(20 * mm, page_h - 20 * mm, f"Zastávka {stop.name}: žádné linky")
        c.save()
        return

    first_page = True
    for line in relevant_lines:
        if not first_page:
            c.showPage()
        first_page = False

        margin_x = 10 * mm
        margin_bottom = 10 * mm
        top_y = page_h - 10 * mm

        line_box_w = 24 * mm
        line_box_h = 24 * mm

        route_col_w = 54 * mm
        route_gap = 8 * mm
        route_block_w = route_col_w * 2 + route_gap + 8 * mm

        table_gap = 10 * mm
        table_x = margin_x + route_block_w + table_gap
        table_w = page_w - table_x - margin_x
        hour_w = 16 * mm
        minute_w = table_w - hour_w

        c.setLineWidth(1.2)
        c.rect(margin_x, top_y - line_box_h, line_box_w, line_box_h)
        c.setFont(PDF_FONT_BOLD, 22)
        c.drawCentredString(margin_x + line_box_w / 2, top_y - 17, str(line.line_number))

        c.setFont(PDF_FONT_BOLD, 14)
        c.drawCentredString(table_x + table_w / 2, top_y - 2, stop.name)

        forward = [stop_lookup[rs.stop_id].name for rs in line.route if rs.stop_id in stop_lookup]
        backward = list(reversed(forward))

        route_font = PDF_FONT_REGULAR
        max_route_text_w = route_col_w - 4 * mm
        longest_route = max(forward + backward, key=len) if (forward or backward) else ""
        route_font_size = _pdf_fit_font_size(longest_route, route_font, max_route_text_w, 10, 6.5)

        route_top_y = top_y - line_box_h - 8 * mm
        c.setFont(PDF_FONT_REGULAR, 11)
        c.drawString(margin_x + 1 * mm, route_top_y, "↓")
        c.drawString(margin_x + route_col_w + route_gap + 1 * mm, route_top_y, "↑")

        route_text_y = route_top_y - 6
        step = 5.3 * mm
        c.setFont(route_font, route_font_size)

        for i in range(max(len(forward), len(backward))):
            if i < len(forward):
                txt = _pdf_ellipsize(forward[i], route_font, route_font_size, max_route_text_w)
                c.drawString(margin_x + 7 * mm, route_text_y, txt)
            if i < len(backward):
                txt = _pdf_ellipsize(backward[i], route_font, route_font_size, max_route_text_w)
                c.drawString(margin_x + route_col_w + route_gap + 7 * mm, route_text_y, txt)
            route_text_y -= step

        times_by_hour = defaultdict(list)
        for trip in line.trips:
            rec = next((r for r in trip.stop_records if r.stop_id == stop_id and not r.goes_other_way and not r.does_not_stop), None)
            if not rec:
                continue
            t = (rec.departure or rec.arrival or "").strip()
            if not t or ":" not in t:
                continue
            hour_text, minute_text = t.split(":")
            times_by_hour[int(hour_text)].append(minute_text)

        existing_hours = sorted(times_by_hour.keys())
        if not existing_hours:
            c.setFont(PDF_FONT_REGULAR, 11)
            c.drawString(table_x, top_y - 20 * mm, "V této zastávce pro linku nejsou žádné časy.")
            continue

        table_top_y = top_y - 20 * mm
        available_h = table_top_y - margin_bottom
        row_count = len(existing_hours)
        row_gap = 0.8 * mm
        row_h = (available_h - ((row_count - 1) * row_gap)) / row_count
        row_h = max(5.6 * mm, row_h)

        current_y = table_top_y
        for hour in existing_hours:
            c.rect(table_x, current_y - row_h, hour_w, row_h)
            c.rect(table_x + hour_w, current_y - row_h, minute_w, row_h)

            c.setFont(PDF_FONT_BOLD, 10)
            c.drawCentredString(table_x + hour_w / 2, current_y - row_h / 2 + 2, f"{hour:02d}")

            mins = "  ".join(sorted(times_by_hour[hour]))
            mins_font_size = _pdf_fit_font_size(mins, PDF_FONT_REGULAR, minute_w - 4 * mm, 10, 7)
            mins = _pdf_ellipsize(mins, PDF_FONT_REGULAR, mins_font_size, minute_w - 4 * mm)

            c.setFont(PDF_FONT_REGULAR, mins_font_size)
            c.drawString(table_x + hour_w + 2 * mm, current_y - row_h / 2 + 2, mins)

            current_y -= row_h + row_gap

    c.save()


def _load_font(size: int, bold: bool = False):
    candidates = []
    if bold:
        candidates = [
            "arialbd.ttf",
            "DejaVuSans-Bold.ttf",
            "LiberationSans-Bold.ttf",
        ]
    else:
        candidates = [
            "arial.ttf",
            "DejaVuSans.ttf",
            "LiberationSans-Regular.ttf",
        ]

    for cand in candidates:
        try:
            return ImageFont.truetype(cand, size=size)
        except Exception:
            continue
    return ImageFont.load_default()


def _fit_font(draw, text, max_width, start_size, bold=False):
    size = start_size
    while size >= 12:
        font = _load_font(size, bold=bold)
        bbox = draw.textbbox((0, 0), text, font=font)
        if bbox[2] - bbox[0] <= max_width:
            return font
        size -= 2
    return _load_font(12, bold=bold)


def _draw_centered(draw, box, text, font, fill=(0, 0, 0)):
    x1, y1, x2, y2 = box
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    tx = x1 + (x2 - x1 - tw) / 2
    ty = y1 + (y2 - y1 - th) / 2 - 4
    draw.text((tx, ty), text, font=font, fill=fill)


def _draw_arrow(draw, x: int, y: int, w: int, h: int, fill=(210, 210, 210)):
    body_h = h // 2
    body_y = y + (h - body_h) // 2
    pts = [
        (x, body_y),
        (x + w - h // 2, body_y),
        (x + w - h // 2, y),
        (x + w, y + h // 2),
        (x + w - h // 2, y + h),
        (x + w - h // 2, body_y + body_h),
        (x, body_y + body_h),
    ]
    draw.polygon(pts, fill=fill)


def _split_stop_name(name: str):
    if "," in name:
        left, right = name.split(",", 1)
        return left.strip(), right.strip()
    return "", name.strip()


def _draw_pinpoint_shape(draw, x, y, w, h, text):
    color = (198, 135, 93)
    cx = x + w / 2
    top = y + 8
    bottom = y + h - 6
    left = x + 10
    right = x + w - 10
    mid_y = y + h * 0.38

    points = [
        (cx, bottom),
        (left + 10, y + h * 0.62),
        (left, mid_y),
        (left + 18, top + 10),
        (cx, top),
        (right - 18, top + 10),
        (right, mid_y),
        (right - 10, y + h * 0.62),
    ]
    draw.polygon(points, fill=color, outline=None)

    inner_r = min(w, h) * 0.23
    draw.ellipse([cx - inner_r, top + 18, cx + inner_r, top + 18 + 2 * inner_r], fill=(220, 170, 130))

    font = _fit_font(draw, str(text), int(w * 0.55), 86, bold=True)
    bbox = draw.textbbox((0, 0), str(text), font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text((cx - tw / 2, top + 30 - th / 2 + inner_r), str(text), font=font, fill=(0, 0, 0))


def _draw_stop_header(draw, width, stop_name, pin_text=None, destinations=None):
    draw.rectangle([25, 20, width - 25, 180], fill=(0, 0, 0))

    obec, misto = _split_stop_name(stop_name)

    if pin_text:
        _draw_pinpoint_shape(draw, width - 300, 8, 240, 260, pin_text)

    usable_w = width - 360 if pin_text else width - 80

    if obec:
        small_font = _fit_font(draw, obec.upper(), usable_w, 34, bold=True)
        big_font = _fit_font(draw, misto.upper(), usable_w, 84, bold=True)
        bbox1 = draw.textbbox((0, 0), obec.upper(), font=small_font)
        bbox2 = draw.textbbox((0, 0), misto.upper(), font=big_font)
        tw1 = bbox1[2] - bbox1[0]
        tw2 = bbox2[2] - bbox2[0]
        draw.text((((width - (280 if pin_text else 0)) - tw1) / 2, 28), obec.upper(), font=small_font, fill=(255, 255, 255))
        draw.text((((width - (280 if pin_text else 0)) - tw2) / 2, 62), misto.upper(), font=big_font, fill=(255, 255, 255))
    else:
        font = _fit_font(draw, misto.upper(), usable_w, 86, bold=True)
        bbox = draw.textbbox((0, 0), misto.upper(), font=font)
        tw = bbox[2] - bbox[0]
        draw.text((((width - (280 if pin_text else 0)) - tw) / 2, 58), misto.upper(), font=font, fill=(255, 255, 255))

    if destinations is not None:
        strip_top = 190
        strip_bottom = 245
        draw.rectangle([25, strip_top, width - 25, strip_bottom], fill=(245, 245, 245))
        text = " · ".join(destinations) if destinations else ""
        font = _fit_font(draw, text, width - 70, 32, bold=True)
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        draw.text(((width - tw) / 2, strip_top + (strip_bottom - strip_top - th) / 2 - 3), text, font=font, fill=(0, 0, 0))
        return strip_bottom + 18

    return 200


def _board_type_1_body(draw, start_y, lines_here):
    cols = 4
    rows = max(1, math.ceil(len(lines_here) / cols))
    cell_w = 300
    cell_h = 180
    margin = 35
    gap = 30

    num_font = _load_font(120, bold=True)

    for idx in range(rows * cols):
        row = idx // cols
        col = idx % cols
        x = margin + col * (cell_w + gap)
        y = start_y + row * (cell_h + gap)
        draw.rounded_rectangle([x, y, x + cell_w, y + cell_h], radius=28, fill=(210, 210, 210))
        if idx < len(lines_here):
            text = str(lines_here[idx]["line_number"])
            _draw_centered(draw, (x, y, x + cell_w, y + cell_h), text, num_font, fill=(0, 0, 0))


def _board_type_2_body(draw, start_y, width, lines_here):
    row_h = 170
    gap = 22
    box_font = _load_font(96, bold=True)
    text_font = _load_font(54, bold=True)

    rows = lines_here if lines_here else [{"line_number": "", "destination": ""}]
    y = start_y
    for item in rows:
        x1 = 35
        box_w = 360
        box_h = 150
        draw.rounded_rectangle([x1, y, x1 + box_w, y + box_h], radius=28, fill=(210, 210, 210))
        if item["line_number"]:
            _draw_centered(draw, (x1, y, x1 + box_w, y + box_h), str(item["line_number"]), box_font, fill=(0, 0, 0))

        arrow_x = x1 + box_w + 40
        arrow_y = y + 12
        _draw_arrow(draw, arrow_x, arrow_y, 260, 126, fill=(210, 210, 210))

        text_box = (arrow_x + 290, y, width - 40, y + box_h)
        _draw_centered(draw, text_box, item["destination"].upper(), text_font, fill=(0, 0, 0))
        y += row_h + gap


def _board_type_3_body(draw, start_y, width):
    return


def _build_stop_board(stop_name: str, lines_here: list, board_type: int):
    width = 1600
    base_height = 900 if board_type in (1, 2) else 420
    img = Image.new("RGB", (width, base_height), (150, 150, 150))
    draw = ImageDraw.Draw(img)

    destinations = [x["destination"] for x in lines_here if x.get("destination")]
    start_y = _draw_stop_header(draw, width, stop_name, pin_text=None, destinations=destinations[:6])

    if board_type == 1:
        _board_type_1_body(draw, start_y, lines_here)
    elif board_type == 2:
        _board_type_2_body(draw, start_y, width, lines_here)
    elif board_type == 3:
        _board_type_3_body(draw, start_y, width)
    else:
        raise ValueError("Neplatný typ tabule")

    return img


def _build_platform_board(stop_name: str, platform_name: str, lines_here: list, board_type: int):
    width = 1600
    base_height = 980 if board_type in (1, 2) else 500
    img = Image.new("RGB", (width, base_height), (150, 150, 150))
    draw = ImageDraw.Draw(img)

    destinations = [x["destination"] for x in lines_here if x.get("destination")]
    start_y = _draw_stop_header(draw, width, stop_name, pin_text=platform_name, destinations=destinations[:8])

    if board_type == 1:
        _board_type_1_body(draw, start_y, lines_here)
    elif board_type == 2:
        _board_type_2_body(draw, start_y, width, lines_here)
    elif board_type == 3:
        _board_type_3_body(draw, start_y, width)
    else:
        raise ValueError("Neplatný typ tabule")

    return img


def _lines_for_stop(db: Database, stop_id: str):
    items = []
    stop_lookup = {s.id: s for s in db.stops}
    for line in sorted(db.lines, key=lambda l: _safe_int(l.line_number, l.line_number)):
        if any(rs.stop_id == stop_id for rs in line.route):
            destination = ""
            if line.route:
                last_stop_id = line.route[-1].stop_id
                last_stop = stop_lookup.get(last_stop_id)
                destination = last_stop.name if last_stop else ""
            items.append({"line_number": line.line_number, "destination": destination})
    return items


def _lines_for_platform(db: Database, stop_id: str, platform_id: str):
    items = []
    stop_lookup = {s.id: s for s in db.stops}
    seen = set()

    for line in sorted(db.lines, key=lambda l: _safe_int(l.line_number, l.line_number)):
        for trip in line.trips:
            rec = next((r for r in trip.stop_records if r.stop_id == stop_id and r.platform_id == platform_id), None)
            if not rec:
                continue

            destination = ""
            if line.route:
                last_stop_id = line.route[-1].stop_id
                last_stop = stop_lookup.get(last_stop_id)
                destination = last_stop.name if last_stop else ""

            key = (line.line_number, destination)
            if key not in seen:
                seen.add(key)
                items.append({"line_number": line.line_number, "destination": destination})

    return items


def export_stop_board_all(db: Database, output_dir: str, board_type: int) -> None:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    for stop in sort_stops(db.stops, db.settings.stop_sort_mode):
        lines_here = _lines_for_stop(db, stop.id)
        img = _build_stop_board(stop.name, lines_here, board_type)
        safe_name = _safe_filename(f"{stop.name}_typ_{board_type}.png")
        img.save(output / safe_name)


def export_stop_board_one(db: Database, output_path: str, stop_id: str, board_type: int) -> None:
    stop = next((s for s in db.stops if s.id == stop_id), None)
    if not stop:
        raise ValueError("Zastávka neexistuje.")
    lines_here = _lines_for_stop(db, stop.id)
    img = _build_stop_board(stop.name, lines_here, board_type)
    img.save(output_path)


def export_platform_board_all(db: Database, output_dir: str, board_type: int) -> None:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    for stop in sort_stops(db.stops, db.settings.stop_sort_mode):
        for platform in stop.platforms:
            lines_here = _lines_for_platform(db, stop.id, platform.id)
            if not lines_here:
                continue
            img = _build_platform_board(stop.name, platform.name, lines_here, board_type)
            safe_name = _safe_filename(f"{stop.name}_nastupiste_{platform.name}_typ_{board_type}.png")
            img.save(output / safe_name)


def export_platform_board_one(db: Database, output_path: str, stop_id: str, platform_id: str, board_type: int) -> None:
    stop = next((s for s in db.stops if s.id == stop_id), None)
    if not stop:
        raise ValueError("Zastávka neexistuje.")
    platform = next((p for p in stop.platforms if p.id == platform_id), None)
    if not platform:
        raise ValueError("Nástupiště neexistuje.")

    lines_here = _lines_for_platform(db, stop.id, platform.id)
    img = _build_platform_board(stop.name, platform.name, lines_here, board_type)
    img.save(output_path)
