# Solution Design Document (SDD)
**App Name:** [ACN_MODULE_AppName]  
**Document Status:** Draft | In Review | Approved  
**Version:** 1.0  
**Last Updated:** YYYY-MM-DD  
**Project:** [Project Name]  
**Client:** [Client Name]

---

## 1. App Overview

| Field | Value |
|---|---|
| App Name | |
| Workday Module | AP / AR / EXP / GL / PROC / BANK |
| Business Process Integrated | e.g., Supplier Invoice Approval, Expense Report Submission |
| AI-Enabled | Yes / No |
| Trigger | User action / Business process event / Scheduled |
| Primary Users | e.g., AP Clerk, Finance Manager, CFO |
| Environments | Sandbox → Implementation → Production |

## 2. Business Purpose & Requirements

### 2.1 Problem Statement
> Describe the business problem this app solves. Why does this need to be an Extend app rather than a configuration change or standard Workday feature?

### 2.2 Business Requirements

| ID | Requirement | Priority | Acceptance Criteria |
|---|---|---|---|
| BR-01 | | Must Have / Should Have / Nice to Have | |
| BR-02 | | | |
| BR-03 | | | |

### 2.3 Out of Scope
> List what this app explicitly does NOT do, to manage expectations.

---

## 3. Architecture

### 3.1 Pages

| Page Name | Type | Purpose | Primary Users |
|---|---|---|---|
| [AppName]_List_Queue | List | Queue view showing all open items | Manager |
| [AppName]_Detail_Record | Detail | Full record view with action buttons | AP Clerk |
| [AppName]_Form_DataCapture | Form | Data entry / update form | AP Clerk |

### 3.2 Orchestrations

| Orchestration Name | Trigger | Purpose | Steps |
|---|---|---|---|
| [AppName]_Trigger_Orch | Business process event / User action | Initial trigger and routing | 1. Validate input 2. Route to appropriate path |
| [AppName]_AI_Classify_Orch | Sub-process | Call AI API and parse response | 1. Call API 2. Parse 3. Validate 4. Log |
| [AppName]_HumanReview_Orch | Human task completion | Process user decision | 1. Read decision 2. Execute action 3. Notify |

### 3.3 Orchestration Flow Diagram

```
[Trigger Event]
    │
    ▼
[Validation Step — check required fields]
    │
    ├─ Invalid ──────────────────────────────► [Error notification + terminate]
    │
    ▼ Valid
[AI Classification (if applicable)]
    │
    ├─ AI unavailable ───────────────────────► [Human review queue (fallback)]
    │
    ▼ AI response received
[Parse + Validate AI Response]
    │
    ├─ Response invalid ─────────────────────► [Human review queue]
    │
    ▼ Response valid
[Decision Gateway — apply business rules]
    │
    ├─ Auto-resolve ─────────────────────────► [Execute action] ──► [Log] ──► [Notify]
    │
    └─ Human review ─────────────────────────► [Human Task] ──► [Execute decision] ──► [Log]
```

### 3.4 Custom Business Objects

| BO Name | Purpose | Key Fields | Related Delivered Object |
|---|---|---|---|
| [FIRM]_[App]_AuditRecord | AI and action audit trail | Input_Summary, AI_Response, Action_Taken, Timestamp | Supplier Invoice |

### 3.5 Related Actions

| Action Label | On Object | Triggers | Available To |
|---|---|---|---|
| View Exception History | Supplier Invoice | Open [App]_List filtered to this invoice | AP Manager |

---

## 4. Security Design

### 4.1 Access Control

| Security Group | App Access Level | Data Visible | Actions Available |
|---|---|---|---|
| AP Clerk | Can use app | Their queue items only | Resolve, Escalate |
| AP Manager | Full queue access | All items | Resolve, Escalate, Override |
| Finance Director | Read-only | All items | View only |

### 4.2 Workday Permissions Required

| Permission | Object | Justification |
|---|---|---|
| Get | Supplier Invoice | Read invoice data for display |
| Put | Supplier Invoice | Update invoice status on resolution |

### 4.3 AI Data Flow (complete if AI-enabled)

| Field Sent to AI | Data Classification | Justification | Client Approval Required? |
|---|---|---|---|
| Invoice exception type | Internal | Required for classification | No |
| Invoice amount range (bucketed) | Internal | Context for routing | No |
| Supplier name | Confidential | Removed — use Supplier ID instead | N/A |

**Fields explicitly NOT sent to AI:**
- Supplier name, address, Tax ID
- Exact invoice amounts
- Any PII
- Bank account information

**AI API:** Claude API (claude-sonnet-5)  
**API Key Storage:** Workday Keychain — key name: `[KEY_NAME]`  
**Fallback if API unavailable:** Route all items to human review queue

---

## 5. Integration Points

### 5.1 Delivered Process Integration

| Delivered Process | Integration Point | How Integrated |
|---|---|---|
| Supplier Invoice Approval | Exception step | Extend sub-process triggers when invoice enters exception state |

### 5.2 External API Calls

| API | Purpose | Endpoint | Auth Method | Timeout |
|---|---|---|---|---|
| Claude API | AI classification | api.anthropic.com | Bearer token (Keychain) | 30s |

---

## 6. Testing

### 6.1 Unit Test Cases

| ID | Test Case | Setup | Expected Result | Pass/Fail |
|---|---|---|---|---|
| UT-01 | Happy path — AI available | Valid invoice exception, AI API online | Exception classified and routed correctly | |
| UT-02 | AI API timeout | Valid exception, API returns 504 | Routes to human review queue within 35s | |
| UT-03 | AI invalid response | API returns non-JSON | Routes to human review queue, logs error | |
| UT-04 | Auto-resolve path | Low-value exception matching auto-resolve rule | Resolved without human task, audit record created | |
| UT-05 | Human review path | High-value exception | Human task created, due date set, correct assignee | |
| UT-06 | Security — wrong role | User not in AP Clerk/Manager group | Cannot access app; receives permission error | |
| UT-07 | Duplicate trigger | Same invoice triggers app twice | Second trigger detected and suppressed | |

### 6.2 UAT Sign-Off

| Stakeholder | Role | Date | Signature |
|---|---|---|---|
| AP Clerk (end user) | | | |
| AP Manager | | | |
| Client IT Security | | | |

---

## 7. Deployment

### 7.1 Deployment Steps

**Sandbox → Implementation:**
1. Export app bundle from Sandbox
2. Import to Implementation tenant
3. Update all Reference IDs to Implementation values
4. Update Keychain credentials (API keys)
5. Assign security groups to relevant users
6. Run smoke test (UT-01 through UT-05)

**Implementation → Production:**
1. Export app bundle from Implementation
2. Import to Production tenant
3. Update all Reference IDs to Production values
4. Update Keychain credentials (Production API keys)
5. Assign security groups (match Implementation)
6. Run smoke test with limited dataset
7. Monitor for first 24 hours post-deployment

### 7.2 Rollback Plan

**Trigger for rollback:** P1 defect identified (data corruption, security breach, core process blocked)

**Rollback steps:**
1. Disable Extend app (remove from business process if applicable)
2. Revert to prior app version in Workday Extend
3. Notify impacted users
4. Communicate ETA for resolution
5. Conduct post-incident review within 48 hours

---

## 8. Approvals

| Role | Name | Date | Status |
|---|---|---|---|
| Solution Architect | | | Pending / Approved |
| Tech Lead | | | Pending / Approved |
| Security Review | | | Pending / Approved |
| Client Business Owner | | | Pending / Approved |
| CoP Extend Lead | | | Pending / Approved |

---

*SDD Template v1.0 — Workday Finance Tech CoP, Extend Sub-agent*
