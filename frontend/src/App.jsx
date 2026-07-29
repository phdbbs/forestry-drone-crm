import React from 'react';
import ReactDOM from 'react-dom/client';
import * as Recharts from 'recharts';
import PropTypes from 'prop-types';
import { createPortal } from 'react-dom';
import { api, fetchMe, login as doLogin, logout as doLogout } from './api';


// ========== Safety Checks ==========
if (!React || !ReactDOM) {
  document.getElementById('error-display').style.display = 'block';
  document.getElementById('error-message').textContent = 'React or ReactDOM failed to load. Check your internet connection.';
  throw new Error('React/ReactDOM not available');
}

const { useState, useEffect, useRef, useCallback, useMemo } = React;

// Safe Recharts access
const AreaChart = Recharts.AreaChart;
const BarChart = Recharts.BarChart;
const PieChart = Recharts.PieChart;
const LineChart = Recharts.LineChart;
const Area = Recharts.Area;
const Bar = Recharts.Bar;
const Pie = Recharts.Pie;
const Cell = Recharts.Cell;
const XAxis = Recharts.XAxis;
const YAxis = Recharts.YAxis;
const CartesianGrid = Recharts.CartesianGrid;
const Tooltip = Recharts.Tooltip;
const Legend = Recharts.Legend;
const ResponsiveContainer = Recharts.ResponsiveContainer || function(p) { return p.children || null; };

// ========== SVG Icon Components ==========
const IconGrid = () => (<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>);
const IconUsers = () => (<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87"/><path d="M16 3.13a4 4 0 010 7.75"/></svg>);
const IconSearch = () => (<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>);
const IconTarget = () => (<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/></svg>);
const IconUserCircle = () => (<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="8" r="3"/><path d="M6.168 18.849A4 4 0 0110 16h4a4 4 0 013.834 2.855"/></svg>);
const IconPhone = () => (<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07 19.5 19.5 0 01-6-6 19.79 19.79 0 01-3.07-8.67A2 2 0 014.11 2h3a2 2 0 012 1.72c.127.96.361 1.903.7 2.81a2 2 0 01-.45 2.11L8.09 9.91a16 16 0 006 6l1.27-1.27a2 2 0 012.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0122 16.92z"/></svg>);
const IconKanban = () => (<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="5" height="18" rx="1"/><rect x="10" y="3" width="5" height="12" rx="1"/><rect x="17" y="3" width="5" height="7" rx="1"/></svg>);
const IconChart = () => (<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>);
const IconBell = () => (<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 01-3.46 0"/></svg>);
const IconSettings = () => (<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 01-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/></svg>);
const IconPlus = () => (<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>);
const IconClock = () => (<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>);
const IconCheck = () => (<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg>);
const IconX = () => (<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>);
const IconArrowRight = () => (<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>);
const IconArrowDown = () => (<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><polyline points="19 12 12 19 5 12"/></svg>);
const IconArrowUp = () => (<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="19" x2="12" y2="5"/><polyline points="5 12 12 5 19 12"/></svg>);
const IconCalendar = () => (<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>);
const IconBuilding = () => (<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="4" y="2" width="16" height="20" rx="1"/><line x1="9" y1="6" x2="9" y2="6.01"/><line x1="15" y1="6" x2="15" y2="6.01"/><line x1="9" y1="10" x2="9" y2="10.01"/><line x1="15" y1="10" x2="15" y2="10.01"/><line x1="9" y1="14" x2="9" y2="14.01"/><line x1="15" y1="14" x2="15" y2="14.01"/><path d="M9 22v-4h6v4"/></svg>);
const IconEye = () => (<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>);
const IconEdit = () => (<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>);
const IconLightning = () => (<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>);
const IconShield = () => (<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>);
const IconDollar = () => (<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6"/></svg>);
const IconActivity = () => (<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>);
const IconDownload = () => (<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>);
const IconFire = () => (<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22c-4.97 0-9-2.69-9-6s4.03-6 9-6c.28-3.5 2-8 5-10 0 4 3 6 3 10s-3.03 6-8 6z"/><path d="M12 22c2.21 0 4-1.12 4-3s-1.79-3-4-3-4 1.12-4 3 1.79 3 4 3z"/></svg>);
const IconLayers = () => (<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/></svg>);
const IconPieChart = () => (<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21.21 15.89A10 10 0 118 2.83"/><path d="M22 12A10 10 0 0012 2v10z"/></svg>);
const IconTrend = () => (<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>);
const IconDrone = () => (<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M5 5l4 4"/><path d="M19 5l-4 4"/><path d="M5 19l4-4"/><path d="M19 19l-4-4"/><circle cx="12" cy="12" r="3"/><circle cx="5" cy="5" r="2"/><circle cx="19" cy="5" r="2"/><circle cx="5" cy="19" r="2"/><circle cx="19" cy="19" r="2"/></svg>);

// ========== Shared Helpers ==========
const num = (v) => {
  if (v === null || v === undefined || v === '') return 0;
  const m = String(v).match(/[\d.]+/);
  return m ? parseFloat(m[0]) : 0;
};

const inputStyle = {
  width: '100%', padding: '8px 10px', borderRadius: 6,
  border: '1px solid #e2e8f0', fontSize: 13, outline: 'none', boxSizing: 'border-box'
};

function Field({ label, children }) {
  return (
    <div className="form-group" style={{ marginBottom: 12 }}>
      <label style={{ display: 'block', fontSize: 12, color: '#64748b', marginBottom: 4 }}>{label}</label>
      {children}
    </div>
  );
}

function Modal({ title, onClose, children }) {
  return createPortal(
    <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(15,23,42,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
      <div onClick={(e) => e.stopPropagation()} className="card" style={{ width: 480, maxWidth: '92vw', padding: 20, background: '#fff' }}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold text-base" style={{ color: '#0f172a' }}>{title}</h2>
          <button className="btn btn-secondary" style={{ padding: '4px 8px' }} onClick={onClose}><IconX /></button>
        </div>
        {children}
      </div>
    </div>,
    document.body
  );
}

const Loading = () => (<div className="card p-6 text-sm" style={{ color: '#64748b' }}>加载中...</div>);

// ========== Page Components ==========

// 1. Dashboard - Smart Workspace
function DashboardPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    api.get('/dashboard')
      .then(d => { if (alive) { setData(d); setLoading(false); } })
      .catch(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, []);

  if (loading || !data) return <Loading />;

  const stats = data.stats || {};
  const statCards = [
    { label: '活跃线索', value: stats.active_leads ?? 0, unit: '条', color: '#166534', bg: '#f0fdf4', icon: <IconTarget /> },
    { label: '商机总数', value: stats.opportunities ?? 0, unit: '个', color: '#3b82f6', bg: '#eff6ff', icon: <IconActivity /> },
    { label: '今日活动', value: stats.today_activities ?? 0, unit: '次', color: '#f59e0b', bg: '#fffbeb', icon: <IconPhone /> },
    { label: '今日待跟进', value: stats.today_followups ?? 0, unit: '项', color: '#8b5cf6', bg: '#f5f3ff', icon: <IconBell /> }
  ];

  const urgentItems = (data.urgent_leads || []).map(l => ({
    id: l.id,
    text: l.title,
    level: l.level === '高匹配' ? 'high' : l.level === '中匹配' ? 'medium' : 'low',
    time: l.deadline || '',
    customer: l.customer_name
  }));

  const newLeads = (data.urgent_leads || []).slice(0, 2).map(l => ({
    id: l.id,
    title: l.title,
    match: l.match_keywords ? 90 : 80,
    customer: l.customer_name,
    amount: '-',
    keywords: (l.match_keywords || '').split(',').filter(Boolean),
    daysLeft: l.deadline ? 3 : 7
  }));

  const todayFollowups = data.today_followups || [];

  return (
    <div className="fade-in">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold" style={{ color: '#0f172a' }}>智能工作台</h1>
          <p className="text-sm mt-1" style={{ color: '#64748b' }}>欢迎回来</p>
        </div>
        <div className="flex gap-2">
          <button className="btn btn-secondary"><IconBell />通知 <span className="badge" style={{ background: '#ef4444', color: '#fff', marginLeft: 4 }}>{stats.urgent_leads || 0}</span></button>
          <button className="btn btn-primary"><IconPlus />新建</button>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-4 mb-6">
        {statCards.map((s, i) => (
          <div key={i} className="card p-5">
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm" style={{ color: '#64748b' }}>{s.label}</span>
              <div style={{ width: 40, height: 40, borderRadius: 10, background: s.bg, display: 'flex', alignItems: 'center', justifyContent: 'center', color: s.color }}>{s.icon}</div>
            </div>
            <div className="flex items-baseline gap-1">
              <span className="text-2xl font-bold" style={{ color: '#0f172a' }}>{s.value}</span>
              <span className="text-sm" style={{ color: '#94a3b8' }}>{s.unit}</span>
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="col-span-2 card p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold" style={{ color: '#0f172a' }}>紧急事项</h2>
            <span className="badge" style={{ background: '#fef2f2', color: '#ef4444' }}>{urgentItems.filter(u => u.level === 'high').length} 项紧急</span>
          </div>
          <div className="space-y-2">
            {(urgentItems.length ? urgentItems : [{ id: 0, text: '暂无紧急线索', level: 'low', time: '' }]).map(item => (
              <div key={item.id} className={`p-3 rounded-lg urgency-${item.level}`}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span style={{ color: item.level === 'high' ? '#ef4444' : item.level === 'medium' ? '#f97316' : '#f59e0b' }}>
                      {item.level === 'high' ? <IconFire /> : item.level === 'medium' ? <IconLightning /> : <IconClock />}
                    </span>
                    <span className="text-sm font-medium">{item.text}{item.customer ? `（${item.customer}）` : ''}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs" style={{ color: '#94a3b8' }}>{item.time}</span>
                    <button className="btn btn-secondary" style={{ padding: '2px 8px', fontSize: 12 }}>处理</button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="card p-5">
          <h2 className="font-semibold mb-4" style={{ color: '#0f172a' }}>今日待跟进</h2>
          <div className="space-y-3">
            {(todayFollowups.length ? todayFollowups : [{ id: 0, content: '暂无待跟进事项', contact_name: '', plan_date: '' }]).map(f => (
              <div key={f.id} className="p-3 rounded-lg" style={{ background: '#f8fafc', border: '1px solid #e2e8f0' }}>
                <div className="flex items-center justify-between mb-1">
                  <span className="font-medium text-sm">{f.plan_date || '--'}</span>
                  <span className="badge" style={{ background: '#dbeafe', color: '#2563eb' }}>跟进</span>
                </div>
                <p className="text-sm font-medium" style={{ color: '#0f172a' }}>{f.customer_name || '客户'}</p>
                <p className="text-xs mt-1" style={{ color: '#64748b' }}>{(f.content || '').substring(0, 30) || '无内容'}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="card p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold" style={{ color: '#0f172a' }}>重点商机</h2>
          <button className="btn btn-secondary" style={{ fontSize: 12 }}>查看全部</button>
        </div>
        <div className="grid grid-cols-2 gap-3">
          {(data.opportunities || []).slice(0, 4).map(opp => (
            <div key={opp.id} className="p-4 rounded-lg" style={{ background: '#f0fdf4', border: '1px solid #bbf7d0' }}>
              <div className="flex items-start justify-between mb-2">
                <h3 className="font-medium text-sm" style={{ color: '#0f172a' }}>{opp.title}</h3>
                <span className="badge" style={{ background: '#166534', color: '#fff' }}>{opp.stage}</span>
              </div>
              <p className="text-xs mb-2" style={{ color: '#64748b' }}>{opp.customer_name} | 金额 {num(opp.amount)}万</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// 2. Customer Management
function CustomerPage() {
  const [list, setList] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState('全部');
  const [expanded, setExpanded] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({ name: '', short_name: '', type: '', level: '', region: '', source: '' });

  const load = () => {
    api.get('/customers').then(d => { setList(d); setLoading(false); }).catch(() => setLoading(false));
  };
  useEffect(() => { load(); }, []);

  const openCreate = () => {
    setEditing(null);
    setForm({ name: '', short_name: '', type: '', level: '', region: '', source: '' });
    setShowModal(true);
  };
  const openEdit = (c) => {
    setEditing(c);
    setForm({ name: c.name, short_name: c.short_name || '', type: c.type || '', level: c.level || '', region: c.region || '', source: c.source || '' });
    setShowModal(true);
  };
  const save = async () => {
    if (!form.name) { alert('请填写客户名称'); return; }
    try {
      if (editing) await api.put('/customers/' + editing.id, form);
      else await api.post('/customers', form);
      setShowModal(false);
      load();
    } catch (e) { alert(e.message); }
  };
  const remove = async (c) => {
    if (!confirm('确认归档该客户「' + c.name + '」？')) return;
    try { await api.del('/customers/' + c.id); load(); } catch (e) { alert(e.message); }
  };

  const filtered = list.filter(c => {
    if (search && !(c.name || '').includes(search)) return false;
    if (typeFilter !== '全部' && (c.type || '') !== typeFilter) return false;
    return true;
  });

  const types = ['全部', '政府', '事业单位', '国有企业', '民营企业', '科研院所', '其他'];
  const levelColor = { A: '#166534', B: '#3b82f6', C: '#f59e0b' };

  return (
    <div className="fade-in">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold" style={{ color: '#0f172a' }}>客户管理</h1>
        <button className="btn btn-primary" onClick={openCreate}><IconPlus />新增客户</button>
      </div>

      <div className="card p-4 mb-4">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 flex-1 p-2 rounded-lg" style={{ background: '#f1f5f9' }}>
            <span style={{ color: '#94a3b8' }}><IconSearch /></span>
            <input value={search} onChange={e => setSearch(e.target.value)} placeholder="搜索客户名称..." style={{ background: 'transparent', border: 'none', outline: 'none', width: '100%', fontSize: 13 }} />
          </div>
          <div className="flex gap-1">
            {types.map(t => (
              <button key={t} onClick={() => setTypeFilter(t)} className={`tab-btn ${typeFilter === t ? 'active' : ''}`}>{t}</button>
            ))}
          </div>
        </div>
      </div>

      <div className="card overflow-hidden">
        {loading ? <div className="p-6 text-sm" style={{ color: '#64748b' }}>加载中...</div> : (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr className="table-header">
                <th style={{ padding: '12px 16px', textAlign: 'left' }}>客户名称</th>
                <th style={{ padding: '12px 16px', textAlign: 'left' }}>类型</th>
                <th style={{ padding: '12px 16px', textAlign: 'left' }}>等级</th>
                <th style={{ padding: '12px 16px', textAlign: 'left' }}>地区</th>
                <th style={{ padding: '12px 16px', textAlign: 'right' }}>联系人</th>
                <th style={{ padding: '12px 16px', textAlign: 'left' }}>来源</th>
                <th style={{ padding: '12px 16px', textAlign: 'center' }}>操作</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(c => (
                <React.Fragment key={c.id}>
                  <tr style={{ borderTop: '1px solid #e2e8f0', cursor: 'pointer' }} onClick={() => setExpanded(expanded === c.id ? null : c.id)}>
                    <td style={{ padding: '12px 16px' }}>
                      <div className="flex items-center gap-2">
                        <IconBuilding />
                        <div>
                          <div className="font-medium text-sm">{c.name}</div>
                          <div className="text-xs" style={{ color: '#94a3b8' }}>{c.short_name || c.id}</div>
                        </div>
                      </div>
                    </td>
                    <td style={{ padding: '12px 16px' }}><span className="badge" style={{ background: '#f1f5f9', color: '#475569' }}>{c.type || '-'}</span></td>
                    <td style={{ padding: '12px 16px' }}><span className="badge" style={{ background: (levelColor[c.level] || '#64748b') + '20', color: levelColor[c.level] || '#64748b' }}>{c.level || '-'}级</span></td>
                    <td style={{ padding: '12px 16px', fontSize: 13, color: '#64748b' }}>{c.region || '-'}</td>
                    <td style={{ padding: '12px 16px', textAlign: 'right', fontSize: 13, fontWeight: 600 }}>{c.contact_count || 0}</td>
                    <td style={{ padding: '12px 16px', fontSize: 13, color: '#64748b' }}>{c.source || '-'}</td>
                    <td style={{ padding: '12px 16px', textAlign: 'center' }} onClick={e => e.stopPropagation()}>
                      <button className="btn btn-secondary" style={{ padding: '3px 8px', fontSize: 12, marginRight: 4 }} onClick={() => openEdit(c)}><IconEdit /></button>
                      <button className="btn btn-secondary" style={{ padding: '3px 8px', fontSize: 12 }} onClick={() => remove(c)}><IconX /></button>
                    </td>
                  </tr>
                  {expanded === c.id && (
                    <tr>
                      <td colSpan="7" style={{ padding: '16px 24px', background: '#f8fafc', borderTop: '1px solid #e2e8f0' }}>
                        <div className="grid grid-cols-2 gap-6">
                          <div>
                            <h3 className="font-semibold text-sm mb-3">客户信息</h3>
                            <div className="space-y-2 text-sm">
                              <div className="flex"><span style={{ color: '#94a3b8', width: 80 }}>简称：</span><span>{c.short_name || '-'}</span></div>
                              <div className="flex"><span style={{ color: '#94a3b8', width: 80 }}>地区：</span><span>{c.region || '-'}</span></div>
                              <div className="flex"><span style={{ color: '#94a3b8', width: 80 }}>来源：</span><span>{c.source || '-'}</span></div>
                              <div className="flex"><span style={{ color: '#94a3b8', width: 80 }}>联系人：</span><span>{c.contact_count || 0} 个</span></div>
                              <div className="flex"><span style={{ color: '#94a3b8', width: 80 }}>动态：</span><span>{c.news_count || 0} 条</span></div>
                            </div>
                          </div>
                          <div>
                            <h3 className="font-semibold text-sm mb-3">互动时间轴</h3>
                            <div className="space-y-3">
                              <div className="flex items-start gap-3">
                                <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#166534', marginTop: 5, flexShrink: 0 }} />
                                <div>
                                  <div className="text-xs" style={{ color: '#94a3b8' }}>客户档案</div>
                                  <div className="text-sm">{c.name}（{c.level || '-'}级）</div>
                                </div>
                              </div>
                            </div>
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {showModal && (
        <Modal title={editing ? '编辑客户' : '新增客户'} onClose={() => setShowModal(false)}>
          <Field label="客户名称"><input style={inputStyle} value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="必填" /></Field>
          <Field label="客户简称"><input style={inputStyle} value={form.short_name} onChange={e => setForm({ ...form, short_name: e.target.value })} /></Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="类型"><input style={inputStyle} value={form.type} onChange={e => setForm({ ...form, type: e.target.value })} placeholder="如 政府 / 事业单位" /></Field>
            <Field label="等级"><input style={inputStyle} value={form.level} onChange={e => setForm({ ...form, level: e.target.value })} placeholder="如 A / B / C" /></Field>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Field label="地区"><input style={inputStyle} value={form.region} onChange={e => setForm({ ...form, region: e.target.value })} /></Field>
            <Field label="来源"><input style={inputStyle} value={form.source} onChange={e => setForm({ ...form, source: e.target.value })} /></Field>
          </div>
          <div className="flex justify-end gap-2 mt-2">
            <button className="btn btn-secondary" onClick={() => setShowModal(false)}>取消</button>
            <button className="btn btn-primary" onClick={save}>保存</button>
          </div>
        </Modal>
      )}
    </div>
  );
}

// 3. Lead Management
function LeadPage() {
  const [all, setAll] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('all');
  const [sourceFilter, setSourceFilter] = useState('全部');

  const load = () => {
    api.get('/leads').then(d => { setAll(d); setLoading(false); }).catch(() => setLoading(false));
  };
  useEffect(() => { load(); }, []);

  const poolLeads = all.filter(l => l.status === 'pool');
  const activeLeads = all.filter(l => l.status !== 'pool');
  const currentLeads = activeTab === 'all' ? activeLeads : poolLeads;

  const sources = ['全部', ...Array.from(new Set(all.map(l => l.source_platform).filter(Boolean)))];
  const filtered = currentLeads.filter(l => sourceFilter === '全部' || (l.source_platform || '') === sourceFilter);

  const matchColor = (m) => m >= 85 ? '#166534' : m >= 70 ? '#3b82f6' : m >= 50 ? '#f59e0b' : '#ef4444';

  const statusText = (s) => ({ active: '活跃', pool: '公海', converted: '已转化', abandoned: '已废弃' }[s] || s);
  const statusStyle = (s) => ({
    active: { bg: '#eff6ff', color: '#2563eb' },
    pool: { bg: '#f1f5f9', color: '#64748b' },
    converted: { bg: '#f0fdf4', color: '#166534' },
    abandoned: { bg: '#fef2f2', color: '#ef4444' }
  }[s] || { bg: '#f1f5f9', color: '#64748b' });

  const claim = async (l) => { try { await api.post('/leads/' + l.id + '/claim', { assignee: '李明' }); load(); } catch (e) { alert(e.message); } };
  const release = async (l) => { try { await api.post('/leads/' + l.id + '/release', {}); load(); } catch (e) { alert(e.message); } };
  const remove = async (l) => { if (!confirm('确认删除线索「' + l.title + '」？')) return; try { await api.del('/leads/' + l.id); load(); } catch (e) { alert(e.message); } };

  return (
    <div className="fade-in">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold" style={{ color: '#0f172a' }}>线索管理</h1>
        <div className="flex gap-2">
          <button className="btn btn-secondary"><IconDownload />导入</button>
          <button className="btn btn-primary"><IconPlus />新建线索</button>
        </div>
      </div>

      <div className="flex items-center gap-4 mb-4">
        <div className="flex border-b" style={{ borderColor: '#e2e8f0' }}>
          <button onClick={() => setActiveTab('all')} className={`tab-btn ${activeTab === 'all' ? 'active' : ''}`}>全部线索 ({activeLeads.length})</button>
          <button onClick={() => setActiveTab('pool')} className={`tab-btn ${activeTab === 'pool' ? 'active' : ''}`}>公海池 ({poolLeads.length})</button>
        </div>
        <div className="flex gap-1 ml-auto">
          <select value={sourceFilter} onChange={e => setSourceFilter(e.target.value)} style={{ fontSize: 13, padding: '4px 8px', borderRadius: 6, border: '1px solid #e2e8f0', color: '#475569', background: '#fff' }}>
            {sources.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
      </div>

      {loading ? <Loading /> : (
        <div className="space-y-3">
          {filtered.map(lead => {
            const st = statusStyle(lead.status);
            return (
              <div key={lead.id} className="card p-4">
                <div className="flex items-start justify-between mb-3">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <h3 className="font-medium text-sm">{lead.title}</h3>
                      <span className="badge" style={{ background: st.bg, color: st.color }}>{statusText(lead.status)}</span>
                    </div>
                    <p className="text-xs" style={{ color: '#64748b' }}>{lead.customer_name || '未知客户'} | {lead.source_platform || '-'} | 预算 {lead.budget || '-'} | 负责人: {lead.assignee || '-'}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <button className="btn btn-secondary" style={{ padding: '3px 10px', fontSize: 12 }}><IconEye />查看</button>
                    {lead.status === 'pool'
                      ? <button className="btn btn-primary" style={{ padding: '3px 10px', fontSize: 12 }} onClick={() => claim(lead)}><IconPlus />领取</button>
                      : <button className="btn btn-secondary" style={{ padding: '3px 10px', fontSize: 12 }} onClick={() => release(lead)}>释放</button>}
                    <button className="btn btn-secondary" style={{ padding: '3px 10px', fontSize: 12 }} onClick={() => remove(lead)}><IconX /></button>
                  </div>
                </div>

                <div className="flex items-center gap-4">
                  <div className="flex-1">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs" style={{ color: '#64748b' }}>匹配度</span>
                      <span className="text-xs font-semibold" style={{ color: matchColor(lead.match_score) }}>{lead.match_score}%</span>
                    </div>
                    <div className="progress-bar">
                      <div className="progress-fill" style={{ width: (lead.match_score || 0) + '%', background: matchColor(lead.match_score) }} />
                    </div>
                  </div>
                  <div className="flex gap-1">
                    {(lead.match_keywords || '').split(',').filter(Boolean).map((kw, ki) => (
                      <span key={ki} className="badge" style={{ background: '#f1f5f9', color: '#475569', fontSize: 11 }}>{kw}</span>
                    ))}
                  </div>
                  <div className="flex items-center gap-1 text-xs" style={{ color: (lead.days_left || 99) <= 3 ? '#ef4444' : '#f59e0b' }}>
                    <IconClock />
                    <span>剩余 {lead.days_left != null ? lead.days_left : '-'} 天</span>
                  </div>
                </div>
              </div>
            );
          })}
          {!filtered.length && <div className="card p-6 text-sm" style={{ color: '#64748b' }}>暂无线索</div>}
        </div>
      )}
    </div>
  );
}

// 4. Opportunity Management
function OpportunityPage() {
  const [list, setList] = useState([]);
  const [loading, setLoading] = useState(true);
  const [viewMode, setViewMode] = useState('list');
  const [expandedOpp, setExpandedOpp] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState({ title: '', customer_id: '', amount: '', current_stage: '初步接触', expected_close: '' });

  const load = () => {
    api.get('/opportunities').then(d => { setList(d); setLoading(false); }).catch(() => setLoading(false));
  };
  useEffect(() => { load(); }, []);

  const stages = ['初步接触', '需求确认', '方案报价', '商务谈判', '合同签订'];
  const stageColors = ['#94a3b8', '#3b82f6', '#f59e0b', '#8b5cf6', '#166534'];
  const stageCounts = stages.map(s => list.filter(o => o.current_stage === s));

  const probColor = (p) => p >= 80 ? '#166534' : p >= 50 ? '#f59e0b' : p >= 30 ? '#3b82f6' : '#ef4444';

  const save = async () => {
    if (!form.title) { alert('请填写商机名称'); return; }
    try { await api.post('/opportunities', form); setShowModal(false); load(); } catch (e) { alert(e.message); }
  };
  const remove = async (o) => { if (!confirm('确认删除商机「' + o.title + '」？')) return; try { await api.del('/opportunities/' + o.id); load(); } catch (e) { alert(e.message); } };

  return (
    <div className="fade-in">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold" style={{ color: '#0f172a' }}>商机管理</h1>
        <div className="flex gap-2">
          <button onClick={() => setViewMode('list')} className={`btn ${viewMode === 'list' ? 'btn-primary' : 'btn-secondary'}`}>列表</button>
          <button onClick={() => setViewMode('board')} className={`btn ${viewMode === 'board' ? 'btn-primary' : 'btn-secondary'}`}>看板</button>
          <button className="btn btn-primary" onClick={() => { setForm({ title: '', customer_id: '', amount: '', current_stage: '初步接触', expected_close: '' }); setShowModal(true); }}><IconPlus />新建商机</button>
        </div>
      </div>

      <div className="card p-4 mb-4">
        <div className="flex items-center justify-between">
          {stages.map((stage, si) => {
            const count = stageCounts[si].length;
            const total = stageCounts[si].reduce((s, o) => s + num(o.amount), 0);
            return (
              <React.Fragment key={stage}>
                <div className="text-center" style={{ flex: 1 }}>
                  <div style={{ width: 48, height: 48, borderRadius: '50%', background: stageColors[si] + '20', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 8px', color: stageColors[si], fontSize: 18, fontWeight: 700 }}>{count}</div>
                  <div className="text-xs font-medium" style={{ color: stageColors[si] }}>{stage}</div>
                  <div className="text-xs mt-1" style={{ color: '#94a3b8' }}>{total}万</div>
                </div>
                {si < stages.length - 1 && <div style={{ flex: 0.5, height: 2, background: '#e2e8f0', alignSelf: 'center', marginTop: -20 }} />}
              </React.Fragment>
            );
          })}
        </div>
      </div>

      {loading ? <Loading /> : viewMode === 'list' ? (
        <div className="card overflow-hidden">
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr className="table-header">
                <th style={{ padding: '12px 16px', textAlign: 'left' }}>商机名称</th>
                <th style={{ padding: '12px 16px', textAlign: 'left' }}>客户</th>
                <th style={{ padding: '12px 16px', textAlign: 'right' }}>金额</th>
                <th style={{ padding: '12px 16px', textAlign: 'left' }}>阶段</th>
                <th style={{ padding: '12px 16px', textAlign: 'center' }}>赢率</th>
                <th style={{ padding: '12px 16px', textAlign: 'left' }}>联系人</th>
                <th style={{ padding: '12px 16px', textAlign: 'left' }}>预计关闭</th>
                <th style={{ padding: '12px 16px', textAlign: 'center' }}>操作</th>
              </tr>
            </thead>
            <tbody>
              {list.map(opp => (
                <React.Fragment key={opp.id}>
                  <tr style={{ borderTop: '1px solid #e2e8f0', cursor: 'pointer' }} onClick={() => setExpandedOpp(expandedOpp === opp.id ? null : opp.id)}>
                    <td style={{ padding: '12px 16px' }}><span className="font-medium text-sm">{opp.title}</span></td>
                    <td style={{ padding: '12px 16px', fontSize: 13 }}>{opp.customer_name || '-'}</td>
                    <td style={{ padding: '12px 16px', textAlign: 'right', fontSize: 13, fontWeight: 600 }}>{num(opp.amount)}万</td>
                    <td style={{ padding: '12px 16px' }}>
                      <span className="badge" style={{ background: stageColors[stages.indexOf(opp.current_stage)] + '20', color: stageColors[stages.indexOf(opp.current_stage)] }}>{opp.current_stage}</span>
                    </td>
                    <td style={{ padding: '12px 16px', textAlign: 'center' }}>
                      <span className="font-semibold text-sm" style={{ color: probColor(opp.probability) }}>{opp.probability}%</span>
                    </td>
                    <td style={{ padding: '12px 16px', fontSize: 13 }}>{opp.contact_name || '-'}</td>
                    <td style={{ padding: '12px 16px', fontSize: 13, color: '#64748b' }}>{opp.expected_close || '-'}</td>
                    <td style={{ padding: '12px 16px', textAlign: 'center' }} onClick={e => e.stopPropagation()}>
                      <button className="btn btn-secondary" style={{ padding: '3px 8px', fontSize: 12 }} onClick={() => remove(opp)}><IconX /></button>
                    </td>
                  </tr>
                  {expandedOpp === opp.id && (
                    <tr>
                      <td colSpan="8" style={{ padding: '16px 24px', background: '#f8fafc', borderTop: '1px solid #e2e8f0' }}>
                        <div className="grid grid-cols-2 gap-6">
                          <div>
                            <h3 className="font-semibold text-sm mb-2">商机详情</h3>
                            <div className="space-y-2 text-sm">
                              <div className="flex"><span style={{ color: '#94a3b8', width: 80 }}>创建日期：</span><span>{opp.created_at || '-'}</span></div>
                              <div className="flex"><span style={{ color: '#94a3b8', width: 80 }}>预计关闭：</span><span>{opp.expected_close || '-'}</span></div>
                              <div className="flex"><span style={{ color: '#94a3b8', width: 80 }}>赢率：</span><span style={{ color: probColor(opp.probability), fontWeight: 600 }}>{opp.probability}%</span></div>
                            </div>
                          </div>
                          <div>
                            <h3 className="font-semibold text-sm mb-2">阶段记录</h3>
                            <div className="space-y-2">
                              {(opp.stages && opp.stages.length) ? opp.stages.map((h, hi) => (
                                <div key={hi} className="flex items-center gap-3">
                                  <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#cbd5e1', flexShrink: 0 }} />
                                  <span className="text-xs" style={{ color: '#94a3b8', width: 40 }}>{h.stage}</span>
                                  <span className="text-sm">{h.content || ''}</span>
                                </div>
                              )) : <div className="text-sm" style={{ color: '#94a3b8' }}>暂无阶段记录</div>}
                            </div>
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="grid grid-cols-5 gap-3">
          {stages.map((stage, si) => {
            const stageOpps = stageCounts[si];
            const total = stageOpps.reduce((s, o) => s + num(o.amount), 0);
            return (
              <div key={stage} className="card p-3" style={{ minHeight: 300 }}>
                <div className="flex items-center justify-between mb-3 pb-2" style={{ borderBottom: '2px solid ' + stageColors[si] }}>
                  <span className="font-medium text-sm">{stage}</span>
                  <span className="text-xs" style={{ color: '#94a3b8' }}>{stageOpps.length}个 | {total}万</span>
                </div>
                <div className="space-y-2">
                  {stageOpps.map(opp => (
                    <div key={opp.id} className="p-3 rounded-lg" style={{ background: '#f8fafc', border: '1px solid #e2e8f0', cursor: 'pointer' }}>
                      <div className="font-medium text-xs mb-1">{opp.title}</div>
                      <div className="text-xs mb-2" style={{ color: '#64748b' }}>{opp.customer_name || '-'}</div>
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold">{num(opp.amount)}万</span>
                        <span className="text-xs" style={{ color: probColor(opp.probability) }}>{opp.probability}%</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {showModal && (
        <Modal title="新建商机" onClose={() => setShowModal(false)}>
          <Field label="商机名称"><input style={inputStyle} value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} placeholder="必填" /></Field>
          <Field label="客户ID"><input style={inputStyle} value={form.customer_id} onChange={e => setForm({ ...form, customer_id: e.target.value ? Number(e.target.value) : '' })} placeholder="关联客户 ID（可选）" /></Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="金额(万)"><input style={inputStyle} value={form.amount} onChange={e => setForm({ ...form, amount: e.target.value })} /></Field>
            <Field label="预计关闭"><input style={inputStyle} type="date" value={form.expected_close} onChange={e => setForm({ ...form, expected_close: e.target.value })} /></Field>
          </div>
          <Field label="当前阶段">
            <select style={inputStyle} value={form.current_stage} onChange={e => setForm({ ...form, current_stage: e.target.value })}>
              {stages.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </Field>
          <div className="flex justify-end gap-2 mt-2">
            <button className="btn btn-secondary" onClick={() => setShowModal(false)}>取消</button>
            <button className="btn btn-primary" onClick={save}>创建</button>
          </div>
        </Modal>
      )}
    </div>
  );
}

// 5. Contact Management
function ContactPage() {
  const [list, setList] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState('全部');
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState({ name: '', title: '', phone: '', email: '', customer_id: '', importance: '', role: '', tags: '' });

  const load = () => {
    api.get('/contacts').then(d => { setList(d); setLoading(false); }).catch(() => setLoading(false));
  };
  useEffect(() => { load(); }, []);

  const roleColors = {
    '决策人': { bg: '#fef2f2', color: '#dc2626' },
    '业务负责人': { bg: '#eff6ff', color: '#2563eb' },
    '技术对接': { bg: '#f0fdf4', color: '#166534' },
    '采购执行': { bg: '#fffbeb', color: '#d97706' }
  };
  const rc = (r) => roleColors[r] || { bg: '#f1f5f9', color: '#475569' };

  const roles = ['全部', ...Array.from(new Set(list.map(c => c.role).filter(Boolean)))];
  const filtered = list.filter(c => {
    if (search && !(c.name || '').includes(search) && !(c.customer_name || '').includes(search)) return false;
    if (roleFilter !== '全部' && (c.role || '') !== roleFilter) return false;
    return true;
  });

  const save = async () => {
    if (!form.name) { alert('请填写联系人姓名'); return; }
    try { await api.post('/contacts', form); setShowModal(false); load(); } catch (e) { alert(e.message); }
  };
  const remove = async (c) => { if (!confirm('确认删除联系人「' + c.name + '」？')) return; try { await api.del('/contacts/' + c.id); load(); } catch (e) { alert(e.message); } };

  return (
    <div className="fade-in">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold" style={{ color: '#0f172a' }}>联系人管理</h1>
        <button className="btn btn-primary" onClick={() => { setForm({ name: '', title: '', phone: '', email: '', customer_id: '', importance: '', role: '', tags: '' }); setShowModal(true); }}><IconPlus />新增联系人</button>
      </div>

      <div className="card p-4 mb-4">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 flex-1 p-2 rounded-lg" style={{ background: '#f1f5f9' }}>
            <span style={{ color: '#94a3b8' }}><IconSearch /></span>
            <input value={search} onChange={e => setSearch(e.target.value)} placeholder="搜索联系人或机构..." style={{ background: 'transparent', border: 'none', outline: 'none', width: '100%', fontSize: 13 }} />
          </div>
          <div className="flex gap-1">
            {roles.map(r => (
              <button key={r} onClick={() => setRoleFilter(r)} className={`tab-btn ${roleFilter === r ? 'active' : ''}`}>{r}</button>
            ))}
          </div>
        </div>
      </div>

      {loading ? <Loading /> : (
        <div className="grid grid-cols-3 gap-4">
          {filtered.map(c => {
            const col = rc(c.role);
            return (
              <div key={c.id} className="card p-5">
                <div className="flex items-start gap-4 mb-4">
                  <div style={{ width: 48, height: 48, borderRadius: '50%', background: col.bg, color: col.color, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18, fontWeight: 700, flexShrink: 0 }}>
                    {c.avatar || (c.name ? c.name[0] : '?')}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <h3 className="font-semibold text-sm">{c.name}</h3>
                      <span className="badge" style={{ background: col.bg, color: col.color }}>{c.role || '未分类'}</span>
                    </div>
                    <p className="text-xs" style={{ color: '#64748b' }}>{c.title || '-'} | {c.customer_name || '-'}</p>
                  </div>
                </div>
                <div className="space-y-2 mb-4">
                  <div className="flex items-center gap-2 text-xs" style={{ color: '#475569' }}><IconPhone />{c.phone || '-'}</div>
                  <div className="flex items-center gap-2 text-xs" style={{ color: '#475569' }}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="2" y="4" width="20" height="16" rx="2" /><polyline points="22,7 12,13 2,7" /></svg>
                    {c.email || '-'}
                  </div>
                </div>
                <div className="flex gap-1 flex-wrap mb-3">
                  {(c.tags || '').split(',').filter(Boolean).map((t, ti) => (
                    <span key={ti} className="badge" style={{ background: '#f1f5f9', color: '#475569', fontSize: 11 }}>{t}</span>
                  ))}
                </div>
                <div className="flex gap-2">
                  <button className="btn btn-primary" style={{ flex: 1, justifyContent: 'center', fontSize: 12, padding: '5px 0' }}><IconPhone />拨打电话</button>
                  <button className="btn btn-secondary" style={{ flex: 1, justifyContent: 'center', fontSize: 12, padding: '5px 0' }} onClick={() => remove(c)}><IconX />删除</button>
                </div>
              </div>
            );
          })}
          {!filtered.length && <div className="card p-6 text-sm" style={{ color: '#64748b' }}>暂无联系人</div>}
        </div>
      )}

      {showModal && (
        <Modal title="新增联系人" onClose={() => setShowModal(false)}>
          <Field label="姓名"><input style={inputStyle} value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="必填" /></Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="职位"><input style={inputStyle} value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} /></Field>
            <Field label="角色"><input style={inputStyle} value={form.role} onChange={e => setForm({ ...form, role: e.target.value })} placeholder="如 决策人" /></Field>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Field label="电话"><input style={inputStyle} value={form.phone} onChange={e => setForm({ ...form, phone: e.target.value })} /></Field>
            <Field label="邮箱"><input style={inputStyle} value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} /></Field>
          </div>
          <Field label="客户ID"><input style={inputStyle} value={form.customer_id} onChange={e => setForm({ ...form, customer_id: e.target.value ? Number(e.target.value) : '' })} placeholder="关联客户 ID（可选）" /></Field>
          <Field label="标签(逗号分隔)"><input style={inputStyle} value={form.tags} onChange={e => setForm({ ...form, tags: e.target.value })} /></Field>
          <div className="flex justify-end gap-2 mt-2">
            <button className="btn btn-secondary" onClick={() => setShowModal(false)}>取消</button>
            <button className="btn btn-primary" onClick={save}>创建</button>
          </div>
        </Modal>
      )}
    </div>
  );
}

// 6. Contact Log
function ContactLogPage() {
  const [followups, setFollowups] = useState([]);
  const [activities, setActivities] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    Promise.all([
      api.get('/followups').catch(() => []),
      api.get('/activities').catch(() => [])
    ]).then(([f, a]) => {
      if (!alive) return;
      setFollowups(f || []);
      setActivities(a || []);
      setLoading(false);
    });
    return () => { alive = false; };
  }, []);

  const datePart = (s) => (s ? String(s).split(' ')[0] : '未知日期');
  const grouped = {};
  followups.forEach(f => {
    const d = datePart(f.plan_date);
    if (!grouped[d]) grouped[d] = [];
    grouped[d].push(f);
  });

  const resultTextColors = { '积极': '#166534', '需跟进': '#92400e', '一般': '#475569' };

  return (
    <div className="fade-in">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold" style={{ color: '#0f172a' }}>日常联络</h1>
        <button className="btn btn-primary"><IconPlus />新建联络计划</button>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <div className="col-span-2">
          <h2 className="font-semibold mb-3" style={{ color: '#0f172a' }}>联络计划（待跟进）</h2>
          {loading ? <Loading /> : Object.keys(grouped).sort().map(date => (
            <div key={date} className="mb-4">
              <div className="flex items-center gap-2 mb-2">
                <IconCalendar />
                <span className="font-medium text-sm">{date}</span>
                <span className="badge" style={{ background: '#f1f5f9', color: '#64748b' }}>{grouped[date].length}项</span>
              </div>
              <div className="space-y-2">
                {grouped[date].map(plan => (
                  <div key={plan.id} className="card p-4">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-sm" style={{ color: '#0f172a' }}>{date}</span>
                        <span className="badge" style={{ background: '#fef3c7', color: '#92400e' }}>待跟进</span>
                      </div>
                      <div className="flex gap-1">
                        <button className="btn btn-secondary" style={{ padding: '3px 8px', fontSize: 12 }}><IconCheck />完成</button>
                        <button className="btn btn-secondary" style={{ padding: '3px 8px', fontSize: 12 }}><IconEdit />记录</button>
                      </div>
                    </div>
                    <div className="text-sm font-medium mb-1">{plan.customer_name || '客户'} - {plan.contact_name || '联系人'}</div>
                    <div className="text-xs" style={{ color: '#64748b' }}>{plan.content}</div>
                  </div>
                ))}
              </div>
            </div>
          ))}

          <h2 className="font-semibold mb-3 mt-6" style={{ color: '#0f172a' }}>最近联络记录</h2>
          <div className="space-y-2">
            {loading ? <Loading /> : activities.map(r => (
              <div key={r.id} className="card p-4">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-medium" style={{ color: '#64748b' }}>{datePart(r.activity_time)}</span>
                    <span className="font-medium text-sm">{r.customer_name || '-'}</span>
                    <span className="badge" style={{ background: '#f1f5f9', color: '#475569' }}>{r.method || '联络'}</span>
                  </div>
                  <span className="text-xs" style={{ color: '#94a3b8' }}>{r.contact_name || ''}</span>
                </div>
                <p className="text-xs" style={{ color: '#475569' }}>{r.content}</p>
              </div>
            ))}
            {!loading && !activities.length && <div className="card p-6 text-sm" style={{ color: '#64748b' }}>暂无联络记录</div>}
          </div>
        </div>

        <div>
          <div className="card p-5 mb-4">
            <div className="flex items-center gap-2 mb-4">
              <span style={{ color: '#8b5cf6' }}><IconLightning /></span>
              <h2 className="font-semibold" style={{ color: '#0f172a' }}>AI 智能建议</h2>
            </div>
            <div className="space-y-3">
              <div className="p-3 rounded-lg" style={{ background: '#f5f3ff', border: '1px solid #e9d5ff' }}>
                <p className="text-xs leading-relaxed" style={{ color: '#4c1d95' }}>根据今日待跟进与活动记录，建议优先处理高匹配线索并按时完成联络计划。</p>
              </div>
            </div>
          </div>

          <div className="card p-5">
            <h2 className="font-semibold mb-3" style={{ color: '#0f172a' }}>联络统计</h2>
            <div className="space-y-3">
              <div className="flex items-center justify-between text-sm">
                <span style={{ color: '#64748b' }}>待跟进事项</span>
                <span className="font-semibold">{followups.length}</span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span style={{ color: '#64748b' }}>联络记录</span>
                <span className="font-semibold">{activities.length}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// 7. Kanban Board (opportunity-based)
function KanbanPage() {
  const [oppList, setOppList] = useState([]);
  const [dragItem, setDragItem] = useState(null);
  const [dragOverCol, setDragOverCol] = useState(null);

  const load = () => {
    api.get('/opportunities').then(d => setOppList(d || [])).catch(() => setOppList([]));
  };
  useEffect(() => { load(); }, []);

  const stages = ['初步接触', '需求确认', '方案报价', '商务谈判', '合同签订'];
  const stageColors = ['#94a3b8', '#3b82f6', '#f59e0b', '#8b5cf6', '#166534'];

  const handleDragStart = (e, oppId) => {
    setDragItem(oppId);
    e.dataTransfer.effectAllowed = 'move';
  };
  const handleDragOver = (e, stage) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    setDragOverCol(stage);
  };
  const handleDragLeave = () => setDragOverCol(null);
  const handleDrop = async (e, targetStage) => {
    e.preventDefault();
    setDragOverCol(null);
    if (!dragItem) return;
    const item = oppList.find(o => o.id === dragItem);
    if (!item || item.current_stage === targetStage) { setDragItem(null); return; }
    try {
      await api.put('/opportunities/' + dragItem, { current_stage: targetStage });
      setOppList(prev => prev.map(o => o.id === dragItem ? { ...o, current_stage: targetStage } : o));
    } catch (err) {
      alert(err.message);
    }
    setDragItem(null);
  };

  return (
    <div className="fade-in">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold" style={{ color: '#0f172a' }}>看板管理</h1>
        <button className="btn btn-primary"><IconPlus />新建商机</button>
      </div>

      <div className="grid grid-cols-5 gap-3" style={{ minHeight: 'calc(100vh - 180px)' }}>
        {stages.map((stage, si) => {
          const stageOpps = oppList.filter(o => o.current_stage === stage);
          const total = stageOpps.reduce((s, o) => s + num(o.amount), 0);
          return (
            <div
              key={stage}
              className={`card p-3 kanban-col ${dragOverCol === stage ? 'drag-over' : ''}`}
              style={{ borderTop: `3px solid ${stageColors[si]}` }}
              onDragOver={(e) => handleDragOver(e, stage)}
              onDragLeave={handleDragLeave}
              onDrop={(e) => handleDrop(e, stage)}
            >
              <div className="flex items-center justify-between mb-3 pb-2" style={{ borderBottom: '1px solid #e2e8f0' }}>
                <span className="font-semibold text-sm">{stage}</span>
                <span className="badge" style={{ background: stageColors[si] + '20', color: stageColors[si] }}>{stageOpps.length}</span>
              </div>
              <div className="text-xs mb-3" style={{ color: '#94a3b8' }}>合计: {total}万</div>
              <div className="space-y-2">
                {stageOpps.map(opp => (
                  <div
                    key={opp.id}
                    className={`kanban-card p-3 rounded-lg ${dragItem === opp.id ? 'dragging' : ''}`}
                    style={{ background: '#f8fafc', border: '1px solid #e2e8f0' }}
                    draggable
                    onDragStart={(e) => handleDragStart(e, opp.id)}
                  >
                    <div className="font-medium text-xs mb-1">{opp.title}</div>
                    <div className="text-xs mb-2" style={{ color: '#64748b' }}>{opp.customer_name || '-'}</div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs font-semibold" style={{ color: '#0f172a' }}>{num(opp.amount)}万</span>
                      <span className="text-xs" style={{ color: opp.probability >= 70 ? '#166534' : opp.probability >= 40 ? '#f59e0b' : '#ef4444' }}>{opp.probability}%</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-xs" style={{ color: '#94a3b8' }}>{opp.contact_name || '-'}</span>
                      <span className="text-xs" style={{ color: '#94a3b8' }}>{(opp.expected_close || '').substring(5)}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// 8. Reports Page
function ReportsPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    api.get('/analytics').then(d => { if (alive) { setData(d); setLoading(false); } }).catch(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, []);

  if (loading || !data) return <Loading />;

  const summary = data.summary || {};
  const summaryCards = [
    { label: '线索总数', value: summary.total_leads ?? 0, change: '—', up: true },
    { label: '商机总数', value: summary.total_opportunities ?? 0, change: '—', up: true },
    { label: '商机总金额', value: Math.round(num(summary.total_amount)) + '万', change: '—', up: true },
    { label: '转化率', value: (summary.conversion_rate ?? 0) + '%', change: '—', up: true }
  ];

  const funnelColors = ['#94a3b8', '#3b82f6', '#f59e0b', '#8b5cf6', '#166534'];
  const pieColors = ['#166534', '#3b82f6', '#ef4444'];
  const monthly = data.monthly_leads || [];
  const funnel = data.funnel || [];
  const winLoss = data.win_loss || [];

  return (
    <div className="fade-in">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold" style={{ color: '#0f172a' }}>数据报表</h1>
        <button className="btn btn-secondary"><IconDownload />导出报表</button>
      </div>

      <div className="grid grid-cols-4 gap-4 mb-6">
        {summaryCards.map((s, i) => (
          <div key={i} className="card p-5">
            <div className="text-sm mb-1" style={{ color: '#64748b' }}>{s.label}</div>
            <div className="text-2xl font-bold mb-1" style={{ color: '#0f172a' }}>{s.value}</div>
            <div className="flex items-center gap-1 text-xs" style={{ color: s.up ? '#22c55e' : '#3b82f6' }}>
              {s.up ? <IconArrowUp /> : <IconArrowDown />}
              <span>{s.change}</span>
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-4 mb-4">
        <div className="card p-5">
          <h2 className="font-semibold mb-4" style={{ color: '#0f172a' }}>线索月度趋势</h2>
          <ResponsiveContainer width="100%" height={250}>
            <AreaChart data={monthly}>
              <defs>
                <linearGradient id="colorLeads" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#166534" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#166534" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="colorConverted" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#f59e0b" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="month" tick={{ fontSize: 12, fill: '#94a3b8' }} />
              <YAxis tick={{ fontSize: 12, fill: '#94a3b8' }} />
              <Tooltip />
              <Legend />
              <Area type="monotone" dataKey="leads" name="新增线索" stroke="#166534" fillOpacity={1} fill="url(#colorLeads)" />
              <Area type="monotone" dataKey="converted" name="已转化" stroke="#f59e0b" fillOpacity={1} fill="url(#colorConverted)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        <div className="card p-5">
          <h2 className="font-semibold mb-4" style={{ color: '#0f172a' }}>商机漏斗（金额/万）</h2>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={funnel} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis type="number" tick={{ fontSize: 12, fill: '#94a3b8' }} />
              <YAxis dataKey="stage" type="category" tick={{ fontSize: 12, fill: '#94a3b8' }} width={70} />
              <Tooltip />
              <Bar dataKey="amount" name="金额(万)" fill="#166534" radius={[0, 4, 4, 0]}>
                {funnel.map((entry, index) => (
                  <Cell key={index} fill={funnelColors[index % funnelColors.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="card p-5">
          <h2 className="font-semibold mb-4" style={{ color: '#0f172a' }}>各阶段商机数</h2>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={funnel}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="stage" tick={{ fontSize: 12, fill: '#94a3b8' }} />
              <YAxis tick={{ fontSize: 12, fill: '#94a3b8' }} />
              <Tooltip />
              <Bar dataKey="count" name="商机数" fill="#3b82f6" radius={[4, 4, 0, 0]}>
                {funnel.map((entry, index) => (
                  <Cell key={index} fill={funnelColors[index % funnelColors.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="card p-5">
          <h2 className="font-semibold mb-4" style={{ color: '#0f172a' }}>赢单/丢单分布</h2>
          <ResponsiveContainer width="100%" height={250}>
            <PieChart>
              <Pie
                data={winLoss}
                cx="50%"
                cy="50%"
                innerRadius={60}
                outerRadius={90}
                paddingAngle={3}
                dataKey="value"
                label={(entry) => entry.name + ': ' + entry.value}
              >
                {winLoss.map((entry, index) => (
                  <Cell key={index} fill={pieColors[index % pieColors.length]} />
                ))}
              </Pie>
              <Tooltip />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}

// ========== Login Page ==========
function LoginPage({ onLogin }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const user = await doLogin(username, password);
      onLogin(user);
    } catch (err) {
      setError(err.message || '登录失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'linear-gradient(135deg, #14532d 0%, #15803d 100%)', padding: 16 }}>
      <form onSubmit={handleSubmit} className="card" style={{ width: 380, maxWidth: '92vw', padding: 32, background: '#fff' }}>
        <div className="flex items-center gap-3 mb-6">
          <div style={{ width: 44, height: 44, borderRadius: 12, background: '#166534', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#f59e0b' }}>
            <IconDrone />
          </div>
          <div>
            <div className="font-bold text-lg" style={{ color: '#0f172a' }}>林业无人机CRM</div>
            <div className="text-xs" style={{ color: '#94a3b8' }}>Forest Drone CRM</div>
          </div>
        </div>
        <h1 className="text-xl font-bold mb-1" style={{ color: '#0f172a' }}>登录</h1>
        <p className="text-sm mb-6" style={{ color: '#64748b' }}>请输入账号密码以继续使用</p>

        <div className="form-group" style={{ marginBottom: 14 }}>
          <label style={{ display: 'block', fontSize: 12, color: '#64748b', marginBottom: 4 }}>用户名</label>
          <input value={username} onChange={e => setUsername(e.target.value)} placeholder="admin" style={inputStyle} autoFocus />
        </div>
        <div className="form-group" style={{ marginBottom: 18 }}>
          <label style={{ display: 'block', fontSize: 12, color: '#64748b', marginBottom: 4 }}>密码</label>
          <input type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="••••••••" style={inputStyle} />
        </div>

        {error && (
          <div className="p-2 mb-3 rounded-lg text-sm" style={{ background: '#fef2f2', color: '#ef4444' }}>{error}</div>
        )}

        <button type="submit" className="btn btn-primary" disabled={loading} style={{ width: '100%', justifyContent: 'center', padding: '10px 0', fontSize: 14 }}>
          {loading ? '登录中...' : '登 录'}
        </button>
        <p className="text-xs mt-4 text-center" style={{ color: '#94a3b8' }}>默认账号：admin / admin123</p>
      </form>
    </div>
  );
}

// ========== Main App ==========
function App() {
  const [currentPage, setCurrentPage] = useState('dashboard');
  const [user, setUser] = useState(null);
  const [authLoading, setAuthLoading] = useState(true);

  useEffect(() => {
    fetchMe()
      .then(u => setUser(u))
      .catch(() => setUser(null))
      .finally(() => setAuthLoading(false));
  }, []);

  const handleLogout = async () => {
    await doLogout();
    setUser(null);
  };

  if (authLoading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', background: '#f8fafc', color: '#64748b' }}>
        加载中...
      </div>
    );
  }

  if (!user) {
    return <LoginPage onLogin={setUser} />;
  }

  const navItems = [
    { id: 'dashboard', label: '智能工作台', icon: <IconGrid /> },
    { id: 'customers', label: '客户管理', icon: <IconUsers /> },
    { id: 'leads', label: '线索管理', icon: <IconTarget /> },
    { id: 'opportunities', label: '商机管理', icon: <IconLayers /> },
    { id: 'contacts', label: '联系人管理', icon: <IconUserCircle /> },
    { id: 'contactlog', label: '日常联络', icon: <IconPhone /> },
    { id: 'kanban', label: '看板管理', icon: <IconKanban /> },
    { id: 'reports', label: '数据报表', icon: <IconChart /> }
  ];

  const pageComponents = {
    dashboard: <DashboardPage />,
    customers: <CustomerPage />,
    leads: <LeadPage />,
    opportunities: <OpportunityPage />,
    contacts: <ContactPage />,
    contactlog: <ContactLogPage />,
    kanban: <KanbanPage />,
    reports: <ReportsPage />
  };

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      {/* Sidebar */}
      <div style={{
        width: 220,
        flexShrink: 0,
        background: 'linear-gradient(180deg, #14532d 0%, #166534 50%, #15803d 100%)',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden'
      }}>
        <div style={{ padding: '20px 16px', borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
          <div className="flex items-center gap-2">
            <div style={{ width: 36, height: 36, borderRadius: 10, background: 'rgba(255,255,255,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <span style={{ color: '#f59e0b' }}><IconDrone /></span>
            </div>
            <div>
              <div className="font-bold text-sm" style={{ color: '#fff' }}>林业无人机CRM</div>
              <div className="text-xs" style={{ color: 'rgba(255,255,255,0.6)' }}>Forest Drone CRM</div>
            </div>
          </div>
        </div>

        <div style={{ flex: 1, overflowY: 'auto', padding: '8px 0' }}>
          {navItems.map(item => (
            <div
              key={item.id}
              className={`sidebar-item ${currentPage === item.id ? 'active' : ''}`}
              onClick={() => setCurrentPage(item.id)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                padding: '10px 16px',
                color: currentPage === item.id ? '#fff' : 'rgba(255,255,255,0.7)',
                fontSize: 13
              }}
            >
              <span style={{ color: currentPage === item.id ? '#f59e0b' : 'rgba(255,255,255,0.5)' }}>{item.icon}</span>
              {item.label}
            </div>
          ))}
        </div>

        <div style={{ padding: '12px 16px', borderTop: '1px solid rgba(255,255,255,0.1)' }}>
          <div className="flex items-center gap-2">
            <div style={{ width: 32, height: 32, borderRadius: '50%', background: 'rgba(255,255,255,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, fontWeight: 600, color: '#fff' }}>
              {(user.username || 'U').slice(0, 1).toUpperCase()}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div className="text-xs font-medium" style={{ color: '#fff' }}>{user.username || '用户'}</div>
              <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.5)' }}>{user.role || '销售'}</div>
            </div>
            <button className="btn btn-secondary" style={{ padding: '4px 8px', fontSize: 11 }} onClick={handleLogout}><IconArrowRight />退出</button>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div style={{ flex: 1, overflow: 'auto', padding: '24px 28px', background: '#f8fafc' }}>
        {pageComponents[currentPage]}
      </div>
    </div>
  );
}

// ========== Mount with error handling ==========
try {
  const rootEl = document.getElementById('root');
  if (!rootEl) throw new Error('Root element not found');
} catch (err) {
  console.error('CRM Application Error:', err);
  const errDisplay = document.getElementById('error-display');
  const errMsg = document.getElementById('error-message');
  if (errDisplay && errMsg) {
    errDisplay.style.display = 'block';
    errMsg.textContent = err.message || String(err);
  }
}

export default App;
