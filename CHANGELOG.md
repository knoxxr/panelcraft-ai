# Changelog

All notable changes to **PanelCraft AI** are documented in this file.

## [0.8.0] - 2026-11-27
### Added
- **Model Context Protocol (MCP) Server — Stdio & Streamable HTTP (`2025-03-26` / `2024-11-05`)**:
  - Added zero-dependency JSON-RPC 2.0 MCP server (`backend/mcp_server.py`) runnable over **Stdio** (`python3 -m backend.mcp_server`) for Claude Desktop, Cursor, Windsurf, VS Code, and Antigravity, AND mounted as **Streamable HTTP** at `POST /mcp` (with discovery at `GET /mcp` and optional Bearer JWT RBAC enforcement).
  - Registered **12 Control Panel Engineering Tools** (`list_tenants`, `list_projects`, `get_panel_design_summary`, `create_project_from_rfp`, `add_load_unit`, `apply_circuit_macro`, `switch_panel_vendor_or_standard`, `run_engineering_verification`, `get_bom_and_io_schedule`, `generate_plc_interlock_st`, `move_mounting_plate_component`, `export_engineering_artifact`).
  - Registered **7 MCP Resources & Templates** (`panelcraft://tenants`, `panelcraft://projects`, `panelcraft://macros`, `panelcraft://projects/{id}/design|eplan.aml|plcopen.xml|main.st`) and **3 Engineering Prompt Templates**.
  - Added interactive **MCP Server & Live Tool Playground** modal (`MCP` button in topbar) with copyable Stdio/HTTP client configs and live JSON-RPC `tools/call` execution.

## [0.7.0] - 2026-11-27
### Added
- **IEC 60909 Short-Circuit & Breaker Selectivity Engine**: Computes prospective 3-phase symmetrical fault current ($I''_{k3}$), peak short-circuit current ($i_p$), minimum fault current ($I_{k1,\min}$), main/branch $I_{cu}$ breaking verification (`ERC-005`), and upstream/downstream Selectivity Matrix (`TOTAL` / `PARTIAL` / `NON_SELECTIVE`, `ERC-006`).
- **IEC 60890 Precision Thermal & Cooling Engineering**: Computes effective enclosure cooling surface ($A_e$) by installation type (freestanding, wall-mounted, bayed), natural dissipation ($P_{\text{nat}}$), predicted uncooled vs cooled internal temperature, and automatically selects Natural Vent, TopTherm Filter Fan, or Blue e+ Panel AC in BOM.
- **Company EPLAN Electric P8 `.ema` Macro Library Editor & XML Exporter**: Tenant-scoped CRUD for company `.ema` paths, Variants (`A–P`), and Placeholder Variable bindings; overrides EPLAN AML (`EPLANMacroVariant`), schematics, downloadable `.ema` Window Macro XML (`<EplanPxfRoot>` + `<O117>` + `<ValueSet>`), and `EPLAN/macros/*.ema` inside the Full Engineering ZIP.

## [0.6.0] - 2026-11-27
### Added
- **Multi-Tenant SaaS Authentication & 4-Role RBAC**: PBKDF2-HMAC-SHA256 password hashing + HS256 JWT tokens with `admin`, `reviewer`, `designer`, and `viewer` roles enforced across projects, catalogs, revision release approvals, and rollbacks.
- **Unified SQLite / PostgreSQL Cloud DB Adapter**: Added `backend/db.py` and PostgreSQL 16 service in `docker-compose.yml` (`DATABASE_URL`) for scalable cloud SaaS deployments.
- **Interactive 2D Mounting Plate Drag-and-Drop Editor**: Drag any component directly on the SVG mounting plate with 10mm grid snap, real-time physical collision (`LAY-001`), boundary overflow (`LAY-002`), and thermal clearance (`LAY-003`) alerts, plus Auto-Reset.
- **Duct-Routed Panel Internal Wire Estimator → BOM Sync**: Automatically computes Manhattan wire-duct lengths (+18% slack) from live 2D component positions and injects `KIV/UL1015` internal wiring meters (`M`) into the Unified BOM.

## [0.5.0] - 2026-11-27
### Added
- **Auto-Paginated Multi-Sheet IEC 61082 Schematics & Multi-Sheet DXF**: Automatically paginates all power drive circuits (`SH-02A`, `SH-02B`, ...) and 100% of PLC I/O channels (`SH-04A`, `SH-04B`, ...) with cross-reference arrows, EPLAN `.ema` macro labels, and manufacturer tenant title blocks.
- **Step-Down Transformer (`-T1`), Panel SCCR (kA) & UL 508A AWG Sizing**: Auto-sizes 380/480V→220V step-down transformers when 220V servo/AC loads exist, computes panel SCCR from breaker $I_{cu}$ ratings, and displays dual `mm² / AWG` wire gauges.
- **Standard EPLAN Circuit Macro Library (1-Click Assembly)**: 6 pre-engineered FA macros (`MACRO-CONV-VFD`, `MACRO-SERVO-2AX`, `MACRO-HEATER-PID`, `MACRO-PUMP-DOL`, `MACRO-PNEU-IO`, `MACRO-SAFETY-PLE`) insertable directly into any project.
- **One-Click Full Engineering Delivery Package (`.zip`)**: Bundles EPLAN AML, EPLAN Parts CSV, PLCopen XML, ST code, I/O CSV, multi-sheet DXF, 2D mounting plate DXF/SVG, BOM, Wire Markers/Labels CSV, printable Engineering Dossier HTML, and FAT Checklist.
- **Organization Workspace Audit Trail**: Logs project edits, macro insertions, and package exports per manufacturer tenant.

## [0.4.0] - 2026-11-27
### Added
- **Multi-Tenant B2B SaaS Workspaces**: Support multiple equipment manufacturers (`K-Battery Automation`, `H-Semicon Systems`, `Apex Robotics & Logistics`, plus `+ Org` creation) with tenant-isolated projects and company standard catalogs.
- **Global PLC Ecosystem (6 Major Vendors)**: Added **Rockwell Automation (ControlLogix 5580)**, **Omron (Sysmac NX102)**, and **Beckhoff (TwinCAT CX/EL)** alongside Mitsubishi Electric, LS Electric, and Siemens with native addressing and **PLCopen TC6 XML** export.
- **Expanded Industrial Electrical Catalog (7 Major Vendors)**: Added **ABB (Tmax XT / AF / ACS380)**, **Fuji Electric (BW / SC-E / FRENIC)**, and **Omron (J7KC / MX2 / 1S / S8VK / G9SE)** plus **UL 508A 3P 480V** support and EPLAN macro mapping (`EPLANMacro` in AML).
- **Cloud SaaS Deployment Kit**: Production `Dockerfile`, `docker-compose.yml`, Nginx reverse proxy (`deploy/nginx.conf`), and `.env.example` for Cloud LLM & multi-tenant cloud hosting.

## [0.3.0] - 2026-11-27
### Added
- **Bilingual UI (English default / Korean toggle)**: Full `EN / KO` live language switcher persisted in browser storage.
- **App Version Management & Project Revision Rollback**: Single-source `VERSION` + `CHANGELOG.md`, revision status promotion (`Draft` -> `In Review` -> `Released`), and one-click snapshot restore/rollback.
- **Auto-Updater & GitHub Community Integration**: GitHub Releases semantic version update checker, platform installer download links, pre-filled GitHub Issue reporter, and GitHub Discussions portal.
- **Cross-Platform Installers & Packaging**: Electron desktop packaging (Windows `.exe`/`.msi`, macOS `.dmg`, Linux `.AppImage`/`.deb`), Capacitor Android (`.apk`/`.aab`), PWA (`manifest.json` + Service Worker), PyInstaller backend bundler, and GitHub Actions automated release workflow.
- **Brand Icon & Screenshots**: Custom multi-resolution app icons (`.png`, `.ico`) and automated full-screen UI screenshots in `screenshots/`.

## [0.2.0] - 2026-11-27
### Added
- **EPLAN AutomationML (CAEX 2.15) Exporter** (`.aml`) with device attributes, PLC rack logical addresses, and mounting plate coordinates.
- **Excel (`.xlsx`) & CSV Load Schedule / Company Catalog Importers** with BOM priority matching.
- **2D Control Panel Mounting Plate Layout** with EMC zone segregation, thermal heatmap overlay, and 1:1 mm AutoCAD DXF export.
- **External & Local LLM Gateway** (Ollama / OpenAI-compatible vLLM & Cloud API) with RFP PDF parsing and IEC 61131-3 ST Interlock & Alarm generator.

## [0.1.0] - 2026-11-26
### Added
- Initial SSOT MVP: deterministic electrical capacity calculator, multi-vendor BOM (LS Electric, Schneider, Siemens, Mitsubishi), PLC I/O allocator & ST scaffolding, 4-sheet IEC 61082 SVG/DXF schematics, ERC/DRC verification, and ECN revision diffing.
