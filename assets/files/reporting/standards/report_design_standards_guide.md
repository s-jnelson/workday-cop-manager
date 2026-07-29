# Workday Finance Report Design Standards Guide
**Version:** 1.0  
**Owner:** Reporting Sub-agent, Workday Finance Tech CoP  
**Effective Date:** 2026-07-08  
**Review Cycle:** Annual

---

## 1. Purpose

This guide establishes firm standards for designing, building, naming, securing, and deploying Workday Financial reports. All custom reports published to the CoP Asset Library or deployed to client tenants must conform to these standards.

Conformance with these standards:
- Reduces report performance issues that cause timeout errors in production
- Ensures consistent security design that prevents unauthorized data access
- Makes reports maintainable by any CoP team member, not just the original builder
- Enables reliable reuse across client deployments

---

## 2. Report Type Selection

Choose the correct report type before building. Using the wrong type wastes build time and produces a worse result.

| Report Type | When to Use | When NOT to Use |
|---|---|---|
| **Simple Report** | Single data source, flat list output, operational lookup | Any report requiring grouping, totals, or multi-source data |
| **Advanced Report** | Most operational Finance reports — filtering, grouping, multiple related sources | When a cross-tab layout is needed (use Matrix instead) |
| **Matrix Report** | Period-over-period comparisons, budget vs. actuals, trial balance with columns | When data doesn't naturally have a row × column structure |
| **Composite Report** | Financial statements combining multiple sections (P&L + Balance Sheet) | Single-topic reports — Composite adds complexity without benefit |
| **Transposed Report** | Multi-period trend data where periods should appear as columns | Reports with fewer than 4 periods — use a Matrix instead |
| **Dashboard Report** | Executive KPI tiles, embedded charts, home page worklets | Detailed operational reports — Dashboard reports aggregate, not detail |
| **Prism Analytics + Discovery Board** | Cross-module analysis, external data integration, historical data beyond Workday retention | Pure Workday-data reports — Prism adds complexity and cost; only use when the native report writer can't meet requirements |

### Decision Tree

```
Does the report need data from OUTSIDE Workday?
  └─ Yes → Prism Analytics + Discovery Board
  └─ No → Is the output a cross-tab (rows × columns)?
              └─ Yes → Matrix Report (period comparison) OR Transposed (dynamic period columns)
              └─ No → Does it combine multiple report sections (e.g. IS + BS)?
                          └─ Yes → Composite Report
                          └─ No → Does it show aggregated KPIs / charts for a homepage?
                                      └─ Yes → Dashboard Report
                                      └─ No → Advanced Report (default)
```

---

## 3. Naming Convention

**Format:** `FIN-[MODULE]-[Description]-v[Version]`

### Module Codes

| Module | Code |
|---|---|
| General Ledger / Financial Accounting | GL |
| Accounts Payable | AP |
| Accounts Receivable | AR |
| Fixed Assets | FA |
| Expenses | EXP |
| Procurement | PROC |
| Banking & Settlement | BANK |
| Financial Projects | PROJ |
| Budget & Planning | BUDG |
| Tax | TAX |
| Consolidation | CONS |
| Revenue Management | REV |
| Cross-Module / Multi-Module | XMOD |

### Description Rules

- Use PascalCase: `TrialBalance` not `trial balance` or `Trial_Balance`
- Maximum 30 characters
- Be specific: `APAgingBySupplier` not `APReport`
- Avoid dates in names — use version numbers instead

### Version Numbers

- Start at v1
- Increment when field mapping, filter logic, or output structure changes materially
- Minor fixes (label changes, prompt default changes) do not require version increment
- Retire old versions rather than deleting — mark them `[RETIRED]` in the description

### Examples

| Good Name | Bad Name | Problem |
|---|---|---|
| `FIN-AP-OpenInvoiceAging-v2` | `AP Aging Report` | Missing prefix, no version |
| `FIN-GL-TrialBalanceByCC-v1` | `FIN-GL-Trial_Balance_Cost_Center_Detail_Report_Jan2026-v1` | Too long, date in name |
| `FIN-EXP-PolicyViolations-v1` | `My Report` | Not descriptive |
| `FIN-XMOD-CFODashboard-v3` | `Dashboard` | Not specific |

---

## 4. Primary Business Object (BO) Selection

The Primary Business Object determines what data is available in the report. Choosing incorrectly means you can't get the data you need, or you get it inefficiently.

### Finance BO Quick Reference

| What You're Reporting On | Primary BO |
|---|---|
| General Ledger transactions, journal entries | Journal Entry |
| GL account balances by period | Ledger Account |
| Supplier invoices (AP) | Supplier Invoice |
| Supplier payments | Supplier Payment |
| Customer invoices (AR) | Customer Invoice |
| Customer payments | Customer Payment |
| Expense reports | Expense Report |
| Expense report lines | Expense Item |
| Purchase orders | Purchase Order |
| Purchase order lines | Purchase Order Line |
| Fixed assets | Asset |
| Depreciation transactions | Asset Transaction |
| Bank transactions | Bank Transaction |
| Budget data | Budget |
| Financial projects | Project |

### Common Mistakes

- Using `Worker` as the primary BO for expense reports (use `Expense Report`)
- Using `Company` as the primary BO for GL transactions (use `Journal Entry` or `Ledger Account`)
- Using `Supplier` for AP aging (use `Supplier Invoice` — Supplier BO doesn't give you invoice data)

---

## 5. Filter Design Standards

Filters are the most common source of report performance problems. Follow these rules on every report.

### Rule 1: Always Filter on Indexed Fields

Workday indexes specific fields on each Business Object. Filtering on indexed fields is orders of magnitude faster than filtering on non-indexed fields.

| Business Object | Always Filter On (Indexed) | Avoid Filtering On (Non-Indexed) |
|---|---|---|
| Journal Entry | Company, Accounting Period, Ledger Account | Memo/Description text, created-by worker |
| Supplier Invoice | Company, Supplier, Invoice Status, Invoice Date | Invoice memo, line descriptions |
| Customer Invoice | Company, Customer, Invoice Status, Invoice Date | Notes fields |
| Expense Report | Company, Expense Report Status, Submit Date | Expense description |
| Asset | Company, Asset Class, Asset Status | Description, memo |

### Rule 2: Require Prompts on Large Datasets

Never allow a report that touches high-volume BOs (Journal Entry, Supplier Invoice, Customer Invoice) to run without at least one required prompt:

```
Minimum required prompts for high-volume reports:
  - Journal Entry reports: Company AND Accounting Period (or date range)
  - Invoice reports: Company AND date range (at minimum)
  - Expense reports: Company AND Status (or date range)
```

### Rule 3: Prompt Design

| Setting | Standard |
|---|---|
| Required prompts | Bold label; include "(Required)" in prompt label |
| Default values | Set defaults that cover 80% of use cases (e.g., current period, active status) |
| Multi-select prompts | Use when users legitimately need to select multiple values |
| Prompt order | Most restrictive (Company, Period) first; optional refinements last |
| Prompt labels | Use business language, not technical field names — "Invoice Status" not "Document_Status_Category_Code" |

---

## 6. Security Design Standards

**Security must be designed before the report is built, not after.**

### 6.1 Security Group Approach

| Approach | Standard |
|---|---|
| **Role-Based Security Groups** | Default for all reports — assign to role, not individual |
| **User-Based Security** | Only for exceptional cases with documented justification |
| **Report Sharing** | Never share with individual users — always share with groups |
| **Admin Access** | Never leave reports accessible only to System Admins in production |

### 6.2 Standard Finance Security Groups

Map each report to one or more of these standard groups:

| Security Group | Typical Report Access |
|---|---|
| Finance Director | All financial reports, including confidential GL detail |
| Controller | All close reports, trial balance, journal entry detail |
| AP Manager | All AP reports including aging and payment detail |
| AP Clerk | AP aging, invoice status — no payment detail |
| AR Manager | All AR reports including collection detail |
| Expense Manager | Expense reports for their organization |
| Financial Analyst | Standard financial statements, budget vs. actuals |
| Auditor | Read-only access to all financial reports, no PII |
| Procurement Manager | PO reports, supplier spend analysis |

### 6.3 Data-Level Security Test

Before publishing, test the report as a non-admin user in the target security group:

1. Create a test user assigned only the target security group
2. Log in as that user
3. Run the report — verify the user sees only the data they should
4. Run the report as a user in a DIFFERENT group — verify they cannot run it or see different data

---

## 7. Performance Standards

Every report must pass these performance gates before publication:

| Gate | Requirement |
|---|---|
| On-demand response time | < 30 seconds for the 90th percentile typical use case |
| Full dataset run | < 5 minutes for the maximum expected dataset |
| Scheduled report generation | Complete within the scheduled window |
| Large output handling | Reports > 100,000 rows must offer an Excel download option |

### Performance Optimization Checklist

- [ ] Primary BO is the most specific available (not a parent BO)
- [ ] All primary filters use indexed fields
- [ ] At least one required prompt restricts the dataset
- [ ] Calculated fields do not call sub-reports on every row
- [ ] Matrix report aggregation is at report level, not calculated field level
- [ ] Report has been tested with production-scale data (not sandbox sample data)
- [ ] Output format is appropriate (avoid PDF for large datasets — use Excel/CSV)

---

## 8. Calculated Fields

### When to Use Field-Level vs. Inline Calculated Fields

| Type | When to Use | Key Difference |
|---|---|---|
| **Field-Level Calculated Field** | When the calculation is needed across multiple reports | Stored on the Business Object; reusable |
| **Inline Calculated Field** | When the calculation is only needed in this one report | Exists only within this report; not reusable |

### Calculated Field Standards

- **Name format:** `[CF] [Description]` — e.g., `[CF] Days Outstanding`, `[CF] Budget Variance %`
- **Document the formula** in the calculated field description field — future maintainers must understand it without reverse-engineering
- **Test edge cases:** division by zero, null inputs, negative values, multi-currency
- **Avoid deeply nested calculations** — split complex logic into multiple calculated fields

### Common Finance Calculated Fields

```
Days Outstanding = (Today - Due Date)
Budget Variance $ = Actual Amount - Budget Amount  
Budget Variance % = (Actual Amount - Budget Amount) / ABS(Budget Amount) × 100
YTD Amount = SUM of period amounts from Period 1 to current period
Running Total = Cumulative sum ordered by date
Aging Bucket = IF(Days Outstanding <= 30, "Current", IF(Days Outstanding <= 60, "31-60", ...))
```

---

## 9. Documentation Requirements

Every report published to the CoP Asset Library must include the following in its Workday description field:

```
Purpose: [One sentence describing what the report shows and who uses it]
Primary Users: [Role(s) — e.g., AP Manager, Controller]
Key Filters: [List of required and recommended prompts]
Security Groups: [Which security groups should have access]
Frequency of Use: [Daily / Weekly / Monthly / Ad-hoc]
Performance Notes: [Any known limitations or large dataset guidance]
Version History: [v1: Initial release. v2: Added Cost Center prompt.]
CoP Asset ID: [Asset ID from the library]
```

---

## 10. Publication Checklist

Before submitting a report to the CoP Asset Library:

- [ ] Report name follows `FIN-[MODULE]-[Description]-v[Version]` convention
- [ ] Description field fully populated (see Section 9)
- [ ] Security groups assigned — tested with non-admin user
- [ ] Performance tested with production-scale data
- [ ] All required prompts set (no unrestricted queries on high-volume BOs)
- [ ] Calculated fields documented
- [ ] Peer reviewed by another reporting consultant
- [ ] UAT completed with a business user from the target audience
- [ ] CoP reporting lead has approved publication

---

*Report Design Standards Guide v1.0 — Workday Finance Tech CoP*  
*Questions or suggested improvements: raise in the CoP bi-weekly call or submit to the reporting sub-agent.*
