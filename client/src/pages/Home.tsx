import { useEffect, useState } from "react";
import { trpc } from "@/lib/trpc";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, PieChart, Pie, Cell } from "recharts";
import { RefreshCw } from "lucide-react";

export default function Home() {
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [refreshCountdown, setRefreshCountdown] = useState(300); // 5 minutes

  // Fetch silver market data
  const comexFuturesQuery = trpc.silverMarket.comexFutures.useQuery();
  const slvInventoryQuery = trpc.silverMarket.slvInventory.useQuery();
  const comexInventoryQuery = trpc.silverMarket.comexInventory.useQuery();
  const lbmaVaultQuery = trpc.silverMarket.lbmaVault.useQuery();

  // Auto-refresh mechanism
  useEffect(() => {
    if (!autoRefresh) return;

    const interval = setInterval(() => {
      setRefreshCountdown((prev) => {
        if (prev <= 1) {
          comexFuturesQuery.refetch();
          slvInventoryQuery.refetch();
          comexInventoryQuery.refetch();
          lbmaVaultQuery.refetch();
          setLastUpdate(new Date());
          return 300;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(interval);
  }, [autoRefresh, comexFuturesQuery, slvInventoryQuery, comexInventoryQuery, lbmaVaultQuery]);

  const handleManualRefresh = () => {
    comexFuturesQuery.refetch();
    slvInventoryQuery.refetch();
    comexInventoryQuery.refetch();
    lbmaVaultQuery.refetch();
    setLastUpdate(new Date());
    setRefreshCountdown(300);
  };

  const formatNumber = (num: string | number | undefined) => {
    if (!num) return "N/A";
    const parsed = typeof num === "string" ? parseFloat(num) : num;
    return parsed.toLocaleString("en-US", { maximumFractionDigits: 2 });
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-white p-4 md:p-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-4xl font-bold mb-2">Silver Market Dashboard</h1>
        <p className="text-slate-400">Real-time COMEX futures, SLV inventory, and global exchange data</p>
        
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mt-6">
          <div className="text-sm text-slate-400">
            <p>Last Updated: {lastUpdate.toLocaleTimeString()}</p>
            <p>Next Refresh: {Math.floor(refreshCountdown / 60)}:{String(refreshCountdown % 60).padStart(2, "0")}</p>
          </div>
          
          <div className="flex gap-2">
            <Button
              onClick={handleManualRefresh}
              disabled={comexFuturesQuery.isLoading}
              className="bg-blue-600 hover:bg-blue-700"
            >
              <RefreshCw className="w-4 h-4 mr-2" />
              Refresh Now
            </Button>
            <Button
              onClick={() => setAutoRefresh(!autoRefresh)}
              variant={autoRefresh ? "default" : "outline"}
            >
              {autoRefresh ? "Auto-Refresh ON" : "Auto-Refresh OFF"}
            </Button>
          </div>
        </div>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        {/* COMEX Futures Card */}
        <Card className="bg-slate-800 border-slate-700">
          <CardHeader>
            <CardTitle>COMEX Silver Futures (MAR2026)</CardTitle>
            <CardDescription>March 2026 Contract - SIH6/SI2603</CardDescription>
          </CardHeader>
          <CardContent>
            {comexFuturesQuery.isLoading ? (
              <div className="text-slate-400">Loading...</div>
            ) : comexFuturesQuery.data?.latest ? (
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-slate-400 text-sm">Open Interest</p>
                    <p className="text-2xl font-bold">{formatNumber(comexFuturesQuery.data.latest.openInterest)}</p>
                    <p className="text-sm text-green-400">
                      {comexFuturesQuery.data.latest.openInterestChange > 0 ? "+" : ""}
                      {formatNumber(comexFuturesQuery.data.latest.openInterestChange)}
                    </p>
                  </div>
                  <div>
                    <p className="text-slate-400 text-sm">Settlement Price</p>
                    <p className="text-2xl font-bold">${comexFuturesQuery.data.latest.settlementPrice}/oz</p>
                  </div>
                  <div>
                    <p className="text-slate-400 text-sm">Total Volume</p>
                    <p className="text-2xl font-bold">{formatNumber(comexFuturesQuery.data.latest.totalVolume)}</p>
                  </div>
                  <div>
                    <p className="text-slate-400 text-sm">Data Source</p>
                    <p className="text-sm font-semibold">{comexFuturesQuery.data.latest.dataSource}</p>
                  </div>
                </div>
                <p className="text-xs text-slate-500">
                  Last recorded: {new Date(comexFuturesQuery.data.latest.recordedAt).toLocaleString()}
                </p>
              </div>
            ) : (
              <div className="text-slate-400">No data available</div>
            )}
          </CardContent>
        </Card>

        {/* SLV Inventory Card */}
        <Card className="bg-slate-800 border-slate-700">
          <CardHeader>
            <CardTitle>iShares Silver Trust (SLV)</CardTitle>
            <CardDescription>Daily Inventory & Flows</CardDescription>
          </CardHeader>
          <CardContent>
            {slvInventoryQuery.isLoading ? (
              <div className="text-slate-400">Loading...</div>
            ) : slvInventoryQuery.data?.latest ? (
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-slate-400 text-sm">Tonnes in Trust</p>
                    <p className="text-2xl font-bold">{formatNumber(slvInventoryQuery.data.latest.tonnesInTrust)}</p>
                  </div>
                  <div>
                    <p className="text-slate-400 text-sm">Ounces in Trust</p>
                    <p className="text-2xl font-bold">{formatNumber(slvInventoryQuery.data.latest.ouncesInTrust)}</p>
                  </div>
                  <div>
                    <p className="text-slate-400 text-sm">Net Flows</p>
                    <p className={`text-2xl font-bold ${(slvInventoryQuery.data.latest.netFlows || 0) < 0 ? "text-red-400" : "text-green-400"}`}>
                      {slvInventoryQuery.data.latest.netFlows ? formatNumber(slvInventoryQuery.data.latest.netFlows) : "N/A"} oz
                    </p>
                  </div>
                  <div>
                    <p className="text-slate-400 text-sm">Share Price</p>
                    <p className="text-2xl font-bold">${slvInventoryQuery.data.latest.sharePrice ? formatNumber(slvInventoryQuery.data.latest.sharePrice) : "N/A"}</p>
                  </div>
                </div>
                <p className="text-xs text-slate-500">
                  Last recorded: {new Date(slvInventoryQuery.data.latest.recordedAt).toLocaleString()}
                </p>
              </div>
            ) : (
              <div className="text-slate-400">No data available</div>
            )}
          </CardContent>
        </Card>

        {/* COMEX Inventory Card */}
        <Card className="bg-slate-800 border-slate-700">
          <CardHeader>
            <CardTitle>COMEX Silver Inventory</CardTitle>
            <CardDescription>Registered vs Eligible Breakdown</CardDescription>
          </CardHeader>
          <CardContent>
            {comexInventoryQuery.isLoading ? (
              <div className="text-slate-400">Loading...</div>
            ) : comexInventoryQuery.data?.latest ? (
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-slate-400 text-sm">Registered</p>
                    <p className="text-2xl font-bold text-blue-400">{formatNumber(comexInventoryQuery.data.latest.registeredOunces)}</p>
                  </div>
                  <div>
                    <p className="text-slate-400 text-sm">Eligible</p>
                    <p className="text-2xl font-bold text-purple-400">{formatNumber(comexInventoryQuery.data.latest.eligibleOunces)}</p>
                  </div>
                  <div>
                    <p className="text-slate-400 text-sm">Total</p>
                    <p className="text-2xl font-bold">{formatNumber(comexInventoryQuery.data.latest.totalOunces)}</p>
                  </div>
                  <div>
                    <p className="text-slate-400 text-sm">Daily Change</p>
                    <p className="text-sm font-semibold">{comexInventoryQuery.data.latest.dailyChange ? formatNumber(comexInventoryQuery.data.latest.dailyChange) : "N/A"}</p>
                  </div>
                </div>
                <p className="text-xs text-slate-500">
                  Last recorded: {new Date(comexInventoryQuery.data.latest.recordedAt).toLocaleString()}
                </p>
              </div>
            ) : (
              <div className="text-slate-400">No data available</div>
            )}
          </CardContent>
        </Card>

        {/* LBMA Vault Card */}
        <Card className="bg-slate-800 border-slate-700">
          <CardHeader>
            <CardTitle>LBMA London Vault Holdings</CardTitle>
            <CardDescription>Monthly Silver Inventory</CardDescription>
          </CardHeader>
          <CardContent>
            {lbmaVaultQuery.isLoading ? (
              <div className="text-slate-400">Loading...</div>
            ) : lbmaVaultQuery.data?.latest ? (
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-slate-400 text-sm">Total Tonnes</p>
                    <p className="text-2xl font-bold">{formatNumber(lbmaVaultQuery.data.latest.totalTonnes)}</p>
                  </div>
                  <div>
                    <p className="text-slate-400 text-sm">Monthly Change</p>
                    <p className={`text-2xl font-bold ${(lbmaVaultQuery.data.latest.monthlyChange || "").startsWith("-") ? "text-red-400" : "text-green-400"}`}>
                      {lbmaVaultQuery.data.latest.monthlyChange || "N/A"}
                    </p>
                  </div>
                  <div className="col-span-2">
                    <p className="text-slate-400 text-sm">Estimated Value</p>
                    <p className="text-2xl font-bold">${formatNumber(lbmaVaultQuery.data.latest.estimatedValue)}</p>
                  </div>
                </div>
                <p className="text-xs text-slate-500">
                  Last recorded: {new Date(lbmaVaultQuery.data.latest.recordedAt).toLocaleString()}
                </p>
              </div>
            ) : (
              <div className="text-slate-400">No data available</div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Charts Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* COMEX Futures History Chart */}
        <Card className="bg-slate-800 border-slate-700">
          <CardHeader>
            <CardTitle>COMEX Futures - 30 Day Trend</CardTitle>
          </CardHeader>
          <CardContent>
            {comexFuturesQuery.data?.history && comexFuturesQuery.data.history.length > 0 ? (
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={comexFuturesQuery.data.history}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#475569" />
                  <XAxis dataKey="recordedAt" stroke="#94a3b8" />
                  <YAxis stroke="#94a3b8" />
                  <Tooltip contentStyle={{ backgroundColor: "#1e293b", border: "1px solid #475569" }} />
                  <Legend />
                  <Line type="monotone" dataKey="openInterest" stroke="#3b82f6" name="Open Interest" />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="text-slate-400 h-80 flex items-center justify-center">No historical data available</div>
            )}
          </CardContent>
        </Card>

        {/* Inventory Breakdown */}
        <Card className="bg-slate-800 border-slate-700">
          <CardHeader>
            <CardTitle>COMEX Inventory Breakdown</CardTitle>
          </CardHeader>
          <CardContent>
            {comexInventoryQuery.data?.latest ? (
              <ResponsiveContainer width="100%" height={300}>
                <PieChart>
                  <Pie
                    data={[
                      { name: "Registered", value: parseFloat(comexInventoryQuery.data.latest.registeredOunces || "0") || 0 },
                      { name: "Eligible", value: parseFloat(comexInventoryQuery.data.latest.eligibleOunces || "0") || 0 },
                    ]}
                    cx="50%"
                    cy="50%"
                    labelLine={false}
                    label={({ name, value }) => `${name}: ${(value / 1000000).toFixed(1)}M oz`}
                    outerRadius={80}
                    fill="#8884d8"
                    dataKey="value"
                  >
                    <Cell fill="#3b82f6" />
                    <Cell fill="#a855f7" />
                  </Pie>
                  <Tooltip formatter={(value) => `${(value / 1000000).toFixed(2)}M oz`} />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="text-slate-400 h-80 flex items-center justify-center">No data available</div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Data Sources Footer */}
      <div className="mt-8 p-4 bg-slate-800 border border-slate-700 rounded-lg">
        <h3 className="font-semibold mb-2">Data Sources & Attribution</h3>
        <ul className="text-sm text-slate-400 space-y-1">
          <li>• COMEX Futures: CME Group (https://www.cmegroup.com)</li>
          <li>• SLV Inventory: iShares (https://www.ishares.com)</li>
          <li>• COMEX Inventory: SilverDashboard (https://silverdashboard.com)</li>
          <li>• LBMA Vault Data: London Bullion Market Association (https://www.lbma.org.uk)</li>
        </ul>
      </div>
    </div>
  );
}
