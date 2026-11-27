<p align="center">
  <img src="assets/icons/icon-256.png" alt="PanelCraft AI Icon" width="110" />
</p>

<h1 align="center">PanelCraft AI</h1>

<p align="center">
  <strong>B2B Cloud SaaS Control Panel SSOT Design Automation Platform (v0.6.0)</strong><br />
  Multi-Tenant RBAC · PostgreSQL/SQLite · EPLAN AML + Macros · 6 PLC &amp; 7 Electrical Vendors · Interactive 2D Drag-and-Drop · Windows / macOS / Linux / Android
</p>

---

## Key Capabilities

- **Multi-Tenant B2B Cloud SaaS, JWT Auth & 4-Role RBAC (`v0.6.0`)**: Organization workspaces (`Org`), PBKDF2-SHA256 + HS256 JWT authentication, 4-role RBAC (`admin`, `reviewer`, `designer`, `viewer`) enforced on mutations and `Released` revision approvals, audit trail, and unified **SQLite / PostgreSQL (`DATABASE_URL`)** database adapter with Docker Compose.
- **Interactive 2D Mounting Plate Drag-and-Drop, Collision & Wire BOM (`v0.6.0`)**: 10mm grid-snapped SVG Drag-and-Drop placement with persisted coordinates, real-time collision (`LAY-001`), plate boundary (`LAY-002`), and drive thermal clearance (`LAY-003`) alerts synced to Rule Checks, Thermal Heatmap overlay, 1:1 mm DXF, and **Manhattan duct-routed Panel Internal Wire length estimation** automatically injected into the Unified BOM (`M`).
- **Deterministic Electrical Sizing & Multi-Vendor BOM**: 3-phase/1-phase rated & starting current, voltage drop, cable SQ↔AWG, step-down transformer auto-sizing, SCCR & UL 508A / IEC 60204-1 / KS C IEC 60364 compliance, 7 electrical vendors (LS Electric, Schneider Electric, Siemens, Mitsubishi Electric, ABB, Fuji Electric, Omron), and **Excel (`.xlsx`) / CSV Load & Company Catalog DB Import**.
- **6-Vendor PLC Rack, I/O Allocation & PLCopen TC6 XML**: Mitsubishi Electric, LS Electric, Siemens, Rockwell Automation, Omron, and Beckhoff native addressing, spare-ratio rack sizing, **PLCopen TC6 XML**, IEC 61131-3 ST scaffolding, and **Natural-Language ST Interlock & Alarm Generator**.
- **Auto-Paginated Multi-Sheet IEC 61082 Schematics & EPLAN Delivery Package**: Automatic page splitting (`SH-02A/B`, `SH-04A/B`), `.ema` macro mapping, multi-sheet AutoCAD `.dxf`, **EPLAN AutomationML (`.aml`) + EPLAN Parts CSV**, Wire Labels CSV, Dossier HTML, and 1-click **Full Engineering Delivery Package (`.zip`)**.
- **Bilingual UI (EN Default / KO), External & Local LLM Gateway, Version Rollback & GitHub Auto-Update**: Offline Engine / Ollama / OpenAI-compatible RFP PDF parsing, revision promotion (`Draft → In Review → Released`), ECN Diff, rollback, and GitHub Releases Auto-Updater + Issues/Discussions.

---

## Screenshots

| Specs & Excel/Catalog Import (EN) | Interactive 2D Drag-and-Drop Layout & Wire BOM |
| :---: | :---: |
| ![Specs & Import](screenshots/01_specs_and_import_en.png) | ![2D Mounting Plate](screenshots/05_mounting_plate_2d_layout_en.png) |

| IEC 61082 Multi-Sheet Schematics | Multi-Tenant Auth & 4-Role RBAC Modal |
| :---: | :---: |
| ![Schematics](screenshots/04_schematics_iec61082_en.png) | ![Auth & RBAC](screenshots/08_auth_rbac_modal_en.png) |

---

## Cross-Platform & Cloud SaaS Deployment

### 1. Local Web Server or Cloud Docker Compose (PostgreSQL 16 + FastAPI)
```bash
# Local (SQLite)
pip install -r requirements.txt
uvicorn backend.main:app --host 0.0.0.0 --port 8000

# Cloud SaaS (PostgreSQL 16 + FastAPI)
docker compose up -d
```

### 2. Desktop Installers — Windows (`.exe`/`.msi`), macOS (`.dmg`), Linux (`.AppImage`/`.deb`)
```bash
# Bundle embedded Python backend binary
pip install pyinstaller
pyinstaller --clean --distpath dist/backend packaging/panelcraft-backend.spec

# Build platform installer with Electron + Auto-Updater
cd desktop
npm install
npm run dist:win    # Windows NSIS (.exe) & MSI
npm run dist:mac    # macOS (.dmg arm64 + x64)
npm run dist:linux  # Linux (.AppImage + .deb)
```

### 3. Android Installer (`.apk` / `.aab`) & PWA
- **PWA**: Open PanelCraft AI in Chrome on Android and tap **Install App** (`manifest.json` + `sw.js`).
- **Native Android APK/AAB (Capacitor)**:
```bash
cd mobile
npm install
npm run cap:add:android
npm run android:apk   # or npm run android:aab
```

### 4. Automated GitHub Releases & Version Bumping
```bash
python3 scripts/bump_version.py 0.4.0
git tag v0.4.0 && git push origin v0.4.0
```
Pushing a `v*.*.*` tag automatically triggers [`.github/workflows/release.yml`](.github/workflows/release.yml) to build and attach Windows, macOS, Linux, and Android installers to GitHub Releases.

---

## Community (Issues & Discussions)
- **Bug Reports & Feature Requests**: Use the **Community ▾** menu inside the app or open an issue via `.github/ISSUE_TEMPLATE/`.
- **Questions, Standards & Ideas**: Join **GitHub Discussions** directly from the app header.

## Running Tests
```bash
python3 -m unittest discover -s tests -v
```
