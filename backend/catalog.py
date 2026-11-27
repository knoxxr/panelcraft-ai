"""Industrial automation component catalog covering major global FA vendors.

Electrical Vendors (7):
- LS Electric, Schneider Electric, Siemens, Mitsubishi Electric, ABB, Fuji Electric, Omron

PLC Vendors (6):
- Mitsubishi Electric (MELSEC iQ-R), LS Electric (XGT XGI), Siemens (SIMATIC S7-1500),
  Rockwell Automation (ControlLogix 5580), Omron (Sysmac NX102), Beckhoff (TwinCAT CX/EL)
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BreakerSpec:
    vendor: str
    part_number: str
    rated_a: int
    poles: int
    icu_ka: int
    spec: str
    price_krw: int
    lead_days: int
    heat_w: float = 4.0


@dataclass(frozen=True)
class ContactorSpec:
    vendor: str
    part_number: str
    rated_a: int
    coil_v: str
    spec: str
    price_krw: int
    lead_days: int
    heat_w: float = 3.5


@dataclass(frozen=True)
class DriveSpec:
    vendor: str
    part_number: str
    drive_kind: str  # "inverter" or "servo"
    rated_kw: float
    voltage_v: int
    spec: str
    price_krw: int
    lead_days: int


@dataclass(frozen=True)
class SmpsSpec:
    vendor: str
    part_number: str
    output_a: float
    output_w: int
    spec: str
    price_krw: int
    lead_days: int


@dataclass(frozen=True)
class PlcCatalogItem:
    vendor: str
    module_type: str  # PSU, CPU, DI, DO, AI, AO
    part_number: str
    channels: int
    spec: str
    price_krw: int
    lead_days: int
    dc24v_a: float = 0.15
    heat_w: float = 4.5


WIRE_AMPACITY_TABLE: list[tuple[float, float]] = [
    (0.75, 8.5),
    (1.5, 13.5),
    (2.5, 18.3),
    (4.0, 24.0),
    (6.0, 31.0),
    (10.0, 42.0),
    (16.0, 56.0),
    (25.0, 73.0),
    (35.0, 89.0),
    (50.0, 108.0),
    (70.0, 136.0),
    (95.0, 164.0),
    (120.0, 188.0),
    (150.0, 216.0),
]

SQ_TO_AWG: dict[float, str] = {
    0.75: "18 AWG",
    1.5: "16 AWG",
    2.5: "14 AWG",
    4.0: "12 AWG",
    6.0: "10 AWG",
    10.0: "8 AWG",
    16.0: "6 AWG",
    25.0: "4 AWG",
    35.0: "2 AWG",
    50.0: "1 AWG",
    70.0: "2/0 AWG",
    95.0: "3/0 AWG",
    120.0: "4/0 AWG",
    150.0: "300 kcmil",
}


def sq_to_awg(sq: float) -> str:
    return SQ_TO_AWG.get(sq, "14 AWG")


@dataclass(frozen=True)
class TransformerSpec:
    vendor: str
    part_number: str
    kva: float
    spec: str
    price_krw: int
    lead_days: int
    heat_w: float


CONTROL_TRANSFORMERS: list[TransformerSpec] = [
    TransformerSpec("Hanyoung Nux", "HY-TR-1KVA", 1.0, "Dry Step-Down Transformer 380/480V→220V 1.0kVA", 145000, 4, 28.0),
    TransformerSpec("Hanyoung Nux", "HY-TR-3KVA", 3.0, "Dry Step-Down Transformer 380/480V→220V 3.0kVA", 285000, 5, 65.0),
    TransformerSpec("Hanyoung Nux", "HY-TR-5KVA", 5.0, "Dry Step-Down Transformer 380/480V→220V 5.0kVA", 440000, 5, 95.0),
    TransformerSpec("Hanyoung Nux", "HY-TR-10KVA", 10.0, "Dry Step-Down Transformer 380/480V→220V 10kVA", 790000, 7, 165.0),
]


def select_control_transformer(required_kva: float) -> TransformerSpec:
    for tr in CONTROL_TRANSFORMERS:
        if tr.kva >= required_kva:
            return tr
    return CONTROL_TRANSFORMERS[-1]


TEMP_DERATING: list[tuple[float, float]] = [
    (30.0, 1.00),
    (35.0, 0.94),
    (40.0, 0.87),
    (45.0, 0.79),
    (50.0, 0.71),
    (55.0, 0.61),
]


def _make_breakers() -> dict[str, list[BreakerSpec]]:
    ratings_3p = [15, 20, 30, 40, 50, 60, 75, 100, 125, 150, 175, 200, 225, 250, 300, 400]
    catalog: dict[str, list[BreakerSpec]] = {}

    # LS Electric
    catalog["LS Electric"] = [
        BreakerSpec(
            "LS Electric",
            f"ABS{50 if r <= 50 else (100 if r <= 100 else (200 if r <= 200 else 400))}c 3P {r}A",
            r, 3,
            18 if r <= 50 else (25 if r <= 100 else (37 if r <= 200 else 50)),
            f"Metasol MCCB 3P {r}AT",
            38000 + (50 if r <= 50 else 100 if r <= 100 else 200) * 520 + r * 280,
            3,
            heat_w=2.5 + r * 0.06,
        )
        for r in ratings_3p
    ]

    # Schneider Electric
    catalog["Schneider Electric"] = [
        BreakerSpec(
            "Schneider Electric",
            f"LV4296{r:02d}" if r < 100 else f"C{250 if r <= 250 else 400}F3TM{r}",
            r, 3,
            36 if r <= 250 else 50,
            f"ComPacT NSX 3P {r}A {36 if r <= 250 else 50}kA",
            62000 + (100 if r <= 100 else 250) * 650 + r * 340,
            7,
            heat_w=2.4 + r * 0.055,
        )
        for r in ratings_3p
    ]

    # Siemens
    catalog["Siemens"] = [
        BreakerSpec(
            "Siemens",
            f"3VA1{1 if r <= 160 else (2 if r <= 250 else 4)}16-4ED32-{r:03d}0",
            r, 3,
            36 if r <= 250 else 55,
            f"SENTRON 3VA1 3P {r}A",
            68000 + (160 if r <= 160 else 250) * 680 + r * 360,
            10,
            heat_w=2.3 + r * 0.055,
        )
        for r in ratings_3p
    ]

    # Mitsubishi Electric
    catalog["Mitsubishi Electric"] = [
        BreakerSpec(
            "Mitsubishi Electric",
            f"NF{63 if r <= 60 else (125 if r <= 125 else (250 if r <= 250 else 400))}-SV 3P {r}A",
            r, 3,
            25 if r <= 125 else 36,
            f"WS-V NF-SV 3P {r}AT",
            54000 + (63 if r <= 60 else 125 if r <= 125 else 250) * 620 + r * 310,
            5,
            heat_w=2.5 + r * 0.058,
        )
        for r in ratings_3p
    ]

    # ABB (Tmax XT)
    catalog["ABB"] = [
        BreakerSpec(
            "ABB",
            f"XT{1 if r <= 160 else (3 if r <= 250 else 5)}N {r} TMD 3P",
            r, 3,
            36 if r <= 250 else 50,
            f"Tmax XT MCCB 3P {r}A 36kA",
            64000 + (160 if r <= 160 else 250) * 660 + r * 330,
            7,
            heat_w=2.3 + r * 0.054,
        )
        for r in ratings_3p
    ]

    # Fuji Electric (G-Twin BW)
    catalog["Fuji Electric"] = [
        BreakerSpec(
            "Fuji Electric",
            f"BW{50 if r <= 50 else (100 if r <= 100 else (250 if r <= 250 else 400))}EAG-3P{r:03d}",
            r, 3,
            18 if r <= 50 else (25 if r <= 100 else 36),
            f"G-Twin BW MCCB 3P {r}A",
            45000 + (50 if r <= 50 else 100 if r <= 100 else 250) * 560 + r * 290,
            4,
            heat_w=2.4 + r * 0.058,
        )
        for r in ratings_3p
    ]

    # Omron (Industrial FA Partner MCCB / S8V ecosystem)
    catalog["Omron"] = [
        BreakerSpec(
            "Omron",
            f"OM-MCCB3P-{r}A",
            r, 3,
            25 if r <= 125 else 36,
            f"FA Industrial MCCB 3P {r}A (Omron Panel Spec)",
            52000 + (100 if r <= 100 else 250) * 580 + r * 300,
            5,
            heat_w=2.5 + r * 0.057,
        )
        for r in ratings_3p
    ]

    return catalog


BREAKERS_3P = _make_breakers()


CONTACTORS: dict[str, list[ContactorSpec]] = {
    "LS Electric": [
        ContactorSpec("LS Electric", "MC-9b DC24V", 9, "DC 24V", "Metasol 9A AC3 1a1b", 22000, 2, 2.8),
        ContactorSpec("LS Electric", "MC-18b DC24V", 18, "DC 24V", "Metasol 18A AC3 1a1b", 29000, 2, 3.2),
        ContactorSpec("LS Electric", "MC-32a DC24V", 32, "DC 24V", "Metasol 32A AC3 2a2b", 46000, 2, 4.0),
        ContactorSpec("LS Electric", "MC-50a DC24V", 50, "DC 24V", "Metasol 50A AC3 2a2b", 78000, 3, 5.2),
        ContactorSpec("LS Electric", "MC-85a DC24V", 85, "DC 24V", "Metasol 85A AC3 2a2b", 128000, 4, 7.0),
        ContactorSpec("LS Electric", "MC-150a DC24V", 150, "DC 24V", "Metasol 150A AC3 2a2b", 245000, 5, 9.5),
    ],
    "Schneider Electric": [
        ContactorSpec("Schneider Electric", "LC1D09BD", 9, "DC 24V", "TeSys Deca 9A AC3 1NO+1NC", 34000, 5, 2.5),
        ContactorSpec("Schneider Electric", "LC1D18BD", 18, "DC 24V", "TeSys Deca 18A AC3 1NO+1NC", 45000, 5, 3.0),
        ContactorSpec("Schneider Electric", "LC1D32BD", 32, "DC 24V", "TeSys Deca 32A AC3 1NO+1NC", 68000, 5, 3.8),
        ContactorSpec("Schneider Electric", "LC1D50ABD", 50, "DC 24V", "TeSys Deca 50A AC3 1NO+1NC", 112000, 7, 4.8),
        ContactorSpec("Schneider Electric", "LC1D80BD", 80, "DC 24V", "TeSys Deca 80A AC3 1NO+1NC", 178000, 7, 6.5),
        ContactorSpec("Schneider Electric", "LC1D150BD", 150, "DC 24V", "TeSys Deca 150A AC3 1NO+1NC", 340000, 10, 8.8),
    ],
    "Siemens": [
        ContactorSpec("Siemens", "3RT2016-1BB41", 9, "DC 24V", "SIRIUS 3RT2 9A AC3 1NO", 36000, 7, 2.6),
        ContactorSpec("Siemens", "3RT2025-1BB40", 17, "DC 24V", "SIRIUS 3RT2 17A AC3 1NO+1NC", 49000, 7, 3.1),
        ContactorSpec("Siemens", "3RT2027-1BB40", 32, "DC 24V", "SIRIUS 3RT2 32A AC3 1NO+1NC", 74000, 7, 3.9),
        ContactorSpec("Siemens", "3RT2036-1NB30", 51, "DC 24V", "SIRIUS 3RT2 51A AC3 1NO+1NC", 124000, 10, 4.9),
        ContactorSpec("Siemens", "3RT2038-1NB30", 80, "DC 24V", "SIRIUS 3RT2 80A AC3 1NO+1NC", 195000, 10, 6.4),
        ContactorSpec("Siemens", "3RT2046-1NB30", 150, "DC 24V", "SIRIUS 3RT2 150A AC3 1NO+1NC", 360000, 12, 8.6),
    ],
    "Mitsubishi Electric": [
        ContactorSpec("Mitsubishi Electric", "S-T10 DC24V", 9, "DC 24V", "MS-T 9A AC3 1a", 28000, 4, 2.7),
        ContactorSpec("Mitsubishi Electric", "S-T20 DC24V", 18, "DC 24V", "MS-T 18A AC3 1a1b", 38000, 4, 3.1),
        ContactorSpec("Mitsubishi Electric", "S-T35 DC24V", 35, "DC 24V", "MS-T 35A AC3 2a2b", 62000, 4, 3.9),
        ContactorSpec("Mitsubishi Electric", "S-T50 DC24V", 50, "DC 24V", "MS-T 50A AC3 2a2b", 96000, 5, 5.0),
        ContactorSpec("Mitsubishi Electric", "S-T80 DC24V", 80, "DC 24V", "MS-T 80A AC3 2a2b", 156000, 5, 6.6),
        ContactorSpec("Mitsubishi Electric", "S-T150 DC24V", 150, "DC 24V", "MS-T 150A AC3 2a2b", 290000, 7, 9.0),
    ],
    "ABB": [
        ContactorSpec("ABB", "AF09-30-10-11", 9, "DC 24V", "AF Contactor 9A 24-60V AC/DC", 35000, 6, 2.4),
        ContactorSpec("ABB", "AF16-30-10-11", 18, "DC 24V", "AF Contactor 18A 24-60V AC/DC", 47000, 6, 2.9),
        ContactorSpec("ABB", "AF30-30-00-11", 32, "DC 24V", "AF Contactor 32A 24-60V AC/DC", 72000, 6, 3.6),
        ContactorSpec("ABB", "AF52-30-00-11", 53, "DC 24V", "AF Contactor 53A 24-60V AC/DC", 118000, 8, 4.7),
        ContactorSpec("ABB", "AF80-30-00-11", 80, "DC 24V", "AF Contactor 80A 24-60V AC/DC", 185000, 8, 6.1),
        ContactorSpec("ABB", "AF146-30-00-11", 146, "DC 24V", "AF Contactor 146A 24-60V AC/DC", 355000, 10, 8.2),
    ],
    "Fuji Electric": [
        ContactorSpec("Fuji Electric", "SC-E02/G DC24V", 9, "DC 24V", "NEO SC-E 9A AC3 1a", 25000, 3, 2.6),
        ContactorSpec("Fuji Electric", "SC-E04/G DC24V", 18, "DC 24V", "NEO SC-E 18A AC3 1a", 34000, 3, 3.1),
        ContactorSpec("Fuji Electric", "SC-E1/G DC24V", 32, "DC 24V", "NEO SC-E 32A AC3 2a2b", 55000, 3, 3.8),
        ContactorSpec("Fuji Electric", "SC-E2S/G DC24V", 50, "DC 24V", "NEO SC-E 50A AC3 2a2b", 88000, 4, 4.9),
        ContactorSpec("Fuji Electric", "SC-E4/G DC24V", 80, "DC 24V", "NEO SC-E 80A AC3 2a2b", 142000, 5, 6.5),
        ContactorSpec("Fuji Electric", "SC-N7/G DC24V", 150, "DC 24V", "NEO SC-N 150A AC3 2a2b", 275000, 6, 8.9),
    ],
    "Omron": [
        ContactorSpec("Omron", "J7KC-09-10 DC24V", 9, "DC 24V", "J7KC Industrial Contactor 9A", 31000, 4, 2.6),
        ContactorSpec("Omron", "J7KC-18-10 DC24V", 18, "DC 24V", "J7KC Industrial Contactor 18A", 42000, 4, 3.1),
        ContactorSpec("Omron", "J7KC-32-11 DC24V", 32, "DC 24V", "J7KC Industrial Contactor 32A", 65000, 4, 3.8),
        ContactorSpec("Omron", "J7KC-50-11 DC24V", 50, "DC 24V", "J7KC Industrial Contactor 50A", 105000, 6, 4.9),
        ContactorSpec("Omron", "J7KC-80-11 DC24V", 80, "DC 24V", "J7KC Industrial Contactor 80A", 168000, 6, 6.4),
        ContactorSpec("Omron", "J7KC-150-11 DC24V", 150, "DC 24V", "J7KC Industrial Contactor 150A", 315000, 8, 8.8),
    ],
}


def _make_drives() -> dict[str, list[DriveSpec]]:
    inv_kws = [0.4, 0.75, 1.5, 2.2, 3.7, 5.5, 7.5, 11.0, 15.0, 22.0]
    srv_kws = [0.2, 0.4, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0]
    data: dict[str, list[DriveSpec]] = {}

    vendor_defs = [
        ("LS Electric", "LSLV{code}G100-4EOFN", "L7NHB{watt:03d}U", 1.00),
        ("Schneider Electric", "ATV320U{code}N4C", "LXM32MD{watt:03d}", 1.28),
        ("Siemens", "6SL3210-1PE{code}-0UL0", "6SL3210-5FB1{watt:02d}", 1.35),
        ("Mitsubishi Electric", "FR-E840-{code}K-1", "MR-J5-{watt:02d}G", 1.22),
        ("ABB", "ACS380-040S-{code}A-4", "MFE190-04AN-{watt:02d}A", 1.30),
        ("Fuji Electric", "FRN{code}E2S-4K", "RYH{watt:03d}F5-VV2", 1.08),
        ("Omron", "3G3MX2-A4{code}-E", "R88D-1SN{watt:02d}H-ECT", 1.25),
    ]

    for vendor, inv_prefix, srv_prefix, mult in vendor_defs:
        items: list[DriveSpec] = []
        for kw in inv_kws:
            code = f"{int(round(kw * 10)):04d}"
            pn = inv_prefix.format(code=code)
            price = int((185000 + kw * 95000) * mult)
            items.append(DriveSpec(vendor, pn, "inverter", kw, 380, f"3P 380-480V VFD Inverter {kw}kW", price, 5))
        for kw in srv_kws:
            watt = int(round(kw * 100))
            pn = srv_prefix.format(watt=watt)
            price = int((420000 + kw * 260000) * mult)
            items.append(DriveSpec(vendor, pn, "servo", kw, 220, f"AC Servo Drive {kw}kW (EtherCAT/Fieldbus)", price, 7))
        data[vendor] = items
    return data


DRIVES = _make_drives()


SMPS_LIST: list[SmpsSpec] = [
    SmpsSpec("Omron", "S8VK-G12024", 5.0, 120, "DIN Rail SMPS DC 24V 5A (120W)", 54000, 2),
    SmpsSpec("Omron", "S8VK-G24024", 10.0, 240, "DIN Rail SMPS DC 24V 10A (240W)", 82000, 2),
    SmpsSpec("MeanWell", "NDR-480-24", 20.0, 480, "DIN Rail SMPS DC 24V 20A (480W)", 128000, 3),
    SmpsSpec("MeanWell", "TDR-960-24", 40.0, 960, "3P DIN Rail SMPS DC 24V 40A (960W)", 285000, 5),
]


PLC_CATALOG: dict[str, dict[str, PlcCatalogItem]] = {
    "Mitsubishi Electric": {
        "PSU": PlcCatalogItem("Mitsubishi Electric", "PSU", "R61P", 0, "MELSEC iQ-R Power Supply AC100-240V", 210000, 5, 0.0, 8.0),
        "CPU": PlcCatalogItem("Mitsubishi Electric", "CPU", "R04CPU", 0, "MELSEC iQ-R CPU 40K Step", 920000, 7, 0.0, 9.0),
        "DI": PlcCatalogItem("Mitsubishi Electric", "DI", "RX41C4", 32, "DC24V 32pt Digital Input (Sink/Source)", 265000, 5, 0.16, 4.2),
        "DO": PlcCatalogItem("Mitsubishi Electric", "DO", "RY41NT2P", 32, "Transistor 32pt Digital Output (Sink)", 295000, 5, 0.22, 4.8),
        "AI": PlcCatalogItem("Mitsubishi Electric", "AI", "R60AD4", 4, "4ch Analog Input (4-20mA/0-10V)", 410000, 7, 0.12, 4.0),
        "AO": PlcCatalogItem("Mitsubishi Electric", "AO", "R60DA4", 4, "4ch Analog Output (4-20mA/0-10V)", 430000, 7, 0.14, 4.5),
    },
    "LS Electric": {
        "PSU": PlcCatalogItem("LS Electric", "PSU", "XGP-ACF2", 0, "XGT Power Module AC110/220V", 145000, 3, 0.0, 7.5),
        "CPU": PlcCatalogItem("LS Electric", "CPU", "XGI-CPUUN", 0, "XGT IEC Standard CPU (Built-in Ethernet)", 640000, 3, 0.0, 8.0),
        "DI": PlcCatalogItem("LS Electric", "DI", "XGI-D24A", 32, "DC24V 32pt Digital Input Module", 175000, 2, 0.16, 4.0),
        "DO": PlcCatalogItem("LS Electric", "DO", "XGQ-TR4A", 32, "Transistor 32pt Digital Output Module", 195000, 2, 0.22, 4.5),
        "AI": PlcCatalogItem("LS Electric", "AI", "XGF-AD4S", 4, "4ch Isolated Analog Input Module", 280000, 4, 0.12, 3.8),
        "AO": PlcCatalogItem("LS Electric", "AO", "XGF-DC4S", 4, "4ch Isolated Analog Output Module", 310000, 4, 0.14, 4.2),
    },
    "Siemens": {
        "PSU": PlcCatalogItem("Siemens", "PSU", "6EP1333-4BA00", 0, "PM 1507 24V/8A S7-1500 Power Module", 270000, 7, 0.0, 8.5),
        "CPU": PlcCatalogItem("Siemens", "CPU", "6ES7515-2AN03-0AB0", 0, "SIMATIC S7-1500 CPU 1515-2 PN", 1450000, 10, 0.0, 10.0),
        "DI": PlcCatalogItem("Siemens", "DI", "6ES7521-1BL00-0AB0", 32, "DI 32x24VDC HF Module", 360000, 7, 0.18, 4.5),
        "DO": PlcCatalogItem("Siemens", "DO", "6ES7522-1BL01-0AB0", 32, "DQ 32x24VDC/0.5A ST Module", 395000, 7, 0.24, 5.2),
        "AI": PlcCatalogItem("Siemens", "AI", "6ES7531-7KF00-0AB0", 8, "AI 8xU/I/RTD/TC ST Module", 580000, 10, 0.15, 4.2),
        "AO": PlcCatalogItem("Siemens", "AO", "6ES7532-5HD00-0AB0", 4, "AQ 4xU/I ST Module", 540000, 10, 0.16, 4.5),
    },
    "Rockwell Automation": {
        "PSU": PlcCatalogItem("Rockwell Automation", "PSU", "1756-PA75", 0, "ControlLogix AC Power Supply 120/240V", 480000, 10, 0.0, 9.5),
        "CPU": PlcCatalogItem("Rockwell Automation", "CPU", "1756-L81E", 0, "ControlLogix 5580 Controller 3MB EtherNet/IP", 2150000, 14, 0.0, 11.0),
        "DI": PlcCatalogItem("Rockwell Automation", "DI", "1756-IB32", 32, "ControlLogix 32pt 24VDC Sink Input", 420000, 10, 0.18, 5.0),
        "DO": PlcCatalogItem("Rockwell Automation", "DO", "1756-OB32", 32, "ControlLogix 32pt 24VDC Source Output", 465000, 10, 0.25, 5.5),
        "AI": PlcCatalogItem("Rockwell Automation", "AI", "1756-IF8", 8, "ControlLogix 8ch Analog Input", 720000, 12, 0.16, 4.8),
        "AO": PlcCatalogItem("Rockwell Automation", "AO", "1756-OF8", 8, "ControlLogix 8ch Analog Output", 760000, 12, 0.18, 5.0),
    },
    "Omron": {
        "PSU": PlcCatalogItem("Omron", "PSU", "NX-PA9001", 0, "Sysmac NX Power Supply Unit", 225000, 5, 0.0, 7.5),
        "CPU": PlcCatalogItem("Omron", "CPU", "NX102-1000", 0, "Sysmac NX102 Controller (EtherCAT + EtherNet/IP)", 1180000, 7, 0.0, 9.0),
        "DI": PlcCatalogItem("Omron", "DI", "NX-ID5442", 16, "NX 16pt DC24V Digital Input Unit", 185000, 5, 0.12, 3.5),
        "DO": PlcCatalogItem("Omron", "DO", "NX-OD5256", 16, "NX 16pt DC24V Transistor Output Unit", 210000, 5, 0.16, 4.0),
        "AI": PlcCatalogItem("Omron", "AI", "NX-AD4608", 4, "NX 4ch Analog Input Unit", 390000, 7, 0.12, 3.8),
        "AO": PlcCatalogItem("Omron", "AO", "NX-DA3605", 4, "NX 4ch Analog Output Unit", 420000, 7, 0.14, 4.0),
    },
    "Beckhoff": {
        "PSU": PlcCatalogItem("Beckhoff", "PSU", "CX2100-0004", 0, "TwinCAT Embedded PC Power Supply 24VDC", 260000, 7, 0.40, 8.0),
        "CPU": PlcCatalogItem("Beckhoff", "CPU", "CX5240-0175", 0, "TwinCAT 3 Embedded PC (Intel Atom, EtherCAT)", 1320000, 10, 0.65, 11.5),
        "DI": PlcCatalogItem("Beckhoff", "DI", "EL1809", 16, "EtherCAT 16ch Digital Input 24VDC", 165000, 5, 0.10, 2.8),
        "DO": PlcCatalogItem("Beckhoff", "DO", "EL2809", 16, "EtherCAT 16ch Digital Output 24VDC 0.5A", 185000, 5, 0.14, 3.2),
        "AI": PlcCatalogItem("Beckhoff", "AI", "EL3054", 4, "EtherCAT 4ch Analog Input 4-20mA", 350000, 7, 0.12, 3.0),
        "AO": PlcCatalogItem("Beckhoff", "AO", "EL4004", 4, "EtherCAT 4ch Analog Output 0-10V", 365000, 7, 0.12, 3.2),
    },
}


SAFETY_RELAY_BY_VENDOR: dict[str, tuple[str, str, int, int]] = {
    "LS Electric": ("Pilz PNOZ s4 (24VDC)", "Safety Relay PL e / Cat.4 (3NO+1NC)", 245000, 5),
    "Schneider Electric": ("XPSUS12AP", "Preventa Safety Module PL e / Cat.4", 265000, 7),
    "Siemens": ("3SK1111-1AB30", "SIRIUS 3SK1 Safety Relay PL e / Cat.4", 280000, 7),
    "Mitsubishi Electric": ("WS0-XTDI80202", "MELSEC Safety Controller PL e", 310000, 7),
    "ABB": ("Sentry BSR23", "ABB Jokab Safety Relay PL e / Cat.4", 255000, 6),
    "Fuji Electric": ("Pilz PNOZ s4 (24VDC)", "Safety Relay PL e / Cat.4 (3NO+1NC)", 245000, 5),
    "Omron": ("G9SE-201 DC24V", "Omron Compact Safety Relay PL e / Cat.4", 235000, 4),
}


def select_breaker(vendor: str, required_a: float) -> BreakerSpec:
    options = BREAKERS_3P.get(vendor, BREAKERS_3P["LS Electric"])
    for b in options:
        if b.rated_a >= required_a:
            return b
    return options[-1]


def select_contactor(vendor: str, required_a: float) -> ContactorSpec:
    options = CONTACTORS.get(vendor, CONTACTORS["LS Electric"])
    for c in options:
        if c.rated_a >= required_a:
            return c
    return options[-1]


def select_drive(vendor: str, kind: str, required_kw: float) -> DriveSpec:
    options = [d for d in DRIVES.get(vendor, DRIVES["LS Electric"]) if d.drive_kind == kind]
    for d in options:
        if d.rated_kw >= required_kw:
            return d
    return options[-1]


def select_smps(required_a: float) -> SmpsSpec:
    for s in SMPS_LIST:
        if s.output_a >= required_a:
            return s
    return SMPS_LIST[-1]


def get_temp_derating(ambient_temp_c: float) -> float:
    for temp, factor in TEMP_DERATING:
        if ambient_temp_c <= temp:
            return factor
    return 0.61


def select_wire_sq(
    design_current_a: float,
    voltage_v: int,
    phases: int,
    length_m: float,
    ambient_temp_c: float,
    max_vdrop_pct: float = 3.0,
) -> tuple[float, float]:
    """Select minimum IEC/KS wire cross-section satisfying both ampacity & voltage drop."""
    derating = get_temp_derating(ambient_temp_c) * 0.85
    k_factor = 1.73205 if phases == 3 else 2.0
    rho_op = 0.0178 * 1.18

    selected_sq = WIRE_AMPACITY_TABLE[-1][0]
    selected_vd = 0.0

    for sq, base_amp in WIRE_AMPACITY_TABLE:
        allowable_amp = base_amp * derating
        vdrop_v = (k_factor * rho_op * length_m * design_current_a) / sq
        vdrop_pct = (vdrop_v / max(voltage_v, 1)) * 100.0
        selected_sq = sq
        selected_vd = vdrop_pct
        if allowable_amp >= design_current_a and vdrop_pct <= max_vdrop_pct:
            return sq, round(vdrop_pct, 2)

    return selected_sq, round(selected_vd, 2)
