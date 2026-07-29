# Workday Extend Development Standards
**Version:** 1.0  
**Owner:** Extend Sub-agent, Workday Finance Tech CoP  
**Status:** Published  
**Effective Date:** 2026-03-31

---

## 1. Purpose

This document defines mandatory development standards for all Workday Extend applications built by the CoP. These standards ensure apps are secure, maintainable, performant, and portable across client tenants.

---

## 2. Naming Conventions

### 2.1 App Names

**Format:** `[FIRM_PREFIX]_[MODULE]_[AppName]`

| Segment | Rule | Example |
|---|---|---|
| FIRM_PREFIX | 3-letter firm prefix (uppercase) | `ACN` |
| MODULE | 4-letter Workday module code | `AP`, `EXP`, `PROC`, `GL` |
| AppName | PascalCase, max 30 chars, no spaces | `InvoiceExceptionHandler` |

**Examples:**
- `ACN_AP_InvoiceExceptionHandler`
- `ACN_EXP_PolicyComplianceMonitor`
- `ACN_GL_PeriodCloseChecklist`

### 2.2 Orchestration Names

**Format:** `[AppName]_[ActionOrEvent]_Orch`

Examples:
- `InvoiceExceptionHandler_ExceptionClassify_Orch`
- `PolicyComplianceMonitor_PolicyReview_Orch`

### 2.3 Custom Business Object Names

**Format:** `[FIRM_PREFIX]_[AppName]_[ObjectDescription]`

Examples:
- `ACN_InvoiceExceptionHandler_ExceptionRecord`
- `ACN_PolicyComplianceMonitor_PolicyViolation`

### 2.4 Page Names

**Format:** `[AppName]_[PageType]_[Description]`

Page types: `Form`, `List`, `Detail`, `Report`

Examples:
- `InvoiceExceptionHandler_List_ExceptionQueue`
- `InvoiceExceptionHandler_Detail_ExceptionRecord`

---

## 3. Development Environment Standards

| Rule | Requirement |
|---|---|
| Build environment | Always develop in Sandbox tenant. Never build directly in Production. |
| Version control | Use Workday Extend's built-in versioning. Tag every release with a version number and date. |
| Branch strategy | Create a new app version for each significant change. Do not overwrite production app versions. |
| Configuration separation | No hardcoded tenant-specific values (tenant URL, ISU credentials, client-specific Reference IDs). Use configurable app settings instead. |
| Secrets management | API keys and credentials must be stored in Workday Keychain, not in orchestration variables or app settings. |

---

## 4. Security Design Standards

Security review is **mandatory** before any Extend app is deployed to Production.

### 4.1 Access Model

| Principle | Standard |
|---|---|
| Role-based access | Assign app access to Workday Security Groups, not individual workers. |
| Least privilege | App security groups should have the minimum Workday permissions needed. Document every permission and its justification. |
| Data visibility | Users should only see data relevant to their role. Use Workday's native security model — do not build custom data filtering in orchestrations. |
| Sensitive data | Mask sensitive fields (account numbers, SSN, payment data) unless the user's role explicitly requires full visibility. |
| Admin bypass | Never use a System Admin account for app data access in production. |

### 4.2 AI Integration Security (Additional Rules)

When an orchestration calls an external AI API:

| Rule | Requirement |
|---|---|
| Data minimization | Send ONLY the fields required for the AI task. Never send full records or bulk data exports to external APIs. |
| PII prohibition | Do not send personally identifiable information (names, SSNs, addresses, email) to external AI APIs without explicit client data privacy approval and DPA in place. |
| Financial data | Amount fields, account numbers, and supplier/customer names sent externally require data classification review and client approval. |
| API credentials | Store external API keys in Workday Keychain. Never embed in orchestration code. |
| Response handling | AI responses must be treated as untrusted input — validate and sanitize before using in downstream Workday actions. |
| Audit trail | Log all AI API calls (input summary, response classification, action taken) to a Custom Business Object for audit purposes. |

### 4.3 Security Review Checklist

Before production deployment:

- [ ] Security group mapping documented
- [ ] Minimum required permissions listed and justified
- [ ] Data-level visibility tested with non-admin users
- [ ] AI data flows reviewed against client data privacy agreement (if applicable)
- [ ] External API credentials stored in Keychain
- [ ] AI audit log Custom BO implemented
- [ ] Security review sign-off obtained from tech lead

---

## 5. Orchestration Design Standards

### 5.1 Error Handling

Every orchestration must handle failure explicitly:

```
Required error handling patterns:
  - Every HTTP step (external API call) must have: 
      success path AND failure/timeout path
  - Failure path options (choose the appropriate one):
      a) Route to human review queue
      b) Send notification to admin and terminate gracefully
      c) Retry with exponential backoff (max 3 retries)
  - Never let an orchestration silently fail
  - Log all failures to the app's audit Custom BO
```

### 5.2 AI/LLM Call Pattern

When calling Claude or another LLM from an orchestration HTTP step:

```
Recommended pattern:
1. System Task (HTTP): Call AI API
   - Timeout: 30 seconds
   - Retry: 2 times with 5s delay
2. Decision Gateway: Did AI respond successfully?
   - Yes: Parse and validate AI response
   - No: Route to human fallback
3. System Task: Validate AI response format
   - Check required fields in response JSON
   - Check for refusal/error indicators
4. Decision Gateway: Is response actionable?
   - Yes: Execute the AI-recommended action
   - No: Route to human review with AI explanation
5. System Task: Log to audit Custom BO
   - Input fields sent (anonymized)
   - AI response summary
   - Action taken
   - Timestamp and user context
```

**Critical:** Every AI-connected orchestration must have a **working fallback path** for when the AI API is unavailable. The fallback should route to a human review queue — the process must not stop.

### 5.3 Human Task Design

| Standard | Requirement |
|---|---|
| Task title | Clear, action-oriented: "Review Invoice Exception: [Invoice #]" not "Approval Required" |
| Task due date | Always set a due date. Never leave human tasks open-ended. |
| Context in task | Surface all relevant context (invoice amount, supplier, exception reason) directly in the task — users should not need to navigate away |
| Escalation | Define escalation if task is not completed within due date |
| Completion actions | Clearly label buttons: "Approve and Pay", "Reject and Notify Supplier", "Escalate to Manager" — not "Approve" / "Reject" |

### 5.4 Performance Standards

| Rule | Requirement |
|---|---|
| Synchronous AI calls | Only for tasks < 3 seconds. Longer tasks must use async pattern. |
| Large data processing | Never process more than 1,000 records in a single orchestration run. Batch into sub-orchestrations. |
| Real-time triggers | Apps triggered on high-frequency events (every invoice submit) must complete within 5 seconds or use async design. |
| Avoid loops | Avoid orchestration loops over large datasets — use Workday reporting as the data source instead. |

---

## 6. Custom Business Object Standards

| Standard | Requirement |
|---|---|
| Naming | Follow Section 2.3 naming convention |
| Audit fields | Every custom BO must include: `Created_By`, `Created_Date`, `Last_Modified_By`, `Last_Modified_Date` |
| Retention | Define data retention period in the SDD. Archive or delete records per client data policy. |
| Reporting | Every custom BO that holds business data must have at least one standard Workday report for audit/review. |
| Relationships | Relate custom BOs to delivered Workday objects (e.g., link `ExceptionRecord` to `Supplier Invoice`) to enable navigation. |

---

## 7. Testing Standards

### 7.1 Unit Testing (in Sandbox)

| Test Case | Requirement |
|---|---|
| Happy path | All orchestration branches execute correctly end-to-end |
| Error path | Failure at each HTTP step is handled by the error branch |
| AI unavailable | Fallback path works when AI API returns 500/timeout |
| AI unexpected response | Validation step correctly rejects malformed AI responses |
| Security | Non-privileged test users can only access what they should |
| Edge cases | Empty inputs, very large values, special characters, null fields |

### 7.2 UAT Requirement

UAT must be conducted with **actual end users** (AP clerks, accountants, managers) in the Implementation tenant, not with developers or system admins. UAT sign-off is required before Production deployment.

### 7.3 Performance Testing

Apps triggered on high-frequency events (invoice submission, expense submission) must be load-tested at 2× expected peak volume before go-live.

---

## 8. Documentation Requirements (Solution Design Document)

Every Extend app must have a completed and approved SDD before Production deployment. See `extend/templates/solution_design_document_template.md` for the full template.

Mandatory SDD sections:

1. App overview and business purpose
2. Architecture (pages, orchestrations, custom objects)
3. Security design (groups, permissions, AI data flows)
4. Integration points (delivered processes, external APIs)
5. Testing plan and UAT results
6. Deployment steps (sandbox → implementation → production)
7. Rollback plan
8. Approval signatures

---

## 9. Deployment Checklist

- [ ] App developed and tested in Sandbox
- [ ] SDD completed and approved
- [ ] Security review sign-off obtained
- [ ] AI data flows reviewed (if applicable)
- [ ] UAT completed with real end users
- [ ] UAT sign-off document saved
- [ ] Performance tested at peak load
- [ ] Rollback plan documented
- [ ] Implementation tenant deployment tested
- [ ] Production deployment executed
- [ ] Post-deployment smoke test passed
- [ ] App documented and submitted to CoP Asset Library

---

*Extend Development Standards v1.0 — Workday Finance Tech CoP*
