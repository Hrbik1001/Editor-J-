[storage.py](https://github.com/user-attachments/files/27099979/storage.py)
from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict
from typing import Any

from models import (
    Carrier,
    Database,
    Duty,
    DutyItem,
    FixedCode,
    Line,
    Platform,
    RouteStop,
    Settings,
    Stop,
    TimeCode,
    TravelTimeRule,
    Trip,
    TripStopRecord,
)


DATA_FILE = "jr_data.json"


def new_id() -> str:
    return uuid.uuid4().hex


def create_default_db() -> Database:
    return Database(
        time_codes=[
            TimeCode(id=new_id(), symbol="1", description="jede v pondělí"),
            TimeCode(id=new_id(), symbol="2", description="jede v úterý"),
            TimeCode(id=new_id(), symbol="3", description="jede ve středu"),
            TimeCode(id=new_id(), symbol="4", description="jede ve čtvrtek"),
            TimeCode(id=new_id(), symbol="5", description="jede v pátek"),
            TimeCode(id=new_id(), symbol="6", description="jede v sobotu"),
            TimeCode(id=new_id(), symbol="7", description="jede v neděli"),
            TimeCode(id=new_id(), symbol="X", description="jede v pracovní dny"),
            TimeCode(id=new_id(), symbol="†", description="jede v neděli a ve svátcích"),
        ],
        fixed_codes=[
            FixedCode(id=new_id(), symbol="x", description="Zastávka na znamení"),
            FixedCode(id=new_id(), symbol="🚂", description="Přestup na linky S a další vlakové spoje"),
        ],
        settings=Settings(stop_sort_mode="code"),
    )


def _platform_from_dict(data: dict[str, Any]) -> Platform:
    return Platform(
        id=data["id"],
        name=data.get("name", ""),
    )


def _stop_from_dict(data: dict[str, Any]) -> Stop:
    return Stop(
        id=data["id"],
        name=data.get("name", ""),
        stop_number=data.get("stop_number", ""),
        coordinates=data.get("coordinates", ""),
        integrated_system=data.get("integrated_system", ""),
        tariff_zone=data.get("tariff_zone", ""),
        platforms=[_platform_from_dict(x) for x in data.get("platforms", [])],
        fixed_code_ids=list(data.get("fixed_code_ids", [])),
    )


def _route_stop_from_dict(data: dict[str, Any]) -> RouteStop:
    return RouteStop(stop_id=data["stop_id"])


def _trip_stop_record_from_dict(data: dict[str, Any]) -> TripStopRecord:
    return TripStopRecord(
        stop_id=data["stop_id"],
        platform_id=data.get("platform_id", ""),
        km=data.get("km", ""),
        speed_kmh=data.get("speed_kmh", ""),
        goes_other_way=bool(data.get("goes_other_way", False)),
        does_not_stop=bool(data.get("does_not_stop", False)),
        arrival=data.get("arrival", ""),
        departure=data.get("departure", ""),
        fixed_code_ids=list(data.get("fixed_code_ids", [])),
    )


def _trip_from_dict(data: dict[str, Any]) -> Trip:
    return Trip(
        id=data["id"],
        line_id=data.get("line_id", ""),
        trip_number=data.get("trip_number", ""),
        time_code_ids=list(data.get("time_code_ids", [])),
        stop_records=[_trip_stop_record_from_dict(x) for x in data.get("stop_records", [])],
        time_shift=int(data.get("time_shift", 0)),
    )


def _line_from_dict(data: dict[str, Any]) -> Line:
    return Line(
        id=data["id"],
        line_number=data.get("line_number", ""),
        name=data.get("name", ""),
        carrier_id=data.get("carrier_id", ""),
        validity_from=data.get("validity_from", ""),
        validity_to=data.get("validity_to", ""),
        route=[_route_stop_from_dict(x) for x in data.get("route", [])],
        trips=[_trip_from_dict(x) for x in data.get("trips", [])],
    )


def _duty_item_from_dict(data: dict[str, Any]) -> DutyItem:
    return DutyItem(
        kind=data.get("kind", ""),
        title=data.get("title", ""),
        ref_trip_id=data.get("ref_trip_id", ""),
        time_from=data.get("time_from", ""),
        time_to=data.get("time_to", ""),
    )


def _duty_from_dict(data: dict[str, Any]) -> Duty:
    return Duty(
        id=data["id"],
        name=data.get("name", ""),
        duty_number=data.get("duty_number", ""),
        carrier_id=data.get("carrier_id", ""),
        items=[_duty_item_from_dict(x) for x in data.get("items", [])],
    )


def _travel_time_from_dict(data: dict[str, Any]) -> TravelTimeRule:
    return TravelTimeRule(
        id=data["id"],
        from_stop_id=data.get("from_stop_id", ""),
        to_stop_id=data.get("to_stop_id", ""),
        km=data.get("km", ""),
        minutes=int(data.get("minutes", 0)),
    )


def load_db(path: str = DATA_FILE) -> Database:
    if not os.path.exists(path):
        return create_default_db()

    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    db = Database(
        carriers=[
            Carrier(
                id=x["id"],
                name=x.get("name", ""),
                ico=x.get("ico", ""),
                abbreviation=x.get("abbreviation", ""),
                logo_path=x.get("logo_path", ""),
                web=x.get("web", ""),
                phone=x.get("phone", ""),
                email=x.get("email", ""),
                seat=x.get("seat", ""),
            )
            for x in raw.get("carriers", [])
        ],
        time_codes=[
            TimeCode(id=x["id"], symbol=x.get("symbol", ""), description=x.get("description", ""))
            for x in raw.get("time_codes", [])
        ],
        fixed_codes=[
            FixedCode(id=x["id"], symbol=x.get("symbol", ""), description=x.get("description", ""))
            for x in raw.get("fixed_codes", [])
        ],
        stops=[_stop_from_dict(x) for x in raw.get("stops", [])],
        travel_times=[_travel_time_from_dict(x) for x in raw.get("travel_times", [])],
        lines=[_line_from_dict(x) for x in raw.get("lines", [])],
        duties=[_duty_from_dict(x) for x in raw.get("duties", [])],
        settings=Settings(
            stop_sort_mode=raw.get("settings", {}).get("stop_sort_mode", "code"),
        ),
    )

    if not db.time_codes and not db.fixed_codes:
        default_db = create_default_db()
        db.time_codes = default_db.time_codes
        db.fixed_codes = default_db.fixed_codes

    return db


def save_db(db: Database, path: str = DATA_FILE) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(asdict(db), f, ensure_ascii=False, indent=2)
