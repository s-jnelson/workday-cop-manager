/**
 * Workday Finance Tech CoP Manager — Dashboard Application
 *
 * Renders all practice data. When the FastAPI backend is running on port 8000
 * it fetches live data; otherwise falls back to embedded seed data so the
 * dashboard is fully functional as a standalone HTML file.
 */

const API_BASE = '/api';

async function apiFetch(url, opts = {}) {
  opts.headers = { 'Content-Type': 'application/json', ...(opts.headers || {}) };
  return fetch(url, opts);
}

// ── State ──────────────────────────────────────────────────────────────────
let state = {
  metrics: null,
  goals: null,
  initiatives: null,
  consultants: null,
  assets: null,
  aiUseCases: null,
  chatHistory: [],
  currentGoalTab: 'practice',
  currentConsultantTab: 'all',
  currentInitFilter: 'all',
  currentAssetFilter: { area: 'all', status: 'all' },
};

// ── Boot ───────────────────────────────────────────────────────────────────
window.addEventListener('DOMContentLoaded', () => {
  loadAllData();
});

async function loadAllData() {
  try {
    const res = await apiFetch(`${API_BASE}/dashboard`);
    if (!res.ok) throw new Error('API error');
    const data = await res.json();
    state.metrics    = data.metrics;
    state.goals      = data.goals;
    state.initiatives= data.initiatives;
    state.consultants= data.consultants;
    state.assets     = data.assets;
    state.aiUseCases = data.ai_use_cases;
  } catch (err) {
    // Server unreachable — use embedded seed data for read-only view
    state.metrics     = getSeedMetrics();
    state.goals       = getSeedGoals();
    state.initiatives = getSeedInitiatives();
    state.consultants = getSeedConsultants();
    state.assets      = getSeedAssets();
    state.aiUseCases  = getSeedAiUseCases();
  }

  renderAll();
  document.getElementById('lastUpdated').textContent =
    `Updated: ${new Date().toLocaleTimeString()}`;
}

function renderAll() {
  renderOverview();
  renderGoals();
  renderInitiatives();
  renderConsultants();
  renderAssets();
  renderAIPipeline();
  renderMethodology();
}

// ── Navigation ─────────────────────────────────────────────────────────────
function switchView(name) {
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  document.getElementById(`view-${name}`)?.classList.add('active');
  document.querySelector(`[data-view="${name}"]`)?.classList.add('active');
  if (name === 'agent' && state.chatHistory.length > 0) {
    const win = document.getElementById('chatWindow');
    if (win) {
      win.innerHTML = '';
      state.chatHistory.forEach(m => appendChat(m.role, m.text));
    }
  }
}

// ── Overview ───────────────────────────────────────────────────────────────
function renderOverview() {
  const m = state.metrics;
  if (!m) return;

  // Health band
  const health = m.focus_area_health || {};
  ['integrations','conversion','reporting','extend'].forEach(area => {
    const h = health[area] || {};
    const item = document.getElementById(`health-${area}`);
    if (item) {
      item.className = `health-item tile-link ${h.health || 'good'}`;
      document.getElementById(`score-${area}`).textContent = h.score ?? '—';
      document.getElementById(`status-${area}`).textContent =
        (h.health || '—').replace('_',' ').toUpperCase();
      const bd = h.score_breakdown || {};
      const bdEl = document.getElementById(`breakdown-${area}`);
      if (bdEl && bd.goals_total) {
        const sign = v => v >= 0 ? `<span class="bd-pos">+${v}</span>` : `<span class="bd-neg">${v}</span>`;
        bdEl.innerHTML =
          `<span class="bd-row">Goals <span>${sign(bd.goal_progress_pts)}</span></span>` +
          `<span class="bd-row">Util <span>${sign(bd.utilization_pts)}</span></span>` +
          `<span class="bd-row">Done <span>${sign(bd.milestone_pts)}</span></span>` +
          `<span class="bd-row">Risks <span>${sign(bd.risk_deduction)}</span></span>`;
      }
    }
  });

  const pm = m.practice_summary || {};
  const dm = m.deployment_metrics || {};
  const am = m.asset_metrics || {};
  const ai = m.ai_metrics || {};

  // KPI bars
  setKpi('methodology', pm.methodology_adoption_pct, 90, '%');
  setKpi('reuse',  am.asset_reuse_rate_pct, 80, '%');
  setKpi('cutover', dm.cutover_success_rate_pct, 95, '%');
  setKpiCount('ai', ai.use_cases_deployed, ai.use_cases_target || 10, '');

  // Blue stats
  setText('kpi-headcount', pm.total_consultants);
  setText('kpi-util', `${pm.avg_utilization_pct}%`);
  setText('kpi-assets', am.published_assets);
  setText('kpi-assets-total', am.total_assets);
  const activeInit = (state.initiatives||[]).filter(i => i.status === 'active').length;
  setText('kpi-initiatives', activeInit);
  setText('kpi-deploy', `${dm.reduction_pct ?? 0}%`);

  // Practice goals list
  const goalsEl = document.getElementById('overviewGoalsList');
  const pg = (state.goals?.practice_goals || []).slice(0, 5);
  goalsEl.innerHTML = pg.map(g => {
    const pct = Math.min(100, Math.round((g.current_value / g.target_value) * 100));
    const cls = pct >= 80 ? 'on-track' : pct >= 40 ? 'at-risk' : 'overdue';
    return `
      <div class="goal-row">
        <div class="goal-row-top">
          <div class="goal-title">${g.title}</div>
          <div class="goal-pct">${pct}%</div>
        </div>
        <div class="goal-meta">Due: ${g.due_date} · Owner: ${g.owner}</div>
        <div class="goal-bar"><div class="goal-fill ${cls}" style="width:${pct}%"></div></div>
      </div>`;
  }).join('');

  // Initiatives list
  const initEl = document.getElementById('overviewInitList');
  const inits = (state.initiatives || []).filter(i => i.status === 'active').slice(0, 5);
  initEl.innerHTML = inits.map(i => `
    <div class="init-row">
      <div class="init-row-top">
        <div class="init-title">${i.title}</div>
        <div class="init-pct">${i.progress_pct}%</div>
      </div>
      <div class="init-meta">Owner: ${i.owner} · Due: ${i.target_completion}</div>
      <div class="init-bar"><div class="init-fill" style="width:${i.progress_pct}%"></div></div>
    </div>`).join('');
}

function setKpi(id, current, target, unit) {
  setText(`kpi-${id}`, `${current}${unit}`);
  const pct = Math.min(100, Math.round((current / target) * 100));
  const bar = document.getElementById(`bar-${id}`);
  if (bar) bar.style.width = `${pct}%`;
}
function setKpiCount(id, current, target, unit) {
  setText(`kpi-${id}`, `${current}${unit}`);
  const pct = Math.min(100, Math.round((current / target) * 100));
  const bar = document.getElementById(`bar-${id}`);
  if (bar) bar.style.width = `${pct}%`;
}
function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val ?? '—';
}

// ── Goals ──────────────────────────────────────────────────────────────────
function renderGoals() {
  switchGoalTab(state.currentGoalTab);
}

window.switchGoalTab = function(tab) {
  state.currentGoalTab = tab;
  document.querySelectorAll('.tab-btn').forEach(b => {
    b.classList.toggle('active', b.textContent.toLowerCase().includes(tab === 'practice' ? 'practice' : tab));
  });

  let goals = [];
  if (tab === 'practice') {
    goals = state.goals?.practice_goals || [];
  } else {
    goals = state.goals?.subagent_goals?.[tab] || [];
  }

  const el = document.getElementById('goalContent');
  if (!el) return;
  el.innerHTML = `<div class="goal-cards">${goals.map(renderGoalCard).join('')}</div>`;
};

const _expandedGoals = new Set();

window.toggleGoalDetail = function(id) {
  _expandedGoals.has(id) ? _expandedGoals.delete(id) : _expandedGoals.add(id);
  const expanded = _expandedGoals.has(id);
  const detail = document.getElementById('gd-' + id);
  const btn    = document.getElementById('gdb-' + id);
  if (detail) detail.style.display = expanded ? 'block' : 'none';
  if (btn)    btn.textContent = expanded ? '▲ Less' : '▾ Details';
};

function renderGoalCard(g) {
  const id  = g.id || g.title.replace(/\W+/g, '-').toLowerCase();
  const pct = Math.min(100, Math.round(((g.current_value || 0) / (g.target_value || 1)) * 100));
  const colorClass = pct >= 80 ? 'on-track' : pct >= 40 ? 'at-risk' : 'overdue';
  const fillColor  = colorClass === 'on-track' ? 'var(--green)' : colorClass === 'at-risk' ? 'var(--amber)' : 'var(--red)';
  const badge = g.status || 'in_progress';

  const bulletSection = (items, label, bullet) => {
    if (!items?.length) return '';
    return `<div class="goal-detail-section">
      <div class="goal-detail-heading">${label}</div>
      ${items.map(i => `<div class="goal-detail-item"><span style="color:${bullet};margin-right:7px;flex-shrink:0">•</span>${i}</div>`).join('')}
    </div>`;
  };

  const hasDetail = g.success_criteria?.length || g.composition?.length || g.how_to_achieve?.length || g.requirements?.length;
  const isExpanded = _expandedGoals.has(id);

  const detailBlock = hasDetail ? `
    <div class="goal-detail" id="gd-${id}" style="display:${isExpanded ? 'block' : 'none'}">
      ${bulletSection(g.success_criteria, 'What Success Looks Like', 'var(--green)')}
      ${bulletSection(g.composition,      'What This Goal Consists Of', 'var(--blue)')}
      ${bulletSection(g.how_to_achieve,   'How We Will Achieve This', 'var(--teal)')}
      ${bulletSection(g.requirements,     'What Is Required', 'var(--amber)')}
    </div>` : '';

  return `
    <div class="goal-card" id="gc-${id}">
      <div class="goal-card-header">
        <div class="goal-card-title">${g.title}</div>
        <div style="display:flex;align-items:center;gap:8px;flex-shrink:0">
          <div class="goal-card-badge badge-${badge}">${badge.replace('_',' ')}</div>
          ${hasDetail ? `<button class="goal-expand-btn" id="gdb-${id}" onclick="toggleGoalDetail('${id}')">${isExpanded ? '▲ Less' : '▾ Details'}</button>` : ''}
        </div>
      </div>
      ${g.description ? `<div class="goal-card-desc">${g.description}</div>` : ''}
      <div class="goal-card-meta-row">
        ${g.owner ? `<span class="goal-owner-chip">Owner: <b>${g.owner}</b></span>` : ''}
      </div>
      <div class="goal-card-stats">
        <div class="stat">
          <div class="stat-label">Current</div>
          <div class="stat-val blue">${g.current_value}${g.unit === 'percent' ? '%' : ''}</div>
        </div>
        <div class="stat">
          <div class="stat-label">Target</div>
          <div class="stat-val">${g.target_value}${g.unit === 'percent' ? '%' : ''}</div>
        </div>
        <div class="stat">
          <div class="stat-label">Progress</div>
          <div class="stat-val" style="color:${fillColor}">${pct}%</div>
        </div>
        ${g.due_date ? `<div class="stat"><div class="stat-label">Due</div><div class="stat-val" style="font-size:14px">${g.due_date}</div></div>` : ''}
      </div>
      <div class="goal-card-bar">
        <div class="goal-card-fill" style="width:${pct}%;background:${fillColor}"></div>
      </div>
      ${detailBlock}
    </div>`;
}

// ── Initiatives ─────────────────────────────────────────────────────────────
function renderInitiatives() { filterInitiatives(state.currentInitFilter || 'all'); }

window.filterInitiatives = function(status) {
  state.currentInitFilter = status;
  document.querySelectorAll('#view-initiatives .filter-btn').forEach(b => {
    b.classList.toggle('active', b.textContent.toLowerCase() === status);
  });
  const inits = status === 'all'
    ? (state.initiatives || [])
    : (state.initiatives || []).filter(i => i.status === status);
  const el = document.getElementById('initiativeCards');
  if (!el) return;
  el.innerHTML = inits.map(i => renderInitCard(i)).join('')
    || '<div class="empty-state">No initiatives match this filter.</div>';
};

function renderInitCard(i) {
  const priorityColor = i.priority === 'critical' ? 'var(--red)' : i.priority === 'high' ? 'var(--amber)' : 'var(--blue)';
  const safeId = (i.id || i.title || '').replace(/[^a-z0-9]/gi, '_');

  // Related items derived from focus_areas overlap
  const areas = i.focus_areas || [];
  const relGoals    = _getRelatedGoals(areas, i.related_goals);
  const relConsults = _getRelatedConsultants(areas, i.related_consultants);
  const relAssets   = _getRelatedAssets(areas, i.related_assets);
  const relAi       = _getRelatedAi(areas, i.related_ai);

  const relSection = (icon, label, items, viewFn) => items.length === 0 ? '' : `
    <div class="init-related-group">
      <div class="init-related-label">${icon} ${label}</div>
      <div class="init-related-items">
        ${items.map(r => `<span class="init-related-chip" onclick="${viewFn}">${r}</span>`).join('')}
      </div>
    </div>`;

  const hasRelated = relGoals.length || relConsults.length || relAssets.length || relAi.length;

  return `
    <div class="init-card" id="init-card-${safeId}">
      <div class="init-card-header">
        <div class="init-card-title">${i.title}</div>
        <div style="display:flex;align-items:center;gap:8px">
          <div class="goal-card-badge badge-${i.status}">${i.status.replace('_',' ')}</div>
          <button class="init-expand-btn" onclick="toggleInitExpand('${safeId}')" title="Show details">⌄</button>
        </div>
      </div>
      <div class="init-card-meta">
        <span class="meta-chip">Priority: <b style="color:${priorityColor}">${i.priority}</b></span>
        <span class="meta-chip">Owner: ${i.owner || '—'}</span>
        <span class="meta-chip">Due: ${i.target_completion || '—'}</span>
        <span class="meta-chip">Domains: ${areas.join(', ') || 'All'}</span>
      </div>
      <div class="init-card-desc">${i.description}</div>
      <div class="init-progress-row">
        <div class="init-progress-bar">
          <div class="init-progress-fill" style="width:${i.progress_pct || 0}%"></div>
        </div>
        <div class="init-progress-pct">${i.progress_pct || 0}% complete</div>
      </div>

      <div class="init-expanded" id="init-exp-${safeId}" style="display:none">
        ${i.deliverables?.length ? `
          <div class="init-section">
            <div class="init-section-label">Deliverables</div>
            <div class="init-deliverable-list">
              ${i.deliverables.map(d => `<div class="deliverable-item">◦ ${d}</div>`).join('')}
            </div>
          </div>` : ''}

        ${i.notes ? `
          <div class="init-section">
            <div class="init-section-label">Notes</div>
            <div class="init-notes-text">${i.notes}</div>
          </div>` : ''}

        ${hasRelated ? `
          <div class="init-section">
            <div class="init-section-label">Related Resources</div>
            ${relSection('◎', 'Goals & KPIs', relGoals,   "switchView('goals');switchGoalTab('practice')")}
            ${relSection('◉', 'Consultants',  relConsults, "switchView('consultants')")}
            ${relSection('▣', 'Assets',       relAssets,   "switchView('assets')")}
            ${relSection('◈', 'AI Pipeline',  relAi,       "switchView('ai')")}
            <div class="init-related-group">
              <div class="init-related-label">▥ Methodology</div>
              <div class="init-related-items">
                <span class="init-related-chip" onclick="switchView('methodology')">View Methodology Phases →</span>
              </div>
            </div>
          </div>` : ''}

        <div class="init-card-actions">
          <button class="init-edit-btn" onclick="openInitiativeManager();imOpenEditById('${i.id || safeId}')">✎ Edit Initiative</button>
        </div>
      </div>
    </div>`;
}

function _getRelatedGoals(areas, explicit) {
  if (!state.goals) return explicit || [];
  const all = [
    ...(state.goals.practice_goals || []),
    ...Object.values(state.goals.subagent_goals || {}).flat()
  ];
  const matched = all
    .filter(g => explicit?.includes(g.id) || areas.some(a => (g.focus_area || '').includes(a)))
    .map(g => g.title)
    .slice(0, 4);
  return matched.length ? matched : (explicit || []).slice(0, 4);
}

function _getRelatedConsultants(areas, explicit) {
  if (!state.consultants) return explicit || [];
  return (state.consultants || [])
    .filter(c => areas.includes(c.focus_area) || explicit?.includes(c.name))
    .map(c => `${c.name} (${c.focus_area})`)
    .slice(0, 5);
}

function _getRelatedAssets(areas, explicit) {
  if (!state.assets) return explicit || [];
  return (state.assets || [])
    .filter(a => areas.includes(a.focus_area) || explicit?.includes(a.name))
    .map(a => a.name)
    .slice(0, 4);
}

function _getRelatedAi(areas, explicit) {
  if (!state.aiUseCases) return explicit || [];
  return (state.aiUseCases || [])
    .filter(a => areas.includes(a.focus_area) || explicit?.includes(a.title))
    .map(a => a.title)
    .slice(0, 4);
}

window.toggleInitExpand = function(safeId) {
  const exp = document.getElementById('init-exp-' + safeId);
  const btn = document.querySelector(`#init-card-${safeId} .init-expand-btn`);
  if (!exp) return;
  const open = exp.style.display !== 'none';
  exp.style.display = open ? 'none' : 'block';
  if (btn) btn.textContent = open ? '⌄' : '⌃';
};

// ── Initiative Manager ───────────────────────────────────────────────────────
let _imData = [];
let _imActiveId = null;

window.openInitiativeManager = async function() {
  document.getElementById('initiativeManager').classList.add('open');
  await imLoadData();
};

window.closeInitiativeManager = function() {
  document.getElementById('initiativeManager').classList.remove('open');
};

async function imLoadData() {
  try {
    const resp = await apiFetch(`${API_BASE}/initiatives`);
    _imData = resp.ok ? await resp.json() : (state.initiatives || getSeedInitiatives());
  } catch {
    _imData = state.initiatives || getSeedInitiatives();
  }
  imRenderList();
}

function imRenderList() {
  const el = document.getElementById('imInitiativeList');
  if (!el) return;
  const dotClass = s => ({ active:'pm-dot-deployed', complete:'pm-dot-deployed',
    planning:'pm-dot-planning', at_risk:'gm-dot-atrisk' }[s] || 'pm-dot-planning');
  el.innerHTML = (_imData || []).map(i => `
    <div class="pm-list-item${_imActiveId === i.id ? ' active' : ''}" id="imli-${i.id}">
      <div class="pm-list-item-title">${i.title}</div>
      <div class="pm-list-item-meta">
        <span class="pm-dot ${dotClass(i.status)}"></span>
        <span style="font-size:10px;color:var(--text-muted)">${(i.status||'').replace('_',' ')}</span>
        <span style="font-size:10px;color:var(--text-dim);margin-left:auto">${i.progress_pct||0}%</span>
      </div>
      <div class="pm-list-item-actions">
        <button class="pm-list-edit-btn" onclick="imOpenEdit('${i.id}')">✎ Edit</button>
        <button class="pm-list-del-btn"  onclick="imRemove('${i.id}')">✕</button>
      </div>
    </div>`).join('') || '<div style="font-size:11px;color:var(--text-dim);padding:12px 4px">No initiatives yet</div>';
}

window.imOpenAdd = function() {
  _imActiveId = 'new';
  imRenderForm(null);
  imHighlightActive();
};

window.imOpenEdit = function(id) {
  const item = _imData.find(i => i.id === id);
  if (!item) return;
  _imActiveId = id;
  imRenderForm(item);
  imHighlightActive();
};

window.imOpenEditById = function(id) {
  const item = _imData.find(i => i.id === id);
  if (item) { _imActiveId = id; imRenderForm(item); imHighlightActive(); }
};

function imHighlightActive() {
  document.querySelectorAll('#imInitiativeList .pm-list-item').forEach(el => el.classList.remove('active'));
  if (_imActiveId && _imActiveId !== 'new') {
    document.getElementById('imli-' + _imActiveId)?.classList.add('active');
  }
}

function imConsultantOptions(selected) {
  return (state.consultants || []).map(c =>
    `<option value="${c.name}"${(selected||[]).includes(c.name)?' selected':''}>${c.name} — ${c.focus_area}</option>`
  ).join('');
}

function imRenderForm(i) {
  const isNew = !i;
  const v = (f, fb = '') => i?.[f] ?? fb;
  const fp = document.getElementById('imFormPanel');
  if (!fp) return;

  const focusAreas = ['integrations','conversion','reporting','extend'];
  const faChecks = focusAreas.map(a => `
    <label style="display:flex;align-items:center;gap:6px;font-size:12px;cursor:pointer">
      <input type="checkbox" value="${a}" ${(v('focus_areas',[])).includes(a)?'checked':''}
        onchange="imSyncFocusAreas()"> ${a.charAt(0).toUpperCase()+a.slice(1)}
    </label>`).join('');

  const statusOpts = ['planning','active','complete','on_hold'].map(s =>
    `<option value="${s}"${v('status','planning')===s?' selected':''}>${s.replace('_',' ')}</option>`).join('');
  const priorityOpts = ['low','medium','high','critical'].map(p =>
    `<option value="${p}"${v('priority','medium')===p?' selected':''}>${p}</option>`).join('');
  const typeOpts = ['deployment_methodology','ai_innovation','knowledge_management','methodology','standards','tooling','other'].map(t =>
    `<option value="${t}"${v('type','deployment_methodology')===t?' selected':''}>${t.replace(/_/g,' ')}</option>`).join('');

  fp.innerHTML = `
    <div class="pm-form-scroll">
      <div class="pm-form-title">${isNew ? '＋ Add New Initiative' : 'Editing: ' + i.title}</div>
      <div class="pm-form-subtitle">${isNew ? 'Fill in the details to add a new practice initiative.' : 'Changes save immediately and update the Initiatives view.'}</div>

      <div class="pm-section">
        <div class="pm-section-label">Initiative Details</div>
        <div class="pm-field">
          <label class="pm-field-label">Title *</label>
          <input class="pm-input" id="imTitle" type="text" value="${v('title').replace(/"/g,'&quot;')}" placeholder="Initiative name">
        </div>
        <div class="pm-field">
          <label class="pm-field-label">Description</label>
          <textarea class="pm-textarea" id="imDesc" rows="3" placeholder="What this initiative aims to achieve">${v('description')}</textarea>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
          <div class="pm-field">
            <label class="pm-field-label">Type</label>
            <select class="pm-select" id="imType">${typeOpts}</select>
          </div>
          <div class="pm-field">
            <label class="pm-field-label">Owner</label>
            <input class="pm-input" id="imOwner" type="text" value="${v('owner','CoP Manager').replace(/"/g,'&quot;')}" placeholder="Owner name or role">
          </div>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px">
          <div class="pm-field">
            <label class="pm-field-label">Status</label>
            <select class="pm-select" id="imStatus">${statusOpts}</select>
          </div>
          <div class="pm-field">
            <label class="pm-field-label">Priority</label>
            <select class="pm-select" id="imPriority">${priorityOpts}</select>
          </div>
          <div class="pm-field">
            <label class="pm-field-label">Progress %</label>
            <input class="pm-input" id="imProgress" type="number" min="0" max="100" value="${v('progress_pct',0)}">
          </div>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
          <div class="pm-field">
            <label class="pm-field-label">Start Date</label>
            <input class="pm-input" id="imStart" type="date" value="${v('start_date')}">
          </div>
          <div class="pm-field">
            <label class="pm-field-label">Target Completion</label>
            <input class="pm-input" id="imDue" type="date" value="${v('target_completion')}">
          </div>
        </div>
      </div>

      <div class="pm-section">
        <div class="pm-section-label">Focus Areas</div>
        <div style="display:flex;gap:16px;flex-wrap:wrap" id="imFocusAreas">${faChecks}</div>
      </div>

      <div class="pm-section">
        <div class="pm-section-label">Deliverables <span style="font-size:10px;color:var(--text-dim);font-weight:400;text-transform:none;letter-spacing:0">— one per line</span></div>
        <div class="pm-field">
          <textarea class="pm-textarea" id="imDeliverables" rows="5" placeholder="One deliverable per line">${(v('deliverables',[])).join('\n')}</textarea>
        </div>
      </div>

      <div class="pm-section">
        <div class="pm-section-label">Assign Consultants</div>
        <div style="font-size:10px;color:var(--text-dim);margin-bottom:6px">Hold Ctrl/Cmd to select multiple</div>
        <select class="pm-select" id="imConsultants" multiple size="5" style="height:auto">
          ${imConsultantOptions(v('related_consultants',[]))}
        </select>
      </div>

      <div class="pm-section">
        <div class="pm-section-label">Notes</div>
        <div class="pm-field">
          <textarea class="pm-textarea" id="imNotes" rows="3" placeholder="Additional context, blockers, or decisions">${v('notes')}</textarea>
        </div>
      </div>

      <div class="pm-form-footer" id="imFormFooter">
        <button class="pm-cancel-btn" onclick="imCancel()">Cancel</button>
        <div style="display:flex;gap:8px">
          ${!isNew ? `<button class="pm-delete-btn" onclick="imRemove('${_imActiveId}')">Delete</button>` : ''}
          <button class="pm-save-btn" onclick="imSave(${isNew})">${isNew ? 'Add Initiative' : 'Save Changes'}</button>
        </div>
      </div>
    </div>`;
}

window.imSyncFocusAreas = function() {};  // checkboxes read at save time

window.imCancel = function() {
  _imActiveId = null;
  imRenderList();
  document.getElementById('imFormPanel').innerHTML = `
    <div class="pm-form-empty">
      <div style="font-size:32px;margin-bottom:12px;opacity:0.3">◆</div>
      <div style="color:var(--text-muted);font-size:13px">Select an initiative to edit, or click <strong>Add New Initiative</strong></div>
    </div>`;
};

window.imRemove = async function(id) {
  if (!confirm('Delete this initiative? This cannot be undone.')) return;
  try {
    await apiFetch(`${API_BASE}/initiatives/${id}`, { method: 'DELETE' });
  } catch (e) { console.warn('imRemove offline:', e.message); }
  _imData = _imData.filter(i => i.id !== id);
  state.initiatives = _imData;
  _imActiveId = null;
  imRenderList();
  renderInitiatives();
  document.getElementById('imFormPanel').innerHTML = `
    <div class="pm-form-empty">
      <div style="font-size:32px;margin-bottom:12px;opacity:0.3">✓</div>
      <div style="color:var(--green);font-size:13px">Initiative removed</div>
    </div>`;
};

window.imSave = async function(isNew) {
  const title = document.getElementById('imTitle')?.value?.trim();
  if (!title) { alert('Please enter an initiative title.'); return; }

  const checkedAreas = [...document.querySelectorAll('#imFocusAreas input[type=checkbox]:checked')].map(cb => cb.value);
  const selectedConsultants = [...(document.getElementById('imConsultants')?.selectedOptions || [])].map(o => o.value);

  const body = {
    title,
    description:          document.getElementById('imDesc')?.value?.trim() || '',
    type:                 document.getElementById('imType')?.value || 'deployment_methodology',
    status:               document.getElementById('imStatus')?.value || 'planning',
    priority:             document.getElementById('imPriority')?.value || 'medium',
    owner:                document.getElementById('imOwner')?.value?.trim() || 'CoP Manager',
    start_date:           document.getElementById('imStart')?.value || '',
    target_completion:    document.getElementById('imDue')?.value || '',
    focus_areas:          checkedAreas,
    deliverables:         (document.getElementById('imDeliverables')?.value || '').split('\n').map(l => l.trim()).filter(Boolean),
    progress_pct:         parseInt(document.getElementById('imProgress')?.value) || 0,
    related_consultants:  selectedConsultants,
    related_goals:        isNew ? [] : (_imData.find(i => i.id === _imActiveId)?.related_goals || []),
    related_assets:       isNew ? [] : (_imData.find(i => i.id === _imActiveId)?.related_assets || []),
    related_ai:           isNew ? [] : (_imData.find(i => i.id === _imActiveId)?.related_ai || []),
    notes:                document.getElementById('imNotes')?.value?.trim() || '',
  };

  const url = isNew ? `${API_BASE}/initiatives` : `${API_BASE}/initiatives/${_imActiveId}`;
  let result = { id: _imActiveId && _imActiveId !== 'new' ? _imActiveId : ('local-' + Date.now()), ...body };
  try {
    const resp = await apiFetch(url, {
      method: isNew ? 'POST' : 'PUT',
      body: JSON.stringify(body),
    });
    if (resp.ok) result = await resp.json();
    else console.warn('imSave API error:', await resp.text());
  } catch (e) { console.warn('imSave offline:', e.message); }

  if (isNew) {
    _imData.push(result);
  } else {
    _imData = _imData.map(i => i.id === _imActiveId ? result : i);
  }
  _imActiveId = result.id;
  state.initiatives = _imData;
  imRenderList();
  imHighlightActive();
  renderInitiatives();

  const footer = document.getElementById('imFormFooter');
  if (footer) {
    const flash = document.createElement('span');
    flash.style.cssText = 'color:var(--green);font-size:12px;align-self:center';
    flash.textContent = '✓ Saved';
    footer.prepend(flash);
    setTimeout(() => flash.remove(), 2500);
  }
};

// ── Consultants ─────────────────────────────────────────────────────────────
function renderConsultants() { switchConsultantTab(state.currentConsultantTab); }

window.switchConsultantTab = function(tab) {
  state.currentConsultantTab = tab;
  document.querySelectorAll('#view-consultants .tab-btn').forEach(b => {
    b.classList.toggle('active', b.textContent.toLowerCase() === tab || (tab === 'all' && b.textContent === 'All'));
  });
  const cs = tab === 'all'
    ? (state.consultants || [])
    : (state.consultants || []).filter(c => c.focus_area === tab);
  const el = document.getElementById('consultantGrid');
  if (!el) return;
  el.innerHTML = cs.map(c => {
    const initials = c.name.split(' ').map(w => w[0]).join('').slice(0, 2);
    const util = c.utilization_pct;
    const utilClass = util > 90 ? 'util-high' : util < 60 ? 'util-low' : 'util-good';
    const certChips = (c.certifications || []).map(cert => `<span class="cert-chip">${cert}</span>`).join('');
    const moduleChips = (c.modules || []).map(m => `<div class="skill-chip">${m}</div>`).join('');

    // Initiative assignments via initiative_ids (or fallback to related_consultants)
    const allInits = state.initiatives || [];
    const assignedInits = (c.initiative_ids||[]).length
      ? (c.initiative_ids||[]).map(id => allInits.find(i => i.id === id)).filter(Boolean)
      : allInits.filter(i => (i.related_consultants||[]).includes(c.name));
    const initChips = assignedInits.slice(0,4).map(i => `<span class="cc-init-chip" onclick="switchView('initiatives')" title="${i.title}">${i.title.length > 28 ? i.title.slice(0,28)+'…' : i.title}</span>`).join('');

    // AI use case assignments
    const allAI = state.aiUseCases || [];
    const assignedAI = (c.ai_use_case_ids||[]).map(id => allAI.find(a => a.id === id)).filter(Boolean);
    const aiChips = assignedAI.slice(0,3).map(a => `<span class="cc-ai-chip" onclick="switchView('ai')" title="${a.title}">${a.title.length > 28 ? a.title.slice(0,28)+'…' : a.title}</span>`).join('');

    // Project assignments
    const today = new Date();
    const projRows = (c.project_assignments||[]).map(p => {
      const rd = p.rolloff_date ? new Date(p.rolloff_date) : null;
      const daysLeft = rd ? Math.ceil((rd - today) / 86400000) : null;
      const rdClass = daysLeft === null ? '' : daysLeft < 30 ? 'rolloff-red' : daysLeft < 90 ? 'rolloff-yellow' : 'rolloff-green';
      const rdLabel = rd ? rd.toLocaleDateString('en-US',{month:'short',day:'numeric',year:'2-digit'}) : '';
      const allocBadge = p.allocation_pct ? `<span class="cc-alloc-pct">${p.allocation_pct}%</span>` : '';
      return `<div class="cc-proj-row">
        <div class="cc-proj-name">${p.project_name||''}</div>
        <div class="cc-proj-meta">
          ${p.role ? `<span class="cc-proj-role">${p.role}</span>` : ''}
          ${allocBadge}
          ${rdLabel ? `<span class="cc-rolloff-chip ${rdClass}">↩ ${rdLabel}</span>` : ''}
        </div>
      </div>`;
    }).join('');

    // Accenture profile button
    const profileBtn = c.enterprise_id
      ? `<a class="cc-profile-btn" href="https://people.accenture.com/People/user/${encodeURIComponent(c.enterprise_id)}" target="_blank" title="Accenture Profile: ${c.name}">Ac</a>`
      : '';
    const emailLink = c.email
      ? `<a href="mailto:${c.email}" class="cc-email-link" title="${c.email}">✉</a>`
      : '';

    return `
      <div class="consultant-card">
        <div class="cc-header">
          <div class="cc-avatar">${initials}</div>
          <div style="flex:1;min-width:0">
            <div class="cc-name">${c.name}</div>
            <div class="cc-level">${c.level}</div>
            <div class="cc-area area-${c.focus_area}">${c.focus_area.charAt(0).toUpperCase() + c.focus_area.slice(1)}</div>
          </div>
          <div style="display:flex;flex-direction:column;gap:4px;align-items:flex-end;flex-shrink:0">
            <button class="cc-edit-btn" onclick="openConsultantManager();cmOpenEditByName('${c.name.replace(/'/g, "\\'")}')" title="Edit consultant">✎</button>
            ${profileBtn}
          </div>
        </div>
        <div class="cc-util-row">
          <div class="cc-util-label">Utilization</div>
          <div class="cc-util-bar"><div class="cc-util-fill ${utilClass}" style="width:${util}%"></div></div>
          <div class="cc-util-pct">${util}%</div>
        </div>
        <div class="cc-meta">
          <span>${c.years_experience} yrs exp</span>
          <span>${c.location}</span>
          ${emailLink}
        </div>
        ${projRows ? `<div class="cc-section-label">Project Assignments</div><div class="cc-projs">${projRows}</div>` : ''}
        ${aiChips ? `<div class="cc-section-label">AI Assignments</div><div class="cc-ais">${aiChips}</div>` : ''}
        ${initChips ? `<div class="cc-section-label">Initiatives</div><div class="cc-inits">${initChips}</div>` : ''}
        ${certChips ? `<div class="cc-section-label">Certifications</div><div class="cc-certs">${certChips}</div>` : ''}
        <div class="cc-section-label">Modules</div>
        <div class="cc-skills">${moduleChips}</div>
      </div>`;
  }).join('') || '<div class="empty-state">No consultants found.</div>';
};

// ── Consultant Manager ───────────────────────────────────────────────────────
let _cmData = [];
let _cmActiveId = null;

window.openConsultantManager = async function() {
  document.getElementById('consultantManager').classList.add('open');
  await cmLoadData();
};

window.closeConsultantManager = function() {
  document.getElementById('consultantManager').classList.remove('open');
};

async function cmLoadData() {
  try {
    const resp = await apiFetch(`${API_BASE}/consultants`);
    _cmData = resp.ok ? await resp.json() : (state.consultants || getSeedConsultants());
  } catch {
    _cmData = state.consultants || getSeedConsultants();
  }
  cmRenderList();
}

function cmRenderList() {
  const el = document.getElementById('cmConsultantList');
  if (!el) return;
  const areaColor = { integrations:'pm-dot-deployed', conversion:'gm-dot-atrisk',
    reporting:'pm-dot-planning', extend:'pm-dot-planning' };
  el.innerHTML = (_cmData || []).map(c => `
    <div class="pm-list-item${_cmActiveId === (c.id||c.name) ? ' active' : ''}" id="cmli-${(c.id||c.name).replace(/\s/g,'_')}">
      <div class="pm-list-item-title">${c.name}</div>
      <div class="pm-list-item-meta">
        <span class="pm-dot ${areaColor[c.focus_area]||'pm-dot-planning'}"></span>
        <span style="font-size:10px;color:var(--text-muted)">${c.level}</span>
        <span style="font-size:10px;color:var(--text-dim);margin-left:auto">${c.utilization_pct||0}% util</span>
      </div>
      <div class="pm-list-item-actions">
        <button class="pm-list-edit-btn" onclick="cmOpenEdit('${c.id||c.name}')">✎ Edit</button>
        <button class="pm-list-del-btn"  onclick="cmRemove('${c.id||c.name}')">✕</button>
      </div>
    </div>`).join('') || '<div style="font-size:11px;color:var(--text-dim);padding:12px 4px">No consultants yet</div>';
}

window.cmOpenAdd = function() { _cmActiveId = 'new'; cmRenderForm(null); cmHighlightActive(); };

window.cmOpenEdit = function(id) {
  const item = _cmData.find(c => (c.id||c.name) === id);
  if (!item) return;
  _cmActiveId = id;
  cmRenderForm(item);
  cmHighlightActive();
};

window.cmOpenEditByName = function(name) {
  const item = _cmData.find(c => c.name === name);
  if (item) { _cmActiveId = item.id || item.name; cmRenderForm(item); cmHighlightActive(); }
};

function cmHighlightActive() {
  document.querySelectorAll('#cmConsultantList .pm-list-item').forEach(el => el.classList.remove('active'));
  const key = (_cmActiveId||'').replace(/\s/g,'_');
  if (_cmActiveId && _cmActiveId !== 'new') document.getElementById('cmli-'+key)?.classList.add('active');
}

window.cmUpdateProfilePreview = function(eid) {
  const el = document.getElementById('cmProfilePreview');
  if (!el) return;
  const trimmed = (eid||'').trim();
  if (trimmed) {
    el.innerHTML = `<a href="https://people.accenture.com/People/user/${encodeURIComponent(trimmed)}" target="_blank" style="color:var(--blue);text-decoration:none">people.accenture.com/People/user/${trimmed}</a>`;
  } else {
    el.textContent = 'Enter Enterprise ID to generate profile link';
  }
};

let _cmProjIdx = 0;
function cmProjectRowHTML(idx, proj) {
  proj = proj || {};
  return `<div class="cm-proj-row" id="cmpr-${idx}">
    <input class="pm-input cm-pr-name" placeholder="Project name" value="${(proj.project_name||'').replace(/"/g,'&quot;')}">
    <input class="pm-input cm-pr-role" placeholder="Role / title" value="${(proj.role||'').replace(/"/g,'&quot;')}">
    <input class="pm-input cm-pr-alloc" type="number" min="0" max="100" placeholder="%" value="${proj.allocation_pct||''}">
    <input class="pm-input cm-pr-date" type="date" value="${proj.rolloff_date||''}">
    <button class="cm-proj-del-btn" onclick="this.closest('.cm-proj-row').remove()" title="Remove">✕</button>
  </div>`;
}

window.cmAddProjectRow = function() {
  const container = document.getElementById('cmProjRows');
  if (!container) return;
  const idx = _cmProjIdx++;
  const div = document.createElement('div');
  div.innerHTML = cmProjectRowHTML(idx, {});
  container.appendChild(div.firstElementChild);
};

function cmRenderForm(c) {
  const isNew = !c;
  const v = (f, fb='') => c?.[f] ?? fb;
  const fp = document.getElementById('cmFormPanel');
  if (!fp) return;

  const levelOpts = ['Analyst','Consultant','Senior Consultant','Manager','Senior Manager','Associate Director','Director'].map(l =>
    `<option value="${l}"${v('level','Consultant')===l?' selected':''}>${l}</option>`).join('');
  const areaOpts = ['integrations','conversion','reporting','extend'].map(a =>
    `<option value="${a}"${v('focus_area','integrations')===a?' selected':''}>${a}</option>`).join('');

  // Build project row HTML
  _cmProjIdx = 0;
  const projRowsHTML = (v('project_assignments',[])).map((p,i) => cmProjectRowHTML(i,p)).join('');
  _cmProjIdx = Math.max(_cmProjIdx, (v('project_assignments',[])).length);

  // Build AI use case checkboxes
  const allAI = state.aiUseCases || [];
  const selectedAI = v('ai_use_case_ids',[]);
  const aiCheckboxes = allAI.map(a => `
    <label class="cm-check-label">
      <input type="checkbox" value="${a.id}" ${selectedAI.includes(a.id)?'checked':''}>
      <span class="cm-check-title">${a.title}</span>
      <span class="cm-check-area">${a.focus_area}</span>
    </label>`).join('');

  // Build initiative checkboxes
  const allInits = state.initiatives || [];
  const selectedInits = v('initiative_ids',[]);
  const initCheckboxes = allInits.map(i => `
    <label class="cm-check-label">
      <input type="checkbox" value="${i.id}" ${selectedInits.includes(i.id)?'checked':''}>
      <span class="cm-check-title">${i.title}</span>
    </label>`).join('');

  const eidVal = v('enterprise_id','').replace(/"/g,'&quot;');
  const profilePreviewHTML = eidVal
    ? `<a href="https://people.accenture.com/People/user/${encodeURIComponent(eidVal)}" target="_blank" style="color:var(--blue);text-decoration:none">people.accenture.com/People/user/${eidVal}</a>`
    : 'Enter Enterprise ID to generate profile link';

  fp.innerHTML = `
    <div class="pm-form-scroll">
      <div class="pm-form-title">${isNew ? '＋ Add Consultant' : 'Editing: ' + c.name}</div>
      <div class="pm-form-subtitle">${isNew ? 'Add a consultant to the practice roster.' : 'Changes update the roster view immediately.'}</div>

      <div class="pm-section">
        <div class="pm-section-label">Personal Details</div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
          <div class="pm-field">
            <label class="pm-field-label">Full Name *</label>
            <input class="pm-input" id="cmName" type="text" value="${v('name').replace(/"/g,'&quot;')}" placeholder="First Last">
          </div>
          <div class="pm-field">
            <label class="pm-field-label">Location</label>
            <input class="pm-input" id="cmLocation" type="text" value="${v('location').replace(/"/g,'&quot;')}" placeholder="City, State">
          </div>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
          <div class="pm-field">
            <label class="pm-field-label">Level</label>
            <select class="pm-select" id="cmLevel">${levelOpts}</select>
          </div>
          <div class="pm-field">
            <label class="pm-field-label">Focus Area</label>
            <select class="pm-select" id="cmArea">${areaOpts}</select>
          </div>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px">
          <div class="pm-field">
            <label class="pm-field-label">Years Exp.</label>
            <input class="pm-input" id="cmYears" type="number" min="0" max="40" value="${v('years_experience',1)}">
          </div>
          <div class="pm-field">
            <label class="pm-field-label">Utilization %</label>
            <input class="pm-input" id="cmUtil" type="number" min="0" max="100" value="${v('utilization_pct',0)}">
          </div>
          <div class="pm-field">
            <label class="pm-field-label">Active Projects</label>
            <input class="pm-input" id="cmProjects" type="number" min="0" max="20" value="${v('active_projects',0)}">
          </div>
        </div>
      </div>

      <div class="pm-section">
        <div class="pm-section-label">Accenture Identity</div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
          <div class="pm-field">
            <label class="pm-field-label">Work Email</label>
            <input class="pm-input" id="cmEmail" type="email" value="${v('email','').replace(/"/g,'&quot;')}" placeholder="firstname.lastname@accenture.com">
          </div>
          <div class="pm-field">
            <label class="pm-field-label">Enterprise ID <span style="font-size:9px;color:var(--text-dim)">(profile link)</span></label>
            <input class="pm-input" id="cmEID" type="text" value="${eidVal}" placeholder="firstname.lastname" oninput="cmUpdateProfilePreview(this.value)">
          </div>
        </div>
        <div id="cmProfilePreview" style="margin-top:6px;font-size:10px;color:var(--text-dim)">${profilePreviewHTML}</div>
      </div>

      <div class="pm-section">
        <div class="pm-section-label" style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px">
          Project Assignments
          <button class="cm-proj-add-btn" onclick="cmAddProjectRow()">＋ Add Project</button>
        </div>
        <div class="cm-proj-header">
          <span>Project</span><span>Role</span><span>Alloc %</span><span>Roll-off Date</span><span></span>
        </div>
        <div id="cmProjRows">${projRowsHTML}</div>
      </div>

      <div class="pm-section">
        <div class="pm-section-label">AI Use Case Assignments</div>
        <div class="cm-checkbox-list" id="cmAIList">${aiCheckboxes||'<div style="font-size:11px;color:var(--text-dim)">No AI use cases available</div>'}</div>
      </div>

      <div class="pm-section">
        <div class="pm-section-label">Initiative Assignments</div>
        <div class="cm-checkbox-list" id="cmInitList">${initCheckboxes||'<div style="font-size:11px;color:var(--text-dim)">No initiatives available</div>'}</div>
      </div>

      <div class="pm-section">
        <div class="pm-section-label">Workday Modules <span style="font-size:10px;color:var(--text-dim);font-weight:400;text-transform:none;letter-spacing:0">— one per line</span></div>
        <textarea class="pm-textarea" id="cmModules" rows="4" placeholder="One module per line">${(v('modules',[])).join('\n')}</textarea>
      </div>

      <div class="pm-section">
        <div class="pm-section-label">Certifications <span style="font-size:10px;color:var(--text-dim);font-weight:400;text-transform:none;letter-spacing:0">— one per line</span></div>
        <textarea class="pm-textarea" id="cmCerts" rows="3" placeholder="One certification per line">${(v('certifications',[])).join('\n')}</textarea>
      </div>

      <div class="pm-form-footer" id="cmFormFooter">
        <button class="pm-cancel-btn" onclick="cmCancel()">Cancel</button>
        <div style="display:flex;gap:8px">
          ${!isNew ? `<button class="pm-delete-btn" onclick="cmRemove('${_cmActiveId}')">Delete</button>` : ''}
          <button class="pm-save-btn" onclick="cmSave(${isNew})">${isNew ? 'Add Consultant' : 'Save Changes'}</button>
        </div>
      </div>
    </div>`;
}

window.cmCancel = function() {
  _cmActiveId = null;
  document.getElementById('cmFormPanel').innerHTML = `<div class="pm-form-empty"><div style="font-size:32px;margin-bottom:12px;opacity:0.3">◉</div><div style="color:var(--text-muted);font-size:13px">Select a consultant to edit, or click <strong>Add Consultant</strong></div></div>`;
};

window.cmRemove = async function(id) {
  if (!confirm('Remove this consultant from the roster? This cannot be undone.')) return;
  try { await apiFetch(`${API_BASE}/consultants/${id}`, { method: 'DELETE' }); } catch(e) { console.warn('cmRemove offline:', e.message); }
  _cmData = _cmData.filter(c => (c.id||c.name) !== id);
  state.consultants = _cmData;
  _cmActiveId = null;
  cmRenderList();
  renderConsultants();
  document.getElementById('cmFormPanel').innerHTML = `<div class="pm-form-empty"><div style="font-size:32px;margin-bottom:12px;opacity:0.3">✓</div><div style="color:var(--green);font-size:13px">Consultant removed</div></div>`;
};

window.cmSave = async function(isNew) {
  const name = document.getElementById('cmName')?.value?.trim();
  if (!name) { alert('Please enter the consultant name.'); return; }
  const splitLines = id => (document.getElementById(id)?.value||'').split('\n').map(l=>l.trim()).filter(Boolean);
  const project_assignments = [...document.querySelectorAll('#cmProjRows .cm-proj-row')].map(row => ({
    project_name: row.querySelector('.cm-pr-name')?.value?.trim() || '',
    role:         row.querySelector('.cm-pr-role')?.value?.trim() || '',
    allocation_pct: parseInt(row.querySelector('.cm-pr-alloc')?.value) || 0,
    rolloff_date: row.querySelector('.cm-pr-date')?.value || ''
  })).filter(p => p.project_name);
  const ai_use_case_ids = [...document.querySelectorAll('#cmAIList input[type=checkbox]:checked')].map(cb => cb.value);
  const initiative_ids  = [...document.querySelectorAll('#cmInitList input[type=checkbox]:checked')].map(cb => cb.value);
  const body = {
    name,
    email:           document.getElementById('cmEmail')?.value?.trim() || '',
    enterprise_id:   document.getElementById('cmEID')?.value?.trim() || '',
    location:        document.getElementById('cmLocation')?.value?.trim() || '',
    level:           document.getElementById('cmLevel')?.value || 'Consultant',
    focus_area:      document.getElementById('cmArea')?.value || 'integrations',
    years_experience:parseInt(document.getElementById('cmYears')?.value) || 0,
    utilization_pct: parseInt(document.getElementById('cmUtil')?.value) || 0,
    active_projects: parseInt(document.getElementById('cmProjects')?.value) || 0,
    modules:         splitLines('cmModules'),
    certifications:  splitLines('cmCerts'),
    project_assignments,
    ai_use_case_ids,
    initiative_ids,
  };
  const url = isNew ? `${API_BASE}/consultants` : `${API_BASE}/consultants/${_cmActiveId}`;
  let result = { id: (_cmActiveId && _cmActiveId !== 'new') ? _cmActiveId : ('local-'+Date.now()), ...body };
  try {
    const resp = await apiFetch(url, { method: isNew?'POST':'PUT', body: JSON.stringify(body) });
    if (resp.ok) result = await resp.json();
    else console.warn('cmSave API error:', await resp.text());
  } catch(e) { console.warn('cmSave offline:', e.message); }
  if (isNew) { _cmData.push(result); } else { _cmData = _cmData.map(c => (c.id||c.name) === _cmActiveId ? result : c); }
  _cmActiveId = result.id || result.name;
  state.consultants = _cmData;
  cmRenderList(); cmHighlightActive(); renderConsultants();
  const footer = document.getElementById('cmFormFooter');
  if (footer) { const f=document.createElement('span'); f.style.cssText='color:var(--green);font-size:12px;align-self:center'; f.textContent='✓ Saved'; footer.prepend(f); setTimeout(()=>f.remove(),2500); }
};

// ── Assets ─────────────────────────────────────────────────────────────────
function renderAssets() { filterAssets('all', 'all'); }

window.filterAssets = function(area, status) {
  const prev = state.currentAssetFilter || { area: 'all', status: 'all' };
  const curArea   = area   !== null ? area   : prev.area;
  const curStatus = status !== null ? status : prev.status;
  state.currentAssetFilter = { area: curArea, status: curStatus };

  // Area filter row — first filter-row in the assets view
  document.querySelectorAll('#view-assets .filter-row:first-of-type .filter-btn').forEach(b => {
    const t = b.textContent.toLowerCase().trim();
    b.classList.toggle('active', (curArea === 'all' && t === 'all') || t === curArea);
  });
  // Status filter row
  const statusMap = { 'all': 'all statuses', 'published': 'published', 'in_progress': 'in progress', 'draft': 'draft' };
  document.querySelectorAll('#assetStatusRow .filter-btn').forEach(b => {
    const t = b.textContent.toLowerCase().trim();
    b.classList.toggle('active', t === (statusMap[curStatus] || curStatus));
  });

  let assets = state.assets || [];
  if (curArea !== 'all') assets = assets.filter(a => a.focus_area === curArea);
  if (curStatus !== 'all') assets = assets.filter(a => a.status === curStatus);
  const el = document.getElementById('assetGrid');
  if (!el) return;
  el.innerHTML = assets.map(a => {
    const hasFile = a.file_path && a.file_path !== null;
    const downloadBtn = hasFile
      ? `<a class="asset-download-btn" href="../${a.file_path}" download title="Download real asset file">↓ Download</a>`
      : `<span class="asset-tenant-note" title="${a.file_note || 'Tenant-specific — no portable file'}">Tenant-specific</span>`;
    const portableBadge = hasFile
      ? `<span class="portable-badge">Portable</span>`
      : '';
    return `
      <div class="asset-card ${hasFile ? 'has-file' : ''}">
        <div class="asset-card-header">
          <div class="asset-name">${a.name} ${portableBadge}</div>
          <div class="asset-status-badge status-${a.status}">${a.status.replace('_',' ')}</div>
        </div>
        <div class="asset-format">${a.format} · ${a.type.replace(/_/g,' ')}</div>
        <div class="asset-desc">${a.description}</div>
        ${a.file_note && !hasFile ? `<div class="asset-file-note">${a.file_note}</div>` : ''}
        <div class="asset-footer">
          <div class="asset-tags">
            ${(a.tags||[]).slice(0,4).map(t => `<div class="asset-tag">${t}</div>`).join('')}
          </div>
          <div class="asset-actions">
            ${downloadBtn}
            <div class="asset-deployments"><span class="dep-count">${a.deployments}</span> deployed</div>
          </div>
        </div>
      </div>`;
  }).join('') || '<div class="empty-state">No assets match this filter.</div>';
};

// ── Asset Manager ────────────────────────────────────────────────────────────
let _amData = [];
let _amActiveId = null;

window.openAssetManager = async function() {
  document.getElementById('assetManager').classList.add('open');
  await amLoadData();
};

window.closeAssetManager = function() {
  document.getElementById('assetManager').classList.remove('open');
};

async function amLoadData() {
  try {
    const resp = await apiFetch(`${API_BASE}/assets`);
    _amData = resp.ok ? await resp.json() : (state.assets || getSeedAssets());
  } catch {
    _amData = state.assets || getSeedAssets();
  }
  amRenderList();
}

function amRenderList() {
  const el = document.getElementById('amAssetList');
  if (!el) return;
  const statusDot = s => ({ published:'pm-dot-deployed', in_progress:'pm-dot-development', draft:'pm-dot-planning' }[s]||'pm-dot-planning');
  el.innerHTML = (_amData||[]).map(a => `
    <div class="pm-list-item${_amActiveId===(a.id||a.name)?'  active':''}" id="amli-${(a.id||a.name||'').replace(/[^a-z0-9]/gi,'_')}">
      <div class="pm-list-item-title">${a.name}</div>
      <div class="pm-list-item-meta">
        <span class="pm-dot ${statusDot(a.status)}"></span>
        <span style="font-size:10px;color:var(--text-muted)">${a.focus_area}</span>
        <span style="font-size:10px;color:var(--text-dim);margin-left:auto">${a.status.replace('_',' ')}</span>
      </div>
      <div class="pm-list-item-actions">
        <button class="pm-list-edit-btn" onclick="amOpenEdit('${a.id||a.name}')">✎ Edit</button>
        <button class="pm-list-del-btn"  onclick="amRemove('${a.id||a.name}')">✕</button>
      </div>
    </div>`).join('') || '<div style="font-size:11px;color:var(--text-dim);padding:12px 4px">No assets yet</div>';
}

window.amOpenAdd = function() { _amActiveId = 'new'; amRenderForm(null); amHighlightActive(); };

window.amOpenEdit = function(id) {
  const item = _amData.find(a => (a.id||a.name) === id);
  if (!item) return;
  _amActiveId = id;
  amRenderForm(item);
  amHighlightActive();
};

function amHighlightActive() {
  document.querySelectorAll('#amAssetList .pm-list-item').forEach(el => el.classList.remove('active'));
  const key = (_amActiveId||'').replace(/[^a-z0-9]/gi,'_');
  if (_amActiveId && _amActiveId !== 'new') document.getElementById('amli-'+key)?.classList.add('active');
}

function amRenderForm(a) {
  const isNew = !a;
  const v = (f, fb='') => a?.[f] ?? fb;
  const fp = document.getElementById('amFormPanel');
  if (!fp) return;

  const areaOpts = ['integrations','conversion','reporting','extend'].map(o =>
    `<option value="${o}"${v('focus_area','integrations')===o?' selected':''}>${o}</option>`).join('');
  const typeOpts = ['conversion_template','integration_template','document_template','report_package','standards_document','tooling','extend_application','analytics_model','other'].map(o =>
    `<option value="${o}"${v('type','document_template')===o?' selected':''}>${o.replace(/_/g,' ')}</option>`).join('');
  const statusOpts = ['published','in_progress','draft','deprecated'].map(o =>
    `<option value="${o}"${v('status','draft')===o?' selected':''}>${o.replace('_',' ')}</option>`).join('');

  fp.innerHTML = `
    <div class="pm-form-scroll">
      <div class="pm-form-title">${isNew ? '＋ Add Asset' : 'Editing: ' + a.name}</div>
      <div class="pm-form-subtitle">${isNew ? 'Add an asset to the library.' : 'Changes update the Asset Library immediately.'}</div>

      <div class="pm-section">
        <div class="pm-section-label">Asset Details</div>
        <div class="pm-field">
          <label class="pm-field-label">Name *</label>
          <input class="pm-input" id="amName" type="text" value="${v('name').replace(/"/g,'&quot;')}" placeholder="Asset name">
        </div>
        <div class="pm-field">
          <label class="pm-field-label">Description</label>
          <textarea class="pm-textarea" id="amDesc" rows="3" placeholder="What this asset is and how to use it">${v('description')}</textarea>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
          <div class="pm-field">
            <label class="pm-field-label">Focus Area</label>
            <select class="pm-select" id="amArea">${areaOpts}</select>
          </div>
          <div class="pm-field">
            <label class="pm-field-label">Type</label>
            <select class="pm-select" id="amType">${typeOpts}</select>
          </div>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px">
          <div class="pm-field">
            <label class="pm-field-label">Format</label>
            <input class="pm-input" id="amFormat" type="text" value="${v('format').replace(/"/g,'&quot;')}" placeholder="e.g. Markdown, CSV">
          </div>
          <div class="pm-field">
            <label class="pm-field-label">Status</label>
            <select class="pm-select" id="amStatus">${statusOpts}</select>
          </div>
          <div class="pm-field">
            <label class="pm-field-label">Version</label>
            <input class="pm-input" id="amVersion" type="text" value="${v('version','1.0').replace(/"/g,'&quot;')}" placeholder="1.0">
          </div>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
          <div class="pm-field">
            <label class="pm-field-label">Deployments (count)</label>
            <input class="pm-input" id="amDeploys" type="number" min="0" value="${v('deployments',0)}">
          </div>
          <div class="pm-field">
            <label class="pm-field-label">File Path (optional)</label>
            <input class="pm-input" id="amFilePath" type="text" value="${v('file_path','').replace(/"/g,'&quot;')}" placeholder="assets/files/...">
          </div>
        </div>
        <div class="pm-field">
          <label class="pm-field-label">File Note / Usage Instructions</label>
          <input class="pm-input" id="amFileNote" type="text" value="${v('file_note','').replace(/"/g,'&quot;')}" placeholder="How to use or access this asset">
        </div>
        <div class="pm-field">
          <label class="pm-field-label">Tags <span style="font-size:10px;color:var(--text-dim);font-weight:400;text-transform:none;letter-spacing:0">— comma-separated</span></label>
          <input class="pm-input" id="amTags" type="text" value="${(v('tags',[])).join(', ').replace(/"/g,'&quot;')}" placeholder="tag1, tag2, tag3">
        </div>
      </div>

      <div class="pm-form-footer" id="amFormFooter">
        <button class="pm-cancel-btn" onclick="amCancel()">Cancel</button>
        <div style="display:flex;gap:8px">
          ${!isNew ? `<button class="pm-delete-btn" onclick="amRemove('${_amActiveId}')">Delete</button>` : ''}
          <button class="pm-save-btn" onclick="amSave(${isNew})">${isNew ? 'Add Asset' : 'Save Changes'}</button>
        </div>
      </div>
    </div>`;
}

window.amCancel = function() {
  _amActiveId = null;
  document.getElementById('amFormPanel').innerHTML = `<div class="pm-form-empty"><div style="font-size:32px;margin-bottom:12px;opacity:0.3">▣</div><div style="color:var(--text-muted);font-size:13px">Select an asset to edit, or click <strong>Add Asset</strong></div></div>`;
};

window.amRemove = async function(id) {
  if (!confirm('Remove this asset? This cannot be undone.')) return;
  try { await apiFetch(`${API_BASE}/assets/${id}`, { method: 'DELETE' }); } catch(e) { console.warn('amRemove offline:', e.message); }
  _amData = _amData.filter(a => (a.id||a.name) !== id);
  state.assets = _amData;
  _amActiveId = null;
  amRenderList();
  renderAssets();
  document.getElementById('amFormPanel').innerHTML = `<div class="pm-form-empty"><div style="font-size:32px;margin-bottom:12px;opacity:0.3">✓</div><div style="color:var(--green);font-size:13px">Asset removed</div></div>`;
};

window.amSave = async function(isNew) {
  const name = document.getElementById('amName')?.value?.trim();
  if (!name) { alert('Please enter the asset name.'); return; }
  const rawPath = document.getElementById('amFilePath')?.value?.trim();
  const body = {
    name,
    description:  document.getElementById('amDesc')?.value?.trim() || '',
    focus_area:   document.getElementById('amArea')?.value || 'integrations',
    type:         document.getElementById('amType')?.value || 'document_template',
    format:       document.getElementById('amFormat')?.value?.trim() || '',
    status:       document.getElementById('amStatus')?.value || 'draft',
    version:      document.getElementById('amVersion')?.value?.trim() || '1.0',
    deployments:  parseInt(document.getElementById('amDeploys')?.value) || 0,
    file_path:    rawPath || null,
    file_note:    document.getElementById('amFileNote')?.value?.trim() || '',
    tags:         (document.getElementById('amTags')?.value||'').split(',').map(t=>t.trim()).filter(Boolean),
  };
  const url = isNew ? `${API_BASE}/assets` : `${API_BASE}/assets/${_amActiveId}`;
  let result = { id: (_amActiveId && _amActiveId !== 'new') ? _amActiveId : ('local-'+Date.now()), ...body };
  try {
    const resp = await apiFetch(url, { method: isNew?'POST':'PUT', body: JSON.stringify(body) });
    if (resp.ok) result = await resp.json();
    else console.warn('amSave API error:', await resp.text());
  } catch(e) { console.warn('amSave offline:', e.message); }
  if (isNew) { _amData.push(result); } else { _amData = _amData.map(a => (a.id||a.name) === _amActiveId ? result : a); }
  _amActiveId = result.id || result.name;
  state.assets = _amData;
  amRenderList(); amHighlightActive(); renderAssets();
  const footer = document.getElementById('amFormFooter');
  if (footer) { const f=document.createElement('span'); f.style.cssText='color:var(--green);font-size:12px;align-self:center'; f.textContent='✓ Saved'; footer.prepend(f); setTimeout(()=>f.remove(),2500); }
};

// ── AI Pipeline ─────────────────────────────────────────────────────────────
function renderAIPipeline() {
  const ucs = state.aiUseCases || [];
  const deployed = ucs.filter(u => u.status === 'deployed');
  const inDev    = ucs.filter(u => u.status === 'in_development');
  const planning = ucs.filter(u => u.status === 'planning');

  const summary = document.getElementById('aiPipelineSummary');
  if (summary) {
    summary.innerHTML = `
      <div class="ai-summary-card">
        <div class="ai-sum-count text-green">${deployed.length}</div>
        <div class="ai-sum-label">Deployed</div>
      </div>
      <div class="ai-summary-card">
        <div class="ai-sum-count text-blue">${inDev.length}</div>
        <div class="ai-sum-label">In Development</div>
      </div>
      <div class="ai-summary-card">
        <div class="ai-sum-count text-muted">${planning.length}</div>
        <div class="ai-sum-label">Planning</div>
      </div>`;
  }

  const kanban = document.getElementById('aiKanban');
  if (!kanban) return;
  kanban.innerHTML = `
    ${renderKanbanCol('Deployed', deployed, 'deployed', 'dot-deployed')}
    ${renderKanbanCol('In Development', inDev, 'in_development', 'dot-dev')}
    ${renderKanbanCol('Planning', planning, 'planning', 'dot-planning')}`;
}

const areaColors = {
  integrations: 'text-blue', conversion: 'text-amber',
  reporting: 'text-teal', extend: 'text-purple',
};

function renderReadinessStars(rating) {
  const n = rating || 0;
  return Array.from({length: 5}, (_, i) =>
    `<span class="${i < n ? 'star-filled' : 'star-empty'}">★</span>`
  ).join('');
}

function renderKanbanCol(title, items, status, dotClass) {
  return `
    <div class="kanban-col">
      <div class="kanban-col-header">
        <div class="kanban-dot ${dotClass}"></div>
        ${title} (${items.length})
      </div>
      ${items.map(uc => {
        const hasFile   = uc.file_path != null;
        const hasGuide  = uc.guide_path != null;
        const hasSample = uc.sample_data_path != null;
        const hasApp    = uc.app_url != null;
        const stars     = uc.readiness_rating != null ? renderReadinessStars(uc.readiness_rating) : '';
        // Extract "01"–"08" from file path — only for Python demos, not HTML tools
        const solId = (hasFile && uc.file_path.endsWith('.py')) ? (uc.file_path.match(/\/(\d{2})_/) || [])[1] : null;
        const titleEsc = (uc.title || '').replace(/'/g, "\\'");
        return `
        <div class="ai-card${hasFile ? ' ai-card-has-solution' : ''}">
          <div class="ai-card-header">
            <div class="ai-card-title">${uc.title}</div>
            ${hasApp ? '<span class="ai-solution-badge ai-solution-badge-app">WEB APP</span>' : hasFile ? '<span class="ai-solution-badge">SOLUTION READY</span>' : ''}
          </div>
          <div class="ai-card-area ${areaColors[uc.focus_area] || ''}">${uc.focus_area}${uc.responsible_agent ? ` · ${uc.responsible_agent}` : ''}</div>
          <div class="ai-card-desc">${uc.description?.substring(0, 130)}${uc.description?.length > 130 ? '…' : ''}</div>
          ${stars ? `<div class="ai-readiness"><span class="ai-readiness-label">Readiness</span><span class="ai-stars">${stars}</span></div>` : ''}
          ${uc.readiness_notes ? `<div class="ai-readiness-notes">${uc.readiness_notes}</div>` : ''}
          <div class="ai-card-roi">ROI: ${uc.estimated_roi}</div>
          <div class="ai-card-tech">
            ${(uc.technology||[]).map(t => `<div class="skill-chip">${t}</div>`).join('')}
          </div>
          ${hasApp || hasFile || hasGuide || hasSample ? `
          <div class="ai-card-links">
            ${hasApp    ? `<a class="ai-link-btn ai-open-app-btn" href="${uc.app_url}" target="_blank" rel="noopener">🚀 Open App</a>` : ''}
            ${solId     ? `<button class="ai-link-btn ai-launch-btn" onclick="launchSolution('${solId}','${titleEsc}')">▶ Run Demo</button>` : ''}
            ${hasFile   ? `<a class="ai-link-btn ai-link-solution" href="../${uc.file_path}" download>⬇ Solution</a>` : ''}
            ${hasGuide  ? `<a class="ai-link-btn ai-link-guide"    href="../${uc.guide_path}" download>📋 Guide</a>` : ''}
            ${hasSample ? `<a class="ai-link-btn ai-link-sample"   href="../${uc.sample_data_path}" download>⬇ Sample Data</a>` : ''}
          </div>` : ''}
        </div>`;
      }).join('') || '<div class="text-muted" style="font-size:12px;padding:8px 0">None</div>'}
    </div>`;
}

// ── AI Solution Launcher ──────────────────────────────────────────────────────
function ensureLaunchModal() {
  if (document.getElementById('launchModal')) return;
  const el = document.createElement('div');
  el.id = 'launchModal';
  el.className = 'launch-overlay';
  el.innerHTML = `
    <div class="launch-modal">
      <div class="launch-modal-header">
        <span id="launchTitle" class="launch-modal-title"></span>
        <div style="display:flex;align-items:center;gap:10px">
          <span id="launchStatus" class="launch-status"></span>
          <button class="launch-close" onclick="closeLaunchModal()">✕</button>
        </div>
      </div>
      <pre class="launch-terminal" id="launchTerminal"></pre>
      <div class="launch-modal-footer">
        <span id="launchMeta" class="text-muted" style="font-size:11px"></span>
        <button class="launch-close-btn" onclick="closeLaunchModal()">Close</button>
      </div>
    </div>`;
  document.body.appendChild(el);
}

window.launchSolution = async function(solId, title) {
  ensureLaunchModal();
  const overlay  = document.getElementById('launchModal');
  const terminal = document.getElementById('launchTerminal');
  const titleEl  = document.getElementById('launchTitle');
  const statusEl = document.getElementById('launchStatus');
  const metaEl   = document.getElementById('launchMeta');

  titleEl.textContent  = title;
  terminal.textContent = '';
  metaEl.textContent   = 'Demo mode — no client data used';
  statusEl.textContent = '⟳ Running…';
  statusEl.className   = 'launch-status running';
  overlay.style.display = 'flex';

  try {
    const res = await apiFetch(`${API_BASE}/ai/run/${solId}`, { method: 'POST' });
    if (!res.ok) {
      const msg = await res.text();
      throw new Error(`Server returned ${res.status}: ${msg}`);
    }
    const reader  = res.body.getReader();
    const decoder = new TextDecoder();
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      terminal.textContent += decoder.decode(value, { stream: true });
      terminal.scrollTop = terminal.scrollHeight;
    }
    statusEl.textContent = '✓ Complete';
    statusEl.className   = 'launch-status complete';
  } catch (err) {
    const offline = err.message.includes('fetch') || err.message.includes('Failed to fetch') || err.message.includes('NetworkError');
    if (offline) {
      terminal.textContent =
        '⚠  CoP Manager API server is not running.\n\n' +
        'To enable live in-dashboard execution:\n' +
        '  1. pip install fastapi uvicorn anthropic\n' +
        '  2. python main.py --serve   (in the workday-cop-manager directory)\n' +
        '  3. Reload this dashboard — the Run Demo button will connect automatically.\n\n' +
        'Alternatively, run the solution locally:\n' +
        '  cd assets/files/ai/solutions\n' +
        '  python 0' + solId + '_*.py --demo --no-ai';
    } else {
      terminal.textContent += `\n\n⚠  ${err.message}`;
    }
    statusEl.textContent = '✗ ' + (offline ? 'Server offline' : 'Error');
    statusEl.className   = 'launch-status error';
  }
};

window.closeLaunchModal = function() {
  const el = document.getElementById('launchModal');
  if (el) el.style.display = 'none';
};

// Close on overlay click (outside modal box)
document.addEventListener('click', e => {
  const overlay = document.getElementById('launchModal');
  if (overlay && e.target === overlay) closeLaunchModal();
});

// ── Methodology ─────────────────────────────────────────────────────────────
function renderMethodology() {
  const phases = getMethodologyPhases();
  const el = document.getElementById('methodologyPhases');
  if (!el) return;
  el.innerHTML = phases.map((p, idx) => `
    <div class="phase-card">
      <div class="phase-header" onclick="togglePhase(${idx})">
        <div class="phase-num">${p.phase}</div>
        <div class="phase-title">${p.name}</div>
        <div class="phase-weeks">~${p.standard_weeks} weeks</div>
        <div class="phase-toggle" id="toggle-${idx}">▼</div>
      </div>
      <div class="phase-body" id="phase-body-${idx}">
        <div>
          <div class="phase-section-label">Activities</div>
          ${(p.activities||[]).map(a => `<div class="phase-item">${a}</div>`).join('')}
        </div>
        <div>
          <div class="phase-section-label">Deliverables</div>
          ${(p.deliverables||[]).map(d => `<div class="phase-item">${d}</div>`).join('')}
        </div>
        <div>
          <div class="phase-section-label">Phase Gates</div>
          ${(p.gates||[]).map(g => `<div class="phase-gate">${g}</div>`).join('')}
        </div>
      </div>
    </div>`).join('');
}

window.togglePhase = function(idx) {
  const body = document.getElementById(`phase-body-${idx}`);
  const toggle = document.getElementById(`toggle-${idx}`);
  if (body) body.classList.toggle('open');
  if (toggle) toggle.textContent = body?.classList.contains('open') ? '▲' : '▼';
};

// ── Agent Console ───────────────────────────────────────────────────────────
window.handleChatKey = function(e) {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendAgentQuery(); }
};

window.quickPrompt = function(text) {
  document.getElementById('chatInput').value = text;
  sendAgentQuery();
};

window.sendAgentQuery = async function() {
  const input = document.getElementById('chatInput');
  const query = input.value.trim();
  if (!query) return;

  appendChat('user', query);
  state.chatHistory.push({role:'user', text: query});
  input.value = '';

  const statusEl = document.getElementById('agentStatus');
  const sendBtn  = document.querySelector('.send-btn');
  if (statusEl) { statusEl.textContent = 'Thinking...'; statusEl.className = 'agent-status thinking'; }
  if (sendBtn) sendBtn.disabled = true;

  try {
    const agent = document.getElementById('agentSelector').value;
    const res = await apiFetch(`${API_BASE}/agent/query`, {
      method: 'POST',
      body: JSON.stringify({ query, agent }),
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    if (data.mode === 'offline') {
      appendChat('assistant', '[Offline mode — answering from local data]\n\n' + data.response);
      state.chatHistory.push({role:'assistant', text: '[Offline mode — answering from local data]\n\n' + data.response});
    } else {
      appendChat('assistant', data.response);
      state.chatHistory.push({role:'assistant', text: data.response});
    }
  } catch (err) {
    appendChat('error',
      'Could not reach the CoP Agent.\n\n' +
      'Make sure the API server is running, then reload this page.\n\n' +
      `Error: ${err.message}`);
    state.chatHistory.push({role:'error', text: '(error)'});
  } finally {
    if (statusEl) { statusEl.textContent = 'Ready'; statusEl.className = 'agent-status'; }
    if (sendBtn) sendBtn.disabled = false;
  }
};

function appendChat(role, text) {
  const win = document.getElementById('chatWindow');
  const msg = document.createElement('div');
  msg.className = `chat-message ${role}`;
  msg.textContent = text;
  win.appendChild(msg);
  win.scrollTop = win.scrollHeight;
}

// ── Seed Data (standalone mode) ─────────────────────────────────────────────
function getSeedMetrics() {
  return {
    last_updated: new Date().toISOString().slice(0,10),
    practice_summary: { total_consultants: 11, active_projects: 8, methodology_adoption_pct: 62, avg_utilization_pct: 77, assets_published: 12, assets_in_progress: 4 },
    deployment_metrics: { avg_deployment_weeks_current: 24.2, avg_deployment_weeks_baseline: 26.0, reduction_pct: 6.9, cutover_success_rate_pct: 87 },
    quality_metrics: { defect_escape_rate_pct: 8.2, avg_client_satisfaction: 8.1, data_defect_rate_pct: 11.0 },
    asset_metrics: { total_assets: 27, published_assets: 22, total_deployments_across_assets: 145, asset_reuse_rate_pct: 45 },
    ai_metrics: { use_cases_identified: 12, use_cases_in_development: 4, use_cases_deployed: 3, use_cases_target: 10 },
    focus_area_health: {
      integrations: { health: 'good',    score: 74, open_risks: 1 },
      conversion:   { health: 'at_risk', score: 58, open_risks: 3 },
      reporting:    { health: 'at_risk', score: 61, open_risks: 2 },
      extend:       { health: 'good',    score: 78, open_risks: 1 },
    },
  };
}

function getSeedGoals() {
  return {
    practice_goals: [
      { id: 'pg-1', title: 'Reduce Average Deployment Timeline by 20%', description: 'Reduce full-suite Finance deployment from 26 weeks to 20 weeks by end of FY2026.', kpi: 'time_to_deploy_reduction', target_value: 20, current_value: 7, unit: 'percent', due_date: '2026-12-31', owner: 'CoP Manager', status: 'in_progress' },
      { id: 'pg-2', title: 'Achieve 90% Methodology Adoption Rate', description: 'Ensure 90% of all active projects follow the standard CoP deployment methodology.', kpi: 'methodology_adoption', target_value: 90, current_value: 62, unit: 'percent', due_date: '2026-09-30', owner: 'CoP Manager', status: 'in_progress' },
      { id: 'pg-3', title: 'Deploy 10 AI Use Cases to Clients', description: 'Identify, build, and deploy at least 10 production AI use cases for Workday Financials.', kpi: 'ai_use_cases_deployed', target_value: 10, current_value: 2, unit: 'count', due_date: '2026-12-31', owner: 'CoP Manager', status: 'in_progress' },
      { id: 'pg-4', title: 'Achieve 95% Cutover Success Rate', description: 'Zero rollbacks on go-live cutovers through improved testing frameworks.', kpi: 'cutover_success_rate', target_value: 95, current_value: 87, unit: 'percent', due_date: '2026-12-31', owner: 'CoP Manager', status: 'in_progress' },
      { id: 'pg-5', title: 'Achieve 80%+ Asset Reuse Rate', description: 'Ensure 80% of deployment work reuses existing CoP-approved assets.', kpi: 'asset_reuse_rate', target_value: 80, current_value: 45, unit: 'percent', due_date: '2026-09-30', owner: 'CoP Manager', status: 'in_progress' },
    ],
    subagent_goals: {
      integrations: [
        { id: 'ig-1', title: 'Build Standard Integration Template Library (50 templates)', target_value: 50, current_value: 18, unit: 'count', due_date: '2026-12-31', status: 'in_progress' },
        { id: 'ig-2', title: 'Reduce Integration Build Time by 30%', target_value: 30, current_value: 12, unit: 'percent', due_date: '2026-12-31', status: 'in_progress' },
        { id: 'ig-3', title: 'Develop AI-powered Integration Error Diagnostics', target_value: 1, current_value: 0, unit: 'delivery', due_date: '2026-06-30', status: 'planning' },
      ],
      conversion: [
        { id: 'cg-1', title: 'Publish V2 Conversion Methodology (all 14 objects)', target_value: 14, current_value: 9, unit: 'objects_covered', due_date: '2026-09-30', status: 'in_progress' },
        { id: 'cg-2', title: 'Build Automated Data Validation Framework', target_value: 1, current_value: 0, unit: 'delivery', due_date: '2026-06-30', status: 'in_progress' },
        { id: 'cg-3', title: 'Achieve <5% Data Defect Rate on Go-Live', target_value: 5, current_value: 11, unit: 'percent', due_date: '2026-12-31', status: 'at_risk' },
      ],
      reporting: [
        { id: 'rg-1', title: 'Build Standard Financial Report Package (100+ reports)', target_value: 100, current_value: 43, unit: 'count', due_date: '2026-09-30', status: 'in_progress' },
        { id: 'rg-2', title: 'Publish Report Design Standards Guide', target_value: 1, current_value: 1, unit: 'delivery', due_date: '2026-03-31', status: 'complete' },
        { id: 'rg-3', title: 'Deploy AI Financial Insights Dashboard to 3 clients', target_value: 3, current_value: 0, unit: 'clients', due_date: '2026-12-31', status: 'planning' },
      ],
      extend: [
        { id: 'eg-1', title: 'Build 5 Reusable Extend Application Templates', target_value: 5, current_value: 1, unit: 'count', due_date: '2026-12-31', status: 'in_progress' },
        { id: 'eg-2', title: 'Develop AI Invoice Processing Extend App', target_value: 1, current_value: 0, unit: 'delivery', due_date: '2026-09-30', status: 'in_progress' },
        { id: 'eg-3', title: 'Publish Extend Development Standards', target_value: 1, current_value: 1, unit: 'delivery', due_date: '2026-03-31', status: 'complete' },
      ],
    },
  };
}

function getSeedInitiatives() {
  return [
    { title: 'Workday Finance Deployment Accelerator Program', description: 'Firm-wide initiative to build, test, and publish a set of accelerators that compress the Finance deployment lifecycle across all technical domains.', type: 'deployment_methodology', status: 'active', priority: 'critical', owner: 'CoP Manager', start_date: '2026-01-15', target_completion: '2026-12-31', focus_areas: ['integrations','conversion','reporting','extend'], deliverables: ['Standardized Integration Template Library','Automated Conversion Validation Framework','Standard Financial Report Package','Reusable Extend Application Templates','Go-Live Cutover Toolkit'], progress_pct: 35 },
    { title: 'AI for Workday Financials — Client Advisory Program', description: 'Develop, pilot, and commercialize AI use cases built on or integrated with Workday Financials that drive measurable client value.', type: 'ai_innovation', status: 'active', priority: 'high', owner: 'CoP Manager', start_date: '2026-02-01', target_completion: '2026-12-31', focus_areas: ['integrations','extend','reporting'], deliverables: ['AI Invoice Processing & Exception Handling','AI Financial Anomaly Detection','AI Integration Error Diagnostics','Natural Language Financial Query Tool','AI Supplier Risk Scoring'], progress_pct: 20 },
    { title: 'Workday Finance Technical CoP Knowledge Hub', description: 'Build a centralized, searchable knowledge repository for all CoP methodology, assets, playbooks, and lessons learned.', type: 'knowledge_management', status: 'active', priority: 'high', owner: 'CoP Manager', start_date: '2026-01-01', target_completion: '2026-06-30', focus_areas: ['integrations','conversion','reporting','extend'], deliverables: ['Asset catalog with search and tagging','Methodology playbooks (one per focus area)','Lessons learned database','Training curriculum by role and level'], progress_pct: 50 },
    { title: 'Conversion Methodology V2', description: 'Overhaul the existing conversion methodology to cover all 14 Workday Financial data objects with standardized mapping templates, validation rules, and rehearsal protocols.', type: 'methodology', status: 'active', priority: 'high', owner: 'conversion', start_date: '2026-01-15', target_completion: '2026-09-30', focus_areas: ['conversion'], deliverables: ['Data mapping templates for all 14 objects','Automated validation rule library','Cutover rehearsal protocol','Post-cutover reconciliation guide'], progress_pct: 60 },
    { title: 'Report Design Standards & Certification Program', description: 'Establish firm standards for Workday report design, naming conventions, security group mapping, and performance optimization.', type: 'standards', status: 'planning', priority: 'medium', owner: 'reporting', start_date: '2026-04-01', target_completion: '2026-08-31', focus_areas: ['reporting'], deliverables: ['Report Design Standards Guide','Naming convention taxonomy','Performance optimization playbook','Internal certification assessment'], progress_pct: 10 },
    { title: 'Integration Monitoring & Alerting Framework', description: 'Build a standard approach for deploying integration monitoring, error alerting, and self-healing patterns across all Workday Finance integration deployments.', type: 'tooling', status: 'active', priority: 'medium', owner: 'integrations', start_date: '2026-03-01', target_completion: '2026-09-30', focus_areas: ['integrations'], deliverables: ['Monitoring configuration templates','Error notification workflow','Integration health dashboard','Incident response runbook'], progress_pct: 25 },
  ];
}

function getSeedConsultants() {
  return [
    { name: 'Alex Rivera', focus_area: 'integrations', level: 'Senior Consultant', certifications: ['Workday Integration Fundamentals','Workday Pro Integrations'], modules: ['Studio','Core Connectors','EIB','REST API'], utilization_pct: 80, active_projects: 2, years_experience: 5, location: 'Chicago, IL' },
    { name: 'Jordan Kim', focus_area: 'integrations', level: 'Consultant', modules: ['EIB','Core Connectors','Document Transformation'], utilization_pct: 75, active_projects: 1, years_experience: 2, location: 'New York, NY' },
    { name: 'Morgan Patel', focus_area: 'integrations', level: 'Manager', modules: ['Studio','PECI','PICOF','RaaS','SOAP','REST'], utilization_pct: 65, active_projects: 3, years_experience: 8, location: 'Dallas, TX' },
    { name: 'Casey Thompson', focus_area: 'conversion', level: 'Senior Consultant', modules: ['iLoad','Data Migration','Spreadsheet Import'], utilization_pct: 85, active_projects: 2, years_experience: 6, location: 'Atlanta, GA' },
    { name: 'Riley Nakamura', focus_area: 'conversion', level: 'Consultant', modules: ['iLoad','Spreadsheet Import','Data Validation'], utilization_pct: 90, active_projects: 2, years_experience: 3, location: 'Seattle, WA' },
    { name: 'Drew Williams', focus_area: 'conversion', level: 'Senior Manager', modules: ['iLoad','CCB','Data Migration Strategy','Cutover Planning'], utilization_pct: 60, active_projects: 4, years_experience: 10, location: 'San Francisco, CA' },
    { name: 'Sam Chen', focus_area: 'reporting', level: 'Senior Consultant', modules: ['Custom Reports','Matrix Reports','Composite Reports','Prism Analytics'], utilization_pct: 78, active_projects: 2, years_experience: 5, location: 'Boston, MA' },
    { name: 'Avery Martinez', focus_area: 'reporting', level: 'Consultant', modules: ['Standard Reports','Custom Reports','Dashboard Reports'], utilization_pct: 82, active_projects: 2, years_experience: 2, location: 'Phoenix, AZ' },
    { name: 'Taylor Brooks', focus_area: 'reporting', level: 'Manager', modules: ['Prism Analytics','Discovery Boards','BIRT','Composite Reports','Calculated Fields'], utilization_pct: 70, active_projects: 3, years_experience: 7, location: 'Denver, CO' },
    { name: 'Quinn Rodriguez', focus_area: 'extend', level: 'Senior Consultant', modules: ['App Design','Orchestrations','Business Objects','Related Actions'], utilization_pct: 88, active_projects: 2, years_experience: 4, location: 'Minneapolis, MN' },
    { name: 'Reese Johnson', focus_area: 'extend', level: 'Manager', modules: ['App Design','Orchestrations','Delivered Processes','Custom Validations','REST API'], utilization_pct: 72, active_projects: 3, years_experience: 9, location: 'Austin, TX' },
  ];
}

function getSeedAssets() {
  const P = 'assets/files'; // base path for portable files
  return [
    // ── Integrations ───────────────────────────────────────────────────────
    { name: 'GL Journal Entry Outbound Integration (Studio)', focus_area: 'integrations', type: 'integration_template', format: 'Workday Studio', description: 'Production-tested Studio integration that extracts posted GL journal entries and transforms to standard file format. Tenant-specific.', version: '2.1', status: 'published', deployments: 12, tags: ['gl','journal-entry','studio','outbound'], file_path: null, file_note: 'Tenant-specific Studio bundle — contact integrations lead.' },
    { name: 'Supplier Invoice Inbound Integration (Core Connector)', focus_area: 'integrations', type: 'integration_template', format: 'Core Connector', description: 'Core Connector template for inbound supplier invoice processing from AP automation tools (Tungsten, Medius, Coupa). Tenant-specific.', version: '1.3', status: 'published', deployments: 8, tags: ['ap','supplier-invoice','inbound','core-connector'], file_path: null, file_note: 'Tenant-specific — contact integrations lead.' },
    { name: 'Bank Statement Reconciliation (EIB)', focus_area: 'integrations', type: 'integration_template', format: 'EIB', description: 'EIB template for loading BAI2 bank statement files for automated bank reconciliation in Workday. Tenant-specific EIB definition.', version: '3.0', status: 'published', deployments: 15, tags: ['banking','bai2','reconciliation','eib'], file_path: null, file_note: 'Tenant-specific EIB — contact integrations lead.' },
    { name: 'Interface Design Document (IDD) Template', focus_area: 'integrations', type: 'document_template', format: 'Markdown', description: 'Standard IDD template: overview, technical design, field mapping, error handling, ISU security, testing plan, scheduling, cutover, and approvals. Required for all CoP integration builds.', version: '1.0', status: 'published', deployments: 0, tags: ['idd','integration','design','documentation','standards'], file_path: `${P}/integrations/templates/interface_design_document_template.md`, file_note: 'Portable — copy and complete for every integration build.' },
    // ── Conversion ─────────────────────────────────────────────────────────
    { name: 'Ledger Accounts / COA iLoad Template', focus_area: 'conversion', type: 'conversion_template', format: 'CSV / iLoad', description: 'Standardized COA / Ledger Account migration template. Object 1 in load sequence. Includes field definitions, validation notes, and example rows.', version: '2.0', status: 'published', deployments: 20, tags: ['coa','conversion','iload','gl'], file_path: `${P}/conversion/templates/01_ledger_accounts_coa_iload.csv`, file_note: 'Delete rows 1–3 before loading. Validate with workday_financial_validator.py.' },
    { name: 'Cost Centers iLoad Template', focus_area: 'conversion', type: 'conversion_template', format: 'CSV / iLoad', description: 'Cost Center worktag migration template. Object 2 in load sequence — must load before any transactional data.', version: '1.0', status: 'published', deployments: 0, tags: ['cost-center','conversion','iload','worktag'], file_path: `${P}/conversion/templates/02_cost_centers_iload.csv`, file_note: 'Delete rows 1–3 before loading.' },
    { name: 'Supplier Master iLoad Template', focus_area: 'conversion', type: 'conversion_template', format: 'CSV / iLoad', description: 'Supplier master migration template: ID, name, category, tax ID, currency, payment terms, payment type, address. Object 3 in load sequence.', version: '1.5', status: 'published', deployments: 14, tags: ['supplier','vendor','conversion','iload','ap'], file_path: `${P}/conversion/templates/03_supplier_master_iload.csv`, file_note: 'Validate with workday_financial_validator.py supplier_master.' },
    { name: 'Customer Master iLoad Template', focus_area: 'conversion', type: 'conversion_template', format: 'CSV / iLoad', description: 'Customer master migration template: ID, name, category, currency, payment terms, credit limit, address. Object 4 in load sequence.', version: '1.0', status: 'published', deployments: 0, tags: ['customer','conversion','iload','ar'], file_path: `${P}/conversion/templates/04_customer_master_iload.csv`, file_note: 'Validate with workday_financial_validator.py customer_master.' },
    { name: 'Open AP Invoices iLoad Template', focus_area: 'conversion', type: 'conversion_template', format: 'CSV / iLoad', description: 'Open (unpaid) supplier invoice balance migration. Covers invoice number, dates, currency, amount, cost center, spend category. Object 5 in load sequence.', version: '1.5', status: 'published', deployments: 14, tags: ['ap','open-balances','invoices','conversion','iload'], file_path: `${P}/conversion/templates/05_open_ap_invoices_iload.csv`, file_note: 'Validate with workday_financial_validator.py open_ap_invoices.' },
    { name: 'Open AR Invoices iLoad Template', focus_area: 'conversion', type: 'conversion_template', format: 'CSV / iLoad', description: 'Open (uncollected) customer invoice balance migration. Covers invoice number, dates, currency, amount, revenue category. Object 6 in load sequence.', version: '1.0', status: 'published', deployments: 0, tags: ['ar','open-balances','invoices','conversion','iload'], file_path: `${P}/conversion/templates/06_open_ar_invoices_iload.csv`, file_note: 'Validate with workday_financial_validator.py open_ar_invoices.' },
    { name: 'Fixed Asset Migration Template', focus_area: 'conversion', type: 'conversion_template', format: 'CSV / iLoad', description: 'Fixed asset register migration: Asset ID, class, acquisition date, original cost, accumulated depreciation, net book value, depreciation method, useful life. Object 7 in load sequence.', version: '1.2', status: 'published', deployments: 9, tags: ['fixed-assets','depreciation','conversion','iload'], file_path: `${P}/conversion/templates/07_fixed_assets_iload.csv`, file_note: 'Validate with workday_financial_validator.py fixed_assets.' },
    { name: 'GL Beginning Balances iLoad Template', focus_area: 'conversion', type: 'conversion_template', format: 'CSV / iLoad', description: 'GL opening balance migration: company, ledger account, period (YYYY-MM), currency, debit/credit amounts, cost center. Object 8 — last in load sequence. Trial balance must balance before loading.', version: '1.0', status: 'published', deployments: 0, tags: ['gl','beginning-balances','trial-balance','conversion','iload'], file_path: `${P}/conversion/templates/08_beginning_balances_gl_iload.csv`, file_note: 'CRITICAL: Debits must = Credits. Validate with workday_financial_validator.py beginning_balances_gl.' },
    { name: 'Bank Accounts iLoad Template', focus_area: 'conversion', type: 'conversion_template', format: 'CSV / iLoad', description: 'Bank account master migration: company, institution, account nickname, type, currency, account number, routing (US), IBAN, SWIFT, payment type. Includes routing number format validation.', version: '1.0', status: 'published', deployments: 0, tags: ['bank','banking','conversion','iload','payments'], file_path: `${P}/conversion/templates/09_bank_accounts_iload.csv`, file_note: 'SENSITIVE — restrict access. Validate with workday_financial_validator.py bank_accounts.' },
    { name: 'Open Purchase Orders iLoad Template', focus_area: 'conversion', type: 'conversion_template', format: 'CSV / iLoad', description: 'Open PO balance migration: PO/line number, supplier, date, currency, quantities, unit price, extended amount, open amount. Includes cross-field validation. Object 9 in load sequence.', version: '1.0', status: 'published', deployments: 0, tags: ['po','purchase-order','conversion','iload','procurement'], file_path: `${P}/conversion/templates/10_open_purchase_orders_iload.csv`, file_note: 'Validate with workday_financial_validator.py open_purchase_orders.' },
    { name: 'Data Validation Rules Library (Python)', focus_area: 'conversion', type: 'tooling', format: 'Python Script', description: 'Standalone Python validator for all 10 conversion objects. Checks required fields, data types, valid values, cross-field rules, and duplicate keys. Returns P1/P2/P3 issues with suggested fixes. Enforces go-live gate (0 P1s, ≤5% defect rate). Excel report output.', version: '1.0', status: 'published', deployments: 3, tags: ['validation','python','automation','data-quality','iload'], file_path: `${P}/conversion/validation/workday_financial_validator.py`, file_note: 'pip install pandas openpyxl — then: python workday_financial_validator.py <object> <file.csv>' },
    { name: 'Intercompany Transactions iLoad Template', focus_area: 'conversion', type: 'conversion_template', format: 'CSV / iLoad', description: 'Intercompany journal entry and AR/AP netting migration template. Covers intercompany codes, elimination accounts, and netting rules for multi-entity Workday tenants. Object 11 in load sequence.', version: '0.9', status: 'in_progress', deployments: 0, tags: ['intercompany','conversion','iload','gl','multi-entity'], file_path: null, file_note: 'In development — contact conversion lead.' },
    { name: 'Budget & Planning Data iLoad Template', focus_area: 'conversion', type: 'conversion_template', format: 'CSV / iLoad', description: 'Historical budget and planning data migration template for Adaptive Planning integration. Covers plan versions, cost center allocations, and annual targets. Object 12 in load sequence.', version: '0.8', status: 'in_progress', deployments: 0, tags: ['budget','planning','adaptive','conversion','iload'], file_path: null, file_note: 'In development — contact conversion lead.' },
    { name: 'Cash & Treasury Positions iLoad Template', focus_area: 'conversion', type: 'conversion_template', format: 'CSV / iLoad', description: 'Opening cash position and treasury balance migration for Workday Treasury module. Covers bank balances, investment positions, and cash forecast seed data. Object 13 in load sequence.', version: '0.8', status: 'in_progress', deployments: 0, tags: ['cash','treasury','conversion','iload','banking'], file_path: null, file_note: 'In development — contact conversion lead.' },
    { name: 'Tax Codes & Rates iLoad Template', focus_area: 'conversion', type: 'conversion_template', format: 'CSV / iLoad', description: 'Tax configuration and historical tax position migration. Covers VAT/GST codes, rates, tax authorities, and tax reporting entities. Object 14 in load sequence.', version: '1.0', status: 'published', deployments: 5, tags: ['tax','vat','gst','conversion','iload','compliance'], file_path: `${P}/conversion/templates/14_tax_codes_rates_iload.csv`, file_note: 'Validate with workday_financial_validator.py tax_codes' },
    // ── Reporting ──────────────────────────────────────────────────────────
    { name: 'Standard Financial Close Report Package', focus_area: 'reporting', type: 'report_package', format: 'Workday Custom Reports', description: 'Set of 25 standard financial close reports covering trial balance, income statement, balance sheet, and cash flow. Tenant-specific Workday report definitions.', version: '2.0', status: 'published', deployments: 18, tags: ['close','financial-statements','gl','reporting'], file_path: null, file_note: 'Tenant-specific — contact reporting lead.' },
    { name: 'AP Aging & Cash Requirements Dashboard', focus_area: 'reporting', type: 'report_package', format: 'Workday Dashboard / Discovery Board', description: 'Executive AP aging dashboard with real-time cash requirement projections and payment approval workflow integration. Tenant-specific.', version: '1.1', status: 'published', deployments: 11, tags: ['ap','aging','cash','dashboard'], file_path: null, file_note: 'Tenant-specific — contact reporting lead.' },
    { name: 'Report Design Standards Guide', focus_area: 'reporting', type: 'standards_document', format: 'Markdown', description: 'Complete CoP report design standard: type selection decision tree, naming convention (FIN-MODULE-Desc-vN), BO selection guide, filter & performance rules, security design, calculated field standards, and publication checklist.', version: '1.0', status: 'published', deployments: 0, tags: ['reporting','standards','naming','security','performance'], file_path: `${P}/reporting/standards/report_design_standards_guide.md`, file_note: 'Portable. Required reading before publishing any report to the library.' },
    { name: 'Financial Prism Analytics Data Model', focus_area: 'reporting', type: 'analytics_model', format: 'Workday Prism Analytics', description: 'Pre-built Prism data model connecting GL, AP, AR, and Expenses for cross-module financial analytics. Tenant-specific Prism configuration.', version: '1.0', status: 'in_progress', deployments: 2, tags: ['prism','analytics','cross-module','data-model'], file_path: null, file_note: 'Tenant-specific — contact reporting lead.' },
    // ── Extend ─────────────────────────────────────────────────────────────
    { name: 'Extend Development Standards', focus_area: 'extend', type: 'standards_document', format: 'Markdown', description: 'Mandatory standards for all Extend apps: naming conventions, environment rules, security design (incl. AI data flow restrictions), orchestration error handling, AI/LLM call pattern, CBO standards, testing requirements, and deployment checklist.', version: '1.0', status: 'published', deployments: 0, tags: ['extend','standards','naming','security','ai','orchestration'], file_path: `${P}/extend/standards/extend_development_standards.md`, file_note: 'Portable. Mandatory for all Extend app builds.' },
    { name: 'Extend Solution Design Document (SDD) Template', focus_area: 'extend', type: 'document_template', format: 'Markdown', description: 'Complete SDD template for Extend apps: architecture, security design (incl. AI data flow table), integration points, test cases, deployment steps, rollback plan, and approvals. Required before any Extend app goes to Production.', version: '1.0', status: 'published', deployments: 0, tags: ['extend','sdd','design','documentation','ai'], file_path: `${P}/extend/templates/solution_design_document_template.md`, file_note: 'Portable. Copy and complete for every Extend app build.' },
    { name: 'Invoice Exception Handling App', focus_area: 'extend', type: 'extend_application', format: 'Workday Extend', description: 'Extend app surfacing supplier invoice exceptions with AI-generated summaries and one-click resolution. Tenant-specific bundle.', version: '1.0', status: 'published', deployments: 3, tags: ['ap','exceptions','extend','ai','automation'], file_path: null, file_note: 'Tenant-specific — contact extend lead. SDD template available as portable asset.' },
    { name: 'Expense Policy Compliance Monitor', focus_area: 'extend', type: 'extend_application', format: 'Workday Extend', description: 'Real-time expense report compliance monitoring with automated flagging and AI policy review. In development. Tenant-specific.', version: '1.0', status: 'in_progress', deployments: 1, tags: ['expenses','compliance','extend','automation'], file_path: null, file_note: 'In development — contact extend lead.' },
  ];
}

function getSeedAiUseCases() {
  const P = 'assets/files/ai';
  return [
    { title: 'AI Invoice Processing & Exception Routing', description: 'Use Claude AI to automatically classify AP invoice exceptions, determine the right resolver based on exception type and amount, and generate natural-language explanations for approvers.', focus_area: 'extend', status: 'deployed', client_deployed: true, clients: ['Client A','Client B'], estimated_roi: '40% reduction in invoice processing time, 60% fewer escalations', technology: ['Claude API','Workday Extend','Workday AP'], file_path: `${P}/solutions/01_invoice_exception_classifier.py`, guide_path: `${P}/guides/01_invoice_exception_classifier_deployment_guide.md`, sample_data_path: `${P}/sample_data/sample_invoice_exceptions.csv`, readiness_rating: 4, readiness_notes: 'Production-tested standalone classifier. Extend integration requires SDD completion and tenant ISU setup.', responsible_agent: 'Extend Sub-agent' },
    { title: 'AI Financial Anomaly Detection', description: 'Statistical ML model that identifies unusual GL transactions, posting patterns, and budget variances using z-score and IQR analysis. No API key required — pure Python.', focus_area: 'reporting', status: 'deployed', client_deployed: true, clients: ['Client C'], estimated_roi: 'Catch 90% of material errors before period close', technology: ['Python ML','pandas','scipy'], file_path: `${P}/solutions/02_financial_anomaly_detector.py`, guide_path: `${P}/guides/02_financial_anomaly_detection_deployment_guide.md`, sample_data_path: `${P}/sample_data/sample_gl_transactions.csv`, readiness_rating: 5, readiness_notes: 'No API key required. Runs on any GL export. Tune z-score threshold per client data volume.', responsible_agent: 'Reporting Sub-agent' },
    { title: 'AI Integration Error Diagnostics', description: 'LLM-powered tool that analyzes Workday integration error logs, identifies root cause from an 11-pattern library, and provides plain-English resolution steps for functional consultants.', focus_area: 'integrations', status: 'in_development', client_deployed: false, clients: [], estimated_roi: '70% reduction in integration support tickets, 4hr MTTR reduction', technology: ['Claude API','Workday Studio','Integration Logs'], file_path: `${P}/solutions/03_integration_error_diagnostics.py`, guide_path: `${P}/guides/03_integration_error_diagnostics_deployment_guide.md`, sample_data_path: null, readiness_rating: 4, readiness_notes: 'Strong rule-based pattern library for 11 error types. Validated against real Studio logs.', responsible_agent: 'Integrations Sub-agent' },
    { title: 'Natural Language Financial Query (Ask Workday)', description: 'Ask finance questions in plain English — Claude maps them to RaaS report structures and returns results. Demo-ready with 7 report templates and embedded sample data.', focus_area: 'reporting', status: 'in_development', client_deployed: false, clients: [], estimated_roi: 'Self-service analytics for 80% of ad-hoc reporting requests', technology: ['Claude API','RaaS','REST API','Workday Reporting'], file_path: `${P}/solutions/04_nl_financial_query.py`, guide_path: `${P}/guides/04_nl_financial_query_deployment_guide.md`, sample_data_path: null, readiness_rating: 3, readiness_notes: 'Demo-ready. Live Workday connection needs client RaaS credentials + 3-4 weeks config.', responsible_agent: 'Reporting Sub-agent' },
    { title: 'Expense Policy AI Compliance Reviewer', description: 'Reviews expense report lines against a configurable 9-rule policy engine, flags violations (P1/P2/P3), and uses Claude to generate manager notes and approval recommendations.', focus_area: 'extend', status: 'in_development', client_deployed: false, clients: [], estimated_roi: '90% auto-resolution of policy violations, 3-day faster reimbursement', technology: ['Claude API','Workday Extend','Workday Expenses'], file_path: `${P}/solutions/07_expense_policy_reviewer.py`, guide_path: `${P}/guides/07_expense_policy_guide.md`, sample_data_path: `${P}/sample_data/sample_expense_report.csv`, readiness_rating: 4, readiness_notes: '9-rule policy engine operational. Policy configurable via JSON. Extend SDD required for production.', responsible_agent: 'Extend Sub-agent' },
    { title: 'AI Supplier Risk Scoring', description: 'Four-dimension risk model (data completeness, payment terms, geographic risk, payment type) scoring supplier master data. Claude generates narratives for HIGH/CRITICAL suppliers.', focus_area: 'integrations', status: 'planning', client_deployed: false, clients: [], estimated_roi: '30% reduction in fraudulent/erroneous payments', technology: ['Claude API','pandas','Workday AP'], file_path: `${P}/solutions/05_supplier_risk_scorer.py`, guide_path: `${P}/guides/05_supplier_risk_guide.md`, sample_data_path: `${P}/sample_data/sample_suppliers_for_risk.csv`, readiness_rating: 4, readiness_notes: 'Configurable risk weights and country list. Claude narrative for HIGH/CRITICAL. Ready to pilot.', responsible_agent: 'Integrations Sub-agent' },
    { title: 'AI Conversion Data Mapping Assistant', description: 'Claude analyzes legacy ERP CSV extracts and automatically suggests Workday field mappings with confidence scores, transformation notes, and data quality flags for 6 financial objects.', focus_area: 'conversion', status: 'planning', client_deployed: false, clients: [], estimated_roi: '50% reduction in data mapping analysis time', technology: ['Claude API','pandas','iLoad'], file_path: `${P}/solutions/06_conversion_mapping_assistant.py`, guide_path: `${P}/guides/06_mapping_assistant_guide.md`, sample_data_path: `${P}/sample_data/sample_legacy_erp_extract.csv`, readiness_rating: 4, readiness_notes: 'Supports 6 financial objects. ~85% mapping accuracy in testing. Human review required before load.', responsible_agent: 'Conversion Sub-agent' },
    { title: 'Workday Address & Banking Data Validator', description: 'Client-facing web tool validating address and banking data against official Workday field-mapping rules for 40+ countries. Upload CSV/Excel, get instant per-row feedback, download a load-ready corrected Excel. No Workday tenant or API key required.', focus_area: 'conversion', status: 'deployed', client_deployed: true, clients: [], estimated_roi: '80% reduction in address/banking load errors; same-day correction vs. 3-5 day manual review', technology: ['Flask','pandas','openpyxl','Python'], file_path: `${P}/solutions/08_address_banking_validator/app.py`, app_url: 'http://localhost:8090', guide_path: `${P}/guides/08_address_banking_validator_deployment_guide.md`, sample_data_path: null, readiness_rating: 5, readiness_notes: 'Rules embedded from official Workday Address Field Mapping + Banking & Address Formatting guides. 40+ countries for addresses, 35+ for banking. Runs standalone on port 8090. No API key required.', responsible_agent: 'Conversion Sub-agent' },
  ];
}

function getMethodologyPhases() {
  return [
    { phase: 1, name: 'Discovery & Design', standard_weeks: 4, activities: ['Workday tenant setup and security baseline','Business requirements gathering (BRD / FRD)','Current state integration landscape mapping','Legacy data source analysis','Report requirements catalog','Extend opportunity assessment','CoP asset applicability review'], deliverables: ['Integration Design Document (IDD)','Data Mapping Workbook (DMW)','Report Design Catalog','Extend Solution Design','Technical Architecture Decision Log'], gates: ['Architecture review signed off','Asset reuse plan approved','IDD approved'] },
    { phase: 2, name: 'Build & Configure', standard_weeks: 10, activities: ['Integration development (Studio / Core Connectors / EIB)','Conversion template build and data extract','Custom report development','Extend application build','Unit testing (all technical components)','Initial data validation run'], deliverables: ['Completed integrations (unit tested)','Validated conversion files (mock load)','Custom report package (UAT-ready)','Extend app (QA complete)','Unit Test Evidence Log'], gates: ['Unit test pass rate ≥95%','First mock conversion defect rate <15%','Report peer review complete'] },
    { phase: 3, name: 'Testing', standard_weeks: 6, activities: ['System Integration Testing (SIT)','User Acceptance Testing (UAT)','Parallel conversion run (mock loads 1 & 2)','End-to-end integration testing','Performance testing for high-volume integrations','Report UAT with finance stakeholders','Cutover rehearsal (at least 1 full dress rehearsal)'], deliverables: ['SIT/UAT sign-off document','Mock conversion results (defect rate ≤5%)','Integration test evidence','Cutover rehearsal results','Performance test results'], gates: ['UAT sign-off achieved','Mock conversion defect rate ≤5%','Cutover rehearsal completed within window','Zero P1 open defects'] },
    { phase: 4, name: 'Cutover & Go-Live', standard_weeks: 2, activities: ['Final data extraction from legacy systems','Production conversion loads (all objects in dependency order)','Integration activation and smoke test','Go-live report validation','Hypercare support (2 weeks post go-live)','Post-cutover reconciliation'], deliverables: ['Production load confirmation','Go-live checklist (signed off)','Reconciliation report','Hypercare tracker','Lessons learned log'], gates: ['All conversion objects loaded with zero P1 defects','Integration smoke tests passed','Finance lead sign-off on go-live'] },
    { phase: 5, name: 'Stabilization & Optimization', standard_weeks: 4, activities: ['Hypercare issue resolution','Integration monitoring activation','Report optimization (performance tuning)','Knowledge transfer to client support team','CoP asset contribution (new templates back to library)','Retrospective and lessons learned capture'], deliverables: ['Hypercare closure report','Asset contributions to CoP library','Client support runbook','Project retrospective'], gates: ['Client acceptance signed','Zero open P1/P2 defects','CoP asset contribution submitted'] },
  ];
}

// ── AI Pipeline Manager ────────────────────────────────────────────────────
let _pmData = [];     // full list of use cases
let _pmActiveId = null; // currently edited id, or 'new'
let _pmTags = [];     // technology tags for current form

window.openPipelineManager = async function() {
  document.getElementById('pipelineManager').classList.add('open');
  await pmLoadData();
};

window.closePipelineManager = function() {
  document.getElementById('pipelineManager').classList.remove('open');
};

async function pmLoadData() {
  try {
    const resp = await apiFetch(`${API_BASE}/ai-use-cases`);
    if (resp.ok) {
      _pmData = await resp.json();
    } else {
      // fallback: use seed data
      _pmData = state.aiUseCases || [];
    }
  } catch {
    _pmData = state.aiUseCases || [];
  }
  pmRenderList(_pmData);
}

function pmFilterList(query) {
  const q = (query || '').toLowerCase();
  const filtered = q ? _pmData.filter(uc =>
    uc.title?.toLowerCase().includes(q) ||
    uc.focus_area?.toLowerCase().includes(q) ||
    uc.status?.toLowerCase().includes(q)
  ) : _pmData;
  pmRenderList(filtered);
}

function pmRenderList(items) {
  const container = document.getElementById('pmSolutionList');
  if (!container) return;
  const statusDot = s => ({
    deployed: 'pm-dot-deployed',
    in_development: 'pm-dot-development',
    planning: 'pm-dot-planning'
  }[s] || 'pm-dot-planning');
  const statusLabel = s => ({deployed:'Deployed',in_development:'In Dev.',planning:'Planning'}[s] || s);

  container.innerHTML = items.map(uc => `
    <div class="pm-list-item${_pmActiveId === uc.id ? ' active' : ''}" id="pmli-${uc.id}">
      <div class="pm-list-item-title">${uc.title || 'Untitled'}</div>
      <div class="pm-list-item-meta">
        <span class="pm-dot ${statusDot(uc.status)}"></span>
        <span style="font-size:10px;color:var(--text-muted)">${statusLabel(uc.status)}</span>
        <span class="pm-area-chip pm-area-${uc.focus_area || ''}">${uc.focus_area || ''}</span>
      </div>
      <div class="pm-list-item-actions">
        <button class="pm-list-edit-btn" onclick="pmOpenEdit('${uc.id}')">✎ Edit</button>
        <button class="pm-list-del-btn"  onclick="pmConfirmDelete('${uc.id}')">✕ Remove</button>
      </div>
    </div>
  `).join('') || '<div style="font-size:11px;color:var(--text-dim);padding:12px 4px">No solutions found</div>';
}

window.pmOpenAdd = function() {
  _pmActiveId = 'new';
  _pmTags = [];
  pmRenderForm(null);
  pmHighlightActive();
};

window.pmOpenEdit = function(id) {
  const uc = _pmData.find(u => u.id === id);
  if (!uc) return;
  _pmActiveId = id;
  _pmTags = [...(uc.technology || [])];
  pmRenderForm(uc);
  pmHighlightActive();
};

function pmHighlightActive() {
  document.querySelectorAll('.pm-list-item').forEach(el => el.classList.remove('active'));
  if (_pmActiveId && _pmActiveId !== 'new') {
    document.getElementById(`pmli-${_pmActiveId}`)?.classList.add('active');
  }
}

function pmRenderForm(uc) {
  const isNew = !uc;
  const v = (field, fallback='') => (uc?.[field] ?? fallback);
  const areaColors   = {integrations:'active-blue', conversion:'active-amber', reporting:'active', extend:'active-purple'};

  const modGuide = !isNew && (uc.file_path || uc.app_url) ? `
    <div class="pm-section">
      <div class="pm-section-label">Where to Modify This Solution</div>
      <div class="pm-mod-guide">
        <div class="pm-mod-guide-title">📁 Configuration & Modification Guide</div>
        ${uc.app_url ? `
        <div class="pm-mod-item">
          <span class="pm-mod-icon">🌐</span>
          <div class="pm-mod-text"><strong>Web App:</strong> Open at <span class="pm-mod-code">${uc.app_url}</span> — must be running before you launch. Start with <span class="pm-mod-code">python ${uc.file_path || 'app.py'}</span></div>
        </div>` : ''}
        ${uc.file_path ? `
        <div class="pm-mod-item">
          <span class="pm-mod-icon">📄</span>
          <div class="pm-mod-text"><strong>Solution code:</strong> <span class="pm-mod-code">${uc.file_path}</span> — this is where the core logic lives. Open in VS Code or any text editor.</div>
        </div>` : ''}
        ${uc.guide_path ? `
        <div class="pm-mod-item">
          <span class="pm-mod-icon">📋</span>
          <div class="pm-mod-text"><strong>Deployment guide:</strong> <span class="pm-mod-code">${uc.guide_path}</span> — step-by-step setup and configuration instructions.</div>
        </div>` : ''}
        ${uc.sample_data_path ? `
        <div class="pm-mod-item">
          <span class="pm-mod-icon">📊</span>
          <div class="pm-mod-text"><strong>Sample/test data:</strong> <span class="pm-mod-code">${uc.sample_data_path}</span> — use this to test the solution before using real client data.</div>
        </div>` : ''}
        <div class="pm-mod-item">
          <span class="pm-mod-icon">⚙</span>
          <div class="pm-mod-text"><strong>Key settings to customize:</strong> status, readiness rating, technology stack, ROI description, and client deployment flag — all editable in this form without touching code.</div>
        </div>
        ${(uc.technology||[]).includes('Claude API') ? `
        <div class="pm-mod-item">
          <span class="pm-mod-icon">🤖</span>
          <div class="pm-mod-text"><strong>Requires API key:</strong> This solution uses Claude AI. Set <span class="pm-mod-code">ANTHROPIC_API_KEY</span> in your environment before running.</div>
        </div>` : ''}
      </div>
    </div>` : '';

  const html = `
    <div class="pm-form-title">${isNew ? '＋ Add New Solution' : `Editing: ${uc.title}`}</div>
    <div class="pm-form-subtitle">${isNew ? 'Fill in the details below to add this solution to the AI pipeline.' : 'All changes are saved to the pipeline immediately.'}</div>

    <div id="pmDeleteConfirm" class="pm-delete-confirm">
      <strong>Delete this solution?</strong> This cannot be undone.
      <div class="pm-delete-confirm-btns">
        <button class="pm-confirm-yes" onclick="pmDeleteConfirmed()">Yes, Delete</button>
        <button class="pm-confirm-no"  onclick="pmHideDeleteConfirm()">Cancel</button>
      </div>
    </div>

    <div class="pm-section">
      <div class="pm-section-label">Basic Information</div>
      <div class="pm-field">
        <label class="pm-field-label">Solution Title *</label>
        <input class="pm-input" id="pmTitle" type="text" value="${v('title')}" placeholder="e.g. AI Invoice Exception Classifier">
      </div>
      <div class="pm-field">
        <label class="pm-field-label">Description</label>
        <textarea class="pm-textarea" id="pmDesc" placeholder="What does this solution do? Who is it for?">${v('description')}</textarea>
      </div>
      <div class="pm-two-col">
        <div class="pm-field">
          <label class="pm-field-label">Focus Area</label>
          <div class="pm-seg" id="pmAreaSeg">
            ${['integrations','conversion','reporting','extend'].map(a =>
              `<button type="button" class="pm-seg-btn${v('focus_area')===a?' '+areaColors[a]:''}" onclick="pmSegSelect('pmAreaSeg',this,'${a}','pm-focus-area')" data-val="${a}">${a.charAt(0).toUpperCase()+a.slice(1)}</button>`
            ).join('')}
          </div>
          <input type="hidden" id="pm-focus-area" value="${v('focus_area','integrations')}">
        </div>
        <div class="pm-field">
          <label class="pm-field-label">Pipeline Status</label>
          <div class="pm-seg" id="pmStatusSeg">
            ${[['planning','Planning',''],['in_development','In Dev.','active-blue'],['deployed','Deployed','active-green']].map(([val,lbl,cls]) =>
              `<button type="button" class="pm-seg-btn${v('status')===val?' '+cls:''}" onclick="pmSegSelect('pmStatusSeg',this,'${val}','pm-status')" data-val="${val}">${lbl}</button>`
            ).join('')}
          </div>
          <input type="hidden" id="pm-status" value="${v('status','planning')}">
        </div>
      </div>
    </div>

    <div class="pm-section">
      <div class="pm-section-label">Readiness &amp; Impact</div>
      <div class="pm-field">
        <label class="pm-field-label">Readiness Rating</label>
        <div class="pm-stars" id="pmStars">
          ${[1,2,3,4,5].map(n => `<span class="pm-star${n<=(v('readiness_rating',0))?' lit':''}" onclick="pmSetRating(${n})">★</span>`).join('')}
        </div>
        <input type="hidden" id="pm-rating" value="${v('readiness_rating',0)}">
        <div class="pm-field-hint">1 = Concept only · 3 = Prototype ready · 5 = Production-tested &amp; deployed</div>
      </div>
      <div class="pm-field">
        <label class="pm-field-label">Readiness Notes</label>
        <textarea class="pm-textarea" id="pmReadinessNotes" placeholder="What's needed before this can be deployed to a client?">${v('readiness_notes')}</textarea>
      </div>
      <div class="pm-field">
        <label class="pm-field-label">Estimated ROI / Business Value</label>
        <input class="pm-input" id="pmRoi" type="text" value="${v('estimated_roi')}" placeholder="e.g. 40% reduction in processing time">
      </div>
    </div>

    <div class="pm-section">
      <div class="pm-section-label">Options &amp; Ownership</div>
      <div class="pm-toggle-row">
        <div class="pm-toggle-info">
          <div class="pm-toggle-title">Client Deployed</div>
          <div class="pm-toggle-desc">This solution has been deployed to at least one client</div>
        </div>
        <label class="pm-toggle">
          <input type="checkbox" id="pmClientDeployed" ${v('client_deployed',false)?'checked':''}>
          <span class="pm-toggle-track"></span>
        </label>
      </div>
      <div class="pm-toggle-row">
        <div class="pm-toggle-info">
          <div class="pm-toggle-title">Internal Use Only</div>
          <div class="pm-toggle-desc">For internal practice use; not yet client-facing</div>
        </div>
        <label class="pm-toggle">
          <input type="checkbox" id="pmInternalUse" ${v('internal_use',true)?'checked':''}>
          <span class="pm-toggle-track"></span>
        </label>
      </div>
      <div class="pm-field" style="margin-top:10px">
        <label class="pm-field-label">Responsible Agent / Owner</label>
        <select class="pm-select" id="pmAgent">
          ${['','integrations','conversion','reporting','extend'].map(a =>
            `<option value="${a}" ${v('responsible_agent')===a?'selected':''}>${a||'— Not assigned —'}</option>`
          ).join('')}
        </select>
      </div>
    </div>

    <div class="pm-section">
      <div class="pm-section-label">Technology Stack</div>
      <div class="pm-tags" id="pmTagsDisplay">
        ${_pmTags.map((t,i) => `<span class="pm-tag">${t}<span class="pm-tag-del" onclick="pmRemoveTag(${i})">×</span></span>`).join('')}
      </div>
      <div class="pm-tag-add-row">
        <input class="pm-tag-input" id="pmTagInput" type="text" placeholder="Add technology (press Enter)…" onkeydown="if(event.key==='Enter'){event.preventDefault();pmAddTag();}">
        <button class="pm-tag-add-btn" type="button" onclick="pmAddTag()">Add</button>
      </div>
      <div class="pm-field-hint">e.g. Claude API, Flask, pandas, Workday Extend</div>
    </div>

    <div class="pm-section">
      <div class="pm-section-label">Technical Details (Optional)</div>
      <div class="pm-field">
        <label class="pm-field-label">App URL</label>
        <input class="pm-input" id="pmAppUrl" type="text" value="${v('app_url')}" placeholder="http://localhost:8090 — only if this is a standalone web app">
        <div class="pm-field-hint">If filled in, an "Open App" button will appear on the pipeline card</div>
      </div>
      <div class="pm-two-col">
        <div class="pm-field">
          <label class="pm-field-label">Solution File Path</label>
          <input class="pm-input" id="pmFilePath" type="text" value="${v('file_path')}" placeholder="assets/files/ai/solutions/…">
        </div>
        <div class="pm-field">
          <label class="pm-field-label">Deployment Guide Path</label>
          <input class="pm-input" id="pmGuidePath" type="text" value="${v('guide_path')}" placeholder="assets/files/ai/guides/…">
        </div>
      </div>
      <div class="pm-field">
        <label class="pm-field-label">Sample Data Path</label>
        <input class="pm-input" id="pmSamplePath" type="text" value="${v('sample_data_path')}" placeholder="assets/files/ai/sample_data/…">
      </div>
    </div>

    ${modGuide}

    <div class="pm-form-footer">
      ${!isNew ? `<button class="pm-cancel-btn" style="color:var(--red);border-color:var(--red-dim)" onclick="pmShowDeleteConfirm()">🗑 Delete Solution</button>` : ''}
      <button class="pm-cancel-btn" onclick="pmCancel()">Cancel</button>
      <button class="pm-save-btn" onclick="pmSave(${isNew?'true':'false'})">
        ${isNew ? '＋ Add to Pipeline' : '✓ Save Changes'}
      </button>
    </div>
  `;

  document.getElementById('pmFormPanel').innerHTML = html;
}

window.pmSegSelect = function(segId, btn, val, hiddenId) {
  document.querySelectorAll(`#${segId} .pm-seg-btn`).forEach(b => {
    b.className = b.className.replace(/ active[\w-]*/g, '');
  });
  // pick color based on hidden field id
  const colorMap = {
    'pm-focus-area': {integrations:'active-blue',conversion:'active-amber',reporting:'active',extend:'active-purple'},
    'pm-status':     {planning:'',in_development:'active-blue',deployed:'active-green'},
  };
  const cls = (colorMap[hiddenId] || {})[val] || 'active';
  if (cls) btn.classList.add(cls);
  document.getElementById(hiddenId).value = val;
};

window.pmSetRating = function(n) {
  document.getElementById('pm-rating').value = n;
  document.querySelectorAll('#pmStars .pm-star').forEach((s, i) => {
    s.classList.toggle('lit', i < n);
  });
};

window.pmAddTag = function() {
  const input = document.getElementById('pmTagInput');
  const val = input.value.trim();
  if (!val || _pmTags.includes(val)) { input.value=''; return; }
  _pmTags.push(val);
  input.value = '';
  pmRefreshTags();
};

window.pmRemoveTag = function(i) {
  _pmTags.splice(i, 1);
  pmRefreshTags();
};

function pmRefreshTags() {
  document.getElementById('pmTagsDisplay').innerHTML =
    _pmTags.map((t, i) => `<span class="pm-tag">${t}<span class="pm-tag-del" onclick="pmRemoveTag(${i})">×</span></span>`).join('');
}

window.pmShowDeleteConfirm = function() {
  document.getElementById('pmDeleteConfirm')?.classList.add('show');
  window.scrollTo(0, 0);
};
window.pmHideDeleteConfirm = function() {
  document.getElementById('pmDeleteConfirm')?.classList.remove('show');
};

window.pmDeleteConfirmed = async function() {
  if (!_pmActiveId || _pmActiveId === 'new') return;
  try {
    const resp = await apiFetch(`${API_BASE}/ai-use-cases/${_pmActiveId}`, { method: 'DELETE' });
    if (!resp.ok) throw new Error('Delete failed');
    _pmData = _pmData.filter(u => u.id !== _pmActiveId);
    _pmActiveId = null;
    pmRenderList(_pmData);
    document.getElementById('pmFormPanel').innerHTML = `
      <div class="pm-form-empty">
        <div style="font-size:32px;margin-bottom:12px;opacity:0.3">✓</div>
        <div style="color:var(--green);font-size:13px">Solution removed from pipeline</div>
      </div>`;
    // refresh main kanban
    renderAIPipeline(); state.aiUseCases = _pmData;
  } catch (e) {
    alert('Could not delete: ' + e.message);
  }
};

window.pmCancel = function() {
  _pmActiveId = null;
  document.getElementById('pmFormPanel').innerHTML = `
    <div class="pm-form-empty">
      <div style="font-size:32px;margin-bottom:12px;opacity:0.3">⊙</div>
      <div style="color:var(--text-muted);font-size:13px">Select a solution to edit, or click <strong>Add New Solution</strong></div>
    </div>`;
  pmRenderList(_pmData);
};

// ── Goal Manager ───────────────────────────────────────────────────────────
let _gmTab      = 'practice';
let _gmData     = {};
let _gmActiveId = null;

window.openGoalManager = async function() {
  _gmTab = state.currentGoalTab || 'practice';
  document.getElementById('goalManager').classList.add('open');
  await gmLoadData();
};

window.closeGoalManager = function() {
  document.getElementById('goalManager').classList.remove('open');
};

async function gmLoadData() {
  try {
    const resp = await apiFetch(`${API_BASE}/goals`);
    if (resp.ok) {
      _gmData = await resp.json();
    } else {
      _gmData = state.goals || getSeedGoals();
    }
  } catch {
    _gmData = state.goals || getSeedGoals();
  }
  gmUpdateTabs();
  gmRenderList();
}

function gmUpdateTabs() {
  document.querySelectorAll('.gm-tab-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.tab === _gmTab);
  });
}

window.gmSwitchTab = function(tab) {
  _gmTab = tab;
  _gmActiveId = null;
  gmUpdateTabs();
  gmRenderList();
  document.getElementById('gmFormPanel').innerHTML = `
    <div class="pm-form-empty">
      <div style="font-size:32px;margin-bottom:12px;opacity:0.3">◎</div>
      <div style="color:var(--text-muted);font-size:13px">Select a goal to edit, or click <strong>Add New Goal</strong></div>
    </div>`;
};

function gmRenderList() {
  const goals = _gmTab === 'practice'
    ? (_gmData.practice_goals || [])
    : (_gmData.subagent_goals?.[_gmTab] || []);

  const container = document.getElementById('gmGoalList');
  if (!container) return;

  const dotClass = s => ({ complete:'pm-dot-deployed', in_progress:'pm-dot-development',
    planning:'pm-dot-planning', overdue:'gm-dot-overdue', at_risk:'gm-dot-atrisk' }[s] || 'pm-dot-planning');
  const statusLabel = s => ({ complete:'Complete', in_progress:'In Progress',
    planning:'Planning', overdue:'Overdue', at_risk:'At Risk' }[s] || s);

  container.innerHTML = goals.map(g => {
    const pct = Math.min(100, Math.round(((g.current_value||0)/(g.target_value||1))*100));
    return `
      <div class="pm-list-item${_gmActiveId === g.id ? ' active' : ''}" id="gmli-${g.id}">
        <div class="pm-list-item-title">${g.title || 'Untitled'}</div>
        <div class="pm-list-item-meta">
          <span class="pm-dot ${dotClass(g.status)}"></span>
          <span style="font-size:10px;color:var(--text-muted)">${statusLabel(g.status)}</span>
          <span style="font-size:10px;color:var(--text-dim);margin-left:auto">${pct}%</span>
        </div>
        <div class="pm-list-item-actions">
          <button class="pm-list-edit-btn" onclick="gmOpenEdit('${g.id}')">✎ Edit</button>
          <button class="pm-list-del-btn"  onclick="gmRemove('${g.id}')">✕ Remove</button>
        </div>
      </div>`;
  }).join('') || '<div style="font-size:11px;color:var(--text-dim);padding:12px 4px">No goals in this area yet</div>';
}

window.gmOpenAdd = function() {
  _gmActiveId = 'new';
  gmRenderForm(null);
  gmHighlightActive();
};

window.gmOpenEdit = function(id) {
  const goals = _gmTab === 'practice'
    ? (_gmData.practice_goals || [])
    : (_gmData.subagent_goals?.[_gmTab] || []);
  const g = goals.find(x => x.id === id);
  if (!g) return;
  _gmActiveId = id;
  gmRenderForm(g);
  gmHighlightActive();
};

function gmHighlightActive() {
  document.querySelectorAll('#gmGoalList .pm-list-item').forEach(el => el.classList.remove('active'));
  if (_gmActiveId && _gmActiveId !== 'new') {
    document.getElementById('gmli-' + _gmActiveId)?.classList.add('active');
  }
}

function gmBullets(arr) { return (arr || []).join('\n'); }

function gmRenderForm(g) {
  const isNew = !g;
  const v = (f, fb='') => g?.[f] ?? fb;
  const fp = document.getElementById('gmFormPanel');
  if (!fp) return;

  const statusBtns = ['planning','in_progress','at_risk','overdue','complete'].map(s => {
    const colorMap = { planning:'', in_progress:'active-blue', at_risk:'active-amber', overdue:'', complete:'active-green' };
    const cls = v('status','in_progress') === s ? (' ' + (colorMap[s] || 'active')) : '';
    return `<button class="pm-seg-btn${cls}" data-val="${s}"
      onclick="gmSegClick(this,'gm-status')">${s.replace('_',' ')}</button>`;
  }).join('');

  fp.innerHTML = `
    <div class="pm-form-scroll">
      <div class="pm-form-title">${isNew ? '＋ Add New Goal / KPI' : 'Editing: ' + g.title}</div>
      <div class="pm-form-subtitle">${isNew
        ? 'Fill in the details to add a goal to the ' + _gmTab + ' area.'
        : 'Changes update the goal card immediately after saving.'}</div>

      <div class="pm-section">
        <div class="pm-section-label">Goal Details</div>
        <div class="pm-field">
          <label class="pm-field-label">Title *</label>
          <input class="pm-input" id="gmTitle" type="text" value="${v('title').replace(/"/g,'&quot;')}" placeholder="Goal or KPI name">
        </div>
        <div class="pm-field">
          <label class="pm-field-label">Description</label>
          <textarea class="pm-textarea" id="gmDesc" rows="2" placeholder="Brief description of this goal">${v('description')}</textarea>
        </div>
        <div class="pm-field">
          <label class="pm-field-label">Owner</label>
          <input class="pm-input" id="gmOwner" type="text" value="${v('owner','CoP Manager').replace(/"/g,'&quot;')}" placeholder="e.g. CoP Manager, Integrations Lead">
        </div>
      </div>

      <div class="pm-section">
        <div class="pm-section-label">Status</div>
        <div style="display:flex;flex-wrap:wrap;gap:6px" id="gmStatusGroup">${statusBtns}</div>
        <input type="hidden" id="gm-status" value="${v('status','in_progress')}">
      </div>

      <div class="pm-section">
        <div class="pm-section-label">Progress &amp; Target</div>
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:10px">
          <div class="pm-field">
            <label class="pm-field-label">Current</label>
            <input class="pm-input" id="gmCurrent" type="number" step="any" value="${v('current_value',0)}">
          </div>
          <div class="pm-field">
            <label class="pm-field-label">Target</label>
            <input class="pm-input" id="gmTarget" type="number" step="any" value="${v('target_value',100)}">
          </div>
          <div class="pm-field">
            <label class="pm-field-label">Unit</label>
            <select class="pm-select" id="gmUnit">
              ${['percent','count','delivery','clients','objects_covered'].map(u =>
                `<option value="${u}"${v('unit','percent')===u?' selected':''}>${u}</option>`).join('')}
            </select>
          </div>
          <div class="pm-field">
            <label class="pm-field-label">Due Date</label>
            <input class="pm-input" id="gmDue" type="date" value="${v('due_date')}">
          </div>
        </div>
      </div>

      <div class="pm-section">
        <div class="pm-section-label">Detail &amp; Context <span style="font-size:10px;color:var(--text-dim);font-weight:400;text-transform:none;letter-spacing:0">— one item per line, shown as bullets on the card</span></div>
        <div class="pm-field">
          <label class="pm-field-label">What Success Looks Like</label>
          <textarea class="pm-textarea" id="gmSuccess" rows="3" placeholder="One success criterion per line">${gmBullets(v('success_criteria',[]))}</textarea>
        </div>
        <div class="pm-field">
          <label class="pm-field-label">What This Goal Consists Of</label>
          <textarea class="pm-textarea" id="gmComposition" rows="3" placeholder="One component per line">${gmBullets(v('composition',[]))}</textarea>
        </div>
        <div class="pm-field">
          <label class="pm-field-label">How We Will Achieve This</label>
          <textarea class="pm-textarea" id="gmHowTo" rows="3" placeholder="One action item per line">${gmBullets(v('how_to_achieve',[]))}</textarea>
        </div>
        <div class="pm-field">
          <label class="pm-field-label">What Is Required</label>
          <textarea class="pm-textarea" id="gmRequirements" rows="3" placeholder="One requirement per line">${gmBullets(v('requirements',[]))}</textarea>
        </div>
      </div>

      <div class="pm-form-footer" id="gmFormFooter">
        <button class="pm-cancel-btn" onclick="gmCancel()">Cancel</button>
        <div style="display:flex;gap:8px">
          ${!isNew ? `<button class="pm-delete-btn" onclick="gmRemove('${_gmActiveId}')">Delete</button>` : ''}
          <button class="pm-save-btn" onclick="gmSave(${isNew})">${isNew ? 'Add Goal' : 'Save Changes'}</button>
        </div>
      </div>
    </div>`;
}

window.gmSegClick = function(btn, hiddenId) {
  const val = btn.dataset.val;
  const colorMap = { planning:'active', in_progress:'active-blue', at_risk:'active-amber', overdue:'active', complete:'active-green' };
  btn.closest('[id^="gm"]').querySelectorAll('.pm-seg-btn').forEach(b => {
    b.className = b.className.replace(/ active[\w-]*/g, '');
  });
  btn.classList.add(colorMap[val] || 'active');
  document.getElementById(hiddenId).value = val;
};

window.gmRemove = function(id) {
  if (!confirm('Delete this goal? This cannot be undone.')) return;
  _gmActiveId = id;
  gmDeleteConfirmed();
};

async function gmDeleteConfirmed() {
  const endpoint = _gmTab === 'practice'
    ? `${API_BASE}/goals/practice/${_gmActiveId}`
    : `${API_BASE}/goals/${_gmTab}/${_gmActiveId}`;

  try {
    const resp = await fetch(endpoint, { method: 'DELETE' });
    if (!resp.ok) throw new Error(await resp.text());
  } catch (e) {
    console.warn('gmDelete API error (removing from local view):', e.message);
  }

  if (_gmTab === 'practice') {
    _gmData.practice_goals = (_gmData.practice_goals || []).filter(g => g.id !== _gmActiveId);
  } else {
    if (_gmData.subagent_goals?.[_gmTab]) {
      _gmData.subagent_goals[_gmTab] = _gmData.subagent_goals[_gmTab].filter(g => g.id !== _gmActiveId);
    }
  }
  _gmActiveId = null;
  state.goals = _gmData;
  gmRenderList();
  renderGoals();
  document.getElementById('gmFormPanel').innerHTML = `
    <div class="pm-form-empty">
      <div style="font-size:32px;margin-bottom:12px;opacity:0.3">✓</div>
      <div style="color:var(--green);font-size:13px">Goal removed</div>
    </div>`;
}

window.gmCancel = function() {
  _gmActiveId = null;
  gmRenderList();
  document.getElementById('gmFormPanel').innerHTML = `
    <div class="pm-form-empty">
      <div style="font-size:32px;margin-bottom:12px;opacity:0.3">◎</div>
      <div style="color:var(--text-muted);font-size:13px">Select a goal to edit, or click <strong>Add New Goal</strong></div>
    </div>`;
};

const gmLines = id => (document.getElementById(id)?.value || '').split('\n').map(l => l.trim()).filter(Boolean);

window.gmSave = async function(isNew) {
  const title = document.getElementById('gmTitle')?.value?.trim();
  if (!title) { alert('Please enter a goal title.'); return; }

  const body = {
    title,
    description:      document.getElementById('gmDesc')?.value?.trim() || '',
    owner:            document.getElementById('gmOwner')?.value?.trim() || 'CoP Manager',
    status:           document.getElementById('gm-status')?.value || 'in_progress',
    current_value:    parseFloat(document.getElementById('gmCurrent')?.value) || 0,
    target_value:     parseFloat(document.getElementById('gmTarget')?.value) || 100,
    unit:             document.getElementById('gmUnit')?.value || 'percent',
    due_date:         document.getElementById('gmDue')?.value || '',
    success_criteria: gmLines('gmSuccess'),
    composition:      gmLines('gmComposition'),
    how_to_achieve:   gmLines('gmHowTo'),
    requirements:     gmLines('gmRequirements'),
    kpi: '', sub_goals: [],
  };

  const endpoint = isNew
    ? (_gmTab === 'practice' ? `${API_BASE}/goals/practice` : `${API_BASE}/goals/${_gmTab}`)
    : (_gmTab === 'practice' ? `${API_BASE}/goals/practice/${_gmActiveId}` : `${API_BASE}/goals/${_gmTab}/${_gmActiveId}`);

  let result = { id: (_gmActiveId && _gmActiveId !== 'new') ? _gmActiveId : ('local-' + Date.now()), ...body };
  try {
    const resp = await fetch(endpoint, {
      method: isNew ? 'POST' : 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (resp.ok) result = await resp.json();
    else console.warn('gmSave API error:', await resp.text());
  } catch (e) {
    console.warn('gmSave (offline mode):', e.message);
  }

  if (_gmTab === 'practice') {
    if (isNew) {
      _gmData.practice_goals = [...(_gmData.practice_goals || []), result];
    } else {
      _gmData.practice_goals = (_gmData.practice_goals || []).map(g => g.id === _gmActiveId ? result : g);
    }
  } else {
    _gmData.subagent_goals = _gmData.subagent_goals || {};
    _gmData.subagent_goals[_gmTab] = _gmData.subagent_goals[_gmTab] || [];
    if (isNew) {
      _gmData.subagent_goals[_gmTab].push(result);
    } else {
      _gmData.subagent_goals[_gmTab] = _gmData.subagent_goals[_gmTab].map(g => g.id === _gmActiveId ? result : g);
    }
  }

  _gmActiveId = result.id;
  state.goals = _gmData;
  gmRenderList();
  gmHighlightActive();
  renderGoals();

  const footer = document.getElementById('gmFormFooter');
  if (footer) {
    const flash = document.createElement('span');
    flash.style.cssText = 'color:var(--green);font-size:12px;align-self:center';
    flash.textContent = '✓ Saved';
    footer.prepend(flash);
    setTimeout(() => flash.remove(), 2500);
  }
};

window.pmSave = async function(isNew) {
  const title = document.getElementById('pmTitle')?.value?.trim();
  if (!title) { alert('Please enter a solution title.'); return; }

  const body = {
    title,
    description:      document.getElementById('pmDesc')?.value || '',
    focus_area:       document.getElementById('pm-focus-area')?.value || 'integrations',
    status:           document.getElementById('pm-status')?.value || 'planning',
    client_deployed:  document.getElementById('pmClientDeployed')?.checked || false,
    internal_use:     document.getElementById('pmInternalUse')?.checked || true,
    estimated_roi:    document.getElementById('pmRoi')?.value || '',
    technology:       _pmTags,
    file_path:        document.getElementById('pmFilePath')?.value?.trim() || null,
    app_url:          document.getElementById('pmAppUrl')?.value?.trim() || null,
    guide_path:       document.getElementById('pmGuidePath')?.value?.trim() || null,
    sample_data_path: document.getElementById('pmSamplePath')?.value?.trim() || null,
    readiness_rating: parseInt(document.getElementById('pm-rating')?.value) || null,
    readiness_notes:  document.getElementById('pmReadinessNotes')?.value || '',
    responsible_agent:document.getElementById('pmAgent')?.value || '',
    clients: [],
  };

  try {
    let result;
    if (isNew) {
      const resp = await apiFetch(`${API_BASE}/ai-use-cases`, {
        method: 'POST', body: JSON.stringify(body),
      });
      if (!resp.ok) throw new Error(await resp.text());
      result = await resp.json();
      _pmData.push(result);
    } else {
      const resp = await apiFetch(`${API_BASE}/ai-use-cases/${_pmActiveId}`, {
        method: 'PUT', body: JSON.stringify(body),
      });
      if (!resp.ok) throw new Error(await resp.text());
      result = await resp.json();
      const idx = _pmData.findIndex(u => u.id === _pmActiveId);
      if (idx >= 0) _pmData[idx] = result;
    }

    _pmActiveId = result.id;
    pmRenderList(_pmData);
    pmHighlightActive();
    // flash save confirmation
    const footer = document.querySelector('.pm-form-footer');
    if (footer) {
      const saved = document.createElement('span');
      saved.style.cssText = 'color:var(--green);font-size:12px;align-self:center';
      saved.textContent = '✓ Saved';
      footer.prepend(saved);
      setTimeout(() => saved.remove(), 2500);
    }
    // refresh main kanban
    state.aiUseCases = _pmData; renderAIPipeline();
  } catch (e) {
    alert('Could not save: ' + e.message + '\n\nNote: requires the API server to be running on port 8000.');
  }
};
