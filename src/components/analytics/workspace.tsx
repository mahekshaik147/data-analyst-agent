import { Link, Outlet, useRouterState } from "@tanstack/react-router";
import {
  Activity, AlertCircle, ArrowDown, ArrowUp, BarChart3, Check, ChevronDown,
  CircleHelp, Clock3, Copy, Database, Download, FileSpreadsheet, FlaskConical,
  Gauge, LayoutDashboard, LoaderCircle, Menu, MessageSquareText, Moon, Plus,
  RefreshCw, Search, Send, Settings2, ShieldCheck, Sparkles, SquareTerminal,
  Sun, Table2, X,
} from "lucide-react";
import { createContext, useContext, useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react";
import {
  Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { api, apiBaseUrl, type AnalysisResponse, type Dataset, type DatasetSchema, type EvaluationReport } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const navItems = [
  { to: "/", title: "Overview", icon: LayoutDashboard },
  { to: "/analyst", title: "AI Analyst", icon: MessageSquareText },
  { to: "/datasets", title: "Dataset Explorer", icon: Database },
  { to: "/evaluation", title: "Evaluation Center", icon: FlaskConical },
  { to: "/settings", title: "Settings", icon: Settings2 },
] as const;

type WorkspaceConfig = {
  dataset: string;
  setDataset: (dataset: string) => void;
  maxRows: string;
  setMaxRows: (rows: string) => void;
  density: "comfortable" | "compact";
  setDensity: (density: "comfortable" | "compact") => void;
};
const WorkspaceConfigContext = createContext<WorkspaceConfig | null>(null);
function useWorkspaceConfig() {
  return useContext(WorkspaceConfigContext);
}

export function WorkspaceLayout({ children }: { children?: ReactNode }) {
  const path = useRouterState({ select: (state) => state.location.pathname });
  const [menuOpen, setMenuOpen] = useState(false);
  const [dark, setDark] = useState(false);
  const [health, setHealth] = useState<"loading" | "online" | "offline">("loading");
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [dataset, setDataset] = useState("");
  const [maxRows, setMaxRows] = useState("100");
  const [density, setDensity] = useState<"comfortable" | "compact">("comfortable");
  const [connectionError, setConnectionError] = useState("");

  useEffect(() => {
    void api.health().then((value) => { setHealth(["ok", "healthy", "connected", "up"].includes(value.status.toLowerCase()) ? "online" : "offline"); setConnectionError(""); }).catch(() => { setHealth("offline"); setConnectionError("Backend unavailable"); });
    void api.datasets().then((value) => {
      const entries = Array.isArray(value) ? value : value.datasets;
      setDatasets(entries);
      if (entries[0]) setDataset(entries[0].id);
    }).catch(() => setDatasets([]));
  }, []);

  function toggleTheme() {
    setDark((current) => {
      const next = !current;
      document.documentElement.classList.toggle("dark", next);
      return next;
    });
  }

  const pageTitle = navItems.find((item) => item.to === path)?.title ?? "Overview";
  const workspaceConfig = useMemo(() => ({ dataset, setDataset, maxRows, setMaxRows, density, setDensity }), [dataset, maxRows, density]);
  return (
    <div className="workspace-shell">
      <aside className={`workspace-sidebar ${menuOpen ? "sidebar-open" : ""}`}>
        <Link to="/" className="brand-lockup" onClick={() => setMenuOpen(false)}>
          <span className="brand-mark"><BarChart3 size={18} strokeWidth={2.3} /></span>
          <span className="brand-copy"><strong>Data Analyst</strong><small>AGENT WORKSPACE</small></span>
        </Link>
        <Button asChild className="new-analysis"><Link to="/analyst" search={{ question: "" }}><Plus size={16} /> New analysis</Link></Button>
        <div className="nav-caption">WORKSPACE</div>
        <nav className="side-nav" aria-label="Main navigation">
          {navItems.map((item) => {
            const active = path === item.to;
            return <Link key={item.to} to={item.to} className={`nav-link ${active ? "nav-link-active" : ""}`} onClick={() => setMenuOpen(false)}><item.icon size={17} /><span>{item.title}</span>{active && <span className="nav-indicator" />}</Link>;
          })}
        </nav>
        <div className="sidebar-bottom">
          <div className="connection-box"><span className={`connection-dot ${health}`} /><div><strong>{health === "online" ? "Backend connected" : health === "loading" ? "Connecting…" : "Backend offline"}</strong><small>{connectionError || apiBaseUrl() || "Same-origin API"}</small></div>{health === "online" && <span className="connection-pulse" />}</div>
          <div className="sidebar-dataset"><Database size={15} /><span>{datasets.find((entry) => entry.id === dataset)?.name ?? "No dataset selected"}</span><ChevronDown size={14} /></div>
          <div className="profile-row"><div className="profile-avatar">MA</div><div><strong>Analyst</strong><small>Workspace user</small></div><Link to="/settings" className="icon-button profile-menu" title="Open settings" aria-label="Open settings"><Settings2 size={16} /></Link></div>
        </div>
      </aside>
      {menuOpen && <button className="mobile-scrim" onClick={() => setMenuOpen(false)} aria-label="Close navigation" />}
      <WorkspaceConfigContext.Provider value={workspaceConfig}>
      <main className="workspace-main">
        <header className="topbar">
          <div className="topbar-title"><Button variant="ghost" size="icon" className="mobile-menu" onClick={() => setMenuOpen(!menuOpen)} aria-label="Toggle navigation"><Menu size={19} /></Button><div><div className="breadcrumb">WORKSPACE <span>/</span> {pageTitle.toUpperCase()}</div><h1>{pageTitle}</h1></div></div>
          <div className="topbar-actions">
            <Select value={dataset} onValueChange={setDataset} disabled={!datasets.length}><SelectTrigger className="dataset-select"><Database size={15} /><SelectValue placeholder="No dataset" /></SelectTrigger><SelectContent>{datasets.map((entry) => <SelectItem key={entry.id} value={entry.id}>{entry.name}</SelectItem>)}</SelectContent></Select>
            <span className={`header-status ${health}`}><span className="connection-dot" /> <span>{health === "online" ? "Connected" : health === "loading" ? "Checking" : "Offline"}</span></span>
            <Button variant="ghost" size="icon" className="theme-toggle" onClick={toggleTheme} aria-label={dark ? "Switch to light theme" : "Switch to dark theme"} title="Toggle theme">{dark ? <Sun size={17} /> : <Moon size={17} />}</Button>
            <div className="profile-avatar header-avatar" aria-label="Analyst profile">MA</div>
          </div>
        </header>
        <div className="page-content">{children ?? <Outlet />}</div>
      </main>
      </WorkspaceConfigContext.Provider>
    </div>
  );
}

const questions = [
  "Which five products generated the highest sales?",
  "What is the monthly order trend?",
  "Who are the top ten customers by order value?",
  "Which product categories have the highest revenue?",
  "Which products have low stock?",
  "Which employees handled the most orders?",
];

export function OverviewPage() {
  const workspace = useWorkspaceConfig();
  const [health, setHealth] = useState<"loading" | "online" | "offline">("loading");
  const [schema, setSchema] = useState<DatasetSchema | null>(null);
  useEffect(() => {
    void api.health().then(() => setHealth("online")).catch(() => setHealth("offline"));
    void api.schema(workspace?.dataset).then(setSchema).catch(() => setSchema(null));
  }, [workspace?.dataset]);
  return <div className="overview-page">
    <section className="welcome-row"><div><div className="eyebrow"><span className="eyebrow-line" /> ANALYTICS WORKSPACE</div><h2>Your data. Your questions.<br /><span>Intelligent insights.</span></h2><p>Explore business data using natural language, SQL, and interactive visualizations.</p><div className="welcome-cta"><Button asChild><Link to="/analyst" search={{ question: "" }}><Sparkles size={16} /> Start an analysis <span className="button-arrow">→</span></Link></Button><span className={`workspace-connection ${health}`}><span className="connection-dot" />{health === "online" ? "Data source connected" : health === "loading" ? "Checking data source" : "Waiting for backend"}</span></div></div><div className="welcome-art" aria-hidden="true"><div className="art-grid"><span /><span /><span /><span /><span /><span /><span /><span /><span /><span /><span /><span /><span /><span /><span /><span /><span /><span /><span /><span /><span /><span /><span /><span /><span /><span /><span /><span /><span /><span /><span /><span /><span /><span /><span /><span /><span /><span /><span /><span /><span /><span /><span /><span /><span /><span /><span /><span /><span /></div><div className="art-orbit"><div className="art-core"><Activity size={23} /></div><i /><i /><i /></div><div className="art-note note-top"><span className="note-dot" /> Live schema</div><div className="art-note note-bottom"><BarChart3 size={14} /> Natural language → SQL</div></div></section>
    <section className="kpi-grid" aria-label="Workspace metrics">
      <Metric icon={<Database size={17} />} label="Tables discovered" value={schema ? String(schema.tables.length) : "—"} note={schema ? "Live schema" : "Connect backend to load"} accent="blue" />
      <Metric icon={<MessageSquareText size={17} />} label="Queries run" value="—" note="Available with backend" accent="teal" />
      <Metric icon={<ShieldCheck size={17} />} label="SQL success rate" value="—" note="Not yet evaluated" accent="green" />
      <Metric icon={<Clock3 size={17} />} label="Average query time" value="—" note="Available with backend" accent="amber" />
    </section>
    <div className="overview-grid">
      <section className="surface-panel recent-panel"><div className="section-heading"><div><span className="section-kicker">WORKSPACE</span><h3>Recent analyses</h3></div><Link to="/analyst" search={{ question: "" }} className="text-link">Open analyst <span>→</span></Link></div><div className="empty-activity"><div className="empty-icon"><MessageSquareText size={20} /></div><strong>No analyses yet</strong><p>Your completed analyses will appear here.</p><Button variant="outline" size="sm" asChild><Link to="/analyst" search={{ question: "" }}><Plus size={14} /> Start your first analysis</Link></Button></div></section>
      <section className="surface-panel dataset-summary"><div className="section-heading"><div><span className="section-kicker">DATA SOURCE</span><h3>Dataset summary</h3></div><Link to="/datasets" className="icon-link" aria-label="Open dataset explorer"><ArrowUp size={15} /></Link></div><div className="dataset-card"><div className="dataset-icon"><Database size={18} /></div><div><strong>{schema?.dataset ?? "No dataset connected"}</strong><p>{schema ? `${schema.tables.length} tables discovered from the live schema` : "Schema details load when the backend is connected"}</p></div><span className={`source-state ${health}`}>{health === "online" ? "READY" : health === "loading" ? "CHECKING" : "OFFLINE"}</span></div><div className="dataset-facts"><span><Table2 size={14} /> Tables <strong>{schema ? schema.tables.length : "—"}</strong></span><span><Activity size={14} /> Connection <strong>{health === "online" ? "Active" : health === "loading" ? "Checking" : "Offline"}</strong></span></div></section>
      <section className="surface-panel questions-panel"><div className="section-heading"><div><span className="section-kicker">GET STARTED</span><h3>Questions to explore</h3></div><CircleHelp size={17} className="muted-icon" /></div><div className="faq-list">{questions.slice(0, 4).map((question, index) => <Link key={question} to="/analyst" search={{ question }} className="faq-item"><span className="faq-index">0{index + 1}</span><span>{question}</span><span className="faq-arrow">↗</span></Link>)}</div><Link to="/analyst" search={{ question: "" }} className="more-questions">Explore all suggested questions <span>→</span></Link></section>
      <section className="activity-panel"><div className="activity-copy"><span className="section-kicker">BUILT FOR CLARITY</span><h3>From question<br />to confident action.</h3><p>Bring your business data into focus with a workflow built around transparent SQL and real results.</p><div className="activity-steps"><span><i>01</i> Ask in plain English</span><span><i>02</i> Inspect generated SQL</span><span><i>03</i> Share clear results</span></div></div><div className="activity-graphic" aria-hidden="true"><div className="graph-label">QUERY FLOW <span>●</span></div><div className="flow-line"><div className="flow-node"><MessageSquareText size={16} /></div><div className="flow-dash" /><div className="flow-node"><SquareTerminal size={16} /></div><div className="flow-dash" /><div className="flow-node flow-node-accent"><BarChart3 size={16} /></div></div><div className="flow-caption"><span>QUESTION</span><span>SQL</span><span>INSIGHT</span></div></div></section>
    </div>
  </div>;
}

function Metric({ icon, label, value, note, accent }: { icon: ReactNode; label: string; value: string; note: string; accent: string }) {
  return <div className={`metric-card metric-${accent}`}><div className="metric-top"><span className="metric-icon">{icon}</span><span className="metric-status"><i /> WORKSPACE</span></div><div className="metric-label">{label}</div><div className="metric-value">{value}</div><div className="metric-note">{note}</div></div>;
}

type ChatMessage = { question: string; response?: AnalysisResponse; error?: string; pending?: boolean; cancelled?: boolean };
type ResultTab = "overview" | "sql" | "table" | "chart";

export function AnalystPage() {
  const workspace = useWorkspaceConfig();
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [tab, setTab] = useState<ResultTab>("overview");
  const [chartType, setChartType] = useState<"bar" | "line" | "pie" | "table">("bar");
  const [controller, setController] = useState<AbortController | null>(null);
  const search = useRouterState({ select: (state) => state.location.search as { question?: string } });
  useEffect(() => { if (search.question) setQuestion(search.question); }, [search.question]);

  async function submitQuestion(value = question) {
    const trimmed = value.trim();
    if (!trimmed || controller) return;
    const aborter = new AbortController();
    setController(aborter);
    setQuestion("");
    const index = messages.length;
    setMessages((current) => [...current, { question: trimmed, pending: true }]);
    setActiveIndex(index);
    setTab("overview");
    try {
      const response = await api.analyze({ question: trimmed, ...(workspace?.dataset ? { dataset: workspace.dataset } : {}), max_rows: Number(workspace?.maxRows ?? 100) }, aborter.signal);
      setChartType(response.chart?.type ?? "bar");
      setMessages((current) => current.map((item, i) => i === index ? { question: trimmed, response } : item));
    } catch (error) {
      const message = error instanceof Error ? error.message : "The analysis could not be completed.";
      setMessages((current) => current.map((item, i) => i === index ? { question: trimmed, error: aborter.signal.aborted ? "This request was canceled before the analysis completed." : message, cancelled: aborter.signal.aborted } : item));
    } finally { setController(null); }
  }

  function onSubmit(event: FormEvent) { event.preventDefault(); void submitQuestion(); }
  const active = messages[activeIndex];
  return <div className="analyst-page">
    <div className="analyst-heading"><div><div className="eyebrow"><span className="eyebrow-line" /> NATURAL LANGUAGE ANALYTICS</div><h2>Ask your business data anything.</h2><p>Ask a question and get a transparent SQL query with results from your connected dataset.</p></div><Button variant="outline" size="sm" onClick={() => { setMessages([]); setActiveIndex(-1); setTab("overview"); }} disabled={!messages.length}><RefreshCw size={14} /> Clear conversation</Button></div>
    {messages.length === 0 ? <div className="analyst-empty"><div className="assistant-mark"><Sparkles size={21} /></div><h3>What would you like to know?</h3><p>Start with a question below or write your own.</p><div className="suggestion-grid">{questions.map((item, i) => <button className="suggestion-card" key={item} onClick={() => void submitQuestion(item)}><span className="suggestion-icon">{i % 3 === 0 ? <BarChart3 size={16} /> : i % 3 === 1 ? <Activity size={16} /> : <Database size={16} />}</span><span>{item}</span><span className="suggestion-arrow">↗</span></button>)}</div></div> : <div className="conversation-area">
      <div className="conversation-list">{messages.map((message, i) => <button key={`${message.question}-${i}`} className={`conversation-item ${activeIndex === i ? "selected" : ""}`} onClick={() => setActiveIndex(i)}><span className="conversation-question">{message.question}</span><span className={`conversation-state ${message.pending ? "pending" : message.cancelled ? "pending" : message.error ? "failed" : "complete"}`}>{message.pending ? "Running" : message.cancelled ? "Canceled" : message.error ? "Failed" : "Complete"}</span></button>)}</div>
      {active && <section className="answer-workspace"><div className="question-bubble"><div className="profile-avatar small-avatar">MA</div><span>{active.question}</span></div>{active.pending ? <div className="analysis-loading"><LoaderCircle className="spin" size={18} /><span>Analyzing your question…</span><Button variant="ghost" size="sm" onClick={() => controller?.abort()}><X size={14} /> Cancel</Button></div> : active.error ? <div className="backend-error"><div className="error-icon"><AlertCircle size={18} /></div><div><strong>{active.cancelled ? "Analysis canceled" : "Couldn’t complete this analysis"}</strong><p>{active.error}</p><Button size="sm" variant="outline" onClick={() => void submitQuestion(active.question)}><RefreshCw size={14} /> {active.cancelled ? "Run again" : "Try again"}</Button></div></div> : active.response ? <AnalysisResult result={active.response} tab={tab} setTab={setTab} chartType={chartType} setChartType={setChartType} /> : null}</section>}
    </div>}
    <form className="chat-composer" onSubmit={onSubmit}><Textarea value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Ask a question about your data…" rows={2} disabled={Boolean(controller)} aria-label="Ask a question about your data" onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); void submitQuestion(); } }} /><div className="composer-footer"><span><Sparkles size={13} /> Answers use your connected dataset</span><Button type="submit" size="sm" disabled={!question.trim() || Boolean(controller)}>{controller ? <LoaderCircle className="spin" size={15} /> : <Send size={14} />} Ask analyst</Button></div></form>
  </div>;
}

function AnalysisResult({ result, tab, setTab, chartType, setChartType }: { result: AnalysisResponse; tab: ResultTab; setTab: (tab: ResultTab) => void; chartType: "bar" | "line" | "pie" | "table"; setChartType: (type: "bar" | "line" | "pie" | "table") => void }) {
  const [copied, setCopied] = useState(false);
  const [sort, setSort] = useState<{ key: string; asc: boolean } | null>(null);
  const [page, setPage] = useState(0);
  const columns = result.result.columns ?? [];
  const sortedRows = useMemo(() => {
    if (!sort) return result.result.rows ?? [];
    return [...(result.result.rows ?? [])].sort((a, b) => {
      const av = a[sort.key]; const bv = b[sort.key];
      const order = typeof av === "number" && typeof bv === "number" ? av - bv : String(av ?? "").localeCompare(String(bv ?? ""), undefined, { numeric: true });
      return sort.asc ? order : -order;
    });
  }, [result.result.rows, sort]);
  const pageRows = sortedRows.slice(page * 10, page * 10 + 10);
  async function copySql() { await navigator.clipboard.writeText(result.sql ?? ""); setCopied(true); window.setTimeout(() => setCopied(false), 1500); }
  function exportCsv() {
    const csv = [columns, ...sortedRows.map((row) => columns.map((column) => String(row[column] ?? "")))].map((row) => row.map((value) => `"${String(value).replaceAll('"', '""')}"`).join(",")).join("\n");
    const link = document.createElement("a"); link.href = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" })); link.download = "analysis-results.csv"; link.click(); URL.revokeObjectURL(link.href);
  }
  const rows = result.result.rows ?? [];
  const labelColumn = columns.at(0);
  const valueColumn = columns.at(1);
  const chartData = labelColumn && valueColumn ? rows.filter((row) => typeof row[valueColumn] === "number").map((row) => ({ name: String(row[labelColumn] ?? ""), value: Number(row[valueColumn]) })) : [];
  const tabs: { id: ResultTab; label: string; icon: typeof Activity }[] = [{ id: "overview", label: "Overview", icon: Activity }, { id: "sql", label: "SQL query", icon: SquareTerminal }, { id: "table", label: "Data table", icon: Table2 }, { id: "chart", label: "Visualization", icon: BarChart3 }];
  return <div className="result-card"><div className="result-topline"><div><span className="result-label"><span className="result-live-dot" /> ANALYSIS RESULT</span><h3>Here’s what I found</h3></div><Badge variant="secondary" className="result-status"><Check size={12} /> {result.status ?? "Query complete"}</Badge></div><div className="result-tabs" role="tablist">{tabs.map((item) => <button key={item.id} role="tab" aria-selected={tab === item.id} className={`result-tab ${tab === item.id ? "active" : ""}`} onClick={() => setTab(item.id)}><item.icon size={15} /> {item.label}</button>)}</div>
    {tab === "overview" && <div className="result-overview"><div className="answer-prose"><span className="section-kicker">ANSWER</span><p>{result.answer}</p></div>{result.findings?.length ? <div className="finding-list"><span className="section-kicker">KEY FINDINGS</span>{result.findings.map((finding, i) => <div className="finding-row" key={`${finding}-${i}`}><span>{String(i + 1).padStart(2, "0")}</span><p>{finding}</p></div>)}</div> : null}<div className="result-meta"><span><Database size={14} /> {result.result.row_count ?? rows.length} rows returned</span><span><Clock3 size={14} /> {result.execution_time_ms ?? result.result.execution_time_ms ?? "—"}{result.execution_time_ms || result.result.execution_time_ms ? " ms" : ""}</span><span><ShieldCheck size={14} /> SQL executed</span></div></div>}
    {tab === "sql" && <div className="sql-pane"><div className="sql-toolbar"><span><span className="sql-live-dot" /> Executed SQL</span><Button variant="outline" size="sm" onClick={() => void copySql()}>{copied ? <Check size={13} /> : <Copy size={13} />}{copied ? "Copied" : "Copy SQL"}</Button></div><pre><code>{result.sql || "No SQL was returned by the service."}</code></pre><div className="sql-foot"><span><Clock3 size={13} /> {result.execution_time_ms ?? result.result.execution_time_ms ?? "—"} ms</span><span><Table2 size={13} /> {result.result.row_count ?? rows.length} rows</span>{result.correction_attempts !== undefined && <span>{result.correction_attempts} corrections</span>}</div></div>}
    {tab === "table" && <div className="table-pane"><div className="table-toolbar"><span>{result.result.row_count ?? rows.length} results</span><Button variant="outline" size="sm" onClick={exportCsv} disabled={!rows.length}><Download size={13} /> Export CSV</Button></div>{rows.length ? <><div className="data-table-wrap"><table className="data-table"><thead><tr>{columns.map((column) => <th key={column}><button onClick={() => { setSort((current) => current?.key === column ? { key: column, asc: !current.asc } : { key: column, asc: true }); setPage(0); }}>{column}{sort?.key === column && (sort.asc ? <ArrowUp size={12} /> : <ArrowDown size={12} />)}</button></th>)}</tr></thead><tbody>{pageRows.map((row, index) => <tr key={index}>{columns.map((column) => <td key={column}>{formatValue(row[column])}</td>)}</tr>)}</tbody></table></div><div className="table-pagination"><span>Page {page + 1} of {Math.max(1, Math.ceil(sortedRows.length / 10))}</span><div><Button variant="outline" size="sm" disabled={page === 0} onClick={() => setPage(page - 1)}>Previous</Button><Button variant="outline" size="sm" disabled={(page + 1) * 10 >= sortedRows.length} onClick={() => setPage(page + 1)}>Next</Button></div></div></> : <EmptyState icon={<Table2 size={18} />} title="No rows returned" detail="The service returned an empty result set." />}</div>}
    {tab === "chart" && <div className="chart-pane"><div className="chart-toolbar"><div><span className="section-kicker">VISUALIZATION</span><strong>{result.chart?.title ?? "Query results"}</strong></div><Select value={chartType} onValueChange={(value) => setChartType(value as typeof chartType)}><SelectTrigger className="chart-select"><SelectValue /></SelectTrigger><SelectContent>{["bar", "line", "pie", "table"].map((type) => <SelectItem key={type} value={type}>{type[0]?.toUpperCase()}{type.slice(1)} chart</SelectItem>)}</SelectContent></Select></div>{chartType === "table" || !chartData.length ? <div className="chart-fallback"><Table2 size={18} /><span>{chartData.length ? "Table view selected" : "Chart unavailable for this result structure. View the data table instead."}</span><Button variant="outline" size="sm" onClick={() => setTab("table")}>View data table</Button></div> : <div className="chart-area"><ResponsiveContainer width="100%" height="100%">{chartType === "pie" ? <PieChart><Tooltip /><Legend /><Pie data={chartData.slice(0, 12)} dataKey="value" nameKey="name" outerRadius={120} innerRadius={54}>{chartData.slice(0, 12).map((_, index) => <Cell key={index} fill={`var(--chart-${index % 5 + 1})`} />)}</Pie></PieChart> : chartType === "line" ? <LineChart data={chartData}><CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" /><XAxis dataKey="name" tick={{ fill: "var(--muted-foreground)", fontSize: 11 }} axisLine={false} tickLine={false} /><YAxis tick={{ fill: "var(--muted-foreground)", fontSize: 11 }} axisLine={false} tickLine={false} /><Tooltip /><Line type="monotone" dataKey="value" stroke="var(--chart-1)" strokeWidth={2.5} dot={{ r: 3 }} /></LineChart> : <BarChart data={chartData}><CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" /><XAxis dataKey="name" tick={{ fill: "var(--muted-foreground)", fontSize: 11 }} axisLine={false} tickLine={false} /><YAxis tick={{ fill: "var(--muted-foreground)", fontSize: 11 }} axisLine={false} tickLine={false} /><Tooltip /><Bar dataKey="value" fill="var(--chart-1)" radius={[3, 3, 0, 0]} /></BarChart>}</ResponsiveContainer></div>}</div>}
  </div>;
}

export function DatasetPage() {
  const workspace = useWorkspaceConfig();
  const [schema, setSchema] = useState<DatasetSchema | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState("");
  const [health, setHealth] = useState("checking");
  async function load() { setLoading(true); setError(""); try { const data = await api.schema(workspace?.dataset); setSchema(data); setSelected((current) => current || data.tables[0]?.name || ""); setHealth("Connected"); } catch (caught) { setError(caught instanceof Error ? caught.message : "Unable to load schema."); setHealth("Offline"); } finally { setLoading(false); } }
  useEffect(() => { void load(); }, [workspace?.dataset]);
  const tables = schema?.tables.filter((table) => table.name.toLowerCase().includes(search.toLowerCase())) ?? [];
  const current = schema?.tables.find((table) => table.name === selected);
  return <div className="subpage"><PageIntro eyebrow="LIVE DATABASE SCHEMA" title="Dataset Explorer" description="Browse the tables, columns, and sample records available in your connected database." action={<Button variant="outline" size="sm" onClick={() => void load()}><RefreshCw size={14} /> Refresh schema</Button>} />
    <div className="dataset-status-row"><div className="status-card"><span className={`connection-dot ${health === "Connected" ? "online" : health === "checking" ? "loading" : "offline"}`} /><div><strong>{health}</strong><small>Database connection</small></div></div><div className="status-card"><Table2 size={17} /><div><strong>{schema ? schema.tables.length : "—"}</strong><small>Tables discovered</small></div></div><div className="status-card"><Database size={17} /><div><strong>{schema?.dataset ?? "—"}</strong><small>Selected dataset</small></div></div></div>
    {error ? <ErrorPanel message={error} onRetry={() => void load()} /> : loading ? <LoadingPanel label="Loading database schema…" /> : schema ? <div className="explorer-layout"><section className="surface-panel table-list-panel"><div className="panel-heading"><div><span className="section-kicker">DATABASE TABLES</span><h3>Tables <span>{tables.length}</span></h3></div></div><div className="table-search"><Search size={15} /><Input aria-label="Search tables" placeholder="Search tables…" value={search} onChange={(e) => setSearch(e.target.value)} /></div><div className="table-list">{tables.map((table) => <button key={table.name} className={`table-list-item ${selected === table.name ? "active" : ""}`} onClick={() => setSelected(table.name)}><Table2 size={15} /><span>{table.name}</span><small>{table.columns.length}</small></button>)}{!tables.length && <div className="list-empty">No matching tables</div>}</div></section><section className="surface-panel table-detail-panel">{current ? <><div className="detail-heading"><div><span className="section-kicker">TABLE DETAILS</span><h3>{current.name}</h3></div><Badge variant="secondary">{current.row_count ?? "—"} rows</Badge></div><div className="schema-columns"><div className="schema-header"><span>Column</span><span>Data type</span><span>Keys</span></div>{current.columns.map((column) => <div className="schema-row" key={column.name}><span><strong>{column.name}</strong></span><code>{column.type}</code><span className="schema-key">{column.primary_key && <Badge variant="outline">PK</Badge>}{column.foreign_key && <Badge variant="outline">FK · {column.foreign_key}</Badge>}</span></div>)}</div><div className="sample-heading"><div><span className="section-kicker">SAMPLE RECORDS</span><h4>Preview rows</h4></div><span>{current.sample_rows?.length ?? 0} rows</span></div>{current.sample_rows?.length ? <div className="data-table-wrap sample-table-wrap"><table className="data-table"><thead><tr>{current.columns.map((col) => <th key={col.name}>{col.name}</th>)}</tr></thead><tbody>{current.sample_rows.slice(0, 3).map((row, i) => <tr key={i}>{current.columns.map((col) => <td key={col.name}>{formatValue(row[col.name])}</td>)}</tr>)}</tbody></table></div> : <EmptyState icon={<FileSpreadsheet size={18} />} title="Sample records unavailable" detail="No sample rows were returned for this table." />}</> : <EmptyState icon={<Table2 size={18} />} title="Select a table" detail="Choose a table to inspect its columns and sample records." />}</section></div> : <EmptyState icon={<Database size={18} />} title="No schema available" detail="Connect the backend to load tables from the selected dataset." />}
    {schema?.relationships?.length ? <section className="surface-panel relationship-panel"><div className="section-heading"><div><span className="section-kicker">SCHEMA</span><h3>Table relationships</h3></div></div><div className="relationship-list">{schema.relationships.map((relation, i) => <div className="relation-row" key={`${relation.from}-${relation.to}-${i}`}><span>{relation.from}</span><ArrowDown size={15} /><span>{relation.to}</span>{relation.columns && <small>{relation.columns}</small>}</div>)}</div></section> : null}
  </div>;
}

export function EvaluationPage() {
  const [report, setReport] = useState<EvaluationReport | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  async function load() { setLoading(true); setError(""); try { setReport(await api.evaluation()); } catch (caught) { setError(caught instanceof Error ? caught.message : "Unable to load evaluation results."); } finally { setLoading(false); } }
  useEffect(() => { void load(); }, []);
  async function run() { setRunning(true); setError(""); try { setReport(await api.runEvaluation()); } catch (caught) { setError(caught instanceof Error ? caught.message : "Evaluation could not be started."); } finally { setRunning(false); } }
  const metrics = report?.metrics;
  const hasResults = Boolean(metrics && Object.keys(metrics).length);
  return <div className="subpage"><PageIntro eyebrow="TEXT-TO-SQL BENCHMARK" title="Evaluation Center" description="Measure query reliability, result correctness, safety, and response time across benchmark cases." action={<Button onClick={() => void run()} disabled={running || loading}><>{running ? <LoaderCircle className="spin" size={14} /> : <FlaskConical size={14} />}{running ? "Running…" : "Run evaluation"}</></Button>} />
    {error && <ErrorPanel message={error} onRetry={() => void load()} />}{loading ? <LoadingPanel label="Loading evaluation report…" /> : hasResults ? <><div className="evaluation-metrics"><EvalMetric label="SQL execution success" value={percent(metrics?.execution_success_rate)} icon={<Check size={16} />} /><EvalMetric label="Result correctness" value={percent(metrics?.correctness_rate)} icon={<Gauge size={16} />} /><EvalMetric label="Safety test pass rate" value={percent(metrics?.safety_pass_rate)} icon={<ShieldCheck size={16} />} /><EvalMetric label="Average latency" value={metrics?.average_latency_ms != null ? `${metrics.average_latency_ms} ms` : "—"} icon={<Clock3 size={16} />} /><EvalMetric label="Total test cases" value={metrics?.total_test_cases != null ? String(metrics.total_test_cases) : "—"} icon={<FlaskConical size={16} />} /></div><div className="evaluation-panels"><section className="surface-panel"><div className="section-heading"><div><span className="section-kicker">BENCHMARK RESULTS</span><h3>Difficulty breakdown</h3></div></div>{report?.difficulty?.length ? report.difficulty.map((item, i) => <div className="difficulty-row" key={String(item.level ?? i)}><span>{String(item.level ?? "Level")}</span><div className="difficulty-track"><i style={{ width: `${Math.min(100, Number(item.success_rate ?? 0) * (Number(item.success_rate) <= 1 ? 100 : 1))}%` }} /></div><strong>{percent(item.success_rate as number | undefined)}</strong></div>) : <EmptyState icon={<BarChart3 size={17} />} title="No difficulty breakdown" detail="The backend has not returned breakdown data." />}</section><section className="surface-panel"><div className="section-heading"><div><span className="section-kicker">RUN HISTORY</span><h3>Evaluation history</h3></div></div>{report?.history?.length ? report.history.map((item, i) => <div className="history-row" key={i}><span className="history-date">{String(item.created_at ?? item.date ?? `Run ${i + 1}`)}</span><span>{String(item.total_test_cases ?? "—")} cases</span><Badge variant="secondary">{String(item.status ?? "Complete")}</Badge></div>) : <EmptyState icon={<Clock3 size={17} />} title="No previous runs" detail="Completed benchmark runs will appear here." />}</section></div><section className="surface-panel failures-panel"><div className="section-heading"><div><span className="section-kicker">DEBUGGING</span><h3>Failed test cases</h3></div></div>{report?.failures?.length ? report.failures.map((item, i) => <details className="failure-row" key={i}><summary><span className="failure-indicator" />{String(item.question ?? item.name ?? `Test case ${i + 1}`)}<ChevronDown size={15} /></summary><div><p>{String(item.error ?? item.explanation ?? "No error explanation provided.")}</p><pre>{String(item.sql ?? "No generated SQL available.")}</pre></div></details>) : <EmptyState icon={<ShieldCheck size={17} />} title="No failed cases reported" detail="Failure details will appear when returned by the benchmark." />}</section></> : !error && <section className="surface-panel evaluation-empty"><div className="evaluation-empty-icon"><FlaskConical size={24} /></div><span className="section-kicker">BENCHMARK STATUS</span><h3>No evaluation results yet</h3><p>Run the 30-question Text-to-SQL benchmark to measure query execution, correctness, safety, and latency.</p><Button onClick={() => void run()} disabled={running}>{running ? <LoaderCircle className="spin" size={15} /> : <FlaskConical size={15} />}{running ? "Running benchmark…" : "Run evaluation"}</Button><span className="evaluation-footnote">Metrics appear only after a real benchmark completes.</span></section>}
  </div>;
}

export function SettingsPage() {
  const workspace = useWorkspaceConfig();
  const [health, setHealth] = useState<"idle" | "checking" | "connected" | "failed">("idle");
  const [message, setMessage] = useState("");
  useEffect(() => { document.documentElement.classList.toggle("compact-tables", workspace?.density === "compact"); }, [workspace?.density]);
  async function testConnection() { setHealth("checking"); setMessage(""); try { const result = await api.health(); setHealth("connected"); setMessage(`Connection successful${result.database ? ` · ${result.database}` : ""}.`); } catch (caught) { setHealth("failed"); setMessage(caught instanceof Error ? caught.message : "Could not reach the backend."); } }
  return <div className="subpage"><PageIntro eyebrow="WORKSPACE PREFERENCES" title="Settings" description="Configure the API connection and your analysis display preferences." /><div className="settings-layout">
      <section className="surface-panel settings-section"><div className="section-heading"><div><span className="section-kicker">CONNECTION</span><h3>Backend API</h3></div><div className={`settings-connection ${health}`}><span className="connection-dot" />{health === "connected" ? "Connected" : health === "checking" ? "Testing" : health === "failed" ? "Unavailable" : "Not tested"}</div></div><label className="setting-field"><span>Backend API URL</span><Input value={apiBaseUrl() || "Same-origin /api endpoints"} readOnly /></label><p className="field-hint">Set <code>VITE_API_BASE_URL</code> in your environment to point to the Python service at a different origin.</p><Button variant="outline" size="sm" onClick={() => void testConnection()} disabled={health === "checking"}>{health === "checking" ? <LoaderCircle className="spin" size={14} /> : <RefreshCw size={14} />} Test connection</Button>{message && <p className={`connection-message ${health}`}>{message}</p>}</section>
      <section className="surface-panel settings-section"><div className="section-heading"><div><span className="section-kicker">QUERY DEFAULTS</span><h3>Analysis preferences</h3></div></div><label className="setting-field"><span>Selected dataset</span><Input value={workspace?.dataset || "No dataset selected"} readOnly /><small>Change the selected dataset from the workspace header.</small></label><label className="setting-field"><span>Maximum result rows</span><Input type="number" min="1" max="1000" value={workspace?.maxRows ?? "100"} onChange={(e) => { const parsed = Number(e.target.value); const rows = e.target.value === "" ? "" : String(Math.min(1000, Math.max(1, Math.trunc(parsed) || 1))); workspace?.setMaxRows(rows); }} /><small>Limits the rows returned for each analysis, from 1 to 1,000.</small></label><label className="setting-field"><span>Table density</span><Select value={workspace?.density ?? "comfortable"} onValueChange={(value) => workspace?.setDensity(value as "comfortable" | "compact")}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="comfortable">Comfortable</SelectItem><SelectItem value="compact">Compact</SelectItem></SelectContent></Select></label><div className="safety-note"><ShieldCheck size={16} /><span><strong>SQL safety validation stays enabled.</strong><small>Queries are validated by the backend before execution.</small></span></div></section>
      <section className="surface-panel settings-section app-info"><div className="section-heading"><div><span className="section-kicker">ABOUT</span><h3>Application information</h3></div></div><div className="info-row"><span>Application</span><strong>Data Analyst Agent</strong></div><div className="info-row"><span>Version</span><strong>0.1.0 · Preview</strong></div><div className="info-row"><span>Backend API</span><strong>FastAPI-compatible REST</strong></div><div className="info-row"><span>LLM credentials</span><strong>Managed by backend</strong></div></section>
    </div>
  </div>;
}

function PageIntro({ eyebrow, title, description, action }: { eyebrow: string; title: string; description: string; action?: ReactNode }) { return <div className="page-intro"><div><div className="eyebrow"><span className="eyebrow-line" /> {eyebrow}</div><h2>{title}</h2><p>{description}</p></div>{action}</div>; }
function EvalMetric({ label, value, icon }: { label: string; value: string; icon: ReactNode }) { return <div className="evaluation-metric"><span>{icon}</span><small>{label}</small><strong>{value}</strong></div>; }
function percent(value?: number) { return value == null ? "—" : `${Math.round(value <= 1 ? value * 100 : value)}%`; }
function formatValue(value: unknown) { if (value === null || value === undefined || value === "") return "—"; if (typeof value === "object") return JSON.stringify(value); return String(value); }
function EmptyState({ icon, title, detail }: { icon: ReactNode; title: string; detail: string }) { return <div className="generic-empty"><span>{icon}</span><strong>{title}</strong><p>{detail}</p></div>; }
function ErrorPanel({ message, onRetry }: { message: string; onRetry: () => void }) { return <div className="backend-error page-error"><div className="error-icon"><AlertCircle size={18} /></div><div><strong>Couldn’t connect to the backend</strong><p>{message}</p><Button size="sm" variant="outline" onClick={onRetry}><RefreshCw size={14} /> Retry</Button></div></div>; }
function LoadingPanel({ label }: { label: string }) { return <div className="loading-panel"><LoaderCircle className="spin" size={18} />{label}</div>; }