import React, { useEffect, useState } from 'react';
import { request } from './api.js';
import { useRef } from 'react';

function formatCell(value) {
  if (value === null || value === undefined) return 'NULL';
  return typeof value === 'object' ? JSON.stringify(value) : String(value);
}

function ResultTable({ columns, rows }) {
  if (!columns.length) return <div className="empty"><span className="empty-symbol">▤</span><p>Chưa có kết quả truy vấn.</p></div>;
  return <div className="table-scroll"><table><thead><tr>{columns.map((column, index) => <th key={index}>{column}</th>)}</tr></thead><tbody>
    {rows.map((row, index) => <tr key={index}>{columns.map((column, cell) => <td key={cell}>{formatCell(Array.isArray(row) ? row[cell] : row[column])}</td>)}</tr>)}
    {!rows.length && <tr><td colSpan={columns.length}>Không có dòng dữ liệu.</td></tr>}
  </tbody></table></div>;
}

export default function App() {
  const [catalog, setCatalog] = useState({ loading: true, items: [], error: '' });
  const [selectedDbId, setSelectedDbId] = useState('');
  const [search, setSearch] = useState('');
  const [schema, setSchema] = useState({ dbId: '', loading: false, data: null, error: '' });
  const [nlp, setNlp] = useState({ loading: true, data: null, error: '' });
  const [question, setQuestion] = useState('');
  const [refresh, setRefresh] = useState(0);
  const [query, setQuery] = useState({ loading: false, result: null, error: '' });
  const queryVersion = useRef(0);

  useEffect(() => {
    queryVersion.current += 1;
    setQuery({ loading: false, result: null, error: '' });
    return () => { queryVersion.current += 1; };
  }, [selectedDbId]);

  function chooseDatabase(dbId) {
    queryVersion.current += 1;
    setQuery({ loading: false, result: null, error: '' });
    setSelectedDbId(dbId);
  }

  async function submitQuestion(event) {
    event.preventDefault();
    if (!nlp.data?.model_loaded || !selectedDbId || !question.trim() || query.loading) return;
    const version = ++queryVersion.current;
    setQuery({ loading: true, result: null, error: '' });
    try {
      const result = await request('/api/query', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: question.trim(), db_id: selectedDbId }),
        timeoutMs: 120000,
      });
      if (version === queryVersion.current) setQuery({ loading: false, result, error: '' });
    } catch (error) {
      if (version === queryVersion.current) setQuery({ loading: false, result: null, error: error.message });
    }
  }

  useEffect(() => {
    let active = true;
    setCatalog({ loading: true, items: [], error: '' });
    request('/api/databases').then(items => {
      if (!active) return;
      setCatalog({ loading: false, items, error: '' });
      setSelectedDbId(current => items.some(item => item.db_id === current)
        ? current : items.find(item => item.db_id === 'cinema')?.db_id ?? items[0]?.db_id ?? '');
    }).catch(error => {
      if (active) setCatalog({ loading: false, items: [], error: error.message });
    });
    return () => { active = false; };
  }, [refresh]);

  useEffect(() => {
    let active = true;
    setNlp({ loading: true, data: null, error: '' });
    request('/nlp/status').then(data => {
      if (active) setNlp({ loading: false, data, error: '' });
    }).catch(error => {
      if (active) setNlp({ loading: false, data: null, error: error.message });
    });
    return () => { active = false; };
  }, [refresh]);

  useEffect(() => {
    if (!selectedDbId) return;
    let active = true;
    setSchema({ dbId: selectedDbId, loading: true, data: null, error: '' });
    request(`/api/databases/${encodeURIComponent(selectedDbId)}/schema`).then(data => {
      if (active) setSchema({ dbId: selectedDbId, loading: false, data, error: '' });
    }).catch(error => {
      if (active) setSchema({ dbId: selectedDbId, loading: false, data: null, error: error.message });
    });
    // Ignore stale responses when the user changes database quickly.
    return () => { active = false; };
  }, [selectedDbId, refresh]);

  const currentSchema = schema.dbId === selectedDbId ? schema : null;
  const tables = currentSchema?.data?.tables ?? [];
  const schemaLoading = Boolean(selectedDbId) && (!currentSchema || currentSchema.loading);
  const matches = catalog.items.filter(item => item.db_id.toLowerCase().includes(search.trim().toLowerCase()));
  const selectedOutsideFilter = selectedDbId && !matches.some(item => item.db_id === selectedDbId);
  const modelLabel = nlp.loading ? 'Đang kiểm tra model…' : nlp.error ? 'Chưa rõ trạng thái model'
    : nlp.data?.model_loaded ? 'Model đã tải' : 'Model chưa tải';

  return <div className="app-shell">
    <header className="header">
      <div className="brand-mark" aria-hidden="true">V<span>↗</span></div>
      <div className="heading"><div className="eyebrow">NATURAL LANGUAGE PROCESSING · DEMO NGHIÊN CỨU</div><h1>Vietnamese Text-to-SQL</h1><p>Truy vấn cơ sở dữ liệu bằng ngôn ngữ tự nhiên tiếng Việt</p></div>
      
    </header>
    <main className="workspace">
      <aside className="panel database-panel">
        <div className="panel-heading"><h2>Cơ sở dữ liệu</h2><span className="engine">ViText2SQL</span></div>
        <div className={`connection ${catalog.loading ? 'pending' : catalog.error ? 'failed' : 'connected'}`} role="status"><i />{catalog.loading ? 'Đang tải danh sách…' : catalog.error ? 'Chưa tải được danh sách' : `${catalog.items.length} database trong dataset`}</div>
        <label className="input-label" htmlFor="database-search">Tìm database</label>
        <input id="database-search" className="database-control" type="search" value={search} onChange={event => setSearch(event.target.value)} placeholder="Nhập db_id…" disabled={catalog.loading || !catalog.items.length} />
        <label className="input-label database-select-label" htmlFor="database-select">Chọn database</label>
        <select id="database-select" className="database-control" value={selectedDbId} onChange={event => chooseDatabase(event.target.value)} disabled={catalog.loading || !catalog.items.length} aria-describedby="database-filter-status">
          {!selectedDbId && <option value="">Chưa chọn database</option>}
          {selectedOutsideFilter && <option value={selectedDbId}>{selectedDbId} (đang chọn)</option>}
          {matches.map(item => <option key={item.db_id} value={item.db_id}>{item.db_id}</option>)}
        </select>
        <p id="database-filter-status" className="filter-status" role="status">{catalog.loading ? 'Đang tải…' : matches.length ? `${matches.length} database phù hợp` : 'Không tìm thấy database phù hợp.'}</p>
        {catalog.error && <p className="error-text" role="alert">{catalog.error}</p>}
        <p className="label">DATABASE ĐANG CHỌN</p><div className="database-name">{selectedDbId || 'Chưa chọn'}</div>
        <div className="schema-heading"><h3>Danh sách bảng</h3><span>{currentSchema?.data ? tables.length : '—'}</span></div>
        <div className="schema-list" aria-busy={schemaLoading}>
          {schemaLoading ? <p className="muted" role="status">Đang tải schema…</p> : tables.map(table => <details className="schema-table" key={`${selectedDbId}:${table.table_id}`}>
            <summary><span><span className="table-icon" aria-hidden="true">▦</span> {table.name}</span><small>{table.columns.length} cột</small></summary>
            <ul>{table.columns.map(column => <li key={column.column_id}><code>{column.name}</code><small>{column.data_type}{column.primary_key ? ' · PK' : ''}</small></li>)}</ul>
          </details>)}
          {currentSchema?.error && <p className="error-text" role="alert">{currentSchema.error}</p>}
          {!schemaLoading && currentSchema?.data && !tables.length && <p className="muted">Schema chưa có bảng.</p>}
        </div>
        <button className="refresh" onClick={() => setRefresh(value => value + 1)} disabled={catalog.loading || schemaLoading || nlp.loading}>↻ Tải lại metadata</button>
        <div className="sidebar-note"><strong>Schema ViText2SQL</strong><p>Mở từng bảng để xem các cột. Tên schema được hiển thị theo dataset tiếng Việt.</p></div>
      </aside>
      <section className="content">
        <section className="panel query-panel">
          <div className="section-kicker">01 / ĐẶT CÂU HỎI</div><h2>Bạn muốn tìm thông tin gì?</h2><p className="muted">Nhập câu hỏi bằng tiếng Việt cho database đã chọn.</p>
          <div className="query-context"><span>Database mục tiêu: <strong>{selectedDbId || 'Chưa chọn'}</strong></span><span className="model-status" role="status">{modelLabel}{nlp.data?.device ? ` · ${nlp.data.device}` : ''}</span></div>
          {nlp.error && <p className="error-text" role="alert">{nlp.error}</p>}
          <form onSubmit={submitQuestion}>
            <label className="input-label" htmlFor="question">Câu hỏi của bạn</label>
            <textarea id="question" value={question} onChange={event => setQuestion(event.target.value)} maxLength={2000} disabled={query.loading} placeholder="Nhập câu hỏi về database đang chọn…" />
            <div className="form-footer"><small>{question.length}/2000 ký tự</small><button className="primary" type="submit" disabled={!nlp.data?.model_loaded || !selectedDbId || !question.trim() || query.loading || schemaLoading || !currentSchema?.data || catalog.loading || Boolean(catalog.error)}>{query.loading ? 'Đang xử lý…' : 'Truy vấn'} <span aria-hidden="true">→</span></button></div>
          </form>
          
          {query.error && <p className="error-text" role="alert">{query.error}</p>}
        </section>
        <div className="result-heading" aria-live="polite"><div className="section-kicker">02 / PHẢN HỒI</div><span>{query.loading ? 'Đang xử lý truy vấn…' : query.result ? `Kết quả từ ${query.result.db_id}` : 'Chưa có kết quả'}</span></div>
        <div className="result-grid">
          <section className="panel result-card"><div className="panel-heading"><h2>Câu lệnh SQL</h2><span className="tag">SQL</span></div><pre className={query.result ? '' : 'sql-placeholder'}><code>{query.result?.generated_sql ?? 'Chưa có câu lệnh SQL.'}</code></pre></section>
          <section className="panel result-card"><div className="panel-heading"><h2>Câu trả lời</h2><span className="tag">Tiếng Việt</span></div><p className={`answer ${query.result?.natural_answer ? '' : 'muted'}`}> {query.result?.natural_answer ?? 'Chưa có câu trả lời.'} </p></section>
        </div>
        <section className="panel results-panel"><div className="panel-heading"><h2>Kết quả truy vấn</h2><span className="tag">{query.result?.row_count ?? 0} dòng</span></div><ResultTable columns={query.result?.columns ?? []} rows={query.result?.rows ?? []} />{query.result?.truncated && <p className="muted">Chỉ hiển thị 100 dòng đầu tiên.</p>}</section>
      </section>
    </main>
    <footer>Vietnamese Text-to-SQL <span>Đồ án cao học · Natural Language Processing</span></footer>
  </div>;
}
