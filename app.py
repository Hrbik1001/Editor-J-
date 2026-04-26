from __future__ import annotations

import copy
from collections import defaultdict
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

from dialogs import (
    CarrierDialog,
    CodeDialog,
    StopDialog,
    LineDialog,
    TripDialog,
    DutyDialog,
    TravelTimeDialog,
)
from exports import (
    export_stops_pdf,
    export_duties_pdf,
    export_lines_pdf,
    export_timetable_xml,
    export_stop_board_all,
    export_stop_board_one,
    export_platform_board_all,
    export_platform_board_one,
    export_stations_xml,
    export_stop_line_timetable_pdf,
)
from storage import load_db, save_db, create_default_db, DATA_FILE, new_id
from ui_utils import confirm_delete, info, error
from models import TimeCode, FixedCode


class JREditorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Editor JŘ")
        self.geometry("1500x920")
        self.minsize(1260, 760)

        self.current_file = DATA_FILE
        self.db = load_db(self.current_file)

        self._build_menu()

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True)

        self.tab_carriers = ttk.Frame(self.notebook)
        self.tab_time_codes = ttk.Frame(self.notebook)
        self.tab_fixed_codes = ttk.Frame(self.notebook)
        self.tab_stops = ttk.Frame(self.notebook)
        self.tab_travel_times = ttk.Frame(self.notebook)
        self.tab_lines = ttk.Frame(self.notebook)
        self.tab_duties = ttk.Frame(self.notebook)
        self.tab_export = ttk.Frame(self.notebook)
        self.tab_settings = ttk.Frame(self.notebook)

        self.notebook.add(self.tab_carriers, text="Dopravci")
        self.notebook.add(self.tab_time_codes, text="Časové kódy")
        self.notebook.add(self.tab_fixed_codes, text="Pevné kódy")
        self.notebook.add(self.tab_stops, text="Zastávky")
        self.notebook.add(self.tab_travel_times, text="Jízdní doby")
        self.notebook.add(self.tab_lines, text="Linky")
        self.notebook.add(self.tab_duties, text="Turnusy")
        self.notebook.add(self.tab_export, text="Export")
        self.notebook.add(self.tab_settings, text="Nastavení")

        self._build_carriers_tab()
        self._build_time_codes_tab()
        self._build_fixed_codes_tab()
        self._build_stops_tab()
        self._build_travel_times_tab()
        self._build_lines_tab()
        self._build_duties_tab()
        self._build_export_tab()
        self._build_settings_tab()

        self.refresh_all()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self._update_title()

    def _build_menu(self):
        menubar = tk.Menu(self)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Nový projekt", command=self.new_project)
        file_menu.add_command(label="Otevřít projekt...", command=self.open_project)
        file_menu.add_command(label="Uložit", command=self.save_project)
        file_menu.add_command(label="Uložit jako...", command=self.save_project_as)
        file_menu.add_separator()
        file_menu.add_command(label="Konec", command=self.on_close)
        menubar.add_cascade(label="Soubor", menu=file_menu)
        self.config(menu=menubar)

    def _update_title(self):
        self.title(f"Editor JŘ - {self.current_file}")

    def refresh_all(self):
        self.refresh_carriers()
        self.refresh_time_codes()
        self.refresh_fixed_codes()
        self.refresh_stops()
        self.refresh_travel_times()
        self.refresh_lines()
        self.refresh_duties()
        self.refresh_settings()

    def save(self):
        save_db(self.db, self.current_file)
        self._update_title()

    def save_project(self):
        self.save()
        info("Projekt byl uložen.")

    def save_project_as(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
            initialfile="jr_data.json",
        )
        if not path:
            return
        self.current_file = path
        self.save()
        info("Projekt byl uložen.")

    def open_project(self):
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json"), ("Vše", "*.*")])
        if not path:
            return
        try:
            self.db = load_db(path)
            self.current_file = path
            self.refresh_all()
            self._update_title()
            info("Projekt byl načten.")
        except Exception as e:
            messagebox.showerror("Chyba", f"Projekt se nepodařilo načíst:\n{e}")

    def new_project(self):
        if not messagebox.askyesno("Nový projekt", "Opravdu vytvořit nový projekt?"):
            return
        self.db = create_default_db()
        self.current_file = DATA_FILE
        self.refresh_all()
        self._update_title()

    def on_close(self):
        self.save()
        self.destroy()

    def get_sorted_stops(self):
        mode = self.db.settings.stop_sort_mode
        if mode == "alpha":
            return sorted(self.db.stops, key=lambda s: s.name.lower())
        return sorted(self.db.stops, key=lambda s: s.stop_number)

    # -------------------- Dopravci --------------------
    def _build_carriers_tab(self):
        self.carriers_tree = self._build_crud_table(
            self.tab_carriers,
            columns=("name", "ico", "abbr", "web", "phone", "email", "seat"),
            headings={
                "name": "Název",
                "ico": "IČO",
                "abbr": "Zkratka",
                "web": "Web",
                "phone": "Tel.",
                "email": "E-mail",
                "seat": "Sídlo",
            },
        )
        self._build_buttons(
            self.tab_carriers,
            [("Přidat", self.add_carrier), ("Upravit", self.edit_carrier), ("Smazat", self.delete_carrier)],
        )

    def refresh_carriers(self):
        self._clear_tree(self.carriers_tree)
        for item in self.db.carriers:
            self.carriers_tree.insert(
                "",
                tk.END,
                iid=item.id,
                values=(item.name, item.ico, item.abbreviation, item.web, item.phone, item.email, item.seat),
            )

    def add_carrier(self):
        dlg = CarrierDialog(self)
        self.wait_window(dlg)
        if dlg.result:
            self.db.carriers.append(dlg.result)
            self.save()
            self.refresh_carriers()

    def edit_carrier(self):
        item = self._selected_by_id(self.carriers_tree, self.db.carriers)
        if not item:
            return
        dlg = CarrierDialog(self, item)
        self.wait_window(dlg)
        if dlg.result:
            idx = self.db.carriers.index(item)
            self.db.carriers[idx] = dlg.result
            self.save()
            self.refresh_carriers()
            self.refresh_lines()
            self.refresh_duties()

    def delete_carrier(self):
        item = self._selected_by_id(self.carriers_tree, self.db.carriers)
        if item and confirm_delete(item.name):
            self.db.carriers.remove(item)
            self.save()
            self.refresh_carriers()
            self.refresh_lines()
            self.refresh_duties()

    # -------------------- Časové kódy --------------------
    def _build_time_codes_tab(self):
        self.time_codes_tree = self._build_crud_table(
            self.tab_time_codes,
            columns=("symbol", "description"),
            headings={"symbol": "Znak", "description": "Popis"},
        )
        self._build_buttons(
            self.tab_time_codes,
            [("Přidat", self.add_time_code), ("Upravit", self.edit_time_code), ("Smazat", self.delete_time_code)],
        )

    def refresh_time_codes(self):
        self._clear_tree(self.time_codes_tree)
        for item in self.db.time_codes:
            self.time_codes_tree.insert("", tk.END, iid=item.id, values=(item.symbol, item.description))

    def add_time_code(self):
        dlg = CodeDialog(self, "Časový kód")
        self.wait_window(dlg)
        if dlg.result:
            self.db.time_codes.append(TimeCode(**dlg.result))
            self.save()
            self.refresh_time_codes()

    def edit_time_code(self):
        item = self._selected_by_id(self.time_codes_tree, self.db.time_codes)
        if not item:
            return
        dlg = CodeDialog(self, "Časový kód", item.symbol, item.description, item.id)
        self.wait_window(dlg)
        if dlg.result:
            idx = self.db.time_codes.index(item)
            self.db.time_codes[idx] = TimeCode(**dlg.result)
            self.save()
            self.refresh_time_codes()

    def delete_time_code(self):
        item = self._selected_by_id(self.time_codes_tree, self.db.time_codes)
        if item and confirm_delete(f"{item.symbol} | {item.description}"):
            self.db.time_codes.remove(item)
            self.save()
            self.refresh_time_codes()

    # -------------------- Pevné kódy --------------------
    def _build_fixed_codes_tab(self):
        self.fixed_codes_tree = self._build_crud_table(
            self.tab_fixed_codes,
            columns=("symbol", "description"),
            headings={"symbol": "Znak", "description": "Popis"},
        )
        self._build_buttons(
            self.tab_fixed_codes,
            [("Přidat", self.add_fixed_code), ("Upravit", self.edit_fixed_code), ("Smazat", self.delete_fixed_code)],
        )

    def refresh_fixed_codes(self):
        self._clear_tree(self.fixed_codes_tree)
        for item in self.db.fixed_codes:
            self.fixed_codes_tree.insert("", tk.END, iid=item.id, values=(item.symbol, item.description))

    def add_fixed_code(self):
        dlg = CodeDialog(self, "Pevný kód")
        self.wait_window(dlg)
        if dlg.result:
            self.db.fixed_codes.append(FixedCode(**dlg.result))
            self.save()
            self.refresh_fixed_codes()

    def edit_fixed_code(self):
        item = self._selected_by_id(self.fixed_codes_tree, self.db.fixed_codes)
        if not item:
            return
        dlg = CodeDialog(self, "Pevný kód", item.symbol, item.description, item.id)
        self.wait_window(dlg)
        if dlg.result:
            idx = self.db.fixed_codes.index(item)
            self.db.fixed_codes[idx] = FixedCode(**dlg.result)
            self.save()
            self.refresh_fixed_codes()

    def delete_fixed_code(self):
        item = self._selected_by_id(self.fixed_codes_tree, self.db.fixed_codes)
        if item and confirm_delete(f"{item.symbol} | {item.description}"):
            self.db.fixed_codes.remove(item)
            self.save()
            self.refresh_fixed_codes()
            self.refresh_stops()
            self.refresh_lines()

    # -------------------- Zastávky --------------------
    def _build_stops_tab(self):
        self.stops_tree = self._build_crud_table(
            self.tab_stops,
            columns=("number", "name", "coords", "ids", "zone", "platforms", "fixed"),
            headings={
                "number": "Číslo zastávky",
                "name": "Název zastávky",
                "coords": "Souřadnice",
                "ids": "Integrovaný systém",
                "zone": "Tarifní zóna/pásmo",
                "platforms": "Nástupiště",
                "fixed": "Pevné kódy",
            },
        )
        self._build_buttons(
            self.tab_stops,
            [("Přidat", self.add_stop), ("Upravit", self.edit_stop), ("Smazat", self.delete_stop)],
        )

    def refresh_stops(self):
        self._clear_tree(self.stops_tree)
        fixed_lookup = {x.id: x for x in self.db.fixed_codes}
        for item in self.get_sorted_stops():
            fixed = ", ".join(fixed_lookup[x].symbol for x in item.fixed_code_ids if x in fixed_lookup)
            platforms = ", ".join(p.name for p in item.platforms)
            self.stops_tree.insert(
                "",
                tk.END,
                iid=item.id,
                values=(
                    item.stop_number,
                    item.name,
                    item.coordinates,
                    item.integrated_system,
                    item.tariff_zone,
                    platforms,
                    fixed,
                ),
            )

    def add_stop(self):
        existing = [s.stop_number for s in self.db.stops]
        dlg = StopDialog(self, self.db.fixed_codes, existing_stop_numbers=existing)
        self.wait_window(dlg)
        if dlg.result:
            self.db.stops.append(dlg.result)
            self.save()
            self.refresh_stops()
            self.refresh_travel_times()
            self.refresh_lines()

    def edit_stop(self):
        item = self._selected_by_id(self.stops_tree, self.db.stops)
        if not item:
            return
        existing = [s.stop_number for s in self.db.stops]
        dlg = StopDialog(self, self.db.fixed_codes, item, existing_stop_numbers=existing)
        self.wait_window(dlg)
        if dlg.result:
            idx = self.db.stops.index(item)
            self.db.stops[idx] = dlg.result
            self.save()
            self.refresh_stops()
            self.refresh_travel_times()
            self.refresh_lines()

    def delete_stop(self):
        item = self._selected_by_id(self.stops_tree, self.db.stops)
        if item and confirm_delete(item.name):
            self.db.stops.remove(item)
            self.db.travel_times = [
                x for x in self.db.travel_times if x.from_stop_id != item.id and x.to_stop_id != item.id
            ]
            for line in self.db.lines:
                line.route = [rs for rs in line.route if rs.stop_id != item.id]
                for trip in line.trips:
                    trip.stop_records = [sr for sr in trip.stop_records if sr.stop_id != item.id]
            self.save()
            self.refresh_stops()
            self.refresh_travel_times()
            self.refresh_lines()

    # -------------------- Jízdní doby --------------------
    def _build_travel_times_tab(self):
        self.travel_times_tree = self._build_crud_table(
            self.tab_travel_times,
            columns=("from", "to", "km", "minutes", "speed"),
            headings={
                "from": "Ze zastávky",
                "to": "Do zastávky",
                "km": "km",
                "minutes": "Jízdní čas (min)",
                "speed": "km/h",
            },
        )
        self._build_buttons(
            self.tab_travel_times,
            [("Přidat", self.add_travel_time), ("Upravit", self.edit_travel_time), ("Smazat", self.delete_travel_time)],
        )

    def refresh_travel_times(self):
        self._clear_tree(self.travel_times_tree)
        stop_lookup = {s.id: s for s in self.db.stops}

        def _sort_key(rule):
            a = stop_lookup.get(rule.from_stop_id)
            b = stop_lookup.get(rule.to_stop_id)
            an = a.stop_number if a else ""
            bn = b.stop_number if b else ""
            return (an, bn)

        for item in sorted(self.db.travel_times, key=_sort_key):
            from_stop = stop_lookup.get(item.from_stop_id)
            to_stop = stop_lookup.get(item.to_stop_id)

            try:
                km = float(item.km.replace(",", "."))
                speed = km / (item.minutes / 60.0) if item.minutes > 0 else 0.0
                speed_text = f"{speed:.1f}".replace(".", ",")
            except Exception:
                speed_text = ""

            self.travel_times_tree.insert(
                "",
                tk.END,
                iid=item.id,
                values=(
                    f"{from_stop.stop_number} | {from_stop.name}" if from_stop else item.from_stop_id,
                    f"{to_stop.stop_number} | {to_stop.name}" if to_stop else item.to_stop_id,
                    item.km,
                    item.minutes,
                    speed_text,
                ),
            )

    def add_travel_time(self):
        if len(self.db.stops) < 2:
            error("Nejdřív vytvoř aspoň dvě zastávky.")
            return
        dlg = TravelTimeDialog(self, self.get_sorted_stops())
        self.wait_window(dlg)
        if dlg.result:
            self.db.travel_times.append(dlg.result)
            self.save()
            self.refresh_travel_times()

    def edit_travel_time(self):
        item = self._selected_by_id(self.travel_times_tree, self.db.travel_times)
        if not item:
            return
        dlg = TravelTimeDialog(self, self.get_sorted_stops(), item)
        self.wait_window(dlg)
        if dlg.result:
            idx = self.db.travel_times.index(item)
            self.db.travel_times[idx] = dlg.result
            self.save()
            self.refresh_travel_times()

    def delete_travel_time(self):
        item = self._selected_by_id(self.travel_times_tree, self.db.travel_times)
        if item and confirm_delete("vybranou jízdní dobu"):
            self.db.travel_times.remove(item)
            self.save()
            self.refresh_travel_times()

    # -------------------- Linky --------------------
    def _build_lines_tab(self):
        main = ttk.Panedwindow(self.tab_lines, orient=tk.VERTICAL)
        main.pack(fill="both", expand=True)

        top = ttk.Frame(main)
        bottom = ttk.Frame(main)
        main.add(top, weight=1)
        main.add(bottom, weight=1)

        self.lines_tree = self._build_crud_table(
            top,
            columns=("number", "name", "carrier", "validity", "route_count", "trip_count"),
            headings={
                "number": "Číslo linky",
                "name": "Název",
                "carrier": "Dopravce",
                "validity": "Platnost",
                "route_count": "Počet zastávek v trase",
                "trip_count": "Počet spojů",
            },
        )
        self.lines_tree.bind("<<TreeviewSelect>>", lambda e: self.refresh_line_trips())

        self._build_buttons(
            top,
            [
                ("Přidat", self.add_line),
                ("Upravit", self.edit_line),
                ("Smazat", self.delete_line),
                ("Duplikovat", self.duplicate_line),
                ("Spoje", self.add_trip),
                ("Duplikovat spoj", self.duplicate_trip),
            ],
        )

        ttk.Label(bottom, text="Spoje vybrané linky").pack(anchor="w", padx=8, pady=(8, 4))
        self.trips_tree = ttk.Treeview(bottom, columns=("number", "codes", "dir", "start", "end"), show="headings")
        for col, label, width in [
            ("number", "Číslo spoje", 120),
            ("codes", "Časové kódy", 220),
            ("dir", "Směr", 160),
            ("start", "Začátek", 120),
            ("end", "Konec", 120),
        ]:
            self.trips_tree.heading(col, text=label)
            self.trips_tree.column(col, width=width, anchor="center")
        self.trips_tree.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        trip_btns = ttk.Frame(bottom)
        trip_btns.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Button(trip_btns, text="Přidat spoj", command=self.add_trip).pack(side="left", padx=4)
        ttk.Button(trip_btns, text="Upravit spoj", command=self.edit_trip).pack(side="left", padx=4)
        ttk.Button(trip_btns, text="Duplikovat spoj", command=self.duplicate_trip).pack(side="left", padx=4)
        ttk.Button(trip_btns, text="Smazat spoj", command=self.delete_trip).pack(side="left", padx=4)

    def refresh_lines(self):
        self._clear_tree(self.lines_tree)
        carrier_lookup = {x.id: x for x in self.db.carriers}
        for item in self.db.lines:
            carrier_name = carrier_lookup[item.carrier_id].name if item.carrier_id in carrier_lookup else ""
            validity = ""
            if item.validity_from or item.validity_to:
                validity = f"{item.validity_from} - {item.validity_to}".strip(" -")
            self.lines_tree.insert(
                "",
                tk.END,
                iid=item.id,
                values=(item.line_number, item.name, carrier_name, validity, len(item.route), len(item.trips)),
            )
        self.refresh_line_trips()

    def refresh_line_trips(self):
        self._clear_tree(self.trips_tree)
        line = self._selected_by_id(self.lines_tree, self.db.lines)
        if not line:
            return
        tc_lookup = {x.id: x for x in self.db.time_codes}
        for trip in line.trips:
            codes = ", ".join(tc_lookup[x].symbol for x in trip.time_code_ids if x in tc_lookup)
            direction = self._trip_direction(trip)
            start = trip.stop_records[0].departure if trip.stop_records else ""
            end = trip.stop_records[-1].arrival if trip.stop_records else ""
            self.trips_tree.insert("", tk.END, iid=trip.id, values=(trip.trip_number, codes, direction, start, end))

    def _trip_direction(self, trip):
        if trip.trip_number.isdigit():
            return "lichý dolů" if int(trip.trip_number) % 2 == 1 else "sudý nahoru"
        return "neurčeno"

    def add_line(self):
        if len(self.db.stops) < 2:
            error("Nejdřív vytvoř aspoň dvě zastávky.")
            return
        dlg = LineDialog(self, self.db.stops, self.db.carriers, stop_sort_mode=self.db.settings.stop_sort_mode)
        self.wait_window(dlg)
        if dlg.result:
            self.db.lines.append(dlg.result)
            self.save()
            self.refresh_lines()

    def edit_line(self):
        item = self._selected_by_id(self.lines_tree, self.db.lines)
        if not item:
            return
        dlg = LineDialog(self, self.db.stops, self.db.carriers, item, stop_sort_mode=self.db.settings.stop_sort_mode)
        self.wait_window(dlg)
        if dlg.result:
            old_trips = item.trips
            dlg.result.trips = old_trips
            idx = self.db.lines.index(item)
            self.db.lines[idx] = dlg.result
            self._sync_trips_to_route(self.db.lines[idx])
            self.save()
            self.refresh_lines()

    def delete_line(self):
        item = self._selected_by_id(self.lines_tree, self.db.lines)
        if item and confirm_delete(f"Linka {item.line_number}"):
            self.db.lines.remove(item)
            self.save()
            self.refresh_lines()
            self.refresh_duties()

    def duplicate_line(self):
        item = self._selected_by_id(self.lines_tree, self.db.lines)
        if not item:
            return
        clone = copy.deepcopy(item)
        clone.id = new_id()
        clone.line_number = f"{item.line_number}_copy"
        clone.trips = []
        self.db.lines.append(clone)
        self.save()
        self.refresh_lines()

    def add_trip(self):
        line = self._selected_by_id(self.lines_tree, self.db.lines)
        if not line:
            error("Vyber linku.")
            return
        self._sync_trips_to_route(line)
        dlg = TripDialog(self, line, self.db.stops, self.db.time_codes, self.db.fixed_codes, self.db.travel_times)
        self.wait_window(dlg)
        if dlg.result:
            if any(t.trip_number == dlg.result.trip_number for t in line.trips):
                error("Číslo spoje musí být v rámci linky jedinečné.")
                return
            line.trips.append(dlg.result)
            self.save()
            self.refresh_lines()
            self.refresh_duties()

    def edit_trip(self):
        line = self._selected_by_id(self.lines_tree, self.db.lines)
        if not line:
            return
        sel = self.trips_tree.selection()
        if not sel:
            return
        trip = next((t for t in line.trips if t.id == sel[0]), None)
        if not trip:
            return
        self._sync_trips_to_route(line)
        dlg = TripDialog(self, line, self.db.stops, self.db.time_codes, self.db.fixed_codes, self.db.travel_times, trip)
        self.wait_window(dlg)
        if dlg.result:
            for other in line.trips:
                if other.id != trip.id and other.trip_number == dlg.result.trip_number:
                    error("Číslo spoje musí být v rámci linky jedinečné.")
                    return
            idx = line.trips.index(trip)
            line.trips[idx] = dlg.result
            self.save()
            self.refresh_lines()
            self.refresh_duties()

    def duplicate_trip(self):
        line = self._selected_by_id(self.lines_tree, self.db.lines)
        if not line:
            error("Vyber linku.")
            return

        sel = self.trips_tree.selection()
        if not sel:
            error("Vyber spoj, který chceš duplikovat.")
            return

        original_trip = next((t for t in line.trips if t.id == sel[0]), None)
        if not original_trip:
            return

        self._sync_trips_to_route(line)

        clone = copy.deepcopy(original_trip)
        clone.id = new_id()

        base = original_trip.trip_number
        existing_numbers = {t.trip_number for t in line.trips}
        if base.isdigit():
            new_number = str(int(base) + 1)
            while new_number in existing_numbers:
                new_number = str(int(new_number) + 1)
        else:
            suffix = 1
            new_number = f"{base}_{suffix}"
            while new_number in existing_numbers:
                suffix += 1
                new_number = f"{base}_{suffix}"
        clone.trip_number = new_number

        dlg = TripDialog(self, line, self.db.stops, self.db.time_codes, self.db.fixed_codes, self.db.travel_times, clone)
        self.wait_window(dlg)
        if dlg.result:
            if any(t.trip_number == dlg.result.trip_number for t in line.trips):
                error("Číslo spoje musí být v rámci linky jedinečné.")
                return
            line.trips.append(dlg.result)
            self.save()
            self.refresh_lines()
            self.refresh_duties()

    def delete_trip(self):
        line = self._selected_by_id(self.lines_tree, self.db.lines)
        if not line:
            return
        sel = self.trips_tree.selection()
        if not sel:
            return
        trip = next((t for t in line.trips if t.id == sel[0]), None)
        if trip and confirm_delete(f"Spoj {trip.trip_number}"):
            line.trips.remove(trip)
            for duty in self.db.duties:
                duty.items = [x for x in duty.items if x.ref_trip_id != trip.id]
            self.save()
            self.refresh_lines()
            self.refresh_duties()

    def _sync_trips_to_route(self, line):
        from models import TripStopRecord

        route_ids = [rs.stop_id for rs in line.route]

        for trip in line.trips:
            buckets = defaultdict(list)
            for sr in trip.stop_records:
                buckets[sr.stop_id].append(copy.deepcopy(sr))

            new_records = []
            for stop_id in route_ids:
                if buckets[stop_id]:
                    new_records.append(buckets[stop_id].pop(0))
                else:
                    new_records.append(TripStopRecord(stop_id=stop_id))

            trip.stop_records = new_records

    # -------------------- Turnusy --------------------
    def _build_duties_tab(self):
        self.duties_tree = self._build_crud_table(
            self.tab_duties,
            columns=("name", "number", "carrier", "items"),
            headings={"name": "Název", "number": "Číslo turnusu", "carrier": "Společnost", "items": "Položek"},
        )
        self._build_buttons(
            self.tab_duties,
            [("Přidat", self.add_duty), ("Duplikovat", self.duplicate_duty), ("Upravit", self.edit_duty), ("Smazat", self.delete_duty)],
        )

    def refresh_duties(self):
        self._clear_tree(self.duties_tree)
        carrier_lookup = {x.id: x for x in self.db.carriers}
        for duty in self.db.duties:
            carrier = carrier_lookup[duty.carrier_id].name if duty.carrier_id in carrier_lookup else ""
            self.duties_tree.insert("", tk.END, iid=duty.id, values=(duty.name, duty.duty_number, carrier, len(duty.items)))

    def _blocked_trip_ids(self):
        blocked = []
        for duty in self.db.duties:
            for item in duty.items:
                if item.kind == "trip":
                    blocked.append(item.ref_trip_id)
        return blocked

    def add_duty(self):
        dlg = DutyDialog(
            self,
            self.db.carriers,
            self.db.lines,
            blocked_trip_ids=self._blocked_trip_ids(),
            time_codes=self.db.time_codes,
        )
        self.wait_window(dlg)
        if dlg.result:
            self.db.duties.append(dlg.result)
            self.save()
            self.refresh_duties()

    def edit_duty(self):
        item = self._selected_by_id(self.duties_tree, self.db.duties)
        if not item:
            return
        dlg = DutyDialog(
            self,
            self.db.carriers,
            self.db.lines,
            item,
            blocked_trip_ids=self._blocked_trip_ids(),
            time_codes=self.db.time_codes,
        )
        self.wait_window(dlg)
        if dlg.result:
            idx = self.db.duties.index(item)
            self.db.duties[idx] = dlg.result
            self.save()
            self.refresh_duties()

    def duplicate_duty(self):
        item = self._selected_by_id(self.duties_tree, self.db.duties)
        if not item:
            return
        clone = copy.deepcopy(item)
        clone.id = new_id()
        clone.duty_number = f"{item.duty_number}_copy"
        clone.name = f"{item.name} kopie"
        self.db.duties.append(clone)
        self.save()
        self.refresh_duties()

    def delete_duty(self):
        item = self._selected_by_id(self.duties_tree, self.db.duties)
        if item and confirm_delete(item.name):
            self.db.duties.remove(item)
            self.save()
            self.refresh_duties()

    # -------------------- Export --------------------
    def _build_export_tab(self):
        wrap = ttk.Frame(self.tab_export, padding=20)
        wrap.pack(fill="both", expand=True)

        ttk.Label(wrap, text="Export", font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(0, 12))

        ttk.Button(wrap, text="Exportovat seznam zastávek (.pdf)", command=self.export_stops).pack(anchor="w", pady=6)
        ttk.Button(wrap, text="Exportovat turnusy (.pdf)", command=self.export_duties).pack(anchor="w", pady=6)
        ttk.Button(wrap, text="Exportovat JŘ linek (.pdf)", command=self.export_lines).pack(anchor="w", pady=6)
        ttk.Button(wrap, text="Exportovat TimeTable.xml", command=self.export_timetable).pack(anchor="w", pady=6)
        ttk.Button(wrap, text="Exportovat Stations.xml", command=self.export_stations).pack(anchor="w", pady=6)
        ttk.Button(wrap, text="Exportovat JŘ pro vybranou zastávku (.pdf)", command=self.export_stop_timetable).pack(anchor="w", pady=6)

        ttk.Separator(wrap).pack(fill="x", pady=12)

        ttk.Button(wrap, text="Exportovat zastávkové tabule - všechny zastávky", command=self.export_stop_boards_all_dialog).pack(anchor="w", pady=6)
        ttk.Button(wrap, text="Exportovat zastávkovou tabuli - vybraná zastávka", command=self.export_stop_board_one_dialog).pack(anchor="w", pady=6)

        ttk.Separator(wrap).pack(fill="x", pady=12)

        ttk.Button(wrap, text="Exportovat tabla nástupišť - všechna", command=self.export_platform_boards_all_dialog).pack(anchor="w", pady=6)
        ttk.Button(wrap, text="Exportovat tablo vybraného nástupiště", command=self.export_platform_board_one_dialog).pack(anchor="w", pady=6)

    def export_stops(self):
        path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
        if path:
            export_stops_pdf(self.db, path)
            info("Seznam zastávek byl exportován.")

    def export_duties(self):
        path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
        if path:
            export_duties_pdf(self.db, path)
            info("Turnusy byly exportovány.")

    def export_lines(self):
        path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
        if path:
            export_lines_pdf(self.db, path)
            info("JŘ linek byly exportovány.")

    def export_timetable(self):
        path = filedialog.asksaveasfilename(defaultextension=".xml", filetypes=[("XML", "*.xml")], initialfile="TimeTable.xml")
        if path:
            export_timetable_xml(self.db, path)
            info("TimeTable.xml byl exportován.")

    def export_stations(self):
        path = filedialog.asksaveasfilename(defaultextension=".xml", filetypes=[("XML", "*.xml")], initialfile="Stations.xml")
        if path:
            export_stations_xml(self.db, path)
            info("Stations.xml byl exportován.")

    def export_stop_timetable(self):
        stop = self._selected_by_id(self.stops_tree, self.db.stops)
        if not stop:
            error("Vyber zastávku v záložce Zastávky.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            initialfile=f"{stop.name}_JR.pdf",
        )
        if path:
            export_stop_line_timetable_pdf(self.db, stop.id, path)
            info("JŘ pro zastávku byl exportován.")

    def _ask_board_type(self):
        return simpledialog.askinteger(
            "Typ tabule",
            "Zadej typ tabule:\n1 = mřížka linek\n2 = linka → konečná\n3 = jen hlava",
            minvalue=1,
            maxvalue=3,
            parent=self,
        )

    def export_stop_boards_all_dialog(self):
        board_type = self._ask_board_type()
        if not board_type:
            return
        folder = filedialog.askdirectory(title="Vyber složku pro export tabulí")
        if not folder:
            return
        try:
            export_stop_board_all(self.db, folder, board_type)
            info("Zastávkové tabule byly exportovány.")
        except Exception as e:
            messagebox.showerror("Chyba", f"Export tabulí selhal:\n{e}")

    def export_stop_board_one_dialog(self):
        board_type = self._ask_board_type()
        if not board_type:
            return
        stop = self._selected_by_id(self.stops_tree, self.db.stops)
        if not stop:
            error("Vyber zastávku v záložce Zastávky.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG", "*.png")],
            initialfile=f"{stop.name}_typ_{board_type}.png",
        )
        if not path:
            return
        try:
            export_stop_board_one(self.db, path, stop.id, board_type)
            info("Zastávková tabule byla exportována.")
        except Exception as e:
            messagebox.showerror("Chyba", f"Export tabule selhal:\n{e}")

    def export_platform_boards_all_dialog(self):
        board_type = self._ask_board_type()
        if not board_type:
            return
        folder = filedialog.askdirectory(title="Vyber složku pro export tabel nástupišť")
        if not folder:
            return
        try:
            export_platform_board_all(self.db, folder, board_type)
            info("Tabla nástupišť byla exportována.")
        except Exception as e:
            messagebox.showerror("Chyba", f"Export tabel nástupišť selhal:\n{e}")

    def export_platform_board_one_dialog(self):
        board_type = self._ask_board_type()
        if not board_type:
            return

        stop = self._selected_by_id(self.stops_tree, self.db.stops)
        if not stop:
            error("Vyber zastávku v záložce Zastávky.")
            return

        if not stop.platforms:
            error("Vybraná zastávka nemá žádná nástupiště.")
            return

        platform_names = [p.name for p in stop.platforms]
        prompt = "Dostupná nástupiště: " + ", ".join(platform_names) + "\nZadej přesně název nástupiště:"
        chosen_name = simpledialog.askstring("Nástupiště", prompt, parent=self)
        if not chosen_name:
            return

        platform = next((p for p in stop.platforms if p.name == chosen_name), None)
        if not platform:
            error("Takové nástupiště u vybrané zastávky není.")
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG", "*.png")],
            initialfile=f"{stop.name}_nastupiste_{platform.name}_typ_{board_type}.png",
        )
        if not path:
            return

        try:
            export_platform_board_one(self.db, path, stop.id, platform.id, board_type)
            info("Tablo nástupiště bylo exportováno.")
        except Exception as e:
            messagebox.showerror("Chyba", f"Export tabla nástupiště selhal:\n{e}")

    # -------------------- Nastavení --------------------
    def _build_settings_tab(self):
        wrap = ttk.Frame(self.tab_settings, padding=20)
        wrap.pack(fill="both", expand=True)

        ttk.Label(wrap, text="Nastavení", font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(0, 12))
        ttk.Label(wrap, text="Řazení zastávek").pack(anchor="w")

        self.stop_sort_combo = ttk.Combobox(wrap, values=["Podle kódu", "Abecedně"], state="readonly", width=20)
        self.stop_sort_combo.pack(anchor="w", pady=(4, 10))

        ttk.Button(wrap, text="Uložit nastavení", command=self.save_settings).pack(anchor="w")

    def refresh_settings(self):
        self.stop_sort_combo.set("Abecedně" if self.db.settings.stop_sort_mode == "alpha" else "Podle kódu")

    def save_settings(self):
        value = self.stop_sort_combo.get()
        self.db.settings.stop_sort_mode = "alpha" if value == "Abecedně" else "code"
        self.save()
        self.refresh_stops()
        self.refresh_travel_times()
        info("Nastavení bylo uloženo.")

    # -------------------- Pomocné --------------------
    def _build_crud_table(self, parent, columns, headings):
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True, padx=8, pady=8)
        tree = ttk.Treeview(frame, columns=columns, show="headings")
        tree.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        scroll.pack(side="right", fill="y")
        tree.configure(yscrollcommand=scroll.set)
        for col in columns:
            tree.heading(col, text=headings[col])
            tree.column(col, width=170, anchor="w")
        return tree

    def _build_buttons(self, parent, buttons):
        frame = ttk.Frame(parent)
        frame.pack(fill="x", padx=8, pady=(0, 8))
        for text, cmd in buttons:
            ttk.Button(frame, text=text, command=cmd).pack(side="left", padx=4)

    def _clear_tree(self, tree):
        for item in tree.get_children():
            tree.delete(item)

    def _selected_by_id(self, tree, items):
        sel = tree.selection()
        if not sel:
            return None
        item_id = sel[0]
        return next((x for x in items if x.id == item_id), None)
