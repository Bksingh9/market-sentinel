import statusData from "../public/status.json";

type Lane = {
  mode: string;
  execution_target: string;
  data: {
    source: string;
    available: boolean;
    dataset_id?: string;
    first_trading_date?: string;
    last_trading_date?: string;
    row_count?: number;
  };
  model: {
    active: boolean;
    version?: string;
    feature_schema?: string;
    threshold?: string;
  };
  validation: {
    promoted_for_paper: boolean;
    fold_metrics: Array<Record<string, unknown>>;
    aggregate_metrics: Record<string, unknown>;
    modeled_costs: string | null;
    maximum_drawdown: string | null;
    expectancy: string | null;
    coverage: string | null;
  };
  paper: {
    sessions_observed: number;
    required_sessions: number;
    complete: boolean;
    calibration_status?: string;
  };
  drift: { status: string };
  data_quality: { status: string };
  blocked_reasons: string[];
};

type DashboardData = {
  generated_at: string;
  scope: string;
  lanes: Record<"US:SPY" | "IN:NIFTYBEES", Lane>;
  disclaimer: string;
};

function Status({ value }: { value: string }) {
  const tone =
    value === "observing" || value === "available"
      ? "bg-cyan-50 text-cyan-900 ring-cyan-200"
      : value === "complete" || value === "active"
        ? "bg-emerald-50 text-emerald-900 ring-emerald-200"
        : "bg-rose-50 text-rose-900 ring-rose-200";
  return (
    <span className={`inline-flex px-2 py-1 text-xs font-semibold ring-1 ${tone}`}>
      {value}
    </span>
  );
}

function EvidenceRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid min-h-11 grid-cols-[minmax(8rem,0.8fr)_minmax(0,1.2fr)] items-center gap-4 border-t border-zinc-200 py-2.5">
      <dt className="text-sm text-zinc-500">{label}</dt>
      <dd className="min-w-0 break-words text-right font-mono text-sm font-semibold text-zinc-950">
        {value}
      </dd>
    </div>
  );
}

function LaneSection({ laneKey, lane }: { laneKey: string; lane: Lane }) {
  const [market, symbol] = laneKey.split(":");
  const progress = `${lane.paper.sessions_observed} / ${lane.paper.required_sessions}`;
  return (
    <section className="border-t border-zinc-300 bg-white">
      <div className="mx-auto max-w-7xl px-5 py-7">
        <header className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-sm font-semibold text-zinc-500">{market} market</p>
            <h2 className="mt-1 text-2xl font-semibold text-zinc-950">{symbol}</h2>
            <p className="mt-1 text-sm text-zinc-600">{lane.execution_target}</p>
          </div>
          <Status value={lane.blocked_reasons.length ? "blocked" : lane.mode} />
        </header>

        <div className="mt-6 grid gap-x-8 gap-y-6 lg:grid-cols-3">
          <dl>
            <h3 className="mb-2 text-sm font-semibold text-zinc-950">Market data</h3>
            <EvidenceRow label="Provider" value={lane.data.source} />
            <EvidenceRow label="Dataset" value={lane.data.dataset_id ?? "not available"} />
            <EvidenceRow label="Range" value={lane.data.available ? `${lane.data.first_trading_date} to ${lane.data.last_trading_date}` : "not available"} />
            <EvidenceRow label="Rows" value={String(lane.data.row_count ?? 0)} />
            <EvidenceRow label="Quality" value={lane.data_quality.status} />
          </dl>

          <dl>
            <h3 className="mb-2 text-sm font-semibold text-zinc-950">Validation evidence</h3>
            <EvidenceRow label="Model" value={lane.model.version ?? "not active"} />
            <EvidenceRow label="Schema" value={lane.model.feature_schema ?? "daily-meta-v1"} />
            <EvidenceRow label="Threshold" value={lane.model.threshold ?? "not selected"} />
            <EvidenceRow label="OOS expectancy" value={lane.validation.expectancy ?? "not measured"} />
            <EvidenceRow label="Modeled costs" value={lane.validation.modeled_costs ?? "not measured"} />
            <EvidenceRow label="Maximum drawdown" value={lane.validation.maximum_drawdown ?? "not measured"} />
            <EvidenceRow label="Acceptance coverage" value={lane.validation.coverage ?? "not measured"} />
          </dl>

          <dl>
            <h3 className="mb-2 text-sm font-semibold text-zinc-950">Paper evidence</h3>
            <EvidenceRow label="Sessions" value={progress} />
            <EvidenceRow label="Status" value={lane.paper.complete ? "complete" : "observing"} />
            <EvidenceRow label="Calibration" value={lane.paper.calibration_status ?? "insufficient-history"} />
            <EvidenceRow label="Drift" value={lane.drift.status} />
            <div className="border-t border-zinc-200 py-3">
              <dt className="text-sm text-zinc-500">Blocked reasons</dt>
              <dd className="mt-2 flex flex-wrap gap-2">
                {lane.blocked_reasons.length ? (
                  lane.blocked_reasons.map((reason) => <Status key={reason} value={reason} />)
                ) : (
                  <Status value="none" />
                )}
              </dd>
            </div>
          </dl>
        </div>
      </div>
    </section>
  );
}

export default function Home() {
  const data = statusData as DashboardData;
  return (
    <main className="min-h-screen bg-zinc-100 text-zinc-950">
      <header className="bg-zinc-950 text-white">
        <div className="mx-auto flex max-w-7xl flex-wrap items-end justify-between gap-5 px-5 py-7">
          <div>
            <h1 className="text-3xl font-semibold">Market Sentinel</h1>
            <p className="mt-2 text-sm text-zinc-300">Historical validation and paper observation</p>
          </div>
          <div className="text-right text-xs text-zinc-400">
            <p>{data.scope}</p>
            <p className="mt-1 font-mono">{data.generated_at}</p>
          </div>
        </div>
      </header>
      {Object.entries(data.lanes).map(([laneKey, lane]) => (
        <LaneSection key={laneKey} laneKey={laneKey} lane={lane} />
      ))}
      <footer className="border-t border-zinc-300 bg-zinc-100">
        <p className="mx-auto max-w-7xl px-5 py-5 text-sm leading-6 text-zinc-600">{data.disclaimer}</p>
      </footer>
    </main>
  );
}
