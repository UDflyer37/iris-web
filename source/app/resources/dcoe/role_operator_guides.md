# OhCR/DCOE Role Operator Guides

TLP:AMBER+STRICT — Use with DFIR-IRIS after `dcoe_bootstrap.py`.

**In-app:** Mission case → `10 - Operator Guides (Read First)` → your role guide.

**Per-user dashboards:**
- `/dashboard` — your tasks and cases
- `/alerts` — shared role filters + private **OhCR-DCOE: My Assigned Alerts**
- Mission case **Tasks** — filter Tags per table below

---

## Team Manager (TM)

**Login:** `dcoe-tm` | **Group:** `OhCR-DCOE-TM`
**SOP role:** Team Lead — reporting authority and NETO coordination

### Responsibilities
- Lead the OhCR/DCOE team; issue mission guidance and enforce METL compliance
- Own the 21 Report MOPs — validate evidence in METL Evidence Index daily
- Sign MOE validation gates before shift turnover
- Assign and prioritize alerts; approve NETO tickets (≥1001) in the tracker
- Conduct daily inbrief; ensure SitRep (7.2.1) is complete before close of business
- Approve Gold Report and AAR before mission close

### METL task filters (Tasks → Tags)
- Primary: `leader-tm`
- Reporting: `tm-checklist-report, tm-checklist-moe`

### Note workspaces
- **01 - Authority and NETO Access** — NETO ticket tracker — approve network actions
- **07 - Daily SitRep** — Validate KM drafts; sign off MOP 7.2.1
- **METL Evidence Index** — 21 Report MOP compliance board
- **08 - Gold Report** — Final outbrief approval (MOP 7.4.1)
- **09 - AAR and Hotwash** — Ensure ≥3 AAR comments (MOP 7.4.2)

### Alert filters
- **OhCR-DCOE: Open Alert Queue** — Start of shift — triage all open alerts
- **OhCR-DCOE: New Unassigned Alerts** — Assign owners to incoming detections
- **OhCR-DCOE: High and Critical** — Escalation review
- **OhCR-DCOE: My Assigned Alerts** (private) — Alerts assigned to you as TM

### IRIS tools
- **Alerts** — Assign detections to SMEs; merge or escalate to child incident cases
- **Mission case → Tasks** — Filter Tags: tm-checklist-report and tm-checklist-moe
- **Mission case → Notes** — NETO tracker, SitRep validation, METL index
- **Manage → Cases** — Create child cases from OhCR-DCOE-INCIDENT template
- **Dashboard** — Your assigned global tasks and open cases

### Start of shift
- Open Alerts → OhCR-DCOE: Open Alert Queue
- Mission case → Tasks → filter leader-tm and tm-checklist-report
- Review 07 - Daily SitRep → Daily Inbrief Log

### During ops
- Assign new alerts to the correct SME
- Log NETO actions in 01 tracker before execution
- Mark METL tasks Done only when evidence is linked in notes

### End of shift
- Confirm KM published OhCR + Customer SitReps
- Mark MOP 7.2.1 task Done with note links
- Update METL Report MOP Evidence Index

### Reporting deliverables
- METL Report MOP evidence (21 items)
- MOE validation sign-offs
- Daily SitRep approval (7.2.1)
- Gold Report / AAR approval (7.4.x)

**Coordinates with:** KM, DTM, NETO, All SMEs

---

## Deputy Team Manager (DTM)

**Login:** `dcoe-dtm` | **Group:** `OhCR-DCOE-DTM`
**SOP role:** Deputy Team Lead — planning and operational oversight

### Responsibilities
- Support TM on mission planning, COA development, and intel integration
- Lead Core Task 2 assessment products with RMA (operational environment, threat)
- Compile planning inputs for Gold Report with KM
- Back-brief TM on hunt/IR status and significant activities
- Assume TM duties when delegated

### METL task filters (Tasks → Tags)
- Primary: `leader-dtm`

### Note workspaces
- **02 - Mission Planning** — Mission analysis, COA worksheet, limitations
- **03 - Battlespace Enumeration** — Review network/vuln inputs from SMEs
- **08 - Gold Report** — Compile planning and assessment sections

### Alert filters
- **OhCR-DCOE: Open Alert Queue** — Situational awareness
- **OhCR-DCOE: Cyber Shield Mission** — Exercise-wide alert picture
- **OhCR-DCOE: My Assigned Alerts** (private) — Alerts assigned to you

### IRIS tools
- **Mission case → Tasks** — Filter Tags: leader-dtm
- **Mission case → Notes** — 02 Mission Planning whiteboard and COA
- **Cases** — Monitor child incident cases linked in 05 index
- **Dashboard** — Your task queue and case list

### Start of shift
- Mission case → Tasks → filter leader-dtm
- Review 02 - Mission Planning for open COA/MA items

### During ops
- Coordinate with ASA on intel requirements
- Ensure hunt cases are linked in 05 - Active Incidents Index

### End of shift
- Brief TM on planning deltas for SitRep
- Update Gold Report outline inputs in 08

### Reporting deliverables
- Mission analysis and COA products (Core Task 2)
- Gold Report planning sections
- DFIR threat detection coordination (3.5.3)

**Coordinates with:** TM, KM, RMA, ASA

---

## Knowledge Manager (KM)

**Login:** `dcoe-km` | **Group:** `OhCR-DCOE-KM`
**SOP role:** Knowledge Manager — system of record and reporting author

### Responsibilities
- Maintain DFIR-IRIS as the authoritative evidence repository
- Author daily OhCR Internal and Customer NETO SitReps (MOP 7.2.1)
- Document unauthorized artifacts per 4.6.3
- Compile Gold Report narrative with DTM/TM
- Maintain METL evidence links and artifact documentation log

### METL task filters (Tasks → Tags)
- Primary: `analyst-km`

### Note workspaces
- **05 - Hunt and Incident Response** — Artifact documentation log
- **06 - Hardening and Mitigations** — Adversary removal and remediation inputs
- **07 - Daily SitRep** — PRIMARY — copy templates daily
- **08 - Gold Report** — Draft executive summary and recommendations
- **METL Evidence Index** — Link evidence for KM-owned MOPs

### Alert filters
- **OhCR-DCOE: Cyber Shield Mission** — Track exercise alerts for SitRep activities
- **OhCR-DCOE: My Assigned Alerts** (private) — Alerts assigned to you

### IRIS tools
- **Mission case → Notes** — Copy SitRep templates daily; never give OhCR version to NETO
- **Mission case → Tasks** — Filter Tags: analyst-km
- **Case → Evidence** — Upload and tag artifacts referenced in notes
- **Case → IOCs/Assets** — Ensure detection context is documented

### Start of shift
- Mission case → Tasks → filter analyst-km
- Review 05 artifact log for overnight additions

### During ops
- Document artifacts as SMEs upload evidence
- Capture significant activities for SitRep section 3

### End of shift
- Copy SitRep TEMPLATE — OhCR Internal → fill → save as SitRep OhCR YYYY-MM-DD
- Copy SitRep TEMPLATE — Customer NETO → sanitize → save as SitRep Customer YYYY-MM-DD
- Notify TM when both are ready for MOP 7.2.1 sign-off

### Reporting deliverables
- Daily SitRep OhCR + Customer versions (7.2.1)
- Artifact documentation (4.6.3)
- Gold Report narrative (7.4.1)
- Adversary removal report inputs (5.3.1)

**Coordinates with:** TM, DTM, All SMEs, NETO (Customer SitRep only)

---

## Risk Management Auditor (RMA)

**Login:** `dcoe-rma` | **Group:** `OhCR-DCOE-RMA`
**SOP role:** Risk Management Auditor SME

### Responsibilities
- Lead operational environment and environmental effects analysis (2.2.1–2.2.2)
- Maintain 5x5 risk matrix and Dynamic Risk Analysis (DRA)
- Document network actions and NETO ticket compliance (3.3.4)
- Validate vulnerability findings feed SitRep and Gold Report
- Support MOE validation with TM on risk-related gates

### METL task filters (Tasks → Tags)
- Primary: `analyst-rma`

### Note workspaces
- **01 - Authority and NETO Access** — Support NETO ticket risk column
- **03 - Battlespace Enumeration** — Vulnerability analysis log
- **04 - Key Terrain and Risk** — 5x5 matrix and DRA — PRIMARY workspace

### Alert filters
- **OhCR-DCOE: High and Critical** — Risk-relevant escalations
- **OhCR-DCOE: My Assigned Alerts** (private) — Alerts assigned to you

### IRIS tools
- **Mission case → Tasks** — Filter Tags: analyst-rma
- **Mission case → Notes** — 04 Cyber Defense Analysis and vuln log
- **Case → Assets** — Register critical assets and key terrain

### Start of shift
- Mission case → Tasks → filter analyst-rma
- Update 04 protect surface / DRA

### During ops
- Score new findings in vulnerability log
- Verify NETO tickets include risk rating

### End of shift
- Provide risk delta summary to KM for SitRep section 4

### Reporting deliverables
- Operational environment reports (2.2.1–2.2.2)
- Network action documentation (3.3.4)
- 5x5 / DRA products for Gold Report

**Coordinates with:** DTM, TM, NETAD, KM

---

## Network Administration SME (NETAD)

**Login:** `dcoe-netad` | **Group:** `OhCR-DCOE-NETAD`
**SOP role:** Network Administration SME

### Responsibilities
- Produce physical and logical network maps (2.6.1–2.6.2)
- Maintain traffic flow overlay (3.3.5)
- Support NETO network action requests with technical detail
- Validate 95%+ network map MOE (3.3.7) with TM
- Provide network context for hunt and hardening recommendations

### METL task filters (Tasks → Tags)
- Primary: `analyst-netad`

### Note workspaces
- **03 - Battlespace Enumeration** — Network map index — PRIMARY
- **06 - Hardening and Mitigations** — Network mitigation details

### Alert filters
- **OhCR-DCOE: SIEM Detections** — Network-relevant detections
- **OhCR-DCOE: My Assigned Alerts** (private) — Alerts assigned to you

### IRIS tools
- **Mission case → Tasks** — Filter Tags: analyst-netad
- **Mission case → Notes** — 03 Network Map and Overlay Index
- **Case → Assets** — Document network assets and topology
- **Case → Evidence** — Attach map files and pcaps metadata

### Start of shift
- Review assigned alerts for network scope
- Update map index links

### During ops
- Support SMEs with network context
- Log overlay changes in 03

### End of shift
- Confirm map coverage % for MOE 3.3.7
- Send network delta to KM

### Reporting deliverables
- Physical network map (2.6.1)
- Logical network map (2.6.2)
- Traffic flow overlay (3.3.5)

**Coordinates with:** RMA, SYSAD, INT, TM

---

## Digital Forensics SME (DF)

**Login:** `dcoe-df` | **Group:** `OhCR-DCOE-DF`
**SOP role:** Digital Forensics SME

### Responsibilities
- Lead forensic analysis on escalated incidents
- Collect and preserve artifacts; coordinate with KM on documentation
- Support DFIR threat detection MOP (3.5.3) with DTM
- Create and maintain child incident cases for deep-dive investigations
- Provide forensic findings for SitRep and Gold Report

### METL task filters (Tasks → Tags)
- Primary: `analyst-df`

### Note workspaces
- **05 - Hunt and Incident Response** — Active incidents and artifact log
- **05 - Hunt and Incident Response** — Link child OhCR-DCOE-INCIDENT cases

### Alert filters
- **OhCR-DCOE: My Assigned Alerts** — Your owned detections (shared filter)
- **OhCR-DCOE: My Assigned Alerts** (private) — Alerts assigned to you

### IRIS tools
- **Alerts → Escalate** — Promote alerts to OhCR-DCOE-INCIDENT child cases
- **Mission case → Tasks** — Filter Tags: analyst-df
- **Case → Evidence** — Upload forensic images, logs, timelines
- **Case → Timeline** — Build event sequence for incidents

### Start of shift
- Alerts → My Assigned Alerts
- Review 05 Active Incidents Index

### During ops
- Work child incident cases
- Upload artifacts; notify KM

### End of shift
- Update incident case status
- Summarize findings for KM SitRep

### Reporting deliverables
- Forensic analysis on incident cases
- DFIR threat detection support (3.5.3)
- Artifact evidence in 05 log

**Coordinates with:** KM, DTM, END, INT

---

## Intrusion Detection SME (INT)

**Login:** `dcoe-int` | **Group:** `OhCR-DCOE-INT`
**SOP role:** Intrusion Detection / Hunt SME

### Responsibilities
- Triage and investigate intrusion-related alerts
- Lead threat hunting on assigned terrain
- Correlate SIEM detections with network and endpoint context
- Escalate confirmed intrusions to child incident cases
- Support hardening and adversary removal analysis

### METL task filters (Tasks → Tags)
- Primary: `analyst-int`

### Note workspaces
- **05 - Hunt and Incident Response** — Hunt findings and incident links
- **06 - Hardening and Mitigations** — Detection-driven mitigations

### Alert filters
- **OhCR-DCOE: SIEM Detections** — Primary detection feed
- **OhCR-DCOE: Exercise Injects** — White-cell hunt scenarios
- **OhCR-DCOE: My Assigned Alerts** (private) — Alerts assigned to you

### IRIS tools
- **Alerts** — Triage SIEM queue; add IOCs and assets
- **Mission case → Tasks** — Filter Tags: analyst-int
- **Cases** — OhCR-DCOE-INCIDENT for confirmed hunts
- **Search** — Cross-case IOC and asset correlation

### Start of shift
- Alerts → SIEM Detections + My Assigned Alerts

### During ops
- Investigate assigned alerts
- Create/update child cases

### End of shift
- Hand open hunts to next shift via case comments

### Reporting deliverables
- Hunt status in 05 index
- Detection analysis for SitRep significant activities

**Coordinates with:** SIEM, END, DF, NETAD

---

## Endpoint Analyst SME (END)

**Login:** `dcoe-end` | **Group:** `OhCR-DCOE-END`
**SOP role:** Endpoint Analysis SME

### Responsibilities
- Analyze endpoint-related alerts and EDR telemetry
- Support forensic collection on workstations and servers
- Document endpoint findings in incident child cases
- Contribute endpoint mitigations to hardening recommendations
- Validate protect-surface matrix for endpoint assets

### METL task filters (Tasks → Tags)
- Primary: `analyst-end`

### Note workspaces
- **04 - Key Terrain and Risk** — Endpoint assets in protect surface
- **05 - Hunt and Incident Response** — Endpoint incident documentation
- **06 - Hardening and Mitigations** — Host mitigation details

### Alert filters
- **OhCR-DCOE: SIEM Detections** — Endpoint-related detections
- **OhCR-DCOE: My Assigned Alerts** (private) — Alerts assigned to you

### IRIS tools
- **Alerts** — Triage endpoint alerts; tag assets
- **Mission case → Tasks** — Filter Tags: analyst-end
- **Case → Assets** — Register hosts under investigation
- **Case → Evidence** — Upload EDR exports and disk artifacts

### Start of shift
- My Assigned Alerts
- Check 04 for endpoint key terrain updates

### During ops
- Work assigned alerts and child cases
- Coordinate with DF on collections

### End of shift
- Update 06 host mitigations
- Brief KM on endpoint findings

### Reporting deliverables
- Endpoint analysis on incidents
- Host mitigation inputs for Gold Report

**Coordinates with:** DF, INT, SIEM, SYSAD

---

## All Source Analyst (ASA)

**Login:** `dcoe-asa` | **Group:** `OhCR-DCOE-ASA`
**SOP role:** All Source Analyst — intelligence and INTSUM

### Responsibilities
- Publish daily INTSUM for inbrief (7.1.2)
- Develop prioritized intelligence requirements (2.4.1)
- Evaluate threat/adversary and COA (2.2.3–2.2.4)
- Coordinate with customer intel sources per SOP
- Feed threat context to hunt SMEs and SitRep

### METL task filters (Tasks → Tags)
- Primary: `analyst-asa`

### Note workspaces
- **02 - Mission Planning** — Intelligence requirements — PRIMARY
- **07 - Daily SitRep** — INTSUM feeds Daily Inbrief Log

### Alert filters
- **OhCR-DCOE: Exercise Injects** — Intel-related injects
- **OhCR-DCOE: My Assigned Alerts** (private) — Alerts assigned to you

### IRIS tools
- **Mission case → Tasks** — Filter Tags: analyst-asa
- **Mission case → Notes** — 02 Intel Requirements; 07 Inbrief Log
- **Case → IOCs** — Document threat indicators from intel sources

### Start of shift
- Post INTSUM to 07 Daily Inbrief Log
- Mission case → Tasks → analyst-asa

### During ops
- Update intel requirements status
- Brief DTM/TM on threat changes

### End of shift
- Ensure INTSUM ready for next inbrief
- Provide threat summary to KM

### Reporting deliverables
- Daily INTSUM (7.1.2)
- Prioritized intel requirements (2.4.1)
- Threat evaluation products (2.2.3–2.2.4)

**Coordinates with:** DTM, TM, INT, KM

---

## SIEM Analyst (SIEM)

**Login:** `dcoe-siem` | **Group:** `OhCR-DCOE-SIEM`
**SOP role:** SIEM Analyst — detection pipeline and alert quality

### Responsibilities
- Monitor SIEM/Security Onion detection feed into IRIS
- Triage new SIEM alerts before TM assignment
- Enrich alerts with assets, IOCs, and severity
- Tag alerts ohcr, dcoe, siem, cyber-shield for filtering
- Support dcoe-siem-api feeder health and tuning

### METL task filters (Tasks → Tags)
- Primary: `analyst-siem`

### Note workspaces
- **05 - Hunt and Incident Response** — Log significant detection patterns

### Alert filters
- **OhCR-DCOE: SIEM Detections** — PRIMARY queue — all SIEM-sourced alerts
- **OhCR-DCOE: New Unassigned Alerts** — Pick up unassigned SIEM alerts
- **OhCR-DCOE: Open Alert Queue** — Full queue situational awareness
- **OhCR-DCOE: My Assigned Alerts** (private) — Alerts assigned to you

### IRIS tools
- **Alerts** — Primary workspace — enrich, tag, request TM assignment
- **Mission case → Tasks** — Filter Tags: analyst-siem
- **Manage → Users** — dcoe-siem-api service account API key for feeder

### Start of shift
- Alerts → OhCR-DCOE: SIEM Detections
- Verify feeder is posting (check newest alerts)

### During ops
- Enrich and route alerts to INT/END/NETAD as appropriate
- Flag injects with inject tag

### End of shift
- Clear or reassign open SIEM alerts
- Note tuning issues for SYSAD

### Reporting deliverables
- Detection pipeline status for SitRep
- Alert quality and tuning notes

**Coordinates with:** TM, INT, END, SYSAD

---

## System Administration SME (SYSAD)

**Login:** `dcoe-sysad` | **Group:** `OhCR-DCOE-SYSAD`
**SOP role:** System Administration SME — platform and logging

### Responsibilities
- Maintain IRIS platform health and user access during exercise
- Support logging/visibility requirements for NETO (2.3.x)
- Assist NETAD with infrastructure asset documentation
- Support SIEM feeder and integration troubleshooting
- Document system changes in NETO tracker when required

### METL task filters (Tasks → Tags)
- Primary: `analyst-sysad`

### Note workspaces
- **01 - Authority and NETO Access** — Logging/access change tickets
- **03 - Battlespace Enumeration** — Infrastructure asset context

### Alert filters
- **OhCR-DCOE: Cyber Shield Mission** — Platform-related exercise alerts
- **OhCR-DCOE: My Assigned Alerts** (private) — Alerts assigned to you

### IRIS tools
- **Mission case → Tasks** — Filter Tags: analyst-sysad
- **Manage → Users** — Support account issues (with TM approval)
- **Server** — dcoe_bootstrap.py and dcoe_siem_feeder.py maintenance

### Start of shift
- Verify IRIS and feeder health
- Mission case → Tasks → analyst-sysad

### During ops
- Support SME access issues
- Assist SIEM with integration errors

### End of shift
- Document infrastructure changes in 01 tracker
- Hand off open tasks

### Reporting deliverables
- Logging/access compliance (2.3.x)
- Platform availability for SitRep

**Coordinates with:** NETAD, SIEM, TM

---
