# AutoGrade → AutoERP integration design

_Status: AutoERP side shipped 2026-09-10 in `erpnext/palm_mill` (branch `feat/palm-mill-module`), with AutoGrade as
the single caller: the scale program feeds AutoGrade, and AutoGrade sends each visit (weights + grading) to AutoERP.
AutoGrade side: not started._

## 0. The question this answers

Should the onsite AI grading system (**AutoGrade**: `palmgrade-api`, `palmgrade-frontend`, `palmgrade-vision`)
push its data straight into the ERP backoffice (**AutoERP**, the ERPNext fork), mapping grading → quality,
truck → truck, supplier → supplier, and let ERPNext's linked documents do the rest?

Short answer: the intent is right, the mapping as stated is not.

Facts this design rests on (verified in both repos and on the `pks.localhost` demo site):

- AutoGrade holds **no commercial data**: no weights, prices, deductions, supplier codes, or approval state.
  It holds suppliers, trucks (plate stored as typed, de-duplicated by normalised plate), `line_assignments`
  (one per truck visit, `active|closed`) and per-bunch AI verdicts in Mongo (`ai_inspections`: ACC/REJ,
  ripeness, tangkai panjang).
- AutoGrade's own spec (`docs/superpowers/specs/2026-07-12-master-data-sync-design.md` §7) already says
  master data is owned by the **backoffice** and pulled down to the mill; edge edits to synced trucks revert.
- The mill is outbound-only (edge → cloud HTTPS). The cloud `palmgrade-api` already receives everything.
- In AutoERP, "everything connected" starts at the **Purchase Receipt**, which needs net kg and a rate.
  The demo looks automatic only because the seeder created every ticket → receipt → invoice link through the
  API. `Weighbridge Ticket` is a DB-only custom DocType with **no controller logic**.
- A separate scale program owns gross/tare and can be connected to AutoERP. AutoERP is cloud-hosted.

Decisions taken: AutoERP owns supplier and truck master data; AutoERP runs in the cloud.

## The visit, end to end

What happens physically, what each system does, and what the AutoERP ticket looks like at that moment.
The order is the real order; steps 3 and 4 can overlap with 5 and the ticket copes with events arriving in
any sequence.

| #   | Where             | Physically                                                                                                  | System event                                                                                                                                     | Weighbridge Ticket                                    |
| --- | ----------------- | ----------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------- |
| 1   | Gate, weighbridge | Truck drives on loaded; plate and supplier noted                                                            | Scale → AutoGrade (mill edge): gate weighing opens a visit. AutoGrade → `upsert_visit` (stage gate). Unknown plate → Truck created without an owner               | created, **Waiting Weight**                           |
| 2   | Loading ramp      | Fruit unloaded onto the grading line                                                                        | Operator assigns the truck to the AutoGrade line                                                                                                 | unchanged                                             |
| 3   | Grading line      | Camera grades every bunch: ACC or REJ; long stalks flagged among ACC; operator can force a reject           | Vision → AutoGrade (hourly batches)                                                                                                              | unchanged                                             |
| 4   | Grading line      | **Rejected bunches go back on the truck**; accepted fruit stays in the ramp                                 | AutoGrade closes the assignment → `upsert_visit` (stage grading: counts, %)                                                                      | sortasi rows written; **Waiting Weight** or **Ready** |
| 5   | Weighbridge       | Truck weighs out **with the rejects on board**: the tare includes them, so net = what stayed                | Scale → AutoGrade: weigh-out. AutoGrade → `upsert_visit` (stage departed: tare, time out)                                                        | net set; **Waiting Grading** or **Ready**             |
| 6   | AutoERP           | Nothing physical                                                                                            | `try_finalize`: potongan and payable kg from the rules, price from the Item Price, submit                                                        | **Finalised**                                         |
| 7   | AutoERP           | Nothing physical                                                                                            | Purchase Receipt (External) or Material Receipt (Internal) into the TBS warehouse, daily batch `TBS-YYYYMMDD`, item discount = potongan | receipt / stock entry linked                          |
| 8   | Backoffice, later | Purchase Invoice per supplier per period, Payment Entry; supplier scorecards; production draws on the batch | standard ERPNext                                                                                                                                 | —                                                     |

**Classification and money.** Three things happen to a load, and they land in three different places:

- **Rejected (REJ)** bunches are returned to the truck. They are never paid: the weigh-out tare carries them
  away, so they are outside net weight. The count and share still reach the ticket (`grading_rej`,
  Mentah %) for supplier statistics.
- **Accepted (ACC)** fruit is what the mill receives: quantity on the receipt = net − sampah kg.
- **Deduction on accepted** fruit: potongan % = Σ (criterion % × weight in Palm Mill Settings), capped, applied
  as the receipt item's discount; sampah (trash) reduces the kilograms instead of the price. Amount paid =
  (net − sampah) × price × (1 − potongan). For Internal loads there is no payment: the stock entry books the
  fruit at the transfer price and potongan is a quality figure only.

Worked example (a real run on the demo site): gross 14,560 kg, tare 5,400 kg → net 9,160 kg; grading
Mentah 9.95 %, Tangkai Panjang 5.58 %; rules Mentah 60, Tangkai Panjang 100 → potongan 11.55 %; payable
8,102 kg × Rp 2,850 = Rp 23,090,700; receipt: 9,160 kg at Rp 2,850 less 11.55 % = Rp 23,090,711 (the
receipt rounds money, the ticket rounds kilograms).

Rule to decide before go-live (§8): the demo's Mentah weight of 60 dates from before physical rejection.
Once rejected bunches leave with the truck they are already excluded by the weighing, so charging Mentah again
as a price deduction penalises the supplier twice. Set the Mentah weight to 0 in Palm Mill Settings when the
line returns rejects, and keep it only where rejects are accepted with a discount instead.

## 1. Principles

- **AutoERP is the system of record** for suppliers, trucks, prices, deductions, tickets, receipts, payments.
- **AutoGrade is a sensor/operations system.** It owns line assignments, per-bunch inspections and images.
- **The scale program is the weight source, and it feeds AutoGrade**, not AutoERP: one system talks to the ERP,
  and AutoGrade knows every truck's weight for its own analytics.
- **One truck visit = one Weighbridge Ticket** in AutoERP. Grading and weight attach to it independently;
  the ticket finalises itself when both are present, or on timeout.
- **AutoGrade cloud is the only caller of AutoERP.** The mill edge and the scale program never hold ERP credentials.
- **Idempotent upserts with natural keys** everywhere; retries are always safe.

## 2. Ownership and direction

| Data                                               | Owner         | Flow                                                                                             |
| -------------------------------------------------- | ------------- | ------------------------------------------------------------------------------------------------ |
| Supplier (name, contact, group, payment terms)     | AutoERP       | AutoERP → AutoGrade cloud (pull) → edge (existing sync)                                          |
| Truck (plate, supplier, class, capacity)           | AutoERP       | AutoERP → AutoGrade; **unknown plates** AutoGrade → AutoERP                                       |
| Site ↔ Company / Warehouse mapping                 | AutoERP       | configured once on the AutoGrade site record                                                     |
| Line assignment, per-bunch inspections, images     | AutoGrade     | stays; ERP gets a summary and a deep link                                                        |
| Grading session summary (per visit)                | AutoGrade     | AutoGrade cloud → AutoERP                                                                        |
| Gross / tare / net, time in / out                  | Scale program | Scale → AutoGrade edge → cloud → AutoERP, inside the visit message (or typed on the ticket form) |
| Deduction rules, price, sumber TBS, blok           | AutoERP       | internal                                                                                         |
| Purchase Receipt / Stock Entry / Invoice / Payment | AutoERP       | internal, created from the ticket                                                                |

Not synced: users, roles, machines, per-bunch rows, images, anything edge → ERP directly.

## 3. Identity

- **Truck.** Normalised plate `upper(regexp_replace(plate, '[^A-Za-z0-9]', ''))` is the cross-system key.
  AutoERP `Truck` gains `plate_normalized` (unique). AutoGrade already has this index (`init-db/022`,
  `src/utils/plateNormalizer.ts`). Both sides store the other's id: AutoGrade `trucks.erp_name`,
  AutoERP `Truck.autograde_id`.
- **Supplier.** AutoERP `Supplier.name` is the id. AutoGrade adds `suppliers.erp_name` (nullable until
  matched). No matching by display name after a one-time initial reconciliation.
- **Site.** AutoGrade `sites` gets `erp_company` and `erp_warehouse` (receiving warehouse for TBS).
- **Visit.** AutoGrade creates a visit id when the gate weighing arrives → `Weighbridge Ticket.autograde_visit_id`
  (unique, the primary integration key). The line assignment id and the scale ticket number are stored as
  secondary keys (`autograde_assignment_id`, `scale_ticket_no`), so a ticket typed by hand from the scale slip is
  adopted by the visit when AutoGrade catches up.
- Timestamps are ISO-8601 with offset; the site timezone (AutoGrade `sites.timezone`) decides `ticket_date`.

## 4. Interfaces

### A. Master data pull — AutoGrade cloud ← AutoERP

Every 5 minutes, cursor on `modified`:

```
GET /api/resource/Supplier?fields=["name","supplier_name","supplier_group","disabled","modified"]
    &filters=[["modified",">","<cursor>"]]&limit_page_length=500
GET /api/resource/Truck?fields=["name","plate_number","plate_normalized","supplier","vehicle_class",
    "modified"]&filters=[["modified",">","<cursor>"]]
```

AutoGrade upserts into PG (`suppliers`, `trucks`) keyed by `erp_name` / normalised plate and marks the rows
`sync_status='pending'`, so the existing edge sync (`edgeSync.service.impl.ts`, 30 s) carries them to the
mill. Disabled in ERP → `status='inactive'` in AutoGrade. The cursor lives in `sync_state` (new column
`erp_pull_cursor`). A native AutoERP **Webhook** (Supplier/Truck `on_update` → AutoGrade
`POST /internal/erp/master-data`) can be added later for lower latency; the pull is the baseline.

### B. Pending trucks up — AutoGrade cloud → AutoERP

On arrival of a truck with no `erp_name`:

```
POST /api/method/erpnext.palm_mill.api.upsert_truck
{ "plate_number": "B 5455 DK", "autograde_id": "<uuid>", "supplier_erp_name": null,
  "capacity": 8.0, "site": "<erp_company>" }
```

AutoERP matches by `plate_normalized`; if absent it creates a `Truck` with no owner and returns `{"name": "B 5455 DK", "supplier": null}`. AutoGrade stores `erp_name`.
The backoffice completes the truck in AutoERP (supplier, class) and the next pull propagates it. This also
covers vision's `UNKNOWN-xxxx` stubs: they stay without an owner until someone types the real plate in AutoERP,
at which point AutoGrade merges through its existing `truck_aliases` mechanism.

### C. The visit — AutoGrade cloud → AutoERP (at each stage, and resent daily)

One message per truck visit, sent when the gate weighing arrives, when the line assignment closes, and when
the truck weighs out; a daily job resends yesterday's visits as a safety net. Every send is a full replacement
of the sections it carries; `stage` is informational. `weighing.time_in` is required (it dates the ticket);
`tare_kg` / `time_out` come at departure, `grading` when the assignment closes. Because the rejected bunches are
back on the truck for the second weighing, net = gross − tare is what stayed at the mill.

```
POST /api/method/erpnext.palm_mill.api.upsert_visit
{ "visit_id": "<uuid>", "site": "<erp company>", "stage": "gate | grading | departed",
  "truck": {"plate_number": "B 7154 QY", "autograde_id": "<uuid>"}, "supplier_erp_name": "KUD Sumber Makmur",
  "scale_ticket_no": "SCL-2026-000201",
  "weighing": {"gross_kg": 14560, "time_in": "2026-09-10T07:41:00+07:00",
               "tare_kg": 5400, "time_out": "2026-09-10T08:35:00+07:00", "driver_name": "Yusuf Maulana"},
  "grading":  {"assignment_id": "<uuid>", "line_code": "L1",
               "started_at": "2026-09-10T07:58:00+07:00", "ended_at": "2026-09-10T08:23:00+07:00",
               "counts": {"total": 412, "acc": 371, "rej": 41, "mentah": 41, "tangkai_panjang": 23, "manual_reject": 3},
               "pct": {"mentah": 9.95, "tangkai_panjang": 5.58},
               "detail_url": "https://app.smagri.id/dashboard/gradings?assignment=<uuid>"},
  "emitted_at": "2026-09-10T08:35:30+07:00" }
```

Criteria mapping (from `getGradingAverage`): `mentah` = REJ (returned to the truck); `tangkai_panjang` = ACC with
`tp_confidence > 0.8`; `matang` = the rest. Sampah and brondolan are not measured by AutoGrade and are not sent.

AutoERP handler:

1. Resolve the Truck by `plate_normalized` (create as in B). Supplier = the ticket's, else the truck's,
   else the payload's.
2. Find the ticket: by `autograde_visit_id`, else `scale_ticket_no`, else `autograde_assignment_id`, else the
   truck's open ticket whose window (± `match_window_hours`) overlaps the weighing, else a new draft.
3. Apply the weighing section (gross, tare, times, driver) and, when present, the grading section: replace the
   Mentah / Tangkai Panjang / Matang rows, keep operator-typed rows (Sampah, Lewat Matang), set the counts,
   the AutoGrade link and `grading_received_at`.
4. `try_finalize` (E). On a finalised ticket nothing is rewritten: identical numbers are acknowledged
   ("visit unchanged"); changed grading sets `grading_revised` and leaves a Comment; changed weights leave a
   Comment.

Manual fallback: the weighbridge operator types the scale slip into the ticket form; the visit adopts that
ticket through `scale_ticket_no`. The scale program itself is an AutoGrade edge concern (§7.2).

### E. Finalisation — inside AutoERP (the automation that does not exist today)

`try_finalize(ticket)` runs after C, after D, and on a 15-minute scheduler:

- Ready when `net_weight_kg > 0` **and** (grading present **or** `time_out + GRADING_TIMEOUT`, default 6 h,
  has passed → finalise with `grading_missing=1` and the default deduction).
- Compute `sampah_kg`, `potongan_pct`, `net_after_deduction_kg` from a new single DocType
  **TBS Grading Rule** (per-criterion deduction % and cap; today these live only in the demo generator's
  `_potongan`). Price from Item Price / the supplier's price list for item TBS on `ticket_date`.
- Submit the ticket. `on_submit`: External → Purchase Receipt (qty = net after deduction,
  rate = harga, `custom_weighbridge_ticket`, dimensions from the ticket, posting time = `time_in`);
  Internal → Stock Entry Material Receipt against the blok. This is exactly what `pks_04_seed.py::_purchase_receipt`
  does from outside; it moves inside the ERP.
- Purchase Invoice and Payment Entry stay on the standard ERPNext flow (create from receipts per supplier per
  period). Automate later once volumes justify it.

Where the logic lives: the **Palm Mill** module of the fork (`erpnext/palm_mill`): all sawit DocTypes are
code DocTypes there (promoted 2026-09-10, tables and data kept), with `weighbridge_ticket.py` holding
`try_finalize`, `create_stock_documents`, the 15-minute `finalize_due_tickets` scheduler and the cancel hook,
and `api.py` holding the three endpoints. The stock documents are created with the caller's permissions:
whoever finalises a ticket (integration user, scheduler as Administrator, or an operator using the
"Penerimaan Stok" button) needs Purchase User + Stock User.

## 5. Reliability

- **Outbox in AutoGrade cloud.** Table `erp_outbox(id, kind, key, payload jsonb, status, attempts, last_error,
next_attempt_at)` and a 30-second single-flight worker with exponential backoff, same shape as `edgeSync`.
  B and C write to the outbox; the worker POSTs. `error` rows are visible on the backoffice UI.
- **Auth.** One AutoERP API key/secret for the `autograde-integration` user holding the roles Palm Mill
  Integration (Truck + Weighbridge Ticket), Purchase User and Stock User (finalisation creates receipts, batches
  and stock entries under ERPNext's own permission checks). Env in AutoGrade: `ERP_BASE_URL`, `ERP_API_KEY`,
  `ERP_API_SECRET` (`erpnext.palm_mill.setup.create_integration_user`). No other system holds ERP credentials.
- **Daily resend.** AutoGrade resends all of yesterday's visits once a day; idempotent upserts make this free
  and it closes any gap the outbox left.
- **Idempotency.** `assignment_id`, `scale_ticket_no`, `plate_normalized` are unique on the ERP side; handlers
  are upserts; the outbox can be replayed at will.
- **Observability.** ERP `Error Log` plus a `Weighbridge Ticket` list filter for "waiting for weight /
  waiting for grading / grading missing"; AutoGrade outbox counts on `/dashboard`.
- **Clock skew.** Matching windows are ±2 h; both sides send offsets; AutoERP never uses `emitted_at` for
  business dates, only `started_at` / `time_in`.

## 6. Phasing (each phase delivers value on its own)

1. **Master data** (A + B). One supplier/truck list; AutoGrade backoffice screens become read-mostly.
2. **Ticket finalisation + weights** (D + E). Receipts and stock are created by AutoERP with no AutoGrade
   involvement at all. This is where most of the "everything becomes crystal clear" actually comes from.
3. **Grading summary** (C). AI results start driving deductions and supplier scorecards.
4. Later: automatic Purchase Invoice per supplier per period, supplier rating fed back to AutoGrade
   (`suppliers.rating`), notifications for trucks still without an owner.

Ticket-level breakdown per phase: §9.

## 7. Schema additions

### 7.1 AutoERP — shipped in `erpnext/palm_mill` (2026-09-10)

**Supplier** — no new fields. The ERP name is the id AutoGrade stores. Supplier group already carries the
source typing the ticket needs (any supplier → External, none → Internal; plasma vs agent is the Supplier Group).

**Truck** (exists on `pks.localhost`; plate as typed is the record name, e.g. `B 5455 DK`)

| Field              | Type                                             | Rules                                                                                                                                                                                                                                                                            |
| ------------------ | ------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `plate_normalized` | Data, read-only, unique                          | Set in `validate`: `re.sub(r"[^A-Za-z0-9]", "", plate_number).upper()`. Same rule as AutoGrade `plateNormalizer.ts`. Unique index so two spellings of one plate cannot coexist. Backfill once for the 58 existing trucks.                                                        |
| `autograde_id`     | Data, read-only, unique when set                 | UUID of the AutoGrade `trucks.id` that first reported this plate. Set by interface B; blank for trucks created in ERP until the next pull round-trips it.                                                                                                                        |
| `source`           | Select `Manual` / `AutoGrade`, read-only         | Audit only: where the record came from.                                                                                                                                                                                                                                          |

Interface A exposes `plate_normalized`, `supplier`, `vehicle_class`, `modified`. A truck the backoffice
still has to complete is simply one whose `supplier` is empty — the Truck list filter for that is the to-do.

**Weighbridge Ticket** (custom DocType on `pks.localhost`)

| Field                                         | Type                                                                           | Rules                                                                        |
| --------------------------------------------- | ------------------------------------------------------------------------------ | ---------------------------------------------------------------------------- |
| `autograde_visit_id`                          | Data, unique when set                                                          | Primary key for interface C (AutoGrade's visit id).                          |
| `autograde_assignment_id`                     | Data, unique when set                                                          | Secondary key: the line assignment.                                          |
| `autograde_url`                               | Data                                                                           | Deep link to the AutoGrade session; shown as a button on the form.           |
| `grading_total`, `grading_acc`, `grading_rej` | Int                                                                            | Raw counts from C; `persen` rows in `grading` are derived from them.         |
| `grading_received_at`                         | Datetime                                                                       | Last time C wrote to this ticket.                                            |
| `grading_missing`                             | Check                                                                          | Set by E when finalised on timeout without grading.                          |
| `grading_revised`                             | Check                                                                          | Set when C arrives after submit; ticket needs review.                        |
| `scale_ticket_no`                             | Data, unique when set                                                          | Secondary key: the scale's slip number; lets a hand-typed ticket be adopted. |
| `weight_received_at`                          | Datetime                                                                       | Last time D wrote to this ticket.                                            |
| `status`                                      | Select `Waiting Weight` / `Waiting Grading` / `Ready` / `Finalised`, read-only | Maintained by `try_finalize`; drives the list filters in §5.                 |

**TBS Grading Rule** (new single DocType)

| Field                   | Type                                                | Rules                                                                                                            |
| ----------------------- | --------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| `rules`                 | Table of (`kriteria` Data, `deduction_pct` Percent) | One row per criterion: Mentah, Tangkai Panjang, Sampah. Deduction is applied to the criterion's share of net kg. |
| `max_potongan_pct`      | Percent                                             | Cap on total deduction (today `MAX_POTONGAN_PCT` in the demo generator).                                         |
| `default_potongan_pct`  | Percent                                             | Applied when grading is missing at timeout.                                                                      |
| `grading_timeout_hours` | Int, default 6                                      | See E.                                                                                                           |
| `tbs_item`              | Link Item                                           | The item receipts are created for.                                                                               |

Where these live: DocType JSON in `erpnext/palm_mill/doctype/*` (Frappe-exported), applied to any site by
`bench migrate`; the patch `erpnext.patches.v17_0.setup_palm_mill` backfills existing data. The demo
generator no longer creates schema; `pks_02_schema.py` only checks it is present.

### 7.2 AutoGrade (their backlog)

| Table                   | Column                                                                                                                                                                           | Rules                                                                                                                                   |
| ----------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| `sites`                 | `erp_company` Text, `erp_warehouse` Text                                                                                                                                         | Set once per site in the cloud backoffice. Required before any push.                                                                    |
| `suppliers`             | `erp_name` Text, nullable, unique                                                                                                                                                | Filled by the pull (A). Row is read-only in the UI once set.                                                                            |
| `trucks`                | `erp_name` Text, nullable, unique                                                                                                                                                | Filled by A or by the response to B. Row is read-only in the UI once set.                                                               |
| `sync_state`            | `erp_pull_cursor` Timestamp                                                                                                                                                      | Last `modified` seen from AutoERP.                                                                                                      |
| `weighings` (new, edge) | `id`, `visit_id`, `scale_ticket_no`, `plate_number`, `gross_kg`, `tare_kg`, `time_in`, `time_out`, `driver_name`, `sync_status`                                                  | Written by the scale intake at the mill (`POST /internal/weighbridge/weighings` from the scale adapter); synced to cloud by `edgeSync`. |
| `visits` (new)          | `id`, `site_id`, `truck_id`, `weighing_id`, `assignment_id`, `stage`, `erp_ticket`                                                                                               | Created at the gate weighing; the line assignment links to it.                                                                          |
| `erp_outbox` (new)      | `id`, `kind` (`truck` / `grading_session`), `key` Text, `payload` JSONB, `status` (`pending` / `sent` / `error`), `attempts` Int, `last_error` Text, `next_attempt_at` Timestamp | Unique on (`kind`, `key`); a re-emit overwrites the payload and resets status to `pending`.                                             |

Jobs: ERP pull every 5 min (A); outbox drain every 30 s single-flight (B, C); visit stage change → send (C);
late-event re-emit for closed assignments within 24 h (C); daily resend of yesterday's visits (C). At the
edge: the scale intake endpoint and the `weighings` / `visits` tables; vision is unchanged.

## 8. Open decisions (business input)

- Deduction table values per criterion and the cap (today `MAX_POTONGAN_PCT` in the demo generator).
- Grading timeout and the default deduction when a line was down.
- Whether Internal visits get tickets from the scale at all (they must, for stock) and whether they need grading.
- The scale program's integration capability: API, file export, or manual.
- The Mentah deduction weight once rejects are physically returned (recommended 0; see "The visit, end to end").
- Whether a whole load can be refused (truck leaves with everything, no ticket finalised) and who decides.

## 9. Backlog

Tickets are grouped by phase because the order is real: each phase ships and pays for itself alone.
ID prefixes: `ERP` = AutoERP, `AG` = palmgrade-api, `FE` = palmgrade-frontend, `SC` = scale adapter,
`OPS` = people and environments. Size is S / M / L. Every ticket that writes to AutoERP names its natural key;
a ticket without one is not ready. Nothing in phases 0–3 touches the mill edge or vision.

| Phase                    | Tickets                                       | What becomes true when it ships                                                               |
| ------------------------ | --------------------------------------------- | --------------------------------------------------------------------------------------------- |
| 0 Prerequisites          | OPS-1, ERP-1, ERP-2, ERP-3, AG-1, OPS-2       | Both systems have the fields and credentials; existing suppliers and trucks are matched once. |
| 1 Master data            | AG-2, AG-3, AG-4, AG-5, ERP-4, FE-1, OPS-3    | One supplier and truck list, owned in AutoERP, visible at the mill within minutes.            |
| 2 Weights + finalisation | ERP-5, ERP-6, ERP-7, ERP-8, ERP-9, SC-1, SC-2 | Every weighed load becomes a submitted ticket and a receipt or stock entry without AutoGrade. |
| 3 Grading summary        | AG-6, AG-7, ERP-10, ERP-11, FE-2              | AI grading drives deductions and price on the ticket.                                         |
| 4 Later                  | ERP-12 and the items in §6                    | Invoicing cadence, rating feedback, production-grade module.                                  |

Critical path: OPS-1 → ERP-1/2/3 → OPS-2 → AG-1…5 + ERP-4 → ERP-5…8 (+ SC-1/2) → AG-6/7 + ERP-10.

### Phase 0 — prerequisites

**OPS-1 · AutoERP · Integration users and role** · S · **done 2026-09-10**

- **Do:** Role `Integration Writer`: read Supplier and Truck; create/write Truck and Weighbridge Ticket; no
  delete, no submit of anything else. Users `autograde-integration` and `scale-integration` with API key +
  secret. Keys go into the AutoGrade cloud env as `ERP_BASE_URL`, `ERP_API_KEY`, `ERP_API_SECRET`, and into the
  scale adapter's config.
- **Done when:** `GET /api/resource/Truck` with the key returns 200 and `DELETE /api/resource/Truck/<name>`
  returns 403.
- **Needs:** nothing.

**ERP-1 · AutoERP · Truck integration fields** · S · **done 2026-09-10**

- **Do:** Add `plate_normalized` (Data, read-only, unique), `autograde_id` (Data, read-only), `source` (Select Manual/AutoGrade). On
  validate: `plate_normalized = re.sub(r"[^A-Za-z0-9]", "", plate_number).upper()`; 
  `supplier` and `vehicle_class` are both set. Backfill the 58 existing trucks. Demo site: extend the `TRUCK`
  spec in `pks_02_schema.py`; the existing `ensure_doctype` field sync applies it.
- **Done when:** saving "B1234XY" while "B 1234 XY" exists is rejected; the Truck list filters on empty `supplier`.
- **Needs:** nothing.

**ERP-2 · AutoERP · Weighbridge Ticket integration fields** · S · **done 2026-09-10**

- **Do:** Add the §7.1 fields: `autograde_assignment_id`, `autograde_url`, `grading_total/acc/rej`,
  `grading_received_at`, `grading_missing`, `grading_revised`, `scale_ticket_no`, `weight_received_at`,
  `status` (Waiting Weight / Waiting Grading / Ready / Finalised, read-only). Unique-when-set on the two keys.
- **Done when:** two draft tickets cannot share an `autograde_assignment_id` or a `scale_ticket_no`; existing
  3,848 tickets get `status = Finalised`.
- **Needs:** nothing.

**ERP-3 · AutoERP · TBS Grading Rule** · S · **done 2026-09-10**

- **Do:** Single DocType per §7.1: `rules` table (kriteria, deduction_pct), `max_potongan_pct`,
  `default_potongan_pct`, `grading_timeout_hours` (6), `tbs_item`. Seed with the demo generator's current
  `_potongan` percentages and `MAX_POTONGAN_PCT` so phase 2 reproduces today's numbers.
- **Done when:** the deduction for a known demo ticket recomputed from the rule equals its stored `potongan_pct`.
- **Needs:** nothing. Business values in §8 can replace the seed later.

**AG-1 · palmgrade-api · Schema for ERP linkage** · S

- **Do:** Migration `init-db/037_erp_link.sql`: `sites.erp_company`, `sites.erp_warehouse`,
  `suppliers.erp_name` (unique, nullable), `trucks.erp_name` (unique, nullable), `sync_state.erp_pull_cursor`,
  table `erp_outbox` (`id`, `kind`, `key`, `payload jsonb`, `status`, `attempts`, `last_error`,
  `next_attempt_at`, unique on `(kind, key)`). Update `src/entities/` row types.
- **Done when:** migrator applies it on a fresh DB and on the existing cloud DB; `pnpm test` green.
- **Needs:** nothing.

**OPS-2 · both · One-time reconciliation** · M

- **Do:** Script in palmgrade-api `scripts/reconcile-erp.ts`: export active suppliers and trucks; match
  suppliers to AutoERP by exact name, trucks by normalised plate; create the missing ones in AutoERP
  (`source=Manual`); write `erp_name` back. Print unmatched suppliers for a human to resolve.
  Run once per environment (staging, then production).
- **Done when:** every active AutoGrade truck and supplier has `erp_name`, or is on the printed exception
  list with a reason.
- **Needs:** OPS-1, ERP-1, AG-1.

### Phase 1 — master data (interfaces A and B)

**AG-2 · palmgrade-api · ERP client** · S

- **Do:** `src/services/erp/erp.client.ts`: `Authorization: token key:secret`, `listModifiedSince(doctype,
cursor, fields)` paging by `limit_start`, `callMethod(name, body)`. Retry with backoff on 5xx and timeouts,
  never on 4xx. Structured errors carrying Frappe's `exc_type`.
- **Done when:** unit tests cover paging, a 502 retry, and a 403 non-retry.
- **Needs:** OPS-1.

**AG-3 · palmgrade-api · Master data pull (A)** · M

- **Do:** `erpPull.service.ts`, `setInterval` 5 min, single-flight, cloud role only. Page Supplier then Truck
  by `modified > erp_pull_cursor`; upsert suppliers by `erp_name`, trucks by normalised plate (fill `erp_name`,
  `supplier_id`); mark rows `sync_status='pending'` so `edgeSync` carries them
  to the mill; advance the cursor only after a page fully succeeds.
- **Done when:** a Truck's owner changed in AutoERP shows on the mill copy within 6 minutes; restarting the
  job mid-page does not skip records.
- **Needs:** AG-1, AG-2, OPS-2.

**AG-4 · palmgrade-api · Outbox worker** · M

- **Do:** `erpOutbox.worker.ts`, `setInterval` 30 s, single-flight, cloud role only. Drain rows with
  `status='pending'` or `status='error'` and `next_attempt_at <= now()`, oldest first, batch 50. Backoff
  30 s → 1 h. Record `attempts`, `last_error`. Structure mirrors `edgeSync.service.impl.ts`.
- **Done when:** with AutoERP down, rows accumulate as `error` with growing `next_attempt_at`; when it returns,
  they drain with no duplicates on the ERP side.
- **Needs:** AG-1, AG-2.

**AG-5 · palmgrade-api · Pending trucks up (B)** · S

- **Do:** In the cloud truck write paths (`truck.service.impl.ts`, `syncInternal` push handler,
  `TruckResolver.resolveOrStub`), when a truck has `erp_name IS NULL`, upsert an outbox row `kind='truck'`,
  `key=<normalised plate>`, payload per §4B. On success store the returned `erp_name`.
- **Done when:** a plate typed at the mill appears in AutoERP without an owner within about a minute of reaching
  the cloud, and a second visit of the same plate creates no second row.
- **Needs:** AG-4, ERP-4.

**ERP-4 · AutoERP · `upsert_truck` (B)** · S · **done 2026-09-10**

- **Do:** Whitelisted method `autoerp.integrations.autograde.upsert_truck`. Key: `plate_normalized`. If found,
  set `autograde_id` when empty and return it; else create with `source=AutoGrade`. Return
  `{name, supplier}`. Role-checked, idempotent, 4xx on malformed plate.
- **Done when:** calling twice with the same payload yields one Truck; calling with two spellings of one plate
  yields one Truck.
- **Needs:** ERP-1, OPS-1.

**FE-1 · palmgrade-frontend · Read-only once ERP-linked** · S

- **Do:** In `truck-list.tsx`, `truck.tsx`, `supplier-form.tsx`: when `erp_name` is set, disable edit and
  delete with the hint "Ubah di AutoERP" and a link to the ERP record; keep create enabled. Add an "ERP" column:
  linked / in ERP without owner / not linked. `GET /trucks` and `GET /suppliers` must return `erp_name` (AG-1).
- **Done when:** a linked truck cannot be edited from either the cloud or the mill UI; an unlinked one can.
- **Needs:** AG-1, AG-3.

**OPS-3 · docs · Runbook** · S

- **Do:** How to complete an owner-less truck in AutoERP; how to read and requeue an `error` outbox row; what to do
  when OPS-2 left an exception.
- **Done when:** a backoffice user completes an owner-less truck end to end from the runbook alone.
- **Needs:** AG-5, FE-1.

### Phase 2 — weights and finalisation (interfaces D and E), no AutoGrade work

**ERP-5 · AutoERP · `upsert_weighing` (D)** · M · **replaced 2026-09-10 by `upsert_visit` (one message from AutoGrade)**

- **Do:** Whitelisted method `autoerp.integrations.weighbridge.upsert_weighing`. Match order: `scale_ticket_no`;
  then same company + truck (by normalised plate, creating a Truck if needed) + draft + `ticket_date` =
  local date of `time_in` + window overlap ±2 h; else create a draft ticket with `sumber_tbs` from the
  supplier group. Set gross/tare/net, times, driver, `weight_received_at`; call `try_finalize`.
- **Done when:** replaying the same weighing changes nothing; a weighing for a plate never seen creates an owner-less
  Truck and a draft ticket in one call.
- **Needs:** ERP-1, ERP-2, OPS-1.

**ERP-6 · AutoERP · `try_finalize` and scheduler** · M · **done 2026-09-10**

- **Do:** Readiness: `net_weight_kg > 0` and (grading rows present, or `time_out + grading_timeout_hours` has
  passed → `grading_missing=1`, `default_potongan_pct`). Compute sampah, potongan (capped), net after deduction,
  price from Item Price / supplier price list on `ticket_date`, nilai. Maintain `status`. Submit. Scheduler
  every 15 min sweeps drafts for timeouts.
- **Done when:** the three cases in ERP-9 pass; a draft with weight but no grading finalises exactly once after
  the timeout.
- **Needs:** ERP-2, ERP-3.

**ERP-7 · AutoERP · Ticket submit creates the stock document** · M · **done 2026-09-10**

- **Do:** `on_submit`: External → Purchase Receipt (item `tbs_item`, qty = net after deduction,
  rate = harga, `custom_weighbridge_ticket`, dimensions, `set_posting_time`, posting datetime = `time_in`,
  warehouse = company default for TBS); Internal → Stock Entry Material Receipt against the blok. Payloads mirror
  `pks_04_seed.py::_purchase_receipt` and its stock entry. `on_cancel` cancels the linked document.
- **Done when:** submitting a ticket produces exactly one linked document; cancelling the ticket cancels it;
  stock ledger and GL agree with the demo's figures for a replayed day.
- **Needs:** ERP-6.

**ERP-8 · AutoERP · Manual entry parity and list filters** · S · **done 2026-09-10** (status indicators; the ticket list's standard filter on `status` covers the saved filters)

- **Do:** The ticket form is usable by a human weighbridge operator: truck picker fills plate/class/driver
  (exists), weights entered by hand, the same `try_finalize` runs on save. List view gets saved filters for the
  four `status` values and a filter on Truck for empty `supplier`.
- **Done when:** an operator can take a load from arrival to submitted receipt without the scale adapter.
- **Needs:** ERP-6, ERP-7.

**SC-1 · scale → AutoGrade · Adapter discovery** · S

- **Do:** Find out what the scale program exposes: HTTP API, a database, a CSV/print export, or nothing. Capture
  a sample of one day's records with field names. Choose the adapter shape (poll DB, tail export folder, or
  manual entry only).
- **Done when:** a one-page note names the source, the fields that map to §4D, and the chosen shape.
- **Needs:** nothing.

**SC-2 · AutoGrade edge · Weighbridge intake** · M

- **Do:** In palmgrade-api at the edge: `POST /internal/weighbridge/weighings` (shared secret like vision's),
  `weighings` + `visits` tables, a visit opened by the gate weighing and linked to the line assignment; a small
  poller on the mill PC reads the source chosen in SC-1 and posts each weighing there. Rows sync to the cloud by
  the existing `edgeSync`; the cloud outbox sends `upsert_visit` on every stage change.
- **Done when:** after a 2-hour internet outage every weighing reaches the cloud and AutoERP once, in order,
  with no operator action.
- **Needs:** SC-1, AG-1, AG-4, ERP-10.

**ERP-9 · AutoERP · Finalisation tests** · S · **written 2026-09-10, not yet run (needs a test site)**

- **Do:** Unit tests for match-or-create (by key, by window, create), readiness, and deduction math in three
  cases: full grading, grading missing at timeout, grading revised after submit (no rewrite, flag + comment).
- **Done when:** tests run in CI against a test site with a seeded TBS Grading Rule.
- **Needs:** ERP-5, ERP-6, ERP-7.

### Phase 3 — grading summary (interface C)

**AG-6 · palmgrade-api · Session summary builder** · M

- **Do:** `gradingSummary.service.ts`: for one `line_assignments.id`, aggregate `ai_inspections` into
  `counts` (`total, acc, rej, mentah, tangkai_panjang, manual_reject`) and `pct` using the `getGradingAverage`
  rules (mentah = REJ; tangkai panjang = ACC with `tp_confidence > 0.8`); resolve `site → erp_company`,
  truck `erp_name`, supplier `erp_name`; build the §4C payload with `detail_url`.
- **Done when:** for a known assignment the summary's counts equal the console's ACC/REJ totals.
- **Needs:** AG-1, OPS-2.

**AG-7 · palmgrade-api · Emit on close and on late events** · M

- **Do:** In the cloud `syncInternal` push handler, when an assignment transitions to `closed`, upsert outbox
  row `kind='grading_session'`, `key=assignment_id`. In `visionIngest`, when an inspection belongs to an
  assignment already closed no more than 24 h ago, re-upsert the row (payload rebuilt, status back to
  `pending`). Debounce 60 s so one hourly batch produces one send.
- **Done when:** closing an assignment sends one summary; a late batch sends exactly one more with higher totals.
- **Needs:** AG-4, AG-6, ERP-10.

**ERP-10 · AutoERP · `upsert_visit` (C)** · M · **done 2026-09-10** (replaces the grading and weighing endpoints)

- **Do:** Whitelisted method `autoerp.integrations.autograde.upsert_grading_session`, steps 1–4 of §4C. Key:
  `autograde_assignment_id`. Writes the `grading` rows (Mentah / Tangkai Panjang / Matang) and the count fields,
  then `try_finalize`. If the ticket is already submitted: no rewrite, set `grading_revised=1`, add a Comment
  with old and new percentages.
- **Done when:** a summary for a weighed draft finalises it; a summary for a plate without a weighing creates a
  draft in Waiting Weight; a revised summary after submit leaves amounts unchanged and flags the ticket.
- **Needs:** ERP-2, ERP-6, OPS-1.

**ERP-11 · AutoERP · Grading provenance on the ticket form** · S · **done 2026-09-10** (fields + AutoGrade button; the weekly chart is not built)

- **Do:** Show `grading_total/acc/rej`, `grading_received_at`, a button to `autograde_url`, and indicators for
  `grading_missing` and `grading_revised`. Dashboard chart "tickets finalised without grading" per week.
- **Done when:** a backoffice user can tell from the form whether the deduction came from AI, default, or
  was revised.
- **Needs:** ERP-10.

**FE-2 · palmgrade-frontend · Assignment deep link** · S

- **Do:** `/dashboard/gradings?assignment=<uuid>` opens the history card filtered to that assignment and scrolls
  to it. This is the target of `detail_url`.
- **Done when:** the link from an AutoERP ticket lands on the right captures.
- **Needs:** nothing.

### Phase 4 — later

**ERP-12 · AutoERP · Promote sawit DocTypes into the fork** · L · **done 2026-09-10**

- **Do:** Move Truck, Weighbridge Ticket, Weighbridge Grading, Blok, Kebun, Divisi, Sumber TBS, Sertifikasi,
  TBS Grading Rule and the three whitelisted methods into the `AutoERP Integrations` module as
  DocType JSON plus controllers, with the ERP-9 tests. Fixes the current `bench migrate` failure. Migrate the
  demo site from DB-only to code DocTypes (`custom=0`).
- **Done when:** a fresh site with the app installed has every DocType without the database dump, and
  `bench migrate` is clean. Should land before production go-live of phase 2.
- **Needs:** ERP-5…ERP-11.

Also in phase 4, not broken down: automatic Purchase Invoice per supplier per period; supplier rating pushed
back to AutoGrade `suppliers.rating`; notifications for trucks left without an owner for more than a day.
