[dialogs.py](https://github.com/user-attachments/files/27099961/dialogs.py)
from __future__ import annotations

import copy
import re
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import List, Optional

from models import (
    Carrier,
    TimeCode,
    FixedCode,
    Stop,
    Platform,
    Line,
    RouteStop,
    Trip,
    TripStopRecord,
    Duty,
    DutyItem,
    TravelTimeRule,
)
from storage import new_id


DATE_RE = re.compile(r"^\d{1,2}\.\d{1,2}\.\s*\d{4}$")


def _parse_time_to_minutes(value: str) -> Optional[int]:
    value = (value or "").strip()
    if not value or ":" not in value:
        return None
    try:
        hh, mm = value.split(":")
        return int(hh) * 60 + int(mm)
    except Exception:
        return None


def _minutes_to_hhmm(total_minutes: int) -> str:
    total_minutes = total_minutes % (24 * 60)
    hh = total_minutes // 60
    mm = total_minutes % 60
    return f"{hh:02d}:{mm:02d}"


def _shift_time_text(value: str, shift_minutes: int) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    mins = _parse_time_to_minutes(value)
    if mins is None:
        return value
    return _minutes_to_hhmm(mins + shift_minutes)


def _parse_km(value: str) -> Optional[float]:
    value = (value or "").strip().replace(",", ".")
    if not value:
        return None
    try:
        return float(value)
    except Exception:
        return None


def _format_km(value: float) -> str:
    return f"{value:.2f}".replace(".", ",")


def _compute_speed(prev_time: str, prev_km: str, cur_time: str, cur_km: str) -> str:
    t1 = _parse_time_to_minutes(prev_time)
    t2 = _parse_time_to_minutes(cur_time)
    k1 = _parse_km(prev_km)
    k2 = _parse_km(cur_km)

    if t1 is None or t2 is None or k1 is None or k2 is None:
        return ""

    dt = t2 - t1
    dk = k2 - k1
    if dt <= 0 or dk < 0:
        return ""

    speed = dk / (dt / 60.0)
    return f"{speed:.1f}".replace(".", ",")


class BaseDialog(tk.Toplevel):
    def __init__(self, master, title: str):
        super().__init__(master)
        self.title(title)
        self.transient(master)
        self.grab_set()
        self.resizable(True, True)
        self.result = None
        self.columnconfigure(1, weight=1)

    def add_buttons(self, row: int):
        frame = ttk.Frame(self)
        frame.grid(row=row, column=0, columnspan=2, pady=10, sticky="e")
        ttk.Button(frame, text="Uložit", command=self.on_save).pack(side="left", padx=5)
        ttk.Button(frame, text="Zrušit", command=self.destroy).pack(side="left", padx=5)

    def on_save(self):
        raise NotImplementedError


class CarrierDialog(BaseDialog):
    def __init__(self, master, carrier: Optional[Carrier] = None):
        super().__init__(master, "Dopravce")
        self.carrier = carrier

        fields = [
            ("Název", "name"),
            ("IČO", "ico"),
            ("Zkratka", "abbreviation"),
            ("Logo", "logo_path"),
            ("Web", "web"),
            ("Tel. číslo", "phone"),
            ("E-mail", "email"),
            ("Kde sídlí", "seat"),
        ]
        self.vars = {}

        for i, (label, key) in enumerate(fields):
            ttk.Label(self, text=label).grid(row=i, column=0, sticky="w", padx=8, pady=4)
            var = tk.StringVar(value=getattr(carrier, key, "") if carrier else "")
            self.vars[key] = var

            if key == "logo_path":
                wrap = ttk.Frame(self)
                wrap.grid(row=i, column=1, sticky="ew", padx=8, pady=4)
                wrap.columnconfigure(0, weight=1)
                ttk.Entry(wrap, textvariable=var).grid(row=0, column=0, sticky="ew")
                ttk.Button(wrap, text="...", width=4, command=self.browse_logo).grid(row=0, column=1, padx=(4, 0))
            else:
                ttk.Entry(self, textvariable=var).grid(row=i, column=1, sticky="ew", padx=8, pady=4)

        self.add_buttons(len(fields))

    def browse_logo(self):
        path = filedialog.askopenfilename(
            title="Vyber logo",
            filetypes=[("Obrázky", "*.png *.jpg *.jpeg *.gif *.bmp *.webp"), ("Vše", "*.*")],
        )
        if path:
            self.vars["logo_path"].set(path)

    def on_save(self):
        if not self.vars["name"].get().strip():
            messagebox.showerror("Chyba", "Název je povinný.")
            return

        self.result = Carrier(
            id=self.carrier.id if self.carrier else new_id(),
            name=self.vars["name"].get().strip(),
            ico=self.vars["ico"].get().strip(),
            abbreviation=self.vars["abbreviation"].get().strip(),
            logo_path=self.vars["logo_path"].get().strip(),
            web=self.vars["web"].get().strip(),
            phone=self.vars["phone"].get().strip(),
            email=self.vars["email"].get().strip(),
            seat=self.vars["seat"].get().strip(),
        )
        self.destroy()


class CodeDialog(BaseDialog):
    def __init__(self, master, title: str, symbol: str = "", description: str = "", item_id: str = ""):
        super().__init__(master, title)
        self.item_id = item_id
        self.var_symbol = tk.StringVar(value=symbol)
        self.var_description = tk.StringVar(value=description)

        ttk.Label(self, text="Znak").grid(row=0, column=0, sticky="w", padx=8, pady=4)
        ttk.Entry(self, textvariable=self.var_symbol).grid(row=0, column=1, sticky="ew", padx=8, pady=4)

        ttk.Label(self, text="Popis").grid(row=1, column=0, sticky="w", padx=8, pady=4)
        ttk.Entry(self, textvariable=self.var_description).grid(row=1, column=1, sticky="ew", padx=8, pady=4)

        self.add_buttons(2)

    def on_save(self):
        if not self.var_symbol.get().strip() or not self.var_description.get().strip():
            messagebox.showerror("Chyba", "Znak i popis jsou povinné.")
            return

        self.result = {
            "id": self.item_id or new_id(),
            "symbol": self.var_symbol.get().strip(),
            "description": self.var_description.get().strip(),
        }
        self.destroy()


class PlatformDialog(BaseDialog):
    def __init__(self, master, platform: Optional[Platform] = None):
        super().__init__(master, "Nástupiště")
        self.platform = platform
        self.var_name = tk.StringVar(value=platform.name if platform else "")

        ttk.Label(self, text="Název nástupiště").grid(row=0, column=0, sticky="w", padx=8, pady=4)
        ttk.Entry(self, textvariable=self.var_name).grid(row=0, column=1, sticky="ew", padx=8, pady=4)

        self.add_buttons(1)

    def on_save(self):
        name = self.var_name.get().strip()
        if not name:
            messagebox.showerror("Chyba", "Název nástupiště je povinný.")
            return

        self.result = Platform(id=self.platform.id if self.platform else new_id(), name=name)
        self.destroy()


class StopDialog(BaseDialog):
    def __init__(
        self,
        master,
        fixed_codes: List[FixedCode],
        stop: Optional[Stop] = None,
        existing_stop_numbers: Optional[List[str]] = None,
    ):
        super().__init__(master, "Zastávka")
        self.fixed_codes = fixed_codes
        self.stop = copy.deepcopy(stop) if stop else Stop(id=new_id(), name="", stop_number="")
        self.existing_stop_numbers = set(existing_stop_numbers or [])
        if stop:
            self.existing_stop_numbers.discard(stop.stop_number)

        self.var_name = tk.StringVar(value=self.stop.name)
        self.var_number = tk.StringVar(value=self.stop.stop_number)
        self.var_coordinates = tk.StringVar(value=self.stop.coordinates)
        self.var_integrated = tk.StringVar(value=self.stop.integrated_system)
        self.var_tariff = tk.StringVar(value=self.stop.tariff_zone)

        ttk.Label(self, text="Název zastávky").grid(row=0, column=0, sticky="w", padx=8, pady=4)
        ttk.Entry(self, textvariable=self.var_name).grid(row=0, column=1, sticky="ew", padx=8, pady=4)

        ttk.Label(self, text="Číslo zastávky").grid(row=1, column=0, sticky="w", padx=8, pady=4)
        ttk.Entry(self, textvariable=self.var_number).grid(row=1, column=1, sticky="ew", padx=8, pady=4)

        ttk.Label(self, text="Souřadnice").grid(row=2, column=0, sticky="w", padx=8, pady=4)
        ttk.Entry(self, textvariable=self.var_coordinates).grid(row=2, column=1, sticky="ew", padx=8, pady=4)

        ttk.Label(self, text="Integrovaný systém").grid(row=3, column=0, sticky="w", padx=8, pady=4)
        ttk.Entry(self, textvariable=self.var_integrated).grid(row=3, column=1, sticky="ew", padx=8, pady=4)

        ttk.Label(self, text="Tarifní zóna / pásmo").grid(row=4, column=0, sticky="w", padx=8, pady=4)
        ttk.Entry(self, textvariable=self.var_tariff).grid(row=4, column=1, sticky="ew", padx=8, pady=4)

        ttk.Label(self, text="Nástupiště").grid(row=5, column=0, sticky="nw", padx=8, pady=4)
        pf_wrap = ttk.Frame(self)
        pf_wrap.grid(row=5, column=1, sticky="nsew", padx=8, pady=4)
        pf_wrap.columnconfigure(0, weight=1)

        self.platforms_list = tk.Listbox(pf_wrap, height=6)
        self.platforms_list.grid(row=0, column=0, sticky="nsew")

        pf_btns = ttk.Frame(pf_wrap)
        pf_btns.grid(row=0, column=1, sticky="ns", padx=(6, 0))
        ttk.Button(pf_btns, text="Přidat", command=self.add_platform).pack(fill="x", pady=2)
        ttk.Button(pf_btns, text="Upravit", command=self.edit_platform).pack(fill="x", pady=2)
        ttk.Button(pf_btns, text="Smazat", command=self.delete_platform).pack(fill="x", pady=2)

        ttk.Label(self, text="Pevné kódy").grid(row=6, column=0, sticky="nw", padx=8, pady=4)
        fc_wrap = ttk.Frame(self)
        fc_wrap.grid(row=6, column=1, sticky="nsew", padx=8, pady=4)

        self.fixed_list = tk.Listbox(fc_wrap, selectmode=tk.MULTIPLE, height=6)
        self.fixed_list.pack(fill="both", expand=True)

        for fc in self.fixed_codes:
            self.fixed_list.insert(tk.END, f"{fc.symbol} | {fc.description}")

        for idx, fc in enumerate(self.fixed_codes):
            if fc.id in self.stop.fixed_code_ids:
                self.fixed_list.selection_set(idx)

        self.refresh_platforms()
        self.add_buttons(7)

    def refresh_platforms(self):
        self.platforms_list.delete(0, tk.END)
        for p in self.stop.platforms:
            self.platforms_list.insert(tk.END, p.name)

    def add_platform(self):
        dlg = PlatformDialog(self)
        self.wait_window(dlg)
        if dlg.result:
            self.stop.platforms.append(dlg.result)
            self.refresh_platforms()

    def edit_platform(self):
        sel = self.platforms_list.curselection()
        if not sel:
            return
        idx = sel[0]
        dlg = PlatformDialog(self, self.stop.platforms[idx])
        self.wait_window(dlg)
        if dlg.result:
            self.stop.platforms[idx] = dlg.result
            self.refresh_platforms()

    def delete_platform(self):
        sel = self.platforms_list.curselection()
        if not sel:
            return
        del self.stop.platforms[sel[0]]
        self.refresh_platforms()

    def on_save(self):
        name = self.var_name.get().strip()
        number = self.var_number.get().strip()

        if not name:
            messagebox.showerror("Chyba", "Název zastávky je povinný.")
            return
        if not number:
            messagebox.showerror("Chyba", "Číslo zastávky je povinné.")
            return
        if number in self.existing_stop_numbers:
            messagebox.showerror("Chyba", "Číslo zastávky už existuje.")
            return

        self.stop.name = name
        self.stop.stop_number = number
        self.stop.coordinates = self.var_coordinates.get().strip()
        self.stop.integrated_system = self.var_integrated.get().strip()
        self.stop.tariff_zone = self.var_tariff.get().strip()
        self.stop.fixed_code_ids = [self.fixed_codes[i].id for i in self.fixed_list.curselection()]
        self.result = self.stop
        self.destroy()


class TravelTimeDialog(BaseDialog):
    def __init__(self, master, stops: List[Stop], travel_time: Optional[TravelTimeRule] = None):
        super().__init__(master, "Jízdní doba")
        self.stops = stops
        self.travel_time = copy.deepcopy(travel_time) if travel_time else TravelTimeRule(
            id=new_id(), from_stop_id="", to_stop_id="", km="", minutes=0
        )

        self.stop_names = [f"{s.stop_number} | {s.name}" for s in self.stops]
        self.var_km = tk.StringVar(value=self.travel_time.km)
        self.var_minutes = tk.StringVar(value=str(self.travel_time.minutes if self.travel_time.minutes else ""))
        self.var_speed = tk.StringVar(value="")

        ttk.Label(self, text="Ze zastávky").grid(row=0, column=0, sticky="w", padx=8, pady=4)
        self.from_combo = ttk.Combobox(self, values=self.stop_names, state="readonly")
        self.from_combo.grid(row=0, column=1, sticky="ew", padx=8, pady=4)

        ttk.Label(self, text="Do zastávky").grid(row=1, column=0, sticky="w", padx=8, pady=4)
        self.to_combo = ttk.Combobox(self, values=self.stop_names, state="readonly")
        self.to_combo.grid(row=1, column=1, sticky="ew", padx=8, pady=4)

        ttk.Label(self, text="km").grid(row=2, column=0, sticky="w", padx=8, pady=4)
        ttk.Entry(self, textvariable=self.var_km).grid(row=2, column=1, sticky="ew", padx=8, pady=4)

        ttk.Label(self, text="Jízdní čas (minuty)").grid(row=3, column=0, sticky="w", padx=8, pady=4)
        ttk.Entry(self, textvariable=self.var_minutes).grid(row=3, column=1, sticky="ew", padx=8, pady=4)

        ttk.Label(self, text="km/h (automaticky)").grid(row=4, column=0, sticky="w", padx=8, pady=4)
        ttk.Entry(self, textvariable=self.var_speed, state="readonly").grid(row=4, column=1, sticky="ew", padx=8, pady=4)

        self.var_km.trace_add("write", lambda *_: self.update_speed())
        self.var_minutes.trace_add("write", lambda *_: self.update_speed())

        if self.travel_time.from_stop_id:
            for i, s in enumerate(self.stops):
                if s.id == self.travel_time.from_stop_id:
                    self.from_combo.current(i)
                    break

        if self.travel_time.to_stop_id:
            for i, s in enumerate(self.stops):
                if s.id == self.travel_time.to_stop_id:
                    self.to_combo.current(i)
                    break

        self.update_speed()
        self.add_buttons(5)

    def update_speed(self):
        km = _parse_km(self.var_km.get())
        try:
            minutes = int((self.var_minutes.get() or "").strip())
        except Exception:
            minutes = None

        if km is None or minutes is None or minutes <= 0:
            self.var_speed.set("")
            return

        speed = km / (minutes / 60.0)
        self.var_speed.set(f"{speed:.1f}".replace(".", ","))

    def on_save(self):
        if self.from_combo.current() < 0 or self.to_combo.current() < 0:
            messagebox.showerror("Chyba", "Vyber obě zastávky.")
            return

        from_stop = self.stops[self.from_combo.current()]
        to_stop = self.stops[self.to_combo.current()]

        if from_stop.id == to_stop.id:
            messagebox.showerror("Chyba", "Zastávky musí být různé.")
            return

        try:
            minutes = int(self.var_minutes.get().strip())
        except Exception:
            messagebox.showerror("Chyba", "Jízdní čas musí být celé číslo minut.")
            return

        km = self.var_km.get().strip().replace(",", ".")
        try:
            km_value = float(km)
        except Exception:
            messagebox.showerror("Chyba", "km musí být číslo.")
            return

        self.result = TravelTimeRule(
            id=self.travel_time.id,
            from_stop_id=from_stop.id,
            to_stop_id=to_stop.id,
            km=f"{km_value:.2f}".replace(".", ","),
            minutes=minutes,
        )
        self.destroy()


class LineDialog(BaseDialog):
    def __init__(self, master, stops: List[Stop], carriers: List[Carrier], line: Optional[Line] = None, stop_sort_mode: str = "code"):
        super().__init__(master, "Linka")
        self.all_stops = self._sort_stops(stops, stop_sort_mode)
        self.carriers = carriers
        self.line = copy.deepcopy(line) if line else Line(id=new_id(), line_number="")

        self.var_number = tk.StringVar(value=self.line.line_number)
        self.var_name = tk.StringVar(value=self.line.name)
        self.var_validity_from = tk.StringVar(value=self.line.validity_from)
        self.var_validity_to = tk.StringVar(value=self.line.validity_to)

        ttk.Label(self, text="Číslo linky").grid(row=0, column=0, sticky="w", padx=8, pady=4)
        ttk.Entry(self, textvariable=self.var_number).grid(row=0, column=1, sticky="ew", padx=8, pady=4)

        ttk.Label(self, text="Název linky").grid(row=1, column=0, sticky="w", padx=8, pady=4)
        ttk.Entry(self, textvariable=self.var_name).grid(row=1, column=1, sticky="ew", padx=8, pady=4)

        ttk.Label(self, text="Platnost od").grid(row=2, column=0, sticky="w", padx=8, pady=4)
        ttk.Entry(self, textvariable=self.var_validity_from).grid(row=2, column=1, sticky="ew", padx=8, pady=4)

        ttk.Label(self, text="Platnost do").grid(row=3, column=0, sticky="w", padx=8, pady=4)
        ttk.Entry(self, textvariable=self.var_validity_to).grid(row=3, column=1, sticky="ew", padx=8, pady=4)

        ttk.Label(self, text="Dopravce").grid(row=4, column=0, sticky="w", padx=8, pady=4)
        carrier_names = [""] + [f"{c.name} ({c.abbreviation})" if c.abbreviation else c.name for c in self.carriers]
        self.carrier_combo = ttk.Combobox(self, values=carrier_names, state="readonly")
        self.carrier_combo.grid(row=4, column=1, sticky="ew", padx=8, pady=4)

        if self.line.carrier_id:
            for i, c in enumerate(self.carriers, start=1):
                if c.id == self.line.carrier_id:
                    self.carrier_combo.current(i)
                    break
        else:
            self.carrier_combo.current(0)

        ttk.Label(self, text="Trasa").grid(row=5, column=0, sticky="nw", padx=8, pady=4)
        route_wrap = ttk.Frame(self)
        route_wrap.grid(row=5, column=1, sticky="nsew", padx=8, pady=4)
        route_wrap.columnconfigure(0, weight=1)

        self.route_list = tk.Listbox(route_wrap, height=10)
        self.route_list.grid(row=0, column=0, sticky="nsew")

        btns = ttk.Frame(route_wrap)
        btns.grid(row=0, column=1, sticky="ns", padx=(6, 0))
        ttk.Button(btns, text="Přidat zastávku", command=self.add_stop_to_route).pack(fill="x", pady=2)
        ttk.Button(btns, text="Smazat zastávku", command=self.remove_stop_from_route).pack(fill="x", pady=2)
        ttk.Button(btns, text="Posunout ↑", command=self.move_up).pack(fill="x", pady=2)
        ttk.Button(btns, text="Posunout ↓", command=self.move_down).pack(fill="x", pady=2)

        self.refresh_route()
        self.add_buttons(6)

    def _sort_stops(self, stops: List[Stop], mode: str):
        if mode == "alpha":
            return sorted(stops, key=lambda s: s.name.lower())
        return sorted(stops, key=lambda s: s.stop_number)

    def refresh_route(self):
        stop_lookup = {s.id: s for s in self.all_stops}
        self.route_list.delete(0, tk.END)
        for rs in self.line.route:
            stop = stop_lookup.get(rs.stop_id)
            self.route_list.insert(tk.END, stop.name if stop else rs.stop_id)

    def add_stop_to_route(self):
        selector = tk.Toplevel(self)
        selector.title("Vyber zastávku")
        selector.transient(self)
        selector.grab_set()

        lb = tk.Listbox(selector, width=50, height=15)
        lb.pack(fill="both", expand=True, padx=8, pady=8)
        for stop in self.all_stops:
            lb.insert(tk.END, f"{stop.stop_number} | {stop.name}")

        def confirm():
            sel = lb.curselection()
            if not sel:
                return
            stop = self.all_stops[sel[0]]
            self.line.route.append(RouteStop(stop_id=stop.id))
            self.refresh_route()
            selector.destroy()

        ttk.Button(selector, text="Vybrat", command=confirm).pack(pady=(0, 8))

    def remove_stop_from_route(self):
        sel = self.route_list.curselection()
        if not sel:
            return
        del self.line.route[sel[0]]
        self.refresh_route()

    def move_up(self):
        sel = self.route_list.curselection()
        if not sel or sel[0] == 0:
            return
        idx = sel[0]
        self.line.route[idx - 1], self.line.route[idx] = self.line.route[idx], self.line.route[idx - 1]
        self.refresh_route()
        self.route_list.selection_set(idx - 1)

    def move_down(self):
        sel = self.route_list.curselection()
        if not sel or sel[0] >= len(self.line.route) - 1:
            return
        idx = sel[0]
        self.line.route[idx + 1], self.line.route[idx] = self.line.route[idx], self.line.route[idx + 1]
        self.refresh_route()
        self.route_list.selection_set(idx + 1)

    def on_save(self):
        if not self.var_number.get().strip():
            messagebox.showerror("Chyba", "Číslo linky je povinné.")
            return
        if len(self.line.route) < 2:
            messagebox.showerror("Chyba", "Linka musí mít aspoň dvě zastávky v trase.")
            return

        validity_from = self.var_validity_from.get().strip()
        validity_to = self.var_validity_to.get().strip()

        if validity_from and not DATE_RE.match(validity_from):
            messagebox.showerror("Chyba", "Platnost od musí být ve formátu den.měsíc. rok")
            return
        if validity_to and not DATE_RE.match(validity_to):
            messagebox.showerror("Chyba", "Platnost do musí být ve formátu den.měsíc. rok")
            return

        self.line.line_number = self.var_number.get().strip()
        self.line.name = self.var_name.get().strip()
        self.line.validity_from = validity_from
        self.line.validity_to = validity_to

        sel = self.carrier_combo.current()
        self.line.carrier_id = self.carriers[sel - 1].id if sel > 0 else ""

        self.result = self.line
        self.destroy()


class TripDialog(BaseDialog):
    def __init__(
        self,
        master,
        line: Line,
        stops: List[Stop],
        time_codes: List[TimeCode],
        fixed_codes: List[FixedCode],
        travel_times: List[TravelTimeRule],
        trip: Optional[Trip] = None,
    ):
        super().__init__(master, "Spoj")
        self.geometry("1550x950")
        self.line = copy.deepcopy(line)
        self.stops = stops
        self.time_codes = time_codes
        self.fixed_codes = fixed_codes
        self.travel_times = travel_times
        self.trip = copy.deepcopy(trip) if trip else Trip(id=new_id(), line_id=line.id, trip_number="")

        self.trip.stop_records = [copy.deepcopy(sr) for sr in self.trip.stop_records]

        route_stop_ids = [x.stop_id for x in self.line.route]
        if not self.trip.stop_records:
            self.trip.stop_records = [TripStopRecord(stop_id=sid) for sid in route_stop_ids]

        self.stop_lookup = {s.id: s for s in self.stops}
        self.travel_lookup = {(r.from_stop_id, r.to_stop_id): r for r in self.travel_times}
        self.selected_record_index: Optional[int] = None
        self._loading_record = False

        self.var_trip_number = tk.StringVar(value=self.trip.trip_number)
        self.var_time_shift = tk.StringVar(value="0")

        ttk.Label(self, text="Číslo spoje").grid(row=0, column=0, sticky="w", padx=8, pady=4)
        ttk.Entry(self, textvariable=self.var_trip_number).grid(row=0, column=1, sticky="ew", padx=8, pady=4)

        ttk.Label(self, text="Posunutí času").grid(row=1, column=0, sticky="w", padx=8, pady=4)
        self.shift_entry = ttk.Entry(self, textvariable=self.var_time_shift)
        self.shift_entry.grid(row=1, column=1, sticky="ew", padx=8, pady=4)
        self.shift_entry.bind("<Return>", self.apply_time_shift_event)

        top_actions = ttk.Frame(self)
        top_actions.grid(row=2, column=0, columnspan=2, sticky="ew", padx=8, pady=(0, 6))
        ttk.Button(top_actions, text="Automaticky doplnit dle jízdních dob", command=self.auto_fill_by_travel_times).pack(side="left", padx=4)
        ttk.Button(top_actions, text="Přepočítat další zastávky od pobytů", command=self.recalculate_from_existing_times).pack(side="left", padx=4)

        ttk.Label(self, text="Časové kódy").grid(row=3, column=0, sticky="nw", padx=8, pady=4)
        self.codes_list = tk.Listbox(self, selectmode=tk.MULTIPLE, height=6, exportselection=False)
        self.codes_list.grid(row=3, column=1, sticky="ew", padx=8, pady=4)

        for tc in self.time_codes:
            self.codes_list.insert(tk.END, f"{tc.symbol} | {tc.description}")
        for i, tc in enumerate(self.time_codes):
            if tc.id in self.trip.time_code_ids:
                self.codes_list.selection_set(i)

        columns = ("stop", "platform", "km", "kmh", "other", "skip", "arr", "dep", "fixed")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", height=14)
        heads = {
            "stop": "Zastávka",
            "platform": "Nástupiště",
            "km": "km",
            "kmh": "km/h",
            "other": "jede_jinudy",
            "skip": "nezastavuje",
            "arr": "příjezd",
            "dep": "odjezd",
            "fixed": "pevný kód",
        }
        for key, label in heads.items():
            self.tree.heading(key, text=label)
            self.tree.column(key, width=125, anchor="center")
        self.tree.grid(row=4, column=0, columnspan=2, sticky="nsew", padx=8, pady=8)
        self.tree.bind("<<TreeviewSelect>>", self.on_select_record)

        editor = ttk.LabelFrame(self, text="Úprava vybraného řádku")
        editor.grid(row=5, column=0, columnspan=2, sticky="ew", padx=8, pady=8)
        for col in range(8):
            editor.columnconfigure(col, weight=1)

        self.var_km = tk.StringVar()
        self.var_auto_kmh = tk.StringVar()
        self.var_other = tk.BooleanVar(value=False)
        self.var_skip = tk.BooleanVar(value=False)
        self.var_arr = tk.StringVar()
        self.var_dep = tk.StringVar()

        ttk.Label(editor, text="Nástupiště").grid(row=0, column=0, padx=6, pady=4, sticky="w")
        self.platform_combo = ttk.Combobox(editor, state="readonly")
        self.platform_combo.grid(row=1, column=0, padx=6, pady=4, sticky="ew")

        ttk.Label(editor, text="km").grid(row=0, column=1, padx=6, pady=4, sticky="w")
        ttk.Entry(editor, textvariable=self.var_km).grid(row=1, column=1, padx=6, pady=4, sticky="ew")

        ttk.Label(editor, text="km/h (automaticky)").grid(row=0, column=2, padx=6, pady=4, sticky="w")
        ttk.Entry(editor, textvariable=self.var_auto_kmh, state="readonly").grid(row=1, column=2, padx=6, pady=4, sticky="ew")

        ttk.Checkbutton(editor, text="jede jinudy", variable=self.var_other, command=self.sync_inline_state).grid(row=0, column=3, padx=6, pady=4, sticky="w")
        ttk.Checkbutton(editor, text="nezastavuje", variable=self.var_skip, command=self.sync_inline_state).grid(row=1, column=3, padx=6, pady=4, sticky="w")

        ttk.Label(editor, text="Příjezd").grid(row=0, column=4, padx=6, pady=4, sticky="w")
        self.arr_entry = ttk.Entry(editor, textvariable=self.var_arr)
        self.arr_entry.grid(row=1, column=4, padx=6, pady=4, sticky="ew")

        ttk.Label(editor, text="Odjezd").grid(row=0, column=5, padx=6, pady=4, sticky="w")
        self.dep_entry = ttk.Entry(editor, textvariable=self.var_dep)
        self.dep_entry.grid(row=1, column=5, padx=6, pady=4, sticky="ew")

        ttk.Label(editor, text="Pevné kódy").grid(row=0, column=6, padx=6, pady=4, sticky="w")
        self.fixed_lb = tk.Listbox(editor, selectmode=tk.MULTIPLE, height=5, exportselection=False)
        self.fixed_lb.grid(row=1, column=6, columnspan=2, padx=6, pady=4, sticky="ew")
        for fc in self.fixed_codes:
            self.fixed_lb.insert(tk.END, f"{fc.symbol} | {fc.description}")

        inline_btns = ttk.Frame(editor)
        inline_btns.grid(row=2, column=0, columnspan=8, sticky="e", padx=6, pady=6)
        ttk.Button(inline_btns, text="Použít změny na řádek", command=self.apply_record_changes).pack(side="left", padx=4)

        ttk.Label(
            self,
            text="Jízdní doby teď počítají i přeskočené zastávky. Konečně méně ručního trápení.",
        ).grid(row=6, column=0, columnspan=2, sticky="w", padx=8)

        self.add_buttons(7)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(4, weight=1)

        self.refresh_records()
        if self.trip.stop_records:
            self.tree.selection_set("0")
            self._load_selected_record(0)

    def _find_rule_skipping_ignored(self, from_index: int):
        if from_index < 0 or from_index >= len(self.trip.stop_records) - 1:
            return None

        start_rec = self.trip.stop_records[from_index]
        start_time = start_rec.departure or start_rec.arrival
        start_km = _parse_km(start_rec.km)

        if not start_time:
            return None

        ignored = 0
        for j in range(from_index + 1, len(self.trip.stop_records)):
            rec = self.trip.stop_records[j]
            if rec.goes_other_way or rec.does_not_stop:
                ignored += 1
                continue

            rule = self.travel_lookup.get((start_rec.stop_id, rec.stop_id))
            if rule:
                return {
                    "target_index": j,
                    "rule": rule,
                    "start_time": start_time,
                    "start_km": start_km,
                }

            break
        return None

    def refresh_records(self):
        selected = self.selected_record_index

        self._loading_record = True
        try:
            for item in self.tree.get_children():
                self.tree.delete(item)

            prev_time = ""
            prev_km = ""

            for idx, rec in enumerate(self.trip.stop_records):
                stop = self.stop_lookup.get(rec.stop_id)
                stop_name = stop.name if stop else rec.stop_id

                platform_name = ""
                if stop and rec.platform_id:
                    for p in stop.platforms:
                        if p.id == rec.platform_id:
                            platform_name = p.name
                            break

                display_time = rec.departure or rec.arrival
                auto_speed = ""
                if not rec.goes_other_way and not rec.does_not_stop and prev_time and prev_km and display_time and rec.km:
                    auto_speed = _compute_speed(prev_time, prev_km, display_time, rec.km)
                rec.speed_kmh = auto_speed

                fixed_text = ", ".join(fc.symbol for fc in self.fixed_codes if fc.id in rec.fixed_code_ids)

                self.tree.insert(
                    "",
                    tk.END,
                    iid=str(idx),
                    values=(
                        stop_name,
                        platform_name,
                        rec.km,
                        auto_speed,
                        "Ano" if rec.goes_other_way else "Ne",
                        "Ano" if rec.does_not_stop else "Ne",
                        rec.arrival,
                        rec.departure,
                        fixed_text,
                    ),
                )

                if not rec.goes_other_way and not rec.does_not_stop and display_time and rec.km:
                    prev_time = display_time
                    prev_km = rec.km

            if selected is not None and 0 <= selected < len(self.trip.stop_records):
                self.tree.selection_set(str(selected))
        finally:
            self._loading_record = False

    def _store_current_record(self):
        if self.selected_record_index is None:
            return
        idx = self.selected_record_index
        if idx >= len(self.trip.stop_records):
            return

        rec = self.trip.stop_records[idx]
        stop = self.stop_lookup.get(rec.stop_id)

        combo_index = self.platform_combo.current()
        if stop and combo_index > 0:
            rec.platform_id = stop.platforms[combo_index - 1].id
        else:
            rec.platform_id = ""

        rec.km = self.var_km.get().strip()
        rec.goes_other_way = bool(self.var_other.get())
        rec.does_not_stop = bool(self.var_skip.get())
        rec.arrival = "" if rec.goes_other_way or rec.does_not_stop else self.var_arr.get().strip()
        rec.departure = "" if rec.goes_other_way or rec.does_not_stop else self.var_dep.get().strip()
        rec.fixed_code_ids = [self.fixed_codes[i].id for i in self.fixed_lb.curselection()]

    def _load_selected_record(self, idx: int):
        if idx < 0 or idx >= len(self.trip.stop_records):
            return

        self._loading_record = True
        try:
            self.selected_record_index = idx
            rec = self.trip.stop_records[idx]
            stop = self.stop_lookup.get(rec.stop_id)

            platform_values = [""]
            if stop:
                platform_values.extend([p.name for p in stop.platforms])
            self.platform_combo["values"] = platform_values

            selected_platform_index = 0
            if stop and rec.platform_id:
                for i, p in enumerate(stop.platforms, start=1):
                    if p.id == rec.platform_id:
                        selected_platform_index = i
                        break
            self.platform_combo.current(selected_platform_index)

            self.var_km.set(rec.km)
            self.var_auto_kmh.set(rec.speed_kmh)
            self.var_other.set(rec.goes_other_way)
            self.var_skip.set(rec.does_not_stop)
            self.var_arr.set(rec.arrival)
            self.var_dep.set(rec.departure)

            self.fixed_lb.selection_clear(0, tk.END)
            for i, fc in enumerate(self.fixed_codes):
                if fc.id in rec.fixed_code_ids:
                    self.fixed_lb.selection_set(i)

            self.sync_inline_state()
        finally:
            self._loading_record = False

    def on_select_record(self, _event=None):
        if self._loading_record:
            return

        sel = self.tree.selection()
        if not sel:
            return

        new_idx = int(sel[0])

        if self.selected_record_index is not None and self.selected_record_index != new_idx:
            self._store_current_record()

        self._load_selected_record(new_idx)

    def sync_inline_state(self):
        if self.var_skip.get() or self.var_other.get():
            self.arr_entry.state(["disabled"])
            self.dep_entry.state(["disabled"])
        else:
            self.arr_entry.state(["!disabled"])
            self.dep_entry.state(["!disabled"])

    def _apply_rule_result_to_target(self, source_index: int, target_index: int, rule: TravelTimeRule):
        prev = self.trip.stop_records[source_index]
        cur = self.trip.stop_records[target_index]

        base_time = prev.departure or prev.arrival
        base_minutes = _parse_time_to_minutes(base_time)
        if base_minutes is None:
            return

        next_time = _minutes_to_hhmm(base_minutes + rule.minutes)

        prev_km = _parse_km(prev.km)
        rule_km = _parse_km(rule.km) or 0.0
        if prev_km is None:
            prev_km = 0.0 if source_index == 0 else None

        if prev_km is not None:
            cur.km = _format_km(prev_km + rule_km)

        if cur.goes_other_way or cur.does_not_stop:
            return

        had_arr = bool(cur.arrival.strip())
        had_dep = bool(cur.departure.strip())

        if had_arr and had_dep:
            a = _parse_time_to_minutes(cur.arrival)
            d = _parse_time_to_minutes(cur.departure)
            stay = (d - a) if a is not None and d is not None else 0
            if stay < 0:
                stay = 0
            cur.arrival = next_time
            cur.departure = _minutes_to_hhmm((_parse_time_to_minutes(next_time) or 0) + stay)
        elif had_arr and not had_dep:
            cur.arrival = next_time
            cur.departure = next_time
        elif not had_arr and had_dep:
            cur.arrival = next_time
            cur.departure = next_time
        else:
            cur.arrival = ""
            cur.departure = next_time

    def _recalculate_downstream_from_index(self, start_index: int):
        current_index = start_index
        while current_index < len(self.trip.stop_records) - 1:
            found = self._find_rule_skipping_ignored(current_index)
            if not found:
                break
            target_index = found["target_index"]
            rule = found["rule"]
            self._apply_rule_result_to_target(current_index, target_index, rule)
            current_index = target_index

    def auto_fill_by_travel_times(self):
        if not self.trip.stop_records:
            return

        self._store_current_record()

        first_valid = None
        for i, rec in enumerate(self.trip.stop_records):
            if not rec.goes_other_way and not rec.does_not_stop:
                first_valid = i
                break

        if first_valid is None:
            messagebox.showerror("Chyba", "Spoj nemá žádnou platnou zastávku.")
            return

        first = self.trip.stop_records[first_valid]
        start_time = (first.departure or first.arrival or "").strip()
        if not start_time:
            messagebox.showerror("Chyba", "Nejdřív vyplň odjezd první obsluhované zastávky.")
            return

        first.departure = start_time
        first.arrival = ""
        if not first.km.strip():
            first.km = "0,00"

        self._recalculate_downstream_from_index(first_valid)
        current = self.selected_record_index
        self.refresh_records()
        if current is not None:
            self._load_selected_record(current)

    def recalculate_from_existing_times(self):
        self._store_current_record()

        base_index = None
        for i, rec in enumerate(self.trip.stop_records):
            if rec.goes_other_way or rec.does_not_stop:
                continue
            if (rec.departure or rec.arrival).strip():
                base_index = i
                break

        if base_index is None:
            messagebox.showerror("Chyba", "Nejdřív musí být někde vyplněný čas.")
            return

        self._recalculate_downstream_from_index(base_index)
        current = self.selected_record_index
        self.refresh_records()
        if current is not None:
            self._load_selected_record(current)

    def apply_record_changes(self):
        self._store_current_record()
        current = self.selected_record_index
        if current is not None:
            self._recalculate_downstream_from_index(current)
        self.refresh_records()
        if current is not None:
            self._load_selected_record(current)

    def apply_time_shift_event(self, _event=None):
        self.apply_time_shift()

    def apply_time_shift(self):
        raw = self.var_time_shift.get().strip().replace(" ", "")
        if not raw:
            return

        try:
            shift = int(raw)
        except ValueError:
            messagebox.showerror("Chyba", "Posunutí času musí být celé číslo minut, třeba +60 nebo -5.")
            return

        if shift == 0:
            return

        self._store_current_record()

        for rec in self.trip.stop_records:
            if rec.arrival:
                rec.arrival = _shift_time_text(rec.arrival, shift)
            if rec.departure:
                rec.departure = _shift_time_text(rec.departure, shift)

        current = self.selected_record_index
        self.refresh_records()
        if current is not None:
            self._load_selected_record(current)

        self.var_time_shift.set("0")

    def on_save(self):
        if not self.var_trip_number.get().strip():
            messagebox.showerror("Chyba", "Číslo spoje je povinné.")
            return

        self._store_current_record()
        self.refresh_records()

        self.trip.trip_number = self.var_trip_number.get().strip()
        self.trip.time_shift = 0
        self.trip.time_code_ids = [self.time_codes[i].id for i in self.codes_list.curselection()]
        self.result = self.trip
        self.destroy()


class DutyDialog(BaseDialog):
    def __init__(self, master, carriers, lines, duty: Optional[Duty] = None, blocked_trip_ids: Optional[List[str]] = None, time_codes: Optional[List[TimeCode]] = None):
        super().__init__(master, "Turnus")
        self.geometry("1650x920")
        self.carriers = carriers
        self.lines = lines
        self.time_codes = time_codes or []
        self.duty = copy.deepcopy(duty) if duty else Duty(id=new_id(), name="", duty_number="")
        self.blocked_trip_ids = set(blocked_trip_ids or [])

        if duty:
            for item in duty.items:
                if item.kind == "trip" and item.ref_trip_id in self.blocked_trip_ids:
                    self.blocked_trip_ids.remove(item.ref_trip_id)

        self.var_name = tk.StringVar(value=self.duty.name)
        self.var_number = tk.StringVar(value=self.duty.duty_number)
        self.var_filter_codes = tk.StringVar()
        self.var_search = tk.StringVar()

        self.tc_lookup = {tc.id: tc.symbol for tc in self.time_codes}
        self.trip_map = {}
        for line in self.lines:
            for trip in line.trips:
                self.trip_map[trip.id] = (line, trip)

        self.trip_options = []
        for line in self.lines:
            for trip in line.trips:
                if trip.id not in self.blocked_trip_ids:
                    self.trip_options.append((line, trip))

        ttk.Label(self, text="Název").grid(row=0, column=0, sticky="w", padx=8, pady=4)
        ttk.Entry(self, textvariable=self.var_name).grid(row=0, column=1, sticky="ew", padx=8, pady=4)

        ttk.Label(self, text="Číslo turnusu").grid(row=1, column=0, sticky="w", padx=8, pady=4)
        ttk.Entry(self, textvariable=self.var_number).grid(row=1, column=1, sticky="ew", padx=8, pady=4)

        ttk.Label(self, text="Společnost").grid(row=2, column=0, sticky="w", padx=8, pady=4)
        carrier_names = [""] + [c.name for c in self.carriers]
        self.carrier_combo = ttk.Combobox(self, values=carrier_names, state="readonly")
        self.carrier_combo.grid(row=2, column=1, sticky="ew", padx=8, pady=4)

        if self.duty.carrier_id:
            for i, c in enumerate(self.carriers, start=1):
                if c.id == self.duty.carrier_id:
                    self.carrier_combo.current(i)
                    break
        else:
            self.carrier_combo.current(0)

        filters = ttk.LabelFrame(self, text="Filtr a vyhledávání")
        filters.grid(row=3, column=0, columnspan=2, sticky="ew", padx=8, pady=6)
        for col in range(4):
            filters.columnconfigure(col, weight=1)

        ttk.Label(filters, text="Filtr časových kódů").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        filter_entry = ttk.Entry(filters, textvariable=self.var_filter_codes)
        filter_entry.grid(row=1, column=0, sticky="ew", padx=6, pady=4)
        filter_entry.bind("<KeyRelease>", lambda e: self.refresh_available())

        ttk.Label(filters, text="Vyhledávání").grid(row=0, column=1, sticky="w", padx=6, pady=4)
        search_entry = ttk.Entry(filters, textvariable=self.var_search)
        search_entry.grid(row=1, column=1, sticky="ew", padx=6, pady=4)
        search_entry.bind("<KeyRelease>", lambda e: self.refresh_available())

        ttk.Label(filters, text="Tip").grid(row=0, column=2, sticky="w", padx=6, pady=4)
        ttk.Label(
            filters,
            text="Např. 7 nebo X nebo 7,X. Hledání bere linku, spoj, IS číslo, začátek, konec i název.",
        ).grid(row=1, column=2, columnspan=2, sticky="w", padx=6, pady=4)

        wrap = ttk.Frame(self)
        wrap.grid(row=4, column=0, columnspan=2, sticky="nsew", padx=8, pady=8)
        wrap.columnconfigure(0, weight=1)
        wrap.columnconfigure(2, weight=1)
        wrap.rowconfigure(1, weight=1)

        ttk.Label(wrap, text="Dostupné spoje").grid(row=0, column=0, sticky="w")
        ttk.Label(wrap, text="Položky turnusu").grid(row=0, column=2, sticky="w")

        available_frame = ttk.Frame(wrap)
        available_frame.grid(row=1, column=0, sticky="nsew")
        available_frame.columnconfigure(0, weight=1)
        available_frame.rowconfigure(0, weight=1)

        self.available_tree = ttk.Treeview(
            available_frame,
            columns=("line", "trip", "isno", "start", "end", "km", "codes"),
            show="headings",
            height=18,
        )
        available_columns = [
            ("line", "Linka", 90),
            ("trip", "Spoj", 90),
            ("isno", "IS", 100),
            ("start", "Začátek", 90),
            ("end", "Konec", 90),
            ("km", "km", 90),
            ("codes", "Kódy", 160),
        ]
        for col, label, width in available_columns:
            self.available_tree.heading(col, text=label)
            self.available_tree.column(col, width=width, anchor="center")
        self.available_tree.grid(row=0, column=0, sticky="nsew")

        avail_scroll = ttk.Scrollbar(available_frame, orient="vertical", command=self.available_tree.yview)
        avail_scroll.grid(row=0, column=1, sticky="ns")
        self.available_tree.configure(yscrollcommand=avail_scroll.set)

        btns = ttk.Frame(wrap)
        btns.grid(row=1, column=1, padx=8, sticky="ns")
        ttk.Button(btns, text="> Přidat spoj", command=self.add_trip).pack(fill="x", pady=2)
        ttk.Button(btns, text="> Bezp. přestávka", command=self.add_safety_break).pack(fill="x", pady=2)
        ttk.Button(btns, text="> Přestávka", command=self.add_break).pack(fill="x", pady=2)
        ttk.Button(btns, text="< Odebrat", command=self.remove_item).pack(fill="x", pady=2)

        items_frame = ttk.Frame(wrap)
        items_frame.grid(row=1, column=2, sticky="nsew")
        items_frame.columnconfigure(0, weight=1)
        items_frame.rowconfigure(0, weight=1)

        self.items_tree = ttk.Treeview(
            items_frame,
            columns=("kind", "line", "trip", "isno", "start", "end", "km"),
            show="headings",
            height=18,
        )
        item_columns = [
            ("kind", "Typ", 120),
            ("line", "Linka", 90),
            ("trip", "Spoj", 90),
            ("isno", "IS", 100),
            ("start", "Začátek", 90),
            ("end", "Konec", 90),
            ("km", "km", 90),
        ]
        for col, label, width in item_columns:
            self.items_tree.heading(col, text=label)
            self.items_tree.column(col, width=width, anchor="center")
        self.items_tree.grid(row=0, column=0, sticky="nsew")

        items_scroll = ttk.Scrollbar(items_frame, orient="vertical", command=self.items_tree.yview)
        items_scroll.grid(row=0, column=1, sticky="ns")
        self.items_tree.configure(yscrollcommand=items_scroll.set)

        summary = ttk.LabelFrame(self, text="Souhrn turnusu")
        summary.grid(row=5, column=0, columnspan=2, sticky="ew", padx=8, pady=6)
        for col in range(3):
            summary.columnconfigure(col, weight=1)

        self.lbl_drive = ttk.Label(summary, text="Řízení: 0 min")
        self.lbl_drive.grid(row=0, column=0, sticky="w", padx=8, pady=6)

        self.lbl_breaks = ttk.Label(summary, text="Přestávky / stání: 0 min")
        self.lbl_breaks.grid(row=0, column=1, sticky="w", padx=8, pady=6)

        self.lbl_km = ttk.Label(summary, text="Celkem km: 0,00")
        self.lbl_km.grid(row=0, column=2, sticky="w", padx=8, pady=6)

        self.columnconfigure(1, weight=1)
        self.rowconfigure(4, weight=1)

        self.refresh_available()
        self.refresh_items()
        self.add_buttons(6)

    def _trip_codes(self, trip):
        return [self.tc_lookup[x] for x in trip.time_code_ids if x in self.tc_lookup]

    def _trip_is_number(self, line, trip):
        return f"{line.line_number}{trip.trip_number}"

    def _trip_start_end(self, trip):
        if not trip.stop_records:
            return "", ""
        first = trip.stop_records[0]
        last = trip.stop_records[-1]
        return (first.departure or first.arrival or "").strip(), (last.arrival or last.departure or "").strip()

    def _trip_km(self, trip):
        kms = [_parse_km(r.km) for r in trip.stop_records]
        kms = [x for x in kms if x is not None]
        if not kms:
            return 0.0
        return max(kms) - min(kms)

    def _trip_matches_filter(self, line, trip):
        filter_raw = self.var_filter_codes.get().strip()
        search_raw = self.var_search.get().strip().lower()

        symbols = self._trip_codes(trip)
        symbol_set = set(symbols)

        if filter_raw:
            requested = {x.strip() for x in filter_raw.split(",") if x.strip()}
            if requested and not requested.issubset(symbol_set):
                return False

        if search_raw:
            start, end = self._trip_start_end(trip)
            is_no = self._trip_is_number(line, trip)
            haystack = " | ".join([
                str(line.line_number),
                str(trip.trip_number),
                str(is_no),
                start,
                end,
                line.name or "",
            ]).lower()
            if search_raw not in haystack:
                return False

        return True

    def refresh_available(self):
        for item in self.available_tree.get_children():
            self.available_tree.delete(item)

        available = []
        for line, trip in self.trip_options:
            if self._trip_matches_filter(line, trip):
                start, end = self._trip_start_end(trip)
                available.append((line, trip, start, end, self._trip_km(trip), self._trip_codes(trip)))

        def _key(x):
            line, trip, *_ = x
            try:
                line_no = int(line.line_number)
            except Exception:
                line_no = 10**9
            try:
                trip_no = int(trip.trip_number)
            except Exception:
                trip_no = 10**9
            return (line_no, line.line_number, trip_no, trip.trip_number)

        available.sort(key=_key)

        for line, trip, start, end, km, symbols in available:
            self.available_tree.insert(
                "",
                tk.END,
                iid=trip.id,
                values=(
                    line.line_number,
                    trip.trip_number,
                    self._trip_is_number(line, trip),
                    start,
                    end,
                    _format_km(km),
                    ",".join(symbols),
                ),
            )

    def refresh_items(self):
        for item in self.items_tree.get_children():
            self.items_tree.delete(item)

        for idx, item in enumerate(self.duty.items):
            iid = f"item_{idx}"

            if item.kind == "trip" and item.ref_trip_id in self.trip_map:
                line, trip = self.trip_map[item.ref_trip_id]
                start, end = self._trip_start_end(trip)
                km = self._trip_km(trip)
                self.items_tree.insert(
                    "",
                    tk.END,
                    iid=iid,
                    values=(
                        "Spoj",
                        line.line_number,
                        trip.trip_number,
                        self._trip_is_number(line, trip),
                        start,
                        end,
                        _format_km(km),
                    ),
                )
            elif item.kind == "safety_break":
                self.items_tree.insert("", tk.END, iid=iid, values=("Bezpečn. přest.", "", "", "", item.time_from, item.time_to, ""))
            elif item.kind == "break":
                self.items_tree.insert("", tk.END, iid=iid, values=("Přestávka", "", "", "", item.time_from, item.time_to, ""))

        self.refresh_summary()

    def refresh_summary(self):
        drive = 0
        breaks = 0
        km_total = 0.0

        for item in self.duty.items:
            if item.kind == "trip" and item.ref_trip_id in self.trip_map:
                _line, trip = self.trip_map[item.ref_trip_id]
                start, end = self._trip_start_end(trip)
                m1 = _parse_time_to_minutes(start)
                m2 = _parse_time_to_minutes(end)
                if m1 is not None and m2 is not None:
                    if m2 < m1:
                        m2 += 24 * 60
                    drive += m2 - m1
                km_total += self._trip_km(trip)
            elif item.kind in ("break", "safety_break"):
                m1 = _parse_time_to_minutes(item.time_from)
                m2 = _parse_time_to_minutes(item.time_to)
                if m1 is not None and m2 is not None:
                    if m2 < m1:
                        m2 += 24 * 60
                    breaks += m2 - m1

        self.lbl_drive.config(text=f"Řízení: {drive} min")
        self.lbl_breaks.config(text=f"Přestávky / stání: {breaks} min")
        self.lbl_km.config(text=f"Celkem km: {_format_km(km_total)}")

    def add_trip(self):
        sel = self.available_tree.selection()
        if not sel:
            return

        trip_id = sel[0]
        idx = next((i for i, (_line, trip) in enumerate(self.trip_options) if trip.id == trip_id), None)
        if idx is None:
            return

        _line, trip = self.trip_options.pop(idx)
        self.duty.items.append(DutyItem(kind="trip", ref_trip_id=trip.id))
        self.refresh_available()
        self.refresh_items()

    def _add_time_item(self, kind: str, title: str):
        dlg = tk.Toplevel(self)
        dlg.title(title)
        dlg.transient(self)
        dlg.grab_set()

        var_from = tk.StringVar()
        var_to = tk.StringVar()

        ttk.Label(dlg, text="Od").grid(row=0, column=0, padx=8, pady=4)
        ttk.Entry(dlg, textvariable=var_from).grid(row=0, column=1, padx=8, pady=4)

        ttk.Label(dlg, text="Do").grid(row=1, column=0, padx=8, pady=4)
        ttk.Entry(dlg, textvariable=var_to).grid(row=1, column=1, padx=8, pady=4)

        def save():
            self.duty.items.append(
                DutyItem(
                    kind=kind,
                    title=title,
                    time_from=var_from.get().strip(),
                    time_to=var_to.get().strip(),
                )
            )
            self.refresh_items()
            dlg.destroy()

        ttk.Button(dlg, text="Uložit", command=save).grid(row=2, column=0, padx=8, pady=8)
        ttk.Button(dlg, text="Zrušit", command=dlg.destroy).grid(row=2, column=1, padx=8, pady=8)

    def add_safety_break(self):
        self._add_time_item("safety_break", "Bezpečnostní přestávka")

    def add_break(self):
        self._add_time_item("break", "Přestávka")

    def remove_item(self):
        sel = self.items_tree.selection()
        if not sel:
            return

        iid = sel[0]
        if not iid.startswith("item_"):
            return

        idx = int(iid.split("_", 1)[1])
        if idx < 0 or idx >= len(self.duty.items):
            return

        item = self.duty.items.pop(idx)

        if item.kind == "trip" and item.ref_trip_id in self.trip_map:
            self.trip_options.append(self.trip_map[item.ref_trip_id])

        self.refresh_available()
        self.refresh_items()

    def on_save(self):
        if not self.var_name.get().strip():
            messagebox.showerror("Chyba", "Název turnusu je povinný.")
            return
        if not self.var_number.get().strip():
            messagebox.showerror("Chyba", "Číslo turnusu je povinné.")
            return

        self.duty.name = self.var_name.get().strip()
        self.duty.duty_number = self.var_number.get().strip()

        sel = self.carrier_combo.current()
        self.duty.carrier_id = self.carriers[sel - 1].id if sel > 0 else ""

        self.result = self.duty
        self.destroy()
