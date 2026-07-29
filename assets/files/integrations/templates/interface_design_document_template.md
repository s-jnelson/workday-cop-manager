# Interface Design Document (IDD)
**Document Status:** Draft | In Review | Approved  
**Version:** 1.0  
**Last Updated:** YYYY-MM-DD  
**Project:** [Project Name]  
**Client:** [Client Name]

---

## 1. Overview

| Field | Value |
|---|---|
| Integration Name | |
| Integration ID | INT-[###] |
| Technology | Workday Studio / Core Connector / EIB / RaaS / REST API |
| Direction | Inbound / Outbound / Bidirectional |
| Source System | |
| Target System | |
| Trigger | Scheduled / Event-Driven / Real-Time |
| Frequency | e.g., Daily at 02:00 EST / On AP Invoice Submit |
| Estimated Volume | e.g., 5,000 records/run |
| Environment | Sandbox / Implementation / Production |

## 2. Business Purpose

> Describe why this integration exists and what business process it supports.

## 3. Technical Design

### 3.1 Technology Choice & Rationale

| Option Considered | Reason Accepted / Rejected |
|---|---|
| Workday Studio | |
| Core Connector | |
| EIB | |
| RaaS | |
| REST API | |

**Selected Technology:** ___  
**Rationale:** ___

### 3.2 Data Flow

```
[Source System]
    │
    ▼ (format: CSV / XML / JSON / SFTP / API call)
[Transformation Layer]
    │
    ▼ (transformed to Workday format)
[Workday]
    │
    ▼ (confirmation / response — if applicable)
[Source System / Monitoring]
```

### 3.3 File / Message Specification

| Property | Value |
|---|---|
| Format | CSV / XML / JSON / Fixed-Width |
| Delimiter (if CSV) | Comma / Pipe / Tab |
| Encoding | UTF-8 |
| Date Format | YYYY-MM-DD |
| Max File Size | |
| Expected Record Count | |
| File Naming Convention | e.g., `SUPPLIER_INVOICES_YYYYMMDD_HHMMSS.csv` |
| Transfer Method | SFTP / HTTPS / API Call / Workday MFT |
| Source Path | |
| Archive Path | |

## 4. Field Mapping

> Complete one row per field. Mark transformation logic where source ≠ target.

| # | Source Field Name | Source Type | Target Field Name (Workday) | Target Type | Required | Transformation Logic | Notes |
|---|---|---|---|---|---|---|---|
| 1 | | | | | Y/N | Direct map / Constant / Lookup / Calculated | |
| 2 | | | | | | | |
| 3 | | | | | | | |
| 4 | | | | | | | |
| 5 | | | | | | | |

### 4.1 Code Table / Reference Data Crosswalk

> List all source codes that must be mapped to Workday Reference IDs.

| Source Code | Source Description | Workday Reference ID | Workday Description | Default if Unmapped |
|---|---|---|---|---|
| | | | | |

## 5. Error Handling

| Scenario | Handling Approach |
|---|---|
| Missing required field | Reject record; log to error report |
| Invalid reference data (unmapped code) | Reject record; use default if defined, else reject |
| Duplicate record | Skip duplicate; log warning |
| Source file not received | Alert via notification; do not fail prior successful records |
| Workday API timeout | Retry 3× with 15-minute backoff; alert if all retries fail |
| Partial file (truncated) | Reject entire file; alert and await resend |

### 5.1 Error Notification

| Recipient | Trigger | Channel |
|---|---|---|
| Integration Support Team | Any failure | Email to [distribution list] |
| Functional Lead | P1 failure (data loss risk) | Email + SMS |
| Client IT | Repeated failures (3+ consecutive) | Email |

### 5.2 Error Log Format

Error logs will be written to: `[path or SFTP location]`

Fields: `Run_ID | Timestamp | Record_ID | Field | Error_Code | Error_Description | Source_Value`

## 6. Security

### 6.1 Integration System User (ISU)

| Property | Value |
|---|---|
| ISU Account Name | ISU_INT_[INTEGRATION_NAME] |
| Security Group | [Security Group Name] |
| Permissions Required | List minimum required (e.g., Get Supplier Invoices, Put Supplier Invoices) |
| Credential Storage | Workday Keychain / External Secret Manager |
| Credential Rotation | Every 90 days |

### 6.2 Network Security

| Property | Value |
|---|---|
| Workday IP Allowlist Required | Yes / No |
| SFTP Authentication | SSH Key / Password |
| Certificate Required | Yes / No — Certificate name: |
| Data in Transit Encryption | TLS 1.2+ |
| Data at Rest Encryption | Yes — at source and in archive |

### 6.3 Data Classification

| Data Element | Classification | Notes |
|---|---|---|
| | Confidential / Internal / Public | |

## 7. Testing

### 7.1 Unit Test Plan

| Test Case | Description | Test Data | Expected Result | Pass/Fail |
|---|---|---|---|---|
| Happy Path | All required fields populated, valid reference data | Sample file with 5 valid records | All 5 records load successfully | |
| Missing Required Field | Blank required field in row 3 | Modified sample file | Row 3 rejected; error logged | |
| Invalid Reference Data | Unmapped code in row 2 | Modified sample file | Row 2 rejected or defaulted per rule | |
| Duplicate Record | Same key in rows 4 and 5 | Modified sample file | Row 5 skipped; row 4 loaded | |
| Empty File | Zero data records | Empty file (header only) | No error; zero records loaded; alert sent | |
| Oversize File | Exceeds max file size | Large file | File rejected; alert sent | |
| Special Characters | Unicode / non-ASCII in text fields | File with accented characters | Records load correctly | |

### 7.2 SIT Test Cases

| Test Case | Scenario | Expected Outcome |
|---|---|---|
| End-to-End Happy Path | Source sends file → Integration processes → Workday updated | Data visible in Workday within SLA |
| Error Recovery | File fails → Error corrected → Resubmitted | Resubmission succeeds |
| Volume Test | Full production volume | Completes within scheduling window |

### 7.3 UAT Sign-Off

| Stakeholder | Role | Date | Signature |
|---|---|---|---|
| Functional Lead | | | |
| Client Finance Lead | | | |
| Client IT / Integration Owner | | | |

## 8. Scheduling & Monitoring

| Property | Value |
|---|---|
| Schedule | e.g., Daily Mon–Fri at 02:00 EST |
| Timezone | |
| Workday Job Name | |
| Expected Completion Time | |
| SLA | e.g., Complete within 2 hours of scheduled start |
| Monitoring Dashboard | Workday Integration Dashboard |
| Alert Threshold | Failure or duration > [X] minutes |
| On-Call Contact | |

## 9. Cutover Considerations

| Item | Detail |
|---|---|
| Last legacy run date | |
| First Workday run date | |
| Parallel run required? | Yes / No |
| Parallel run period | |
| Historical data handling | Load historical records? Date range? |
| Cutover smoke test | Steps to verify first production run succeeded |

## 10. Approvals

| Role | Name | Date | Status |
|---|---|---|---|
| Solution Architect | | | Pending / Approved |
| Functional Lead | | | Pending / Approved |
| Technical Lead | | | Pending / Approved |
| Client IT Owner | | | Pending / Approved |
| CoP Review (if reusable asset) | | | Pending / Approved |

---
*Template version: CoP v1.0 — Integrations Sub-agent*  
*To contribute improvements, submit to the CoP Asset Library via the standard contribution process.*
