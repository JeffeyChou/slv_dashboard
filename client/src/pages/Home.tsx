import { useEffect, useState } from "react";
import { trpc } from "@/lib/trpc";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, PieChart, Pie, Cell } from "recharts";
import { RefreshCw, TrendingUp, Activity, Globe, Layers, DollarSign, Percent, BarChart2, Anchor } from "lucide-react";

interface SilverData {
  futures: {
    contract: string;
    price: number;
    open_interest: number;
    volume: number;
    timestamp: string;
  };
  slv: {
    inventory_tonnes: string;
    inventory_ounces: string;
    timestamp: string;
  };
  cme: {
    registered: number;
    eligible: number;
    total: number;
    registered_to_total_ratio: number;
    timestamp: string;
  };
  lbma: {
    holdings_tonnes: string;
    timestamp: string;
  };
  macro: {
    usd_index: number;
    real_yield: number;
    usd_cny: number;
    gold_silver_ratio: number;
    basis_comex: any;
  };
  options: {
    put_call_ratio: number;
    call_volume: number;
    put_volume: number;
    iv_skew_10pct: number;
    expiry: string;
  };
  cot: {
    description?: string;
    status?: string;
  };
  shfe: {
    contract: string;
    price: number;
    oi: number;
    volume: number;
    turnover_ratio: number;
    oi_concentration: number;
    curve_slope: any;
    date: string;
    status: string;
  };
  shfe_warrants: {
    warrants: number;
    status: string;
  };
  derived: {
    shanghai_premium_usd: any;
    paper_to_physical_ratio: any;
  };
}

export default function Home() {
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [refreshCountdown, setRefreshCountdown] = useState(300);
  const [apiData, setApiData] = useState<SilverData | null>(null);
  const [loading, setLoading] = useState(true);

  // Existing TRPC queries (kept for history charts if available)
  const comexFuturesQuery = trpc.silverMarket.comexFutures.useQuery();
  const comexInventoryQuery = trpc.silverMarket.comexInventory.useQuery();

  const fetchApiData = async () => {
    try {
      setLoading(true);
      const res = await fetch('/api/data');
      if (res.ok) {
        const data = await res.json();
        setApiData(data);
      }
    } catch (error) {
      console.error("Failed to fetch API data", error);
    } finally {
      setLoading(false);
      setLastUpdate(new Date());
    }
  };

  useEffect(() => {
    fetchApiData();
  }, []);

  // Auto-refresh mechanism
  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(() => {
      setRefreshCountdown((prev) => {
        if (prev <= 1) {
          fetchApiData();
          comexFuturesQuery.refetch();
          comexInventoryQuery.refetch();
          return 300;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(interval);
  }, [autoRefresh]);

  const handleManualRefresh = () => {
    fetchApiData();
    comexFuturesQuery.refetch();
    comexInventoryQuery.refetch();
    setRefreshCountdown(300);
  };

  const formatNumber = (num: string | number | undefined, decimals = 2) => {
    if (num === undefined || num === null || num === "N/A") return "N/A";
    const parsed = typeof num === "string" ? parseFloat(num) : num;
    return isNaN(parsed) ? "N/A" : parsed.toLocaleString("en-US", { maximumFractionDigits: decimals });
  };

  return (
    <div className="min-h-screen bg-slate-950 text-white p-4 md:p-8 font-sans">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-4xl font-bold mb-2 bg-gradient-to-r from-blue-400 to-emerald-400 text-transparent bg-clip-text">Silver Market Intelligence</h1>
        <p className="text-slate-400">Advanced Analytics: COMEX, SHFE, Inventories & Macro Drivers</p>
        
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mt-6">
          <div className="text-sm text-slate-400 flex items-center gap-4">
            <span className="flex items-center gap-2"><Activity className="w-4 h-4" /> Live</span>
            <span>Last Updated: {lastUpdate.toLocaleTimeString()}</span>
            <span>Next Refresh: {Math.floor(refreshCountdown / 60)}:{String(refreshCountdown % 60).padStart(2, "0")}</span>
          </div>
          
          <div className="flex gap-2">
            <Button onClick={handleManualRefresh} className="bg-blue-600 hover:bg-blue-700">
              <RefreshCw className="w-4 h-4 mr-2" /> Refresh
            </Button>
            <Button onClick={() => setAutoRefresh(!autoRefresh)} variant={autoRefresh ? "default" : "outline"}>
              {autoRefresh ? "Auto On" : "Auto Off"}
            </Button>
          </div>
        </div>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        
        {/* P0: SHFE Data */}
        <Card className="bg-slate-900 border-slate-800 lg:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-emerald-400"><Globe className="w-5 h-5" /> SHFE Silver (Shanghai)</CardTitle>
            <CardDescription>Price, OI & Market Structure (P0)</CardDescription>
          </CardHeader>
          <CardContent className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <p className="text-slate-500 text-xs uppercase">Contract</p>
              <p className="text-xl font-bold">{apiData?.shfe?.contract || "N/A"}</p>
            </div>
            <div>
              <p className="text-slate-500 text-xs uppercase">Price (CNY)</p>
              <p className="text-xl font-bold text-emerald-400">{formatNumber(apiData?.shfe?.price, 0)}</p>
            </div>
            <div>
              <p className="text-slate-500 text-xs uppercase">Open Interest</p>
              <p className="text-xl font-bold">{formatNumber(apiData?.shfe?.oi, 0)}</p>
            </div>
            <div>
              <p className="text-slate-500 text-xs uppercase">Turnover Ratio</p>
              <p className="text-xl font-bold">{formatNumber(apiData?.shfe?.turnover_ratio, 2)}</p>
            </div>
            <div>
              <p className="text-slate-500 text-xs uppercase">OI Concentration</p>
              <p className="text-lg font-semibold">{formatNumber(apiData?.shfe?.oi_concentration, 4)}</p>
            </div>
            <div>
              <p className="text-slate-500 text-xs uppercase">Curve Slope</p>
              <p className="text-lg font-semibold">{formatNumber(apiData?.shfe?.curve_slope)}</p>
            </div>
             <div>
              <p className="text-slate-500 text-xs uppercase">Warrants (kg)</p>
              <p className="text-lg font-semibold text-yellow-500">{formatNumber(apiData?.shfe_warrants?.warrants, 0)}</p>
            </div>
             <div>
              <p className="text-slate-500 text-xs uppercase">Shanghai Premium ($)</p>
              <p className={`text-xl font-bold ${parseFloat(apiData?.derived?.shanghai_premium_usd || 0) > 0 ? "text-green-400" : "text-red-400"}`}>
                {formatNumber(apiData?.derived?.shanghai_premium_usd)}
              </p>
            </div>
          </CardContent>
        </Card>

        {/* P0: COMEX & Structure */}
        <Card className="bg-slate-900 border-slate-800 lg:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-blue-400"><Layers className="w-5 h-5" /> COMEX Structure</CardTitle>
            <CardDescription>Futures, Inventory & Physical Tightness</CardDescription>
          </CardHeader>
          <CardContent className="grid grid-cols-2 md:grid-cols-4 gap-4">
             <div>
              <p className="text-slate-500 text-xs uppercase">Futures Price</p>
              <p className="text-xl font-bold text-blue-400">{formatNumber(apiData?.futures?.price)}</p>
            </div>
            <div>
              <p className="text-slate-500 text-xs uppercase">Futures OI</p>
              <p className="text-xl font-bold">{formatNumber(apiData?.futures?.open_interest, 0)}</p>
            </div>
            <div>
              <p className="text-slate-500 text-xs uppercase">Registered Inv</p>
              <p className="text-xl font-bold text-orange-400">{formatNumber(apiData?.cme?.registered, 0)}</p>
            </div>
            <div>
              <p className="text-slate-500 text-xs uppercase">Reg/Total Ratio</p>
              <p className="text-xl font-bold text-orange-400">{formatNumber(apiData?.cme?.registered_to_total_ratio, 4)}</p>
            </div>
             <div className="col-span-2 bg-slate-800 p-2 rounded">
              <p className="text-slate-400 text-xs uppercase flex items-center gap-1">Paper to Physical Ratio <Anchor className="w-3 h-3" /></p>
              <p className="text-2xl font-bold text-white">{apiData?.derived?.paper_to_physical_ratio || "N/A"} x</p>
              <p className="text-xs text-slate-500">Futures OI (oz) / Registered Inv</p>
            </div>
            <div className="col-span-2 bg-slate-800 p-2 rounded">
               <p className="text-slate-400 text-xs uppercase">SLV Inventory</p>
               <div className="flex justify-between items-baseline">
                 <p className="text-xl font-bold">{formatNumber(apiData?.slv?.inventory_tonnes)} t</p>
                 <p className="text-sm text-slate-400">{formatNumber(apiData?.slv?.inventory_ounces, 0)} oz</p>
               </div>
            </div>
          </CardContent>
        </Card>

        {/* P1: Options & Sentiment */}
        <Card className="bg-slate-900 border-slate-800">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-purple-400"><TrendingUp className="w-5 h-5" /> Options & Sentiment</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex justify-between">
              <span className="text-slate-400 text-sm">Put/Call Ratio</span>
              <span className="font-bold">{apiData?.options?.put_call_ratio}</span>
            </div>
             <div className="flex justify-between">
              <span className="text-slate-400 text-sm">Call Vol</span>
              <span className="font-bold text-green-400">{formatNumber(apiData?.options?.call_volume, 0)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400 text-sm">IV Skew (10%)</span>
              <span className={`font-bold ${ (apiData?.options?.iv_skew_10pct || 0) > 0 ? "text-green-400" : "text-red-400"}`}>
                {apiData?.options?.iv_skew_10pct}
              </span>
            </div>
            <div className="pt-2 border-t border-slate-800">
              <p className="text-xs text-slate-500">COT Status</p>
              <p className="text-sm font-medium">{apiData?.cot?.status || "N/A"}</p>
            </div>
          </CardContent>
        </Card>

        {/* P2: Macro Drivers */}
        <Card className="bg-slate-900 border-slate-800">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-yellow-400"><DollarSign className="w-5 h-5" /> Macro Drivers</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
             <div className="flex justify-between">
              <span className="text-slate-400 text-sm">USD Index</span>
              <span className="font-bold">{formatNumber(apiData?.macro?.usd_index)}</span>
            </div>
             <div className="flex justify-between">
              <span className="text-slate-400 text-sm">US 10Y Real Yield</span>
              <span className="font-bold text-blue-400">{formatNumber(apiData?.macro?.real_yield)}%</span>
            </div>
             <div className="flex justify-between">
              <span className="text-slate-400 text-sm">Gold/Silver Ratio</span>
              <span className="font-bold text-yellow-500">{formatNumber(apiData?.macro?.gold_silver_ratio)}</span>
            </div>
             <div className="flex justify-between">
              <span className="text-slate-400 text-sm">USD/CNY</span>
              <span className="font-bold">{formatNumber(apiData?.macro?.usd_cny, 4)}</span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Historical Charts (Keep existing if available) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="bg-slate-900 border-slate-800">
          <CardHeader>
            <CardTitle className="text-slate-300">COMEX Futures Trend (30D)</CardTitle>
          </CardHeader>
          <CardContent>
             {comexFuturesQuery.data?.history && comexFuturesQuery.data.history.length > 0 ? (
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={comexFuturesQuery.data.history}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis dataKey="recordedAt" stroke="#64748b" tickFormatter={(d) => new Date(d).toLocaleDateString()} />
                  <YAxis stroke="#64748b" />
                  <Tooltip contentStyle={{ backgroundColor: "#0f172a", border: "1px solid #1e293b" }} />
                  <Legend />
                  <Line type="monotone" dataKey="openInterest" stroke="#3b82f6" dot={false} strokeWidth={2} name="Open Interest" />
                  <Line type="monotone" dataKey="settlementPrice" stroke="#10b981" dot={false} strokeWidth={2} name="Price" yAxisId={1} />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="text-slate-500 h-64 flex items-center justify-center">History Data Unavailable (DB)</div>
            )}
          </CardContent>
        </Card>

        <Card className="bg-slate-900 border-slate-800">
          <CardHeader>
            <CardTitle className="text-slate-300">Inventory Distribution</CardTitle>
          </CardHeader>
          <CardContent>
             {apiData?.cme ? (
               <div className="h-[300px]">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={[
                        { name: "Registered", value: apiData.cme.registered || 0 },
                        { name: "Eligible", value: apiData.cme.eligible || 0 },
                      ]}
                      cx="50%"
                      cy="50%"
                      innerRadius={60}
                      outerRadius={80}
                      paddingAngle={5}
                      dataKey="value"
                    >
                      <Cell fill="#f97316" />
                      <Cell fill="#64748b" />
                    </Pie>
                    <Tooltip formatter={(val: number) => `${(val/1000000).toFixed(1)}M oz`} />
                    <Legend />
                  </PieChart>
                </ResponsiveContainer>
                <div className="text-center mt-2">
                   <p className="text-sm text-slate-400">Total: {formatNumber((apiData.cme.total || 0)/1000000, 2)}M oz</p>
                </div>
               </div>
            ) : (
              <div className="text-slate-500 h-64 flex items-center justify-center">Loading Inventory Data...</div>
            )}
          </CardContent>
        </Card>
      </div>

       <div className="mt-8 text-center text-slate-600 text-sm">
        <p>Silver Market Intelligence Dashboard v2.0 | Powered by Python Data Fetcher & React</p>
      </div>
    </div>
  );
}
