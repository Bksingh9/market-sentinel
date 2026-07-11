# Market Sentinel Deployment And Tunnel Runbook

## Product Boundary

Market Sentinel has two runtime surfaces:

- Public/private dashboard: read-only status, model, schedule, and readiness visibility.
- Live execution: local supervised process that can submit orders only after live preflight and explicit order confirmation pass.

Do not expose broker credentials, local environment files, order-submission scripts, or any endpoint that can call `submit-order` through a public URL.

## Selected Open-Source Tunnel

Use `cloudflare/cloudflared` for the private operator tunnel.

Why this path:

- The client is open source and licensed Apache-2.0.
- It supports named tunnels that can sit behind Cloudflare Access.
- It avoids exposing the local machine by opening inbound firewall ports.
- It gives a cleaner production path than ad-hoc localhost tunnel URLs.

Do not use an unauthenticated quick tunnel for live operations. A quick tunnel can be acceptable for a short read-only demo, but live broker setup and order supervision require identity-gated access.

## Deployment Shape

1. Deploy `apps/control-center` with Sites as a read-only control center when Sites is enabled for the workspace.
2. If Sites is unavailable, deploy `apps/control-center/static-dashboard` with GitHub Pages. The workflow is `.github/workflows/deploy-control-center-pages.yml`.
3. Keep broker credentials only in the local operator process or a private secret manager.
4. Run live preflight locally with `plugins/market-sentinel-brokers/scripts/check-readiness.ps1`.
5. Use the cloudflared named tunnel only for dashboard visibility, not for order submission.
6. Submit real orders only through `submit-confirmed-order.ps1` after the user confirms the exact order parameters and `I_CONFIRM_REAL_MONEY_ORDER`.

## GitHub Pages Fallback

The GitHub Pages workflow publishes only `apps/control-center/static-dashboard` and the sanitized `apps/control-center/public/status.json` file. It does not publish Python code, broker scripts, `.env` files, credentials, or live order submission commands.

To publish from GitHub:

1. Merge this branch to `main`, or run the workflow manually from the Actions tab.
2. Confirm the repository Pages source is GitHub Actions if GitHub asks for setup.
3. Use the Pages URL only as a read-only dashboard.

## Cloudflared Named Tunnel

Create the tunnel and DNS route in Cloudflare Zero Trust, then copy `ops/tunnel/cloudflared-market-sentinel.example.yml` to a private config file outside the repository. Fill in the real tunnel ID, credentials file path, and hostname.

Start the tunnel from the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File plugins\market-sentinel-brokers\scripts\start-readonly-dashboard-tunnel.ps1 -ConfigPath C:\Secure\market-sentinel\cloudflared.yml -TunnelName market-sentinel-control
```

The script requires a named tunnel config. It will not start an unauthenticated random public URL.

## Access Policy

Configure Cloudflare Access or an equivalent identity gate before the dashboard hostname is reachable:

- allow only the operator account or a tightly scoped operator group;
- require MFA where available;
- keep audit logs enabled;
- do not allow anonymous access;
- do not route any local API that can place, modify, or cancel orders.

## Live Readiness

The dashboard can show `ready_to_trade=true` only when local preflight sees real local values for broker credentials, static IP allowlisting, compliance flags, and account allowlisting. Do not edit `status.json` by hand to force readiness.

## Rollback

To stop public visibility:

1. Stop the cloudflared process.
2. Disable or remove the Cloudflare Access application route.
3. Rotate any broker keys that were exposed outside the local operator process.
4. Set `MARKET_SENTINEL_MODE=emergency` before any recovery work.
