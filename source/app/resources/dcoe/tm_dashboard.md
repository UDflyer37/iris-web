# OhCR / DCOE Team Manager — IRIS Dashboard Guide

TLP:AMBER+STRICT (internal)

This guide covers the **Team Manager (TM)** daily workflow in DFIR-IRIS after running `dcoe_bootstrap.py`.

**Team-wide role guides:** Each of the 11 operators has a pre-configured guide inside the mission case (`10 - Operator Guides`) plus a private **My Assigned Alerts** filter. Full reference: `role_operator_guides.md`.

---

## 1. Login and mission setup

| Step | Action |
|------|--------|
| 1 | Log in as `dcoe-tm` |
| 2 | **Manage → Customers** — create the NETO/customer for this mission |
| 3 | **Manage → Cases → New** — template **`OhCR-DCOE-MISSION-MASTER`** |
| 4 | Set case custom attributes (**OhCR/DCOE Mission** tab): OPORD, NETO org, ticket counter `1001` |
| 5 | Brief team: open **`10 - Operator Guides (Read First)`** — each member reads their role guide |
| 6 | Confirm each SME can see **OhCR-DCOE: My Assigned Alerts** under Alerts → Saved filters |

---

## 2. TM landing views (bookmarks)

| View | Navigation | Purpose |
|------|------------|---------|
| **Alert queue** | **Alerts** → saved filter **OhCR-DCOE: Open Alert Queue** | Primary SOC triage |
| **Mission checklist** | Open mission case → **Tasks** tab | 85 METL items |
| **Reporting index** | Mission case → note **METL Report MOP Evidence Index** | 21 report deliverables |
| **NETO tracker** | Mission case → `01 - Authority and NETO Access` | Ticket # ≥ 1001 |
| **Daily SitRep** | Mission case → `07 - Daily SitRep` | MOP 7.2.1 |
| **Reporting templates** | Mission case → `11 - Reporting Template Library` | All formal reports |
| **Network topology** | Sidebar → **Network Topology** | NETAD / team terrain view |

Direct alert URL pattern (after selecting a saved filter once, note the `filter_id`):

```
https://<iris-host>/alerts?cid=<case_id>&filter_id=<id>
```

---

## 3. Saved alert filters (seeded by bootstrap)

| Filter name | Use when |
|-------------|----------|
| **OhCR-DCOE: Open Alert Queue** | Morning triage — status New / Assigned / In Progress |
| **OhCR-DCOE: New Unassigned Alerts** | Assign owners to incoming detections |
| **OhCR-DCOE: Exercise Injects** | Cyber Shield white-cell traffic (`inject` tag) |
| **OhCR-DCOE: SIEM Detections** | Security Onion / SIEM pipeline (`siem` tag) |
| **OhCR-DCOE: High and Critical** | Priority escalation review |
| **OhCR-DCOE: Cyber Shield Mission** | All exercise-tagged alerts |

**How to apply:** Alerts page → expand **Filters** → **Saved filters** dropdown → select preset → page reloads with criteria.

To recreate filters after a fresh bootstrap, re-run:

```bash
docker exec iriswebapp_app python3 /iriswebapp/scripts/dcoe_bootstrap.py
```

(Bootstrap skips existing templates but re-checks filters by name.)

---

## 4. METL task checklist filters (mission case)

On **Case → Tasks**, use the DataTables column filter on **Tags**:

| Search tag | Shows |
|------------|-------|
| `tm-checklist-report` | **21 Report MOPs** (TM reporting requirements) |
| `tm-checklist-moe` | **MOE validation gates** (TM sign-off) |
| `mop-7.2.1` | Daily SitRep task |
| `mop-7.4.1` | Gold Report / NDP outbrief |
| `mop-3.3.4` | NETO network action documentation |
| `analyst-km` | Knowledge Manager owned items |
| `leader-tm` | TM-led items |
| `mop-2.3.2` | NETO access request |

**TM daily closeout:** all tasks tagged `tm-checklist-report` due today must be **Done** or linked to evidence in notes.

---

## 5. TM daily rhythm

### Morning (MOP 7.1.x)

1. Confirm ASA posted INTSUM (note or `07` inbrief log)
2. Conduct inbrief — update `07 - Daily SitRep` → **Daily Inbrief Log**
3. Open **OhCR-DCOE: Open Alert Queue** — assign new alerts
4. Review mission tasks tagged `tm-checklist-report` due today

### During operations

| Event | IRIS action |
|-------|-------------|
| New SIEM detection | Appears in Alerts (feeder) → assign → escalate or merge |
| Exercise inject | Tag includes `inject` — use inject filter |
| NETO approval needed | Add row to `01` NETO tracker note; create ticket task |
| Informal NETO update | Case comment on mission case |
| New investigation | Child case from **`OhCR-DCOE-INCIDENT`** template |

### End of day (MOP 7.2.1)

1. KM copies **SitRep TEMPLATE — OhCR Internal** → fill → save as `SitRep OhCR YYYY-MM-DD`
2. KM copies **SitRep TEMPLATE — Customer NETO** → sanitize → save as `SitRep Customer YYYY-MM-DD`
3. TM marks task **`[7.2.1]`** Done with links to both notes
4. Update **METL Report MOP Evidence Index**

### Last day (MOP 7.4.x)

1. KM completes **`08 - Gold Report`** outline
2. TM validates ≥3 AAR entries in **`09 - AAR and Hotwash`**
3. Close remaining MOE tasks (`tm-checklist-moe`)
4. Set mission case state → **Closed**

---

## 6. SIEM → IRIS alert feeder

### One-time setup

1. Run bootstrap and note the **`dcoe-siem-api`** API key (printed at end, or retrieve from **Manage → Users**)
2. Copy config:

```bash
cp source/app/resources/dcoe/dcoe_siem_feeder.example.json dcoe_siem_feeder.json
# Edit iris_url (your LAN HTTPS IP), iris_api_key, default_customer_id
```

3. Optional: set `ioc_type_ids` and `asset_type_ids` after checking **Manage → IOC Types** and **Asset Types**

### Test from analyst laptop (LAN)

```bash
# Connectivity
python3 scripts/dcoe_siem_feeder.py --config dcoe_siem_feeder.json --ping

# Dry-run sample batch
python3 scripts/dcoe_siem_feeder.py --config dcoe_siem_feeder.json \
  --file source/app/resources/dcoe/sample_alerts.jsonl --dry-run

# Submit sample batch
python3 scripts/dcoe_siem_feeder.py --config dcoe_siem_feeder.json \
  --file source/app/resources/dcoe/sample_alerts.jsonl
```

### Single alert (manual / script wrapper)

```bash
python3 scripts/dcoe_siem_feeder.py --config dcoe_siem_feeder.json \
  --title "Suspicious RDP session" \
  --severity high \
  --customer-id 1 \
  --tags "ohcr,dcoe,siem,cyber-shield" \
  --asset "WS-042" \
  --ioc "10.10.50.42"
```

### Security Onion / SIEM integration pattern

```
Detection rule → export script (JSON line) → dcoe_siem_feeder.py --file alerts.jsonl
```

Run on a 5-minute cron from the IRIS server or a trusted analyst jump box on the exercise VLAN.

**TLS:** set `"verify_tls": false` in config for self-signed LAN certificates (exercise only).

---

## 7. Role quick reference

Each role has an **in-app operator guide** (mission case notes) and **private alert filter**.

| Login | Role | METL tag filter | Primary workspace |
|-------|------|-----------------|-------------------|
| `dcoe-tm` | Team Manager | `leader-tm`, `tm-checklist-report` | Alerts, NETO tracker, METL index |
| `dcoe-dtm` | Deputy TM | `leader-dtm` | `02 - Mission Planning`, Gold Report |
| `dcoe-km` | Knowledge Manager | `analyst-km` | `07`/`08` SitRep and Gold Report |
| `dcoe-rma` | Risk Auditor | `analyst-rma` | `04 - Key Terrain and Risk` |
| `dcoe-netad` | Network SME | `analyst-netad` | `03 - Battlespace Enumeration` |
| `dcoe-df` | Digital Forensics | `analyst-df` | Child incident cases, artifact log |
| `dcoe-int` | Intrusion / Hunt | `analyst-int` | SIEM detections, hunt cases |
| `dcoe-end` | Endpoint Analyst | `analyst-end` | Endpoint alerts, host mitigations |
| `dcoe-asa` | All Source Analyst | `analyst-asa` | INTSUM, intel requirements |
| `dcoe-siem` | SIEM Analyst | `analyst-siem` | SIEM detection queue |
| `dcoe-sysad` | System Admin | `analyst-sysad` | Platform and logging support |

See `role_operator_guides.md` for full responsibilities, daily workflows, and IRIS tool usage per role.

---

## 8. LAN deployment reminders

- Team browsers → `https://<iris-server-ip>` (port 443)
- Use **local accounts** until LDAP is configured
- Customer-facing notes: **TLP:AMBER**; internal: **TLP:AMBER+STRICT**
- Do not give OhCR SitRep (with reservist names) to NETO — per SOP 7.2.1

---

## 9. Re-bootstrap / exercise reset

```bash
DCOE_BOOTSTRAP_PASSWORD='YourTeamPassword' \
  docker exec -e DCOE_BOOTSTRAP_PASSWORD iriswebapp_app \
  python3 /iriswebapp/scripts/dcoe_bootstrap.py
```

Templates are not duplicated if they already exist. Delete old case templates in **Manage → Case Templates** before re-bootstrap if you need a fresh METL task set **with operator guides**.

Re-bootstrap also creates per-user **OhCR-DCOE: My Assigned Alerts** private filters for all 11 roles.
