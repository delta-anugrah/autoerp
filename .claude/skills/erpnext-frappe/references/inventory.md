# Inventori ERPNext — DocType & Laporan

Diekstrak langsung dari `frappe/erpnext` @ `84a32c40f4f` (branch `develop`,
2026-08-25). Hitungan: **534 DocType** (282 master + 252 child) di **21 modul**,
plus **184 laporan**.

Kegunaan berkas ini: memastikan sesuatu **sudah ada atau belum** sebelum kita
bikin DocType baru di app sendiri. Tidak semua modul dipakai untuk PKS — lihat
"Yang relevan untuk PKS" di bagian akhir.

**Arti tanda:**

| Tanda | Arti |
|---|---|
| `[S]` | Single — satu baris global, biasanya halaman Settings |
| `[✓sub]` | Submittable — punya `docstatus` 0/1/2, tidak bisa diedit setelah submit |
| `[tree]` | Nested set — punya induk/anak (Warehouse, Cost Center, Item Group, dst) |
| (polos) | Master biasa |

Child table (252 buah, `istable: 1`) **tidak** didaftar satu-satu — jumlahnya
disebut per modul. Child tidak punya halaman sendiri; cari lewat parent-nya.

---

# Bagian 1 — DocType master per modul


## Accounts — 92 master (+99 child)
- Account [tree]
- Account Category
- Account Closing Balance [✓sub]
- Accounting Dimension
- Accounting Dimension Filter
- Accounting Period
- Accounts Settings [S]
- Advance Payment Ledger Entry [✓sub]
- Bank
- Bank Account
- Bank Account Balance
- Bank Account Subtype
- Bank Account Type
- Bank Clearance [S]
- Bank Guarantee [✓sub]
- Bank Reconciliation Tool [S]
- Bank Statement Import
- Bank Statement Import Log
- Bank Transaction [✓sub]
- Bank Transaction Rule
- Bisect Accounting Statements [S]
- Bisect Nodes
- Budget [✓sub]
- Cashier Closing [✓sub]
- Chart of Accounts Importer [S]
- Cheque Print Template
- Cost Center [tree]
- Cost Center Allocation [✓sub]
- Coupon Code
- Currency Exchange Settings [S]
- Dunning [✓sub]
- Dunning Type
- Exchange Rate Revaluation [✓sub]
- Finance Book
- Financial Report Template
- Fiscal Year
- GL Entry [✓sub]
- Invoice Discounting [✓sub]
- Item Tax Template
- Journal Entry [✓sub]
- Journal Entry Template
- Ledger Health
- Ledger Health Monitor [S]
- Ledger Merge
- Loyalty Point Entry
- Loyalty Program
- Mode of Payment
- Monthly Distribution
- Opening Invoice Creation Tool [S]
- POS Closing Entry [✓sub]
- POS Invoice [✓sub]
- POS Invoice Merge Log [✓sub]
- POS Opening Entry [✓sub]
- POS Profile
- POS Settings [S]
- Party Link
- Payment Entry [✓sub]
- Payment Gateway Account
- Payment Ledger Entry [✓sub]
- Payment Order [✓sub]
- Payment Reconciliation [S]
- Payment Request [✓sub]
- Payment Term
- Payment Terms Template
- Pegged Currencies [S]
- Period Closing Voucher [✓sub]
- Pricing Rule
- Process Deferred Accounting [✓sub]
- Process Payment Reconciliation [✓sub]
- Process Payment Reconciliation Log
- Process Period Closing Voucher [✓sub]
- Process Statement Of Accounts
- Process Subscription [✓sub]
- Promotional Scheme
- Purchase Invoice [✓sub]
- Purchase Taxes and Charges Template
- Repost Accounting Ledger [✓sub]
- Repost Payment Ledger [✓sub]
- Sales Invoice [✓sub]
- Sales Taxes and Charges Template
- Share Transfer [✓sub]
- Share Type
- Shareholder
- Shipping Rule
- Subscription
- Subscription Plan
- Subscription Settings [S]
- Tax Category
- Tax Rule
- Tax Withholding Category
- Tax Withholding Group
- Unreconcile Payment [✓sub]

## Assets — 14 master (+12 child)
- Asset [✓sub]
- Asset Activity
- Asset Capitalization [✓sub]
- Asset Category
- Asset Depreciation Schedule [✓sub]
- Asset Maintenance
- Asset Maintenance Log [✓sub]
- Asset Maintenance Team
- Asset Movement [✓sub]
- Asset Repair [✓sub]
- Asset Shift Allocation [✓sub]
- Asset Shift Factor
- Asset Value Adjustment [✓sub]
- Location [tree]

## Bulk Transaction — 2 master (+0 child)
- Bulk Transaction Log
- Bulk Transaction Log Detail

## Buying — 10 master (+9 child)
- Buying Settings [S]
- Purchase Order [✓sub]
- Request for Quotation [✓sub]
- Supplier
- Supplier Quotation [✓sub]
- Supplier Scorecard
- Supplier Scorecard Criteria
- Supplier Scorecard Period [✓sub]
- Supplier Scorecard Standing
- Supplier Scorecard Variable

## CRM — 15 master (+13 child)
- Appointment
- Appointment Booking Settings [S]
- CRM Settings [S]
- Campaign
- Competitor
- Contract [✓sub]
- Contract Template
- Email Campaign
- Lead
- Market Segment
- Opportunity
- Opportunity Lost Reason
- Opportunity Type
- Prospect
- Sales Stage

## Communication — 1 master (+1 child)
- Communication Medium

## EDI — 2 master (+0 child)
- Code List
- Common Code

## ERPNext Integrations — 1 master (+0 child)
- Plaid Settings [S]

## Maintenance — 2 master (+3 child)
- Maintenance Schedule [✓sub]
- Maintenance Visit [✓sub]

## Manufacturing — 19 master (+30 child)
- BOM [✓sub]
- BOM Creator [✓sub]
- BOM Update Log [✓sub]
- BOM Update Tool [S]
- Blanket Order [✓sub]
- Downtime Entry
- Job Card [✓sub]
- Manufacturing Settings [S]
- Master Production Schedule
- Operation
- Plant Floor
- Production Plan [✓sub]
- Production Plan Schedule
- Routing
- Sales Forecast [✓sub]
- Work Order [✓sub]
- Workstation
- Workstation Operating Component
- Workstation Type

## Projects — 10 master (+5 child)
- Activity Cost
- Activity Type
- Project
- Project Template
- Project Type
- Project Update [✓sub]
- Projects Settings [S]
- Task [tree]
- Task Type
- Timesheet [✓sub]

## Quality Management — 8 master (+8 child)
- Non Conformance
- Quality Action
- Quality Feedback
- Quality Feedback Template
- Quality Goal
- Quality Meeting
- Quality Procedure [tree]
- Quality Review

## Regional — 4 master (+1 child)
- Import Supplier Invoice
- Lower Deduction Certificate
- South Africa VAT Settings
- UAE VAT Settings

## Selling — 12 master (+8 child)
- Customer
- Delivery Schedule Item
- Industry Type
- Installation Note [✓sub]
- Party Specific Item
- Product Bundle [✓sub]
- Proforma Invoice [✓sub]
- Quotation [✓sub]
- SMS Center [S]
- Sales Order [✓sub]
- Sales Partner Type
- Selling Settings [S]

## Setup — 28 master (+12 child)
- Authorization Control [S]
- Authorization Rule
- Branch
- Brand
- Company [tree]
- Currency Exchange
- Customer Group [tree]
- Department [tree]
- Designation
- Driver
- Email Digest
- Employee [tree]
- Employee Group
- Global Defaults [S]
- Holiday List
- Incoterm
- Item Group [tree]
- Party Type
- Quotation Lost Reason
- Sales Partner
- Sales Person [tree]
- Supplier Group [tree]
- Terms and Conditions
- Territory [tree]
- Transaction Deletion Record [✓sub]
- UOM
- UOM Conversion Factor
- Vehicle

## Stock — 45 master (+33 child)
- Batch
- Bin
- Customs Tariff Number
- Delivery Note [✓sub]
- Delivery Settings [S]
- Delivery Trip [✓sub]
- Inventory Dimension
- Item
- Item Alternative
- Item Attribute
- Item Lead Time
- Item Manufacturer
- Item Price
- Item Standard Cost [✓sub]
- Item Variant Settings [S]
- Landed Cost Voucher [✓sub]
- Manufacturer
- Material Request [✓sub]
- Packing Slip [✓sub]
- Pick List [✓sub]
- Price List
- Purchase Receipt [✓sub]
- Putaway Rule
- Quality Inspection [✓sub]
- Quality Inspection Parameter
- Quality Inspection Parameter Group
- Quality Inspection Template
- Quick Stock Balance [S]
- Repost Item Valuation [✓sub]
- Serial No
- Serial and Batch Bundle [✓sub]
- Shipment [✓sub]
- Shipment Parcel Template
- Stock Closing Balance
- Stock Closing Entry [✓sub]
- Stock Entry [✓sub]
- Stock Entry Type
- Stock Ledger Entry [✓sub]
- Stock Reconciliation [✓sub]
- Stock Reposting Settings [S]
- Stock Reservation Entry [✓sub]
- Stock Settings [S]
- UOM Category
- Warehouse [tree]
- Warehouse Type

## Subcontracting — 4 master (+9 child)
- Subcontracting BOM
- Subcontracting Inward Order [✓sub]
- Subcontracting Order [✓sub]
- Subcontracting Receipt [✓sub]

## Support — 6 master (+5 child)
- Issue
- Issue Priority
- Issue Type
- Service Level Agreement
- Support Settings [S]
- Warranty Claim

## Telephony — 4 master (+1 child)
- Call Log
- Incoming Call Settings
- Telephony Call Type [✓sub]
- Voice Call Settings

## Utilities — 3 master (+1 child)
- Rename Tool [S]
- Video
- Video Settings [S]

---

# Bagian 2 — Laporan bawaan per modul


## Accounts (52)
- Account Balance
- Accounts Payable
- Accounts Payable Summary
- Accounts Receivable
- Accounts Receivable Summary
- Asset Depreciation Ledger
- Asset Depreciations and Balances
- Balance Sheet
- Bank Clearance Summary
- Bank Reconciliation Statement
- Billed Items To Be Received
- Budget Variance Report
- Calculated Discount Mismatch
- Cash Flow
- Cheques and Deposits Incorrectly cleared
- Consolidated Financial Statement
- Consolidated Trial Balance
- Custom Financial Statement
- Customer Ledger Summary
- Deferred Revenue and Expense
- Delivered Items To Be Billed
- Dimension-wise Accounts Balance Report
- Financial Ratios
- General Ledger
- General and Payment Ledger Comparison
- Gross Profit
- Gross and Net Profit Report
- Inactive Sales Items
- Invalid Ledger Entries
- Item-wise Purchase Register
- Item-wise Sales Register
- POS Register
- Payment Ledger
- Payment Period Based On Invoice Date
- Profit and Loss Statement
- Profitability Analysis
- Purchase Invoice Trends
- Purchase Register
- Received Items To Be Billed
- Sales Invoice Trends
- Sales Partners Commission
- Sales Payment Summary
- Sales Register
- Share Balance
- Share Ledger
- Supplier Ledger Summary
- TDS Computation Summary
- Tax Withholding Details
- Trial Balance
- Trial Balance (Simple)
- Trial Balance for Party
- Voucher-wise Balance

## Assets (3)
- Asset Activity
- Asset Maintenance
- Fixed Asset Register

## Buying (10)
- Item-wise Purchase History
- Procurement Tracker
- Purchase Analytics
- Purchase Order Analysis
- Purchase Order Trends
- Requested Items to Order and Receive
- Subcontract Order Summary
- Subcontracted Item To Be Received
- Subcontracted Raw Materials To Be Transferred
- Supplier Quotation Comparison

## CRM (9)
- Campaign Efficiency
- First Response Time for Opportunity
- Lead Conversion Time
- Lead Details
- Lead Owner Efficiency
- Lost Opportunity
- Opportunity Summary by Sales Stage
- Prospects Engaged But Not Converted
- Sales Pipeline Analytics

## Maintenance (1)
- Maintenance Schedules

## Manufacturing (21)
- BOM Explorer
- BOM Operations Time
- BOM Stock Analysis
- BOM Variance Report
- Completed Work Orders
- Cost of Poor Quality Report
- Downtime Analysis
- Exponential Smoothing Forecasting
- Issued Items Against Work Order
- Job Card Summary
- Material Requirements Planning Report
- Open Work Orders
- Process Loss Report
- Production Analytics
- Production Plan Summary
- Production Planning Report
- Quality Inspection Summary
- Work Order Consumed Materials
- Work Order Stock Report
- Work Order Summary
- Work Orders in Progress

## Projects (5)
- Daily Timesheet Summary
- Delayed Tasks Summary
- Project Summary
- Project wise Stock Tracking
- Timesheet Billing Summary

## Quality Management (1)
- Review

## Regional (4)
- Electronic Invoice Register
- IRS 1099
- UAE VAT 201
- VAT Audit Report

## Selling (23)
- Address And Contacts
- Available Stock for Packing Items
- Customer Acquisition and Loyalty
- Customer Credit Balance
- Customer-wise Item Price
- Customers Without Any Sales Transactions
- Inactive Customers
- Item-wise Sales History
- Lost Quotations
- Payment Terms Status for Sales Order
- Pending SO Items For Purchase Request
- Quotation Trends
- Sales Analytics
- Sales Order Analysis
- Sales Order Trends
- Sales Partner Commission Summary
- Sales Partner Target Variance based on Item Group
- Sales Partner Transaction Summary
- Sales Person Commission Summary
- Sales Person Target Variance Based On Item Group
- Sales Person-wise Transaction Summary
- Territory Target Variance Based On Item Group
- Territory-wise Sales

## Stock (50)
- Available Batch Report
- Available Serial No
- BOM Search
- Batch Item Expiry Status
- Batch-Wise Balance History
- COGS By Item Group
- Delayed Item Report
- Delayed Order Report
- Delivery Note Trends
- FIFO Queue vs Qty After Transaction Comparison
- Incorrect Balance Qty After Transaction
- Incorrect Serial No Valuation
- Incorrect Serial and Batch Bundle
- Incorrect Stock Value Report
- Item Balance (Simple)
- Item Price Stock
- Item Prices
- Item Shortage Report
- Item Variant Details
- Item Where Used
- Item Wise Consumption
- Item-wise Price List Rate
- Items To Be Requested
- Itemwise Recommended Reorder Level
- Landed Cost Report
- Material Requests for which Supplier Quotations are not created
- Negative Batch Report
- Product Bundle Balance
- Purchase Receipt Trends
- Requested Items To Be Transferred
- Reserved Stock
- Serial No Ledger
- Serial No Service Contract Expiry
- Serial No Status
- Serial No Warranty Expiry
- Serial No and Batch Traceability
- Serial and Batch Summary
- Stock Ageing
- Stock Analytics
- Stock Balance
- Stock Ledger
- Stock Ledger Invariant Check
- Stock Ledger Variance
- Stock Projected Qty
- Stock Qty vs Batch Qty
- Stock Qty vs Serial No Count
- Stock and Account Value Comparison
- Total Stock Summary
- Warehouse Wise Stock Balance
- Warehouse wise Item Balance Age and Value

## Support (4)
- First Response Time for Issues
- Issue Analytics
- Issue Summary
- Support Hour Distribution

## Utilities (1)
- YouTube Interactions

---

# Bagian 3 — Yang relevan untuk PKS

## Dipakai langsung

| DocType | Peran di PKS |
|---|---|
| `Item`, `Item Group`, `UOM`, `Batch` | TBS, CPO, kernel, cangkang, fiber; batch per hari/kapal |
| `Supplier`, `Supplier Group` | Pemasok TBS (inti, plasma, pihak ketiga) |
| `Purchase Receipt` `[✓sub]` | Penerimaan TBS — tempat menempelkan Quality Inspection |
| `Quality Inspection` `[✓sub]` + `Quality Inspection Template`/`Parameter` | Jembatan hasil grading Palmgrade |
| `BOM` `[✓sub]` + child `BOM Secondary Item` | Alokasi joint-cost TBS → CPO + kernel + by-product |
| `Work Order` `[✓sub]`, `Job Card` `[✓sub]` | Batch olah harian |
| `Stock Entry` `[✓sub]`, `Stock Ledger Entry` `[✓sub]` | Mutasi stok, `Manufacture` / `Repack` |
| `Warehouse` `[tree]`, `Bin` | Tangki timbun, gudang kernel, stok lapangan |
| `Sales Order` `[✓sub]`, `Delivery Note` `[✓sub]`, `Sales Invoice` `[✓sub]` | Penjualan CPO/kernel |
| `Account` `[tree]`, `Cost Center` `[tree]`, `GL Entry` `[✓sub]` | Akuntansi; COA Indonesia tersedia |
| `Landed Cost Voucher` `[✓sub]` | Bebankan ongkos angkut ke harga pokok |
| `Asset` + `Asset Depreciation Schedule` | Boiler, press, sterilizer, kendaraan |

## Laporan yang langsung berguna

Manufacturing: `Process Loss Report`, `BOM Variance Report`, `Cost of Poor Quality Report`,
`Work Order Summary`, `Production Analytics`, `Quality Inspection Summary`
Stock: `Stock Balance`, `Stock Ledger`, `Stock Ageing`, `Batch-Wise Balance History`,
`Landed Cost Report`, `Item Wise Consumption`, `Stock and Account Value Comparison`
Accounts: `Profit and Loss Statement`, `Balance Sheet`, `Gross Profit`, `General Ledger`,
`Item-wise Purchase Register`, `Accounts Payable`

## Tidak dipakai (jangan buang waktu)

`Telephony`, `Support`, `CRM` (sebagian), `Subscription`/`POS`, `EDI`,
`Regional` (isinya AU/IT/ZA/TR/AE/US saja), `Bulk Transaction`, `Utilities/Video`.

## Yang harus dibuat sendiri — nol padanan di ERPNext

Jembatan timbang (tiket bruto/tara/netto), sortasi & potongan TBS, kontrak
plasma/inti dan bagi hasil, OER/KER harian, traceability ISPO/RSPO per blok
kebun. Semuanya jadi DocType di app kita sendiri, **bukan** modifikasi ERPNext.
