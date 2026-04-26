[models.py](https://github.com/user-attachments/files/27099972/models.py)
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Carrier:
    id: str
    name: str
    ico: str = ""
    abbreviation: str = ""
    logo_path: str = ""
    web: str = ""
    phone: str = ""
    email: str = ""
    seat: str = ""


@dataclass
class TimeCode:
    id: str
    symbol: str
    description: str


@dataclass
class FixedCode:
    id: str
    symbol: str
    description: str


@dataclass
class Platform:
    id: str
    name: str


@dataclass
class Stop:
    id: str
    name: str
    stop_number: str
    coordinates: str = ""
    integrated_system: str = ""
    tariff_zone: str = ""
    platforms: list[Platform] = field(default_factory=list)
    fixed_code_ids: list[str] = field(default_factory=list)


@dataclass
class RouteStop:
    stop_id: str


@dataclass
class TripStopRecord:
    stop_id: str
    platform_id: str = ""
    km: str = ""
    speed_kmh: str = ""
    goes_other_way: bool = False
    does_not_stop: bool = False
    arrival: str = ""
    departure: str = ""
    fixed_code_ids: list[str] = field(default_factory=list)


@dataclass
class Trip:
    id: str
    line_id: str
    trip_number: str
    time_code_ids: list[str] = field(default_factory=list)
    stop_records: list[TripStopRecord] = field(default_factory=list)
    time_shift: int = 0


@dataclass
class Line:
    id: str
    line_number: str
    name: str = ""
    carrier_id: str = ""
    validity_from: str = ""
    validity_to: str = ""
    route: list[RouteStop] = field(default_factory=list)
    trips: list[Trip] = field(default_factory=list)


@dataclass
class DutyItem:
    kind: str
    title: str = ""
    ref_trip_id: str = ""
    time_from: str = ""
    time_to: str = ""


@dataclass
class Duty:
    id: str
    name: str
    duty_number: str
    carrier_id: str = ""
    items: list[DutyItem] = field(default_factory=list)


@dataclass
class TravelTimeRule:
    id: str
    from_stop_id: str
    to_stop_id: str
    km: str = ""
    minutes: int = 0


@dataclass
class Settings:
    stop_sort_mode: str = "code"


@dataclass
class Database:
    carriers: list[Carrier] = field(default_factory=list)
    time_codes: list[TimeCode] = field(default_factory=list)
    fixed_codes: list[FixedCode] = field(default_factory=list)
    stops: list[Stop] = field(default_factory=list)
    travel_times: list[TravelTimeRule] = field(default_factory=list)
    lines: list[Line] = field(default_factory=list)
    duties: list[Duty] = field(default_factory=list)
    settings: Settings = field(default_factory=Settings)
