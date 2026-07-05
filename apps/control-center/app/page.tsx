import statusData from "../public/status.json";

type Gate = {
  name: string;
  state: string;
};

type DashboardData = {
  status: {
    mode: string;
    account_id: string;
    live_small_blocked_by_default: boolean;
    apis: {
      alpaca_real_api_enabled: boolean;
      groww_real_api_enabled: boolean;
      twilio_alerts_enabled: boolean;
    };
    ruflo: {
      role: string;
      can_place_orders: boolean;
      checks: string[];
    };
  };
  model: {
    mode: string;
    active_version: string;
    last_trained_at: string | null;
    accuracy: string | null;
    feature_set: string[];
    can_place_orders: boolean;
  };
  scheduled_orders: Array<{
    id: string;
    symbol: string;
    market: string;
    eligible_at: string;
    expires_at: string;
    status: string;
    model_version: string;
    gate: string;
  }>;
  equity_summary: Record<string, string>;
  validation_gates: Gate[];
};

function StatePill({ state }: { state: string }) {
  const tone =
    state === "ready" || state === "advisory"
      ? "bg-emerald-50 text-emerald-800 ring-emerald-200"
      : state === "blocked"
        ? "bg-rose-50 text-rose-800 ring-rose-200"
        : state === "pending"
          ? "bg-sky-50 text-sky-800 ring-sky-200"
          : "bg-amber-50 text-amber-800 ring-amber-200";
  return (
    <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ring-1 ${tone}`}>
      {state}
    </span>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="border border-slate-200 bg-white p-3">
      <dt className="text-sm text-slate-500">{label}</dt>
      <dd className="mt-1 break-words font-mono text-base font-semibold text-slate-950">{value}</dd>
    </div>
  );
}

export default function Home() {
  const data = statusData as DashboardData;

  return (
    <main className="min-h-screen bg-slate-100 text-slate-950">
      <section className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl flex-col gap-5 px-5 py-6 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase text-slate-500">Market Sentinel</p>
            <h1 className="mt-2 text-3xl font-semibold tracking-normal md:text-4xl">Control Center</h1>
          </div>
          <div className="grid grid-cols-2 gap-3 text-sm md:grid-cols-5">
            <Metric label="Mode" value={data.status.mode} />
            <Metric label="Account" value={data.status.account_id} />
            <Metric label="Live-small" value={data.status.live_small_blocked_by_default ? "blocked" : "armed"} />
            <Metric label="ML" value={data.model.mode} />
            <Metric label="RUFLO" value={data.status.ruflo.role} />
          </div>
        </div>
      </section>

      <div className="mx-auto grid max-w-7xl gap-5 px-5 py-6 lg:grid-cols-2">
        <section className="border border-slate-200 bg-white p-5">
          <div className="flex items-center justify-between gap-4">
            <h2 className="text-xl font-semibold">Validation Gates</h2>
            <StatePill state="blocked" />
          </div>
          <div className="mt-5 divide-y divide-slate-200">
            {data.validation_gates.map((gate) => (
              <div className="flex items-center justify-between gap-4 py-3" key={gate.name}>
                <span className="font-medium">{gate.name}</span>
                <StatePill state={gate.state} />
              </div>
            ))}
          </div>
        </section>

        <section className="border border-slate-200 bg-white p-5">
          <h2 className="text-xl font-semibold">Real API Readiness</h2>
          <div className="mt-5 grid gap-3 sm:grid-cols-3">
            <Metric label="Alpaca" value={data.status.apis.alpaca_real_api_enabled ? "enabled" : "off"} />
            <Metric label="Groww" value={data.status.apis.groww_real_api_enabled ? "enabled" : "off"} />
            <Metric label="Twilio" value={data.status.apis.twilio_alerts_enabled ? "enabled" : "off"} />
          </div>
          <p className="mt-4 text-sm leading-6 text-slate-600">
            Real APIs are wired behind environment flags and credentials. Live orders remain blocked until engine gates pass.
          </p>
        </section>

        <section className="border border-slate-200 bg-white p-5">
          <div className="flex items-center justify-between gap-4">
            <h2 className="text-xl font-semibold">ML Model</h2>
            <StatePill state={data.model.mode} />
          </div>
          <dl className="mt-5 grid grid-cols-2 gap-3">
            <Metric label="Active version" value={data.model.active_version} />
            <Metric label="Accuracy" value={data.model.accuracy ?? "not trained"} />
            <div className="col-span-2 border border-slate-200 bg-white p-3">
              <dt className="text-sm text-slate-500">Feature set</dt>
              <dd className="mt-1 text-sm font-medium text-slate-950">{data.model.feature_set.join(", ")}</dd>
            </div>
          </dl>
        </section>

        <section className="border border-slate-200 bg-white p-5">
          <h2 className="text-xl font-semibold">Equity Summary</h2>
          <dl className="mt-5 grid grid-cols-2 gap-3">
            {Object.entries(data.equity_summary).map(([key, value]) => (
              <Metric key={key} label={key.replace("_", " ")} value={value} />
            ))}
          </dl>
        </section>

        <section className="border border-slate-200 bg-white p-5 lg:col-span-2">
          <h2 className="text-xl font-semibold">Scheduled Intents</h2>
          <div className="mt-5 divide-y divide-slate-200">
            {data.scheduled_orders.map((order) => (
              <div className="grid gap-3 py-3 md:grid-cols-[1fr_auto]" key={order.id}>
                <div>
                  <p className="font-medium">
                    {order.symbol} / {order.market}
                  </p>
                  <p className="mt-2 text-sm text-slate-600">{order.gate}</p>
                  <p className="mt-2 font-mono text-xs text-slate-500">
                    {order.eligible_at} to {order.expires_at}
                  </p>
                </div>
                <div className="flex items-start gap-2">
                  <StatePill state={order.status} />
                  <StatePill state={order.model_version ? "advisory" : "not-started"} />
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="border border-slate-200 bg-white p-5 lg:col-span-2">
          <h2 className="text-xl font-semibold">Compliance Checklist</h2>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            {data.status.ruflo.checks.map((check) => (
              <div className="border border-slate-200 bg-slate-50 p-4" key={check}>
                <p className="font-medium">{check}</p>
                <p className="mt-2 text-sm text-slate-600">
                  Human verification required before live-small trading can be considered.
                </p>
              </div>
            ))}
          </div>
        </section>
      </div>
    </main>
  );
}
