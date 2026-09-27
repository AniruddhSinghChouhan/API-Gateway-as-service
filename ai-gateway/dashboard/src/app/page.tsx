"use client";

import React, { useState, useEffect } from "react";
import {
  Activity,
  Key,
  Layers,
  ShieldCheck,
  Zap,
  Cpu,
  Database,
  ArrowUpRight,
  TrendingDown,
  RefreshCw,
  Plus,
  Copy,
  Check,
  AlertTriangle,
  Play,
  Send,
  Terminal,
  ExternalLink,
  ChevronRight,
  Lock,
  Search,
  Sparkles,
  Sliders,
  DollarSign,
  Clock,
  CheckCircle2,
  Trash2,
  Gauge
} from "lucide-react";

const GATEWAY_URL = process.env.NEXT_PUBLIC_GATEWAY_URL || "";

interface MetricData {
  total_requests: number;
  total_tokens: number;
  total_cost_usd: number;
  avg_latency_ms: number;
  cache_hits: number;
  cache_hit_rate: number;
  cost_saved_usd: number;
  provider_breakdown: Array<{
    provider: string;
    requests: number;
    avg_latency: number;
    total_cost: number;
  }>;
  model_breakdown: Array<{
    model: string;
    requests: number;
    avg_latency: number;
  }>;
}

interface VirtualKeyItem {
  id: string;
  name: string;
  key_prefix: string;
  masked_key: string;
  token_cap: number | null;
  cost_cap: number | null;
  current_tokens: number;
  current_cost: number;
  rate_limit_rpm: number;
  rate_limit_tpm: number;
  allowed_models: string[];
  is_active: boolean;
  created_at: string;
}

interface RequestLogItem {
  id: string;
  key_name: string;
  provider: string;
  model: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  latency_ms: number;
  cost_usd: number;
  status_code: number;
  cache_hit: string;
  routing_strategy: string;
  error_message: string | null;
  created_at: string;
}

export default function Dashboard() {
  const [activeTab, setActiveTab] = useState<"overview" | "keys" | "playground" | "logs" | "routing">("overview");
  const [gatewayStatus, setGatewayStatus] = useState<"online" | "offline" | "checking">("checking");
  const [metrics, setMetrics] = useState<MetricData | null>(null);
  const [keys, setKeys] = useState<VirtualKeyItem[]>([]);
  const [logs, setLogs] = useState<RequestLogItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  // Key creation modal state
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [newKeyName, setNewKeyName] = useState("");
  const [newTokenCap, setNewTokenCap] = useState("1000000");
  const [newCostCap, setNewCostCap] = useState("50.00");
  const [newRpm, setNewRpm] = useState("120");
  const [createdSecretKey, setCreatedSecretKey] = useState<string | null>(null);
  const [copiedKey, setCopiedKey] = useState(false);
  const [keyCreateError, setKeyCreateError] = useState<string | null>(null);
  const [isSubmittingKey, setIsSubmittingKey] = useState(false);

  // Playground state
  const [pgModel, setPgModel] = useState("openai/gpt-oss-20b");
  const [pgStrategy, setPgStrategy] = useState("cost-optimized");
  const [pgPrompt, setPgPrompt] = useState("Explain AI Gateways in 2 concise sentences.");
  const [pgStream, setPgStream] = useState(false);
  const [pgOutput, setPgOutput] = useState("");
  const [pgLoading, setPgLoading] = useState(false);
  const [pgMeta, setPgMeta] = useState<any>(null);

  // Log filter
  const [logFilter, setLogFilter] = useState("ALL");
  const [searchQuery, setSearchQuery] = useState("");

  const fetchData = async () => {
    setRefreshing(true);
    try {
      // Health check
      const healthRes = await fetch(`${GATEWAY_URL}/health`).catch(() => null);
      if (healthRes && healthRes.ok) {
        setGatewayStatus("online");
      } else {
        setGatewayStatus("offline");
      }

      // Fetch Metrics
      const mRes = await fetch(`${GATEWAY_URL}/api/metrics`).catch(() => null);
      if (mRes && mRes.ok) {
        const mData = await mRes.json();
        setMetrics(mData);
      }

      // Fetch Keys
      const kRes = await fetch(`${GATEWAY_URL}/api/keys`).catch(() => null);
      if (kRes && kRes.ok) {
        const kData = await kRes.json();
        setKeys(kData);
      }

      // Fetch Logs
      const lRes = await fetch(`${GATEWAY_URL}/api/logs?limit=50`).catch(() => null);
      if (lRes && lRes.ok) {
        const lData = await lRes.json();
        setLogs(lData);
      }
    } catch (err) {
      console.error("Failed to fetch gateway data:", err);
      setGatewayStatus("offline");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleCreateKey = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newKeyName.trim()) return;
    setKeyCreateError(null);
    setIsSubmittingKey(true);

    try {
      const res = await fetch(`${GATEWAY_URL}/api/keys`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: newKeyName,
          token_cap: newTokenCap ? parseInt(newTokenCap) : null,
          cost_cap: newCostCap ? parseFloat(newCostCap) : null,
          rate_limit_rpm: newRpm ? parseInt(newRpm) : 120,
          allowed_models: ["*"],
        }),
      });

      if (res.ok) {
        const data = await res.json();
        setCreatedSecretKey(data.api_key);
        fetchData();
      } else {
        const errJson = await res.json().catch(() => ({ detail: "Server error" }));
        setKeyCreateError(`Failed (${res.status}): ${errJson.detail || res.statusText}`);
      }
    } catch (err: any) {
      console.error("Key creation error:", err);
      setKeyCreateError(
        "Cannot reach AI Gateway at http://localhost:8000. Please start the backend service in a terminal: python -m uvicorn main:app --host 0.0.0.0 --port 8000"
      );
    } finally {
      setIsSubmittingKey(false);
    }
  };

  const handleRevokeKey = async (keyId: string) => {
    if (!confirm("Are you sure you want to revoke this virtual key?")) return;
    try {
      const res = await fetch(`${GATEWAY_URL}/api/keys/${keyId}`, { method: "DELETE" });
      if (res.ok) {
        fetchData();
      }
    } catch (err) {
      console.error("Revoke error:", err);
    }
  };

  const runPlaygroundTest = async () => {
    setPgLoading(true);
    setPgOutput("");
    setPgMeta(null);

    const testKey = process.env.NEXT_PUBLIC_TEST_KEY || "gw-live-master-enterprise-key-2026";
    const startTime = performance.now();

    try {
      if (pgStream) {
        const res = await fetch(`${GATEWAY_URL}/v1/chat/completions`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${testKey}`,
            "x-routing-strategy": pgStrategy,
          },
          body: JSON.stringify({
            model: pgModel,
            messages: [{ role: "user", content: pgPrompt }],
            stream: true,
          }),
        });

        if (!res.ok) {
          const errData = await res.text();
          setPgOutput(`Error: ${errData}`);
          setPgLoading(false);
          return;
        }

        const reader = res.body?.getReader();
        const decoder = new TextDecoder();
        let fullText = "";

        if (reader) {
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            const chunkStr = decoder.decode(value, { stream: true });
            const lines = chunkStr.split("\n");
            for (const line of lines) {
              if (line.startsWith("data: ") && line !== "data: [DONE]") {
                try {
                  const parsed = JSON.parse(line.slice(6));
                  const delta = parsed.choices?.[0]?.delta?.content || "";
                  fullText += delta;
                  setPgOutput(fullText);
                } catch (e) {
                  // chunk parsing
                }
              }
            }
          }
        }
        const latency = performance.now() - startTime;
        setPgMeta({
          latency_ms: Math.round(latency),
          provider: "streamed",
          cache_hit: "NONE",
        });
      } else {
        const res = await fetch(`${GATEWAY_URL}/v1/chat/completions`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${testKey}`,
            "x-routing-strategy": pgStrategy,
          },
          body: JSON.stringify({
            model: pgModel,
            messages: [{ role: "user", content: pgPrompt }],
            stream: false,
          }),
        });

        const data = await res.json();
        if (res.ok) {
          setPgOutput(data.choices?.[0]?.message?.content || "No content returned.");
          setPgMeta(data.gateway);
        } else {
          setPgOutput(`Error (${res.status}): ${JSON.stringify(data.detail || data)}`);
        }
      }
      fetchData();
    } catch (err: any) {
      setPgOutput(`Connection error: ${err.message}`);
    } finally {
      setPgLoading(false);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(true);
    setTimeout(() => setCopiedKey(false), 2000);
  };

  const filteredLogs = logs.filter((l) => {
    if (logFilter !== "ALL" && l.provider.toUpperCase() !== logFilter) return false;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      return (
        l.model.toLowerCase().includes(q) ||
        l.key_name?.toLowerCase().includes(q) ||
        l.cache_hit.toLowerCase().includes(q)
      );
    }
    return true;
  });

  return (
    <div className="min-h-screen flex flex-col bg-[#090d16] text-slate-100 selection:bg-cyan-500/20 selection:text-cyan-300">
      {/* Top Header */}
      <header className="border-b border-slate-800/80 bg-slate-900/60 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-cyan-500 via-indigo-500 to-purple-500 flex items-center justify-center shadow-lg shadow-cyan-500/20">
              <Zap className="h-5 w-5 text-white animate-pulse" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-extrabold text-lg tracking-tight bg-gradient-to-r from-white via-slate-100 to-slate-400 bg-clip-text text-transparent">
                  AI Gateway
                </span>
                <span className="text-[10px] uppercase font-bold tracking-widest px-2 py-0.5 rounded-full bg-cyan-500/10 border border-cyan-500/30 text-cyan-400">
                  Enterprise
                </span>
              </div>
              <p className="text-xs text-slate-400 hidden sm:block">LLM Router & Multi-Provider Proxy</p>
            </div>
          </div>

          <div className="flex items-center space-x-3">
            {/* Status Indicator */}
            <div className="flex items-center space-x-2 px-3 py-1.5 rounded-lg bg-slate-800/60 border border-slate-700/60 text-xs">
              <span
                className={`h-2.5 w-2.5 rounded-full ${
                  gatewayStatus === "online"
                    ? "bg-emerald-400 shadow-md shadow-emerald-400/50"
                    : gatewayStatus === "offline"
                    ? "bg-rose-500 shadow-md shadow-rose-500/50"
                    : "bg-amber-400 animate-pulse"
                }`}
              />
              <span className="text-slate-300 font-medium capitalize">
                {gatewayStatus === "online" ? "Gateway Live" : gatewayStatus}
              </span>
            </div>

            {/* Refresh Button */}
            <button
              onClick={fetchData}
              disabled={refreshing}
              className="p-2 rounded-lg bg-slate-800/60 border border-slate-700/60 text-slate-400 hover:text-white hover:bg-slate-700/50 transition"
              title="Refresh Data"
            >
              <RefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin text-cyan-400" : ""}`} />
            </button>

            {/* Quick Create Key Button */}
            <button
              onClick={() => {
                setCreatedSecretKey(null);
                setNewKeyName("");
                setIsModalOpen(true);
              }}
              className="flex items-center space-x-1.5 px-3.5 py-1.5 rounded-lg bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white font-medium text-xs shadow-md shadow-cyan-500/20 transition transform active:scale-95"
            >
              <Plus className="h-4 w-4" />
              <span>Create Key</span>
            </button>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex space-x-1 border-t border-slate-800/50 overflow-x-auto">
          {[
            { id: "overview", label: "Overview & Analytics", icon: Activity },
            { id: "keys", label: "Virtual Keys & Budgets", icon: Key },
            { id: "playground", label: "Test Playground", icon: Terminal },
            { id: "logs", label: "Live Telemetry Logs", icon: Layers },
            { id: "routing", label: "Router & Guardrails", icon: ShieldCheck },
          ].map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`flex items-center space-x-2 py-3 px-4 text-xs font-semibold border-b-2 transition whitespace-nowrap ${
                  isActive
                    ? "border-cyan-400 text-cyan-400 bg-cyan-500/5"
                    : "border-transparent text-slate-400 hover:text-slate-200 hover:border-slate-700"
                }`}
              >
                <Icon className="h-4 w-4" />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl mx-auto w-full px-4 sm:px-6 lg:px-8 py-8">
        {/* ============================================================== */}
        {/* TAB 1: OVERVIEW & ANALYTICS */}
        {/* ============================================================== */}
        {activeTab === "overview" && (
          <div className="space-y-8 animate-fadeIn">
            {/* KPI Cards Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
              {/* Total Requests */}
              <div className="glass-card p-5 rounded-2xl relative overflow-hidden">
                <div className="flex justify-between items-start">
                  <div>
                    <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Total Requests</p>
                    <h3 className="text-3xl font-extrabold text-white mt-1">
                      {metrics ? metrics.total_requests.toLocaleString() : "..."}
                    </h3>
                  </div>
                  <div className="p-2.5 rounded-xl bg-cyan-500/10 border border-cyan-500/20 text-cyan-400">
                    <Activity className="h-5 w-5" />
                  </div>
                </div>
                <div className="mt-4 flex items-center text-xs text-emerald-400 font-medium space-x-1">
                  <ArrowUpRight className="h-4 w-4" />
                  <span>100% Availability</span>
                  <span className="text-slate-500 ml-1">· Real-time</span>
                </div>
              </div>

              {/* Avg Latency */}
              <div className="glass-card p-5 rounded-2xl relative overflow-hidden">
                <div className="flex justify-between items-start">
                  <div>
                    <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Avg Latency</p>
                    <h3 className="text-3xl font-extrabold text-white mt-1">
                      {metrics ? `${metrics.avg_latency_ms} ms` : "..."}
                    </h3>
                  </div>
                  <div className="p-2.5 rounded-xl bg-purple-500/10 border border-purple-500/20 text-purple-400">
                    <Clock className="h-5 w-5" />
                  </div>
                </div>
                <div className="mt-4 flex items-center text-xs text-cyan-400 font-medium space-x-1">
                  <Zap className="h-4 w-4" />
                  <span>Groq Powered (~60ms)</span>
                </div>
              </div>

              {/* Cache Hit Rate */}
              <div className="glass-card p-5 rounded-2xl relative overflow-hidden">
                <div className="flex justify-between items-start">
                  <div>
                    <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Cache Hit Rate</p>
                    <h3 className="text-3xl font-extrabold text-white mt-1">
                      {metrics ? `${metrics.cache_hit_rate}%` : "..."}
                    </h3>
                  </div>
                  <div className="p-2.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
                    <Database className="h-5 w-5" />
                  </div>
                </div>
                <div className="mt-4 flex items-center text-xs text-emerald-400 font-medium space-x-1">
                  <TrendingDown className="h-4 w-4" />
                  <span>{metrics?.cache_hits || 0} requests served from cache</span>
                </div>
              </div>

              {/* Total Cost & Savings */}
              <div className="glass-card p-5 rounded-2xl relative overflow-hidden">
                <div className="flex justify-between items-start">
                  <div>
                    <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Gateway Spend</p>
                    <h3 className="text-3xl font-extrabold text-white mt-1">
                      {metrics ? `$${metrics.total_cost_usd.toFixed(4)}` : "..."}
                    </h3>
                  </div>
                  <div className="p-2.5 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-400">
                    <DollarSign className="h-5 w-5" />
                  </div>
                </div>
                <div className="mt-4 flex items-center text-xs text-emerald-400 font-medium space-x-1">
                  <span>Saved ${metrics?.cost_saved_usd.toFixed(4) || "0.0000"} via Caching</span>
                </div>
              </div>
            </div>

            {/* Provider Topology & Latency Comparison */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Providers Status */}
              <div className="glass-card p-6 rounded-2xl lg:col-span-2 space-y-5">
                <div className="flex items-center justify-between">
                  <div>
                    <h4 className="text-base font-bold text-white flex items-center space-x-2">
                      <Cpu className="h-5 w-5 text-cyan-400" />
                      <span>Multi-Provider Routing Topology</span>
                    </h4>
                    <p className="text-xs text-slate-400 mt-0.5">Active upstream endpoints with automatic failover</p>
                  </div>
                  <span className="text-xs px-2.5 py-1 rounded-full bg-cyan-500/10 text-cyan-300 border border-cyan-500/20">
                    Strategy: Cost-Optimized
                  </span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  {[
                    {
                      name: "Groq LPU (Active)",
                      provider: "groq",
                      model: "openai/gpt-oss-20b",
                      latency: "45ms",
                      cost: "$0.0001 / 1K",
                      status: "ACTIVE",
                      badge: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
                    },
                    {
                      name: "OpenAI Fallback",
                      provider: "openai",
                      model: "gpt-4o-mini",
                      latency: "310ms",
                      cost: "$0.00015 / 1K",
                      status: "READY",
                      badge: "bg-blue-500/10 text-blue-400 border-blue-500/30",
                    },
                    {
                      name: "Anthropic Messages",
                      provider: "anthropic",
                      model: "claude-3-5-sonnet",
                      latency: "480ms",
                      cost: "$0.003 / 1K",
                      status: "READY",
                      badge: "bg-purple-500/10 text-purple-400 border-purple-500/30",
                    },
                    {
                      name: "Google Gemini",
                      provider: "gemini",
                      model: "gemini-1.5-flash",
                      latency: "280ms",
                      cost: "$0.000075 / 1K",
                      status: "READY",
                      badge: "bg-amber-500/10 text-amber-400 border-amber-500/30",
                    },
                  ].map((p, idx) => (
                    <div
                      key={idx}
                      className="p-4 rounded-xl bg-slate-800/40 border border-slate-700/60 hover:border-slate-600 transition flex flex-col justify-between"
                    >
                      <div className="flex items-start justify-between">
                        <div>
                          <p className="font-semibold text-sm text-slate-100">{p.name}</p>
                          <p className="text-xs text-slate-400 font-mono mt-0.5">{p.model}</p>
                        </div>
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${p.badge}`}>
                          {p.status}
                        </span>
                      </div>
                      <div className="mt-4 pt-3 border-t border-slate-700/40 flex items-center justify-between text-xs">
                        <span className="text-slate-400">
                          Est. Latency: <strong className="text-cyan-300">{p.latency}</strong>
                        </span>
                        <span className="text-slate-400">
                          Rate: <strong className="text-slate-200">{p.cost}</strong>
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Cache Layer Breakdown */}
              <div className="glass-card p-6 rounded-2xl space-y-5 flex flex-col justify-between">
                <div>
                  <h4 className="text-base font-bold text-white flex items-center space-x-2">
                    <Database className="h-5 w-5 text-emerald-400" />
                    <span>Two-Tier Caching Engine</span>
                  </h4>
                  <p className="text-xs text-slate-400 mt-0.5">Exact hash match + Vector semantic matching</p>
                </div>

                <div className="space-y-4">
                  <div className="p-3.5 rounded-xl bg-slate-800/40 border border-slate-700/60">
                    <div className="flex justify-between items-center text-xs mb-1.5">
                      <span className="font-semibold text-slate-300">Tier 1: Exact Hash Cache (Redis/RAM)</span>
                      <span className="text-emerald-400 font-bold">&lt; 5ms</span>
                    </div>
                    <p className="text-[11px] text-slate-400 leading-relaxed">
                      Deterministic SHA-256 prompt hashing delivers sub-5ms responses and 100% cost reduction on identical requests.
                    </p>
                  </div>

                  <div className="p-3.5 rounded-xl bg-slate-800/40 border border-slate-700/60">
                    <div className="flex justify-between items-center text-xs mb-1.5">
                      <span className="font-semibold text-slate-300">Tier 2: Semantic Cache (Vector Sim)</span>
                      <span className="text-cyan-400 font-bold">&gt; 0.88 Cosine</span>
                    </div>
                    <p className="text-[11px] text-slate-400 leading-relaxed">
                      Matches semantically equivalent queries using cosine similarity over feature vectors to eliminate duplicate LLM generation.
                    </p>
                  </div>
                </div>

                <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-xs text-emerald-300 flex items-center space-x-2">
                  <Sparkles className="h-4 w-4 shrink-0" />
                  <span>Cache hits bypass external LLM billing completely.</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ============================================================== */}
        {/* TAB 2: VIRTUAL KEYS & BUDGET MANAGEMENT */}
        {/* ============================================================== */}
        {activeTab === "keys" && (
          <div className="space-y-6 animate-fadeIn">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <h3 className="text-xl font-bold text-white flex items-center space-x-2">
                  <Key className="h-5 w-5 text-cyan-400" />
                  <span>Virtual Key Management & Budget Caps</span>
                </h3>
                <p className="text-xs text-slate-400 mt-1">
                  Issue customer and service virtual keys with hard budget quotas, token caps, and rate limits.
                </p>
              </div>
              <button
                onClick={() => {
                  setCreatedSecretKey(null);
                  setNewKeyName("");
                  setIsModalOpen(true);
                }}
                className="flex items-center space-x-2 px-4 py-2 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold text-xs shadow-lg shadow-cyan-500/25 transition"
              >
                <Plus className="h-4 w-4" />
                <span>Issue New Virtual Key</span>
              </button>
            </div>

            {/* Virtual Keys Table */}
            <div className="glass-card rounded-2xl overflow-hidden border border-slate-800">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-800/60 border-b border-slate-700/60 text-slate-400 uppercase tracking-wider font-semibold">
                    <tr>
                      <th className="py-3 px-4">Key Name & Prefix</th>
                      <th className="py-3 px-4">Budget ($ USD)</th>
                      <th className="py-3 px-4">Token Cap</th>
                      <th className="py-3 px-4">Rate Limit</th>
                      <th className="py-3 px-4">Status</th>
                      <th className="py-3 px-4 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    {keys.length === 0 ? (
                      <tr>
                        <td colSpan={6} className="py-8 text-center text-slate-400">
                          No virtual keys found. Create your first key above.
                        </td>
                      </tr>
                    ) : (
                      keys.map((k) => {
                        const costPct = k.cost_cap ? Math.min(100, Math.round((k.current_cost / k.cost_cap) * 100)) : 0;
                        const tokenPct = k.token_cap ? Math.min(100, Math.round((k.current_tokens / k.token_cap) * 100)) : 0;

                        return (
                          <tr key={k.id} className="hover:bg-slate-800/30 transition">
                            <td className="py-3.5 px-4">
                              <p className="font-semibold text-white">{k.name}</p>
                              <code className="text-[11px] text-slate-400 bg-slate-800/80 px-1.5 py-0.5 rounded font-mono">
                                {k.masked_key}
                              </code>
                            </td>
                            <td className="py-3.5 px-4 min-w-[160px]">
                              <div className="flex justify-between text-xs mb-1">
                                <span className="font-medium text-slate-200">${k.current_cost.toFixed(3)}</span>
                                <span className="text-slate-400">
                                  {k.cost_cap ? `Cap: $${k.cost_cap.toFixed(2)}` : "Unlimited"}
                                </span>
                              </div>
                              {k.cost_cap && (
                                <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
                                  <div
                                    className={`h-full rounded-full ${
                                      costPct > 85 ? "bg-rose-500" : costPct > 60 ? "bg-amber-400" : "bg-cyan-500"
                                    }`}
                                    style={{ width: `${costPct}%` }}
                                  />
                                </div>
                              )}
                            </td>
                            <td className="py-3.5 px-4 min-w-[160px]">
                              <div className="flex justify-between text-xs mb-1">
                                <span className="font-medium text-slate-200">
                                  {(k.current_tokens / 1000).toFixed(1)}k
                                </span>
                                <span className="text-slate-400">
                                  {k.token_cap ? `${(k.token_cap / 1000).toFixed(0)}k cap` : "Unlimited"}
                                </span>
                              </div>
                              {k.token_cap && (
                                <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
                                  <div
                                    className={`h-full rounded-full ${
                                      tokenPct > 85 ? "bg-rose-500" : tokenPct > 60 ? "bg-amber-400" : "bg-purple-500"
                                    }`}
                                    style={{ width: `${tokenPct}%` }}
                                  />
                                </div>
                              )}
                            </td>
                            <td className="py-3.5 px-4 font-mono text-slate-300">
                              {k.rate_limit_rpm} RPM / {(k.rate_limit_tpm / 1000).toFixed(0)}k TPM
                            </td>
                            <td className="py-3.5 px-4">
                              <span
                                className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${
                                  k.is_active
                                    ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                                    : "bg-rose-500/10 text-rose-400 border-rose-500/30"
                                }`}
                              >
                                {k.is_active ? "ACTIVE" : "REVOKED"}
                              </span>
                            </td>
                            <td className="py-3.5 px-4 text-right">
                              {k.is_active && (
                                <button
                                  onClick={() => handleRevokeKey(k.id)}
                                  className="text-slate-400 hover:text-rose-400 p-1.5 rounded hover:bg-slate-800 transition"
                                  title="Revoke Key"
                                >
                                  <Trash2 className="h-4 w-4" />
                                </button>
                              )}
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* ============================================================== */}
        {/* TAB 3: TEST PLAYGROUND */}
        {/* ============================================================== */}
        {activeTab === "playground" && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 animate-fadeIn">
            {/* Playground Input Config */}
            <div className="glass-card p-6 rounded-2xl space-y-5">
              <div>
                <h3 className="text-base font-bold text-white flex items-center space-x-2">
                  <Terminal className="h-5 w-5 text-cyan-400" />
                  <span>Gateway Request Playground</span>
                </h3>
                <p className="text-xs text-slate-400 mt-1">
                  Test chat completions through the gateway with custom models and routing strategies.
                </p>
              </div>

              {/* Model & Strategy select */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="text-xs font-semibold text-slate-300 block mb-1.5">Model / Target</label>
                  <select
                    value={pgModel}
                    onChange={(e) => setPgModel(e.target.value)}
                    className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-cyan-400"
                  >
                    <option value="openai/gpt-oss-20b">Groq: openai/gpt-oss-20b (Ultra-Fast)</option>
                    <option value="qwen/qwen3.8-27b">Groq: qwen/qwen3.8-27b</option>
                    <option value="openai/gpt-oss-120b">Groq: openai/gpt-oss-120b</option>
                    <option value="cost-optimized">Gateway Virtual: Cost-Optimized</option>
                    <option value="latency-optimized">Gateway Virtual: Latency-Optimized</option>
                  </select>
                </div>

                <div>
                  <label className="text-xs font-semibold text-slate-300 block mb-1.5">Routing Strategy</label>
                  <select
                    value={pgStrategy}
                    onChange={(e) => setPgStrategy(e.target.value)}
                    className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-cyan-400"
                  >
                    <option value="cost-optimized">Cost-Optimized</option>
                    <option value="latency-optimized">Latency-Optimized</option>
                    <option value="round-robin">Round Robin</option>
                    <option value="weighted">Weighted Load Balancing</option>
                  </select>
                </div>
              </div>

              {/* Streaming Toggle */}
              <div className="flex items-center justify-between p-3 rounded-xl bg-slate-800/40 border border-slate-700/60">
                <div>
                  <span className="text-xs font-semibold text-slate-200">Server-Sent Events (SSE) Streaming</span>
                  <p className="text-[11px] text-slate-400">Stream tokens in real-time as they are generated</p>
                </div>
                <button
                  type="button"
                  onClick={() => setPgStream(!pgStream)}
                  className={`w-11 h-6 rounded-full transition relative flex items-center px-0.5 ${
                    pgStream ? "bg-cyan-500" : "bg-slate-700"
                  }`}
                >
                  <div
                    className={`h-5 w-5 rounded-full bg-white transition-transform ${
                      pgStream ? "transform translate-x-5" : ""
                    }`}
                  />
                </button>
              </div>

              {/* Prompt Input */}
              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1.5">User Prompt</label>
                <textarea
                  rows={4}
                  value={pgPrompt}
                  onChange={(e) => setPgPrompt(e.target.value)}
                  placeholder="Enter a prompt to send through the AI gateway..."
                  className="w-full bg-slate-800/80 border border-slate-700 rounded-xl p-3 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-400 font-mono"
                />
              </div>

              {/* Send Request Button */}
              <button
                onClick={runPlaygroundTest}
                disabled={pgLoading}
                className="w-full py-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-slate-950 font-bold text-xs flex items-center justify-center space-x-2 shadow-lg shadow-cyan-500/25 transition disabled:opacity-50"
              >
                {pgLoading ? (
                  <>
                    <RefreshCw className="h-4 w-4 animate-spin" />
                    <span>Processing Gateway Request...</span>
                  </>
                ) : (
                  <>
                    <Play className="h-4 w-4 fill-current" />
                    <span>Execute Chat Completion</span>
                  </>
                )}
              </button>
            </div>

            {/* Output & Telemetry */}
            <div className="glass-card p-6 rounded-2xl flex flex-col justify-between space-y-4">
              <div>
                <div className="flex items-center justify-between mb-2">
                  <h4 className="text-base font-bold text-white flex items-center space-x-2">
                    <Sparkles className="h-5 w-5 text-purple-400" />
                    <span>Gateway Response & Metadata</span>
                  </h4>
                  {pgMeta && (
                    <div className="flex items-center space-x-2">
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                        {pgMeta.provider?.toUpperCase()}
                      </span>
                      {pgMeta.cache_hit && pgMeta.cache_hit !== "NONE" && (
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-cyan-500/10 text-cyan-400 border border-cyan-500/30">
                          CACHE {pgMeta.cache_hit}
                        </span>
                      )}
                    </div>
                  )}
                </div>

                {/* Output Box */}
                <div className="min-h-[220px] max-h-[300px] overflow-y-auto bg-slate-900/90 border border-slate-800 rounded-xl p-4 font-mono text-xs text-slate-200 whitespace-pre-wrap leading-relaxed">
                  {pgOutput || (
                    <span className="text-slate-600 italic">Click "Execute Chat Completion" to view output...</span>
                  )}
                </div>
              </div>

              {/* Telemetry info badge */}
              {pgMeta && (
                <div className="grid grid-cols-3 gap-3 p-3 rounded-xl bg-slate-800/40 border border-slate-700/60 text-xs text-slate-300">
                  <div>
                    <span className="text-slate-500 block text-[10px] uppercase">Latency</span>
                    <strong className="text-cyan-400 font-semibold">{pgMeta.latency_ms} ms</strong>
                  </div>
                  <div>
                    <span className="text-slate-500 block text-[10px] uppercase">Cache Hit</span>
                    <strong className="text-emerald-400 font-semibold">{pgMeta.cache_hit || "NONE"}</strong>
                  </div>
                  <div>
                    <span className="text-slate-500 block text-[10px] uppercase">Cost USD</span>
                    <strong className="text-slate-200 font-semibold">
                      {pgMeta.cost_usd !== undefined ? `$${pgMeta.cost_usd.toFixed(5)}` : "Free / $0"}
                    </strong>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ============================================================== */}
        {/* TAB 4: LIVE TELEMETRY LOGS */}
        {/* ============================================================== */}
        {activeTab === "logs" && (
          <div className="space-y-5 animate-fadeIn">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <h3 className="text-xl font-bold text-white flex items-center space-x-2">
                  <Layers className="h-5 w-5 text-cyan-400" />
                  <span>Real-Time Request Telemetry</span>
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">Auditing latency, token consumption, and cache hits</p>
              </div>

              {/* Filter Buttons */}
              <div className="flex items-center space-x-2 overflow-x-auto">
                {["ALL", "GROQ", "OPENAI", "ANTHROPIC", "GEMINI"].map((prov) => (
                  <button
                    key={prov}
                    onClick={() => setLogFilter(prov)}
                    className={`px-3 py-1 rounded-lg text-xs font-semibold transition ${
                      logFilter === prov
                        ? "bg-cyan-500/20 text-cyan-400 border border-cyan-500/30"
                        : "bg-slate-800/60 text-slate-400 border border-slate-700/60 hover:text-slate-200"
                    }`}
                  >
                    {prov}
                  </button>
                ))}
              </div>
            </div>

            {/* Logs Table */}
            <div className="glass-card rounded-2xl overflow-hidden border border-slate-800">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-800/60 border-b border-slate-700/60 text-slate-400 uppercase tracking-wider font-semibold">
                    <tr>
                      <th className="py-3 px-4">Time</th>
                      <th className="py-3 px-4">Provider / Model</th>
                      <th className="py-3 px-4">Key</th>
                      <th className="py-3 px-4">Latency</th>
                      <th className="py-3 px-4">Tokens</th>
                      <th className="py-3 px-4">Cost</th>
                      <th className="py-3 px-4">Cache</th>
                      <th className="py-3 px-4 text-right">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 font-mono">
                    {filteredLogs.length === 0 ? (
                      <tr>
                        <td colSpan={8} className="py-8 text-center text-slate-400 font-sans">
                          No logs found matching criteria.
                        </td>
                      </tr>
                    ) : (
                      filteredLogs.map((l) => (
                        <tr key={l.id} className="hover:bg-slate-800/30 transition text-slate-300">
                          <td className="py-3 px-4 text-[11px] text-slate-400 whitespace-nowrap">
                            {new Date(l.created_at).toLocaleTimeString()}
                          </td>
                          <td className="py-3 px-4">
                            <span className="font-semibold text-white font-sans">{l.provider.toUpperCase()}</span>
                            <span className="text-[11px] text-slate-400 block font-mono">{l.model}</span>
                          </td>
                          <td className="py-3 px-4 text-slate-300 font-sans">{l.key_name || "Master Key"}</td>
                          <td className="py-3 px-4 text-cyan-400 font-semibold">{l.latency_ms} ms</td>
                          <td className="py-3 px-4 text-slate-300">
                            {l.total_tokens} <span className="text-slate-500 text-[10px]">({l.prompt_tokens}/{l.completion_tokens})</span>
                          </td>
                          <td className="py-3 px-4 text-slate-200">
                            {l.cost_usd > 0 ? `$${l.cost_usd.toFixed(5)}` : "$0.00"}
                          </td>
                          <td className="py-3 px-4">
                            <span
                              className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${
                                l.cache_hit === "EXACT"
                                  ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                                  : l.cache_hit === "SEMANTIC"
                                  ? "bg-purple-500/10 text-purple-400 border-purple-500/30"
                                  : "bg-slate-800 text-slate-500 border-slate-700"
                              }`}
                            >
                              {l.cache_hit}
                            </span>
                          </td>
                          <td className="py-3 px-4 text-right">
                            <span
                              className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${
                                l.status_code === 200
                                  ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                                  : "bg-rose-500/10 text-rose-400 border-rose-500/30"
                              }`}
                            >
                              {l.status_code}
                            </span>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* ============================================================== */}
        {/* TAB 5: ROUTER & GUARDRAILS CONFIG */}
        {/* ============================================================== */}
        {activeTab === "routing" && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 animate-fadeIn">
            {/* Routing Engine Settings */}
            <div className="glass-card p-6 rounded-2xl space-y-4">
              <h4 className="text-base font-bold text-white flex items-center space-x-2">
                <Sliders className="h-5 w-5 text-cyan-400" />
                <span>Intelligent Router Engine</span>
              </h4>
              <p className="text-xs text-slate-400">
                Configure load balancing strategies, failover thresholds, and latency EWMA weights.
              </p>

              <div className="space-y-3 pt-2">
                <div className="p-3 rounded-xl bg-slate-800/40 border border-slate-700/60 flex items-center justify-between">
                  <div>
                    <span className="text-xs font-semibold text-slate-200">Automatic Fallback Failover</span>
                    <p className="text-[11px] text-slate-400">Failover across providers on 429 rate limit or 5xx server errors</p>
                  </div>
                  <span className="text-xs font-bold text-emerald-400 px-2 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/20">
                    ENABLED
                  </span>
                </div>

                <div className="p-3 rounded-xl bg-slate-800/40 border border-slate-700/60 flex items-center justify-between">
                  <div>
                    <span className="text-xs font-semibold text-slate-200">Degraded Provider Cooldown</span>
                    <p className="text-[11px] text-slate-400">Temporarily pause routing to failing providers</p>
                  </div>
                  <span className="text-xs font-mono text-cyan-300">30 seconds</span>
                </div>

                <div className="p-3 rounded-xl bg-slate-800/40 border border-slate-700/60 flex items-center justify-between">
                  <div>
                    <span className="text-xs font-semibold text-slate-200">HTTP Connection Timeout</span>
                    <p className="text-[11px] text-slate-400">Maximum upstream request wait time</p>
                  </div>
                  <span className="text-xs font-mono text-cyan-300">45.0s</span>
                </div>
              </div>
            </div>

            {/* Guardrails Settings */}
            <div className="glass-card p-6 rounded-2xl space-y-4">
              <h4 className="text-base font-bold text-white flex items-center space-x-2">
                <ShieldCheck className="h-5 w-5 text-emerald-400" />
                <span>Enterprise Guardrails & Safety</span>
              </h4>
              <p className="text-xs text-slate-400">
                Inspect inputs and outputs for sensitive PII data and prompt injection attacks.
              </p>

              <div className="space-y-3 pt-2">
                <div className="p-3 rounded-xl bg-slate-800/40 border border-slate-700/60 flex items-center justify-between">
                  <div>
                    <span className="text-xs font-semibold text-slate-200">Automated PII Redaction</span>
                    <p className="text-[11px] text-slate-400">Masks Credit Cards, SSNs, Emails, and Phone Numbers</p>
                  </div>
                  <span className="text-xs font-bold text-emerald-400 px-2 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/20">
                    ACTIVE
                  </span>
                </div>

                <div className="p-3 rounded-xl bg-slate-800/40 border border-slate-700/60 flex items-center justify-between">
                  <div>
                    <span className="text-xs font-semibold text-slate-200">Prompt Injection Shield</span>
                    <p className="text-[11px] text-slate-400">Blocks jailbreaks and system override prompts</p>
                  </div>
                  <span className="text-xs font-bold text-emerald-400 px-2 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/20">
                    BLOCK (400)
                  </span>
                </div>

                <div className="p-3 rounded-xl bg-slate-800/40 border border-slate-700/60 flex items-center justify-between">
                  <div>
                    <span className="text-xs font-semibold text-slate-200">Sliding Window Rate Limiter</span>
                    <p className="text-[11px] text-slate-400">RPM and TPM enforcement via Redis & In-Memory Fallback</p>
                  </div>
                  <span className="text-xs font-bold text-emerald-400 px-2 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/20">
                    ACTIVE
                  </span>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* ============================================================== */}
      {/* MODAL: CREATE VIRTUAL KEY */}
      {/* ============================================================== */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-fadeIn">
          <div className="glass-card max-w-md w-full p-6 rounded-2xl border border-slate-700 shadow-2xl relative">
            <div className="flex justify-between items-start mb-4">
              <div>
                <h3 className="text-lg font-bold text-white flex items-center space-x-2">
                  <Key className="h-5 w-5 text-cyan-400" />
                  <span>Issue New Virtual Key</span>
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Configure budget limits and quotas for this key.
                </p>
              </div>
              <button
                onClick={() => setIsModalOpen(false)}
                className="text-slate-400 hover:text-white text-lg"
              >
                ✕
              </button>
            </div>

            {createdSecretKey ? (
              <div className="space-y-4">
                <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs">
                  <p className="font-bold flex items-center space-x-1.5 mb-1">
                    <CheckCircle2 className="h-4 w-4" />
                    <span>Virtual Key Generated Successfully!</span>
                  </p>
                  <p className="text-[11px] text-slate-300">
                    Please copy this secret key now. For security purposes, it will never be displayed again.
                  </p>
                </div>

                <div className="p-3 bg-slate-900 border border-slate-700 rounded-xl flex items-center justify-between">
                  <code className="text-xs text-cyan-300 font-mono break-all">{createdSecretKey}</code>
                  <button
                    onClick={() => copyToClipboard(createdSecretKey)}
                    className="ml-2 p-2 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition"
                    title="Copy Key"
                  >
                    {copiedKey ? <Check className="h-4 w-4 text-emerald-400" /> : <Copy className="h-4 w-4" />}
                  </button>
                </div>

                <button
                  onClick={() => setIsModalOpen(false)}
                  className="w-full py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-white text-xs font-semibold transition"
                >
                  Done
                </button>
              </div>
            ) : (
              <form onSubmit={handleCreateKey} className="space-y-4">
                {keyCreateError && (
                  <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-start space-x-2 animate-fadeIn">
                    <AlertTriangle className="h-4 w-4 shrink-0 text-rose-400 mt-0.5" />
                    <span>{keyCreateError}</span>
                  </div>
                )}

                <div>
                  <label className="text-xs font-semibold text-slate-300 block mb-1">Key Name / Label</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Production Mobile App"
                    value={newKeyName}
                    onChange={(e) => setNewKeyName(e.target.value)}
                    className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-400"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs font-semibold text-slate-300 block mb-1">Cost Cap ($ USD)</label>
                    <input
                      type="number"
                      step="1"
                      placeholder="e.g. 50"
                      value={newCostCap}
                      onChange={(e) => setNewCostCap(e.target.value)}
                      className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-400"
                    />
                  </div>
                  <div>
                    <label className="text-xs font-semibold text-slate-300 block mb-1">Token Cap</label>
                    <input
                      type="number"
                      placeholder="e.g. 1000000"
                      value={newTokenCap}
                      onChange={(e) => setNewTokenCap(e.target.value)}
                      className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-400"
                    />
                  </div>
                </div>

                <div>
                  <label className="text-xs font-semibold text-slate-300 block mb-1">Rate Limit (Requests / Min)</label>
                  <input
                    type="number"
                    value={newRpm}
                    onChange={(e) => setNewRpm(e.target.value)}
                    className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-cyan-400"
                  />
                </div>

                <div className="pt-2 flex space-x-2">
                  <button
                    type="button"
                    onClick={() => setIsModalOpen(false)}
                    className="w-1/2 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold transition"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={isSubmittingKey}
                    className="w-1/2 py-2.5 rounded-xl bg-cyan-500 hover:bg-cyan-400 disabled:opacity-50 text-slate-950 text-xs font-bold transition shadow-lg shadow-cyan-500/20 flex items-center justify-center space-x-1.5"
                  >
                    {isSubmittingKey ? (
                      <>
                        <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                        <span>Creating...</span>
                      </>
                    ) : (
                      <span>Create Virtual Key</span>
                    )}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
