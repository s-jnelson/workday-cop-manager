# Workday Finance Tech CoP — AI Solutions Library

**Version:** 1.0 | **Date:** 2026-07-08 | **Maintained by:** Workday Finance Tech Community of Practice

---

## Overview

The Workday Finance Tech Community of Practice (CoP) AI Solutions Library is a curated collection of production-ready Python tools that apply AI and automation to common Workday Finance implementation and operations challenges. Each solution is built to run immediately with minimal setup, targets a specific finance practitioner use case, and is designed to accelerate client engagements — not replace practitioner expertise.

This library reflects the CoP's belief that AI tools are most valuable when they are transparent, configurable, and firmly under the control of the human practitioner. Every solution in this library can operate in a rule-based mode without AI, exposes its logic as readable Python code, and produces outputs that are immediately reviewable by the engagement team before being shared with a client. Solutions are organized by Workday practice area and assigned to a responsible sub-agent — the practitioner community member most qualified to maintain, extend, and deploy that solution in client environments.

---

## Solution Catalog

| # | Solution Name | Focus Area | Status | Responsible Agent | Key Technology | Script File | Guide |
|---|---|---|---|---|---|---|---|
| 01 | GL Anomaly Detector | Reporting & Analytics | Ready | Reporting Sub-agent | pandas, scipy, anthropic | `solutions/01_gl_anomaly_detector.py` | `guides/01_gl_anomaly_guide.md` |
| 02 | Budget Variance Explainer | Reporting & Analytics | Ready | Reporting Sub-agent | pandas, anthropic | `solutions/02_budget_variance_explainer.py` | `guides/02_budget_variance_guide.md` |
| 03 | iLoad Data Validator | Integrations | Ready | Integrations Sub-agent | pandas, re | `solutions/03_iload_validator.py` | `guides/03_iload_validator_guide.md` |
| 04 | RaaS Report Builder | Reporting & Analytics | Ready | Reporting Sub-agent | requests, anthropic | `solutions/04_raas_builder.py` | `guides/04_raas_builder_guide.md` |
| 05 | Supplier Risk Scorer | Integrations | Ready | Integrations Sub-agent | pandas, anthropic | `solutions/05_supplier_risk_scorer.py` | `guides/05_supplier_risk_guide.md` |
| 06 | Conversion Mapping Assistant | Conversion | Ready | Conversion Sub-agent | pandas, anthropic | `solutions/06_conversion_mapping_assistant.py` | `guides/06_mapping_assistant_guide.md` |
| 07 | Expense Policy Reviewer | Extend / Operations | Ready | Extend Sub-agent | pandas, anthropic, openpyxl | `solutions/07_expense_policy_reviewer.py` | `guides/07_expense_policy_guide.md` |

---

## Getting Started

### 1. Set Up Your Anthropic API Key

Most solutions use Claude AI for analysis and narrative generation. You need an Anthropic API key:

1. Obtain a key from the CoP Extend Lead (see Contact section below) or create one at https://console.anthropic.com
2. Set the key in your environment:

```bash
# Windows (Command Prompt)
set ANTHROPIC_API_KEY=sk-ant-api03-...

# Windows (PowerShell)
$env:ANTHROPIC_API_KEY = "sk-ant-api03-..."

# macOS / Linux
export ANTHROPIC_API_KEY=sk-ant-api03-...
```

3. To persist the key across sessions, add it to your shell profile (`.bashrc`, `.zshrc`) or Windows environment variables via System Properties.

### 2. Install Required Packages

Install all packages needed across all solutions at once:

```bash
pip install anthropic pandas numpy scipy openpyxl tabulate
```

Or install per-solution using the requirements block below.

### 3. Run Your First Solution

Every solution includes a `--demo` flag that uses embedded sample data — no input files or Workday access needed:

```bash
# Try the Supplier Risk Scorer
python solutions/05_supplier_risk_scorer.py --demo

# Try the Expense Policy Reviewer (no API key needed in --no-ai mode)
python solutions/07_expense_policy_reviewer.py --demo --no-ai

# Try the Conversion Mapping Assistant (API key required)
python solutions/06_conversion_mapping_assistant.py --demo
```

### 4. Folder Structure

```
assets/files/ai/
├── AI_SOLUTIONS_INDEX.md          ← You are here
├── solutions/
│   ├── 01_gl_anomaly_detector.py
│   ├── 02_budget_variance_explainer.py
│   ├── 03_iload_validator.py
│   ├── 04_raas_builder.py
│   ├── 05_supplier_risk_scorer.py
│   ├── 06_conversion_mapping_assistant.py
│   └── 07_expense_policy_reviewer.py
└── guides/
    ├── 01_gl_anomaly_guide.md
    ├── 02_budget_variance_guide.md
    ├── 03_iload_validator_guide.md
    ├── 04_raas_builder_guide.md
    ├── 05_supplier_risk_guide.md
    ├── 06_mapping_assistant_guide.md
    └── 07_expense_policy_guide.md
```

---

## Requirements

The following packages are used across all 7 solutions. Install all at once or selectively per solution.

```
# requirements.txt
# Workday Finance Tech CoP — AI Solutions Library
# Install: pip install -r requirements.txt

# AI / LLM
anthropic>=0.34.0

# Data processing
pandas>=2.0.0
numpy>=1.25.0

# Statistical analysis (Solution 01)
scipy>=1.11.0

# Excel output (Solution 07)
openpyxl>=3.1.0

# Table formatting (Solution 06)
tabulate>=0.9.0
```

---

## Practice Deployment Principles

The CoP follows these principles when deploying AI solutions to client environments:

1. **Human in the loop, always.** AI-generated outputs (narratives, recommendations, mappings) are advisory inputs to practitioner judgment — never automated decisions. Every solution that uses AI also supports a `--no-ai` or equivalent mode so the practitioner can always explain exactly what logic produced a result.

2. **Client data stays protected.** Solutions follow a minimum-necessary-data approach: PII columns are stripped before AI processing, demo data is used for presentations and training, and client data is never used in CoP knowledge-sharing sessions without explicit written permission.

3. **Configurable, not hard-coded.** Every solution externalizes its key parameters (policy thresholds, risk lists, object definitions) via CLI flags and JSON configuration files. Practitioners can adapt to client-specific requirements without touching source code.

4. **Transparent scoring and logic.** Rule-based components (risk scoring, policy violation detection) produce traceable, auditable outputs. Practitioners must be able to explain to a client exactly why a supplier was flagged HIGH or why an expense was marked P1 — without relying on AI as the explanation.

5. **Production readiness is a journey, not a checklist.** Each solution's Agent Readiness Assessment section honestly documents what is ready for immediate use, what needs client-specific customization, and what the known limitations are. Practitioners are expected to read this section before deploying to a client and to update it when they discover new limitations or improvements.

---

## Adding New AI Use Cases

To contribute a new solution to the library:

1. **Identify the use case** — describe the problem, the Workday data source, and the expected output. Propose it in the CoP Slack channel `#ai-solutions-wg`.

2. **Assign a responsible sub-agent** — determine which practice area owns the solution (Reporting, Integrations, Conversion, or Extend).

3. **Follow the solution structure:**
   - Script in `solutions/NN_solution_name.py` with `--demo` flag, `--no-ai` option where applicable, and full docstring
   - Guide in `guides/NN_solution_name_guide.md` using the standard 10-section template
   - Add a row to this index table

4. **Review requirements:** All solutions must include embedded demo data (no external file needed for `--demo`), graceful error handling for missing API keys or packages, and structured output files (CSV at minimum).

5. **Submit for CoP review** — share the script and guide in the `#ai-solutions-wg` channel for peer review before adding to the shared library. Two reviewers from different sub-agents are required.

---

## Contact

| Role | Placeholder |
|---|---|
| **Extend Sub-agent Lead** | [extend-lead@yourfirm.com] — Primary maintainer for Solutions 03, 07 and all Workday Extend integrations |
| **Reporting Sub-agent Lead** | [reporting-lead@yourfirm.com] — Primary maintainer for Solutions 01, 02, 04 and RaaS/Prism analytics |
| **Integrations Sub-agent Lead** | [integrations-lead@yourfirm.com] — Primary maintainer for Solution 05, EIB patterns, iLoad templates |
| **Conversion Sub-agent Lead** | [conversion-lead@yourfirm.com] — Primary maintainer for Solution 06, iLoad/EIB conversion patterns |
| **CoP AI Working Group** | [#ai-solutions-wg on CoP Slack] — General discussion, new use case proposals, cross-solution issues |

*Replace placeholder emails with actual contact information before sharing this index with client teams.*
