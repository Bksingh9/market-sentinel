import statusData from "../public/status.json";

type Gate = {
  name: string;
  state: string;
};

type DashboardData = {
  status: {
    mode: string;
    primary_broker: string;
    account_id: string;
    live_small_blocked_by_default: boolean;
    apis: {
      alpaca_real_api_enabled: boolean;
      alpaca_credentials_present: boolean;
      groww_real_api_enabled: boolean;
      groww_credentials_present: boolean;
      dhan_real_api_enabled: boolean;
      dhan_credentials_present: boolean;
      dhan_static_ip_configured: boolean;
      dhan_security_map_present: boolean;
      twilio_alerts_enabled: boolean;
      twilio_credentials_present: boolean;
      twilio_sender_configured: boolean;
      twilio_messaging_service_configured: boolean;
      twilio_status_callback_configured: boolean;
    };
    live_preflight: {
      ready_to_trade: boolean;
      apis: {
        alpaca: {
          ready: boolean;
        };
        groww: {
          ready: boolean;
        };
        dhan: {
          ready: boolean;
        };
      };
      alerts: {
        twilio: {
          ready: boolean;
        };
      };
    };
    ruflo: {
      role: string;
      can_place_orders: boolean;
      checks: string[];
    };
    deployment: DeploymentStatus;
  };
  deployment: DeploymentStatus;
  model: {
    mode: string;
    active_version: string;
    last_trained_at: string | null;
    accuracy: string | null;
    validation_rows: number;
    promotion_threshold: string;
    promoted: boolean;
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

type DeploymentStatus = {
  public_control_center: string;
  private_execution: string;
  selected_tunnel: string;
  tunnel_license: string;
  tunnel_access_policy: string;
  live_order_endpoint_public: boolean;
  broker_secrets_public: boolean;
  operator_confirmation_required: string;
  public_dashboard_url: string | null;
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
            <Metric label="Broker" value={data.status.primary_broker} />
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
            <Metric label="Dhan" value={data.status.apis.dhan_real_api_enabled ? "enabled" : "off"} />
            <Metric label="Twilio" value={data.status.apis.twilio_alerts_enabled ? "enabled" : "off"} />
            <Metric label="Live preflight" value={data.status.live_preflight.ready_to_trade ? "ready" : "blocked"} />
            <Metric label="Alpaca live" value={data.status.live_preflight.apis.alpaca.ready ? "ready" : "blocked"} />
            <Metric label="Groww live" value={data.status.live_preflight.apis.groww.ready ? "ready" : "blocked"} />
            <Metric label="Dhan live" value={data.status.live_preflight.apis.dhan.ready ? "ready" : "blocked"} />
            <Metric label="Twilio alerts" value={data.status.live_preflight.alerts.twilio.ready ? "ready" : "blocked"} />
            <Metric label="Alpaca keys" value={data.status.apis.alpaca_credentials_present ? "present" : "missing"} />
            <Metric label="Groww token" value={data.status.apis.groww_credentials_present ? "present" : "missing"} />
            <Metric label="Dhan token" value={data.status.apis.dhan_credentials_present ? "present" : "missing"} />
            <Metric label="Dhan static IP" value={data.status.apis.dhan_static_ip_configured ? "ready" : "missing"} />
            <Metric label="Dhan scrip map" value={data.status.apis.dhan_security_map_present ? "present" : "missing"} />
            <Metric label="Twilio auth" value={data.status.apis.twilio_credentials_present ? "present" : "missing"} />
            <Metric label="Twilio sender" value={data.status.apis.twilio_sender_configured ? "configured" : "missing"} />
            <Metric
              label="Twilio service"
              value={data.status.apis.twilio_messaging_service_configured ? "configured" : "direct"}
            />
            <Metric
              label="Twilio callback"
              value={data.status.apis.twilio_status_callback_configured ? "configured" : "missing"}
            />
          </div>
          <p className="mt-4 text-sm leading-6 text-slate-600">
            Real APIs are wired behind environment flags and credentials. Live orders remain blocked until engine gates pass.
          </p>
        </section>

        <section className="border border-slate-200 bg-white p-5">
          <div className="flex items-center justify-between gap-4">
            <h2 className="text-xl font-semibold">ML Model</h2>
            <StatePill state={data.model.promoted ? "ready" : "blocked"} />
          </div>
          <dl className="mt-5 grid grid-cols-2 gap-3">
            <Metric label="Active version" value={data.model.active_version} />
            <Metric label="Accuracy" value={data.model.accuracy ?? "not trained"} />
            <Metric label="90% gate" value={data.model.promoted ? "passed" : "blocked"} />
            <Metric label="Validation rows" value={String(data.model.validation_rows)} />
            <Metric label="Threshold" value={data.model.promotion_threshold} />
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
          <div className="flex items-center justify-between gap-4">
            <h2 className="text-xl font-semibold">Deployment Boundary</h2>
            <StatePill state={data.deployment.live_order_endpoint_public ? "blocked" : "ready"} />
          </div>
          <div className="mt-5 grid gap-3 md:grid-cols-3">
            <Metric label="Public app" value={data.deployment.public_control_center} />
            <Metric label="Execution" value={data.deployment.private_execution} />
            <Metric label="Tunnel" value={data.deployment.selected_tunnel} />
            <Metric label="License" value={data.deployment.tunnel_license} />
            <Metric label="Order endpoint" value={data.deployment.live_order_endpoint_public ? "public" : "not public"} />
            <Metric label="Secrets" value={data.deployment.broker_secrets_public ? "exposed" : "not exposed"} />
            <div className="border border-slate-200 bg-white p-3 md:col-span-2">
              <dt className="text-sm text-slate-500">Access policy</dt>
              <dd className="mt-1 text-sm font-medium leading-6 text-slate-950">
                {data.deployment.tunnel_access_policy}
              </dd>
            </div>
            <div className="border border-slate-200 bg-white p-3">
              <dt className="text-sm text-slate-500">Real-money confirmation</dt>
              <dd className="mt-1 break-words font-mono text-sm font-semibold text-slate-950">
                {data.deployment.operator_confirmation_required}
              </dd>
            </div>
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
