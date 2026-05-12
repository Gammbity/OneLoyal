import {
  Activity,
  Archive,
  BarChart3,
  Check,
  ChevronRight,
  FileText,
  Gift,
  LayoutDashboard,
  Loader2,
  LogOut,
  Pause,
  Play,
  PlugZap,
  Plus,
  RefreshCw,
  Search,
  ShieldCheck,
  TicketCheck,
  Trash2,
  Trophy,
  Upload,
  Users,
  X,
} from "lucide-react";
import type { DependencyList, FormEvent, ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";
import type { LucideIcon } from "lucide-react";

import {
  apiRequest,
  clearTokens,
  getStoredAccessToken,
  login,
  logout,
  me,
  query,
} from "./api";
import { t, loadLanguage, setLanguage, getLanguage } from "./i18n";
import type {
  Campaign,
  CampaignOverview,
  CloseToNextReportItem,
  Customer,
  GiftLiabilityReport,
  GiftTier,
  ID,
  ImportBatch,
  ImportPreview,
  ImportRow,
  Integration,
  MeResponse,
  Paginated,
  Progress,
  RewardClaim,
  RewardClaimsReport,
  SalesManagerReportItem,
  SyncHealthReport,
  SyncRun,
  TopCustomerReportItem,
  OpsStatusResponse,
  RecoverStuckSyncsResponse,
  RecoverNotificationsResponse,
} from "./types";
import {
  asJson,
  compactNumber,
  money,
  parseJsonObject,
  shortDate,
  shortDateTime,
  titleCase,
} from "./utils";
import PortalApp from "./PortalApp";

type RouteKey =
  | "dashboard"
  | "campaigns"
  | "gift-tiers"
  | "customers"
  | "imports"
  | "integrations"
  | "claims"
  | "reports"
  | "ops";

type Resource<T> = {
  data: T;
  loading: boolean;
  error: string | null;
  reload: () => void;
};

const emptyPage = <T,>(): Paginated<T> => ({
  items: [],
  pagination: { limit: 50, offset: 0, total: 0, has_more: false },
});

const routeMeta: Array<{
  key: RouteKey;
  label: string;
  icon: LucideIcon;
}> = [
  { key: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { key: "campaigns", label: "Campaigns", icon: Trophy },
  { key: "gift-tiers", label: "Gift Tiers", icon: Gift },
  { key: "customers", label: "Customers", icon: Users },
  { key: "imports", label: "Imports", icon: Upload },
  { key: "integrations", label: "Integrations", icon: PlugZap },
  { key: "claims", label: "Reward Claims", icon: TicketCheck },
  { key: "reports", label: "Reports", icon: BarChart3 },
  { key: "ops", label: "Operations", icon: Activity },
];

function errorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return "Request failed.";
}

function useResource<T>(
  loader: () => Promise<T>,
  deps: DependencyList,
  initial: T,
): Resource<T> {
  const [data, setData] = useState<T>(initial);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    loader()
      .then((value) => {
        if (!cancelled) {
          setData(value);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(errorMessage(err));
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [...deps, revision]);

  return {
    data,
    loading,
    error,
    reload: () => setRevision((value) => value + 1),
  };
}

function StatusPill({ value }: { value: string }) {
  return <span className={`pill ${value}`}>{titleCase(value)}</span>;
}

function Button({
  icon: Icon,
  variant = "primary",
  children,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  icon?: LucideIcon;
  variant?: "primary" | "secondary" | "warning" | "danger" | "ghost";
}) {
  return (
    <button className={`button ${variant}`} {...props}>
      {Icon ? <Icon size={16} /> : null}
      {children}
    </button>
  );
}

function IconButton({
  icon: Icon,
  label,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  icon: LucideIcon;
  label: string;
}) {
  return (
    <button className="icon-button" title={label} aria-label={label} {...props}>
      <Icon size={17} />
    </button>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <div className="field">
      <label>{label}</label>
      {children}
    </div>
  );
}

function Panel({
  title,
  action,
  children,
}: {
  title: string;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="panel">
      <div className="panel-header">
        <h2>{title}</h2>
        {action}
      </div>
      <div className="panel-body">{children}</div>
    </section>
  );
}

function Stat({
  label,
  value,
}: {
  label: string;
  value: string | number;
}) {
  return (
    <section className="panel stat">
      <span>{label}</span>
      <strong>{value}</strong>
    </section>
  );
}

function Table({
  headers,
  children,
}: {
  headers: string[];
  children: ReactNode;
}) {
  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            {headers.map((header) => (
              <th key={header}>{header}</th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}

function Notice({
  kind,
  children,
}: {
  kind: "error" | "success";
  children: ReactNode;
}) {
  return <div className={`notice ${kind}`}>{children}</div>;
}

function Empty({ children = "No records found." }: { children?: ReactNode }) {
  return <div className="empty">{children}</div>;
}

function Loading() {
  return (
    <div className="notice">
      <Loader2 size={16} /> Loading
    </div>
  );
}

function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
}) {
  return (
    <header className="page-header">
      <div className="page-title">
        <h1>{title}</h1>
        {subtitle ? <p>{subtitle}</p> : null}
      </div>
      {actions ? <div className="actions">{actions}</div> : null}
    </header>
  );
}

function CampaignPicker({
  campaigns,
  value,
  onChange,
}: {
  campaigns: Campaign[];
  value: ID;
  onChange: (value: ID) => void;
}) {
  return (
    <select
      className="select"
      value={value}
      onChange={(event) => onChange(event.target.value)}
    >
      <option value="">Select campaign</option>
      {campaigns.map((campaign) => (
        <option key={campaign.id} value={campaign.id}>
          {campaign.title}
        </option>
      ))}
    </select>
  );
}

function LoginScreen({
  onLogin,
}: {
  onLogin: (session: MeResponse) => void;
}) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const auth = await login(email, password);
      onLogin({
        user: auth.user,
        company: auth.company,
        role: auth.user.role,
        company_id: auth.user.company_id,
      });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="login-shell">
      <section className="login-panel">
        <div className="brand">
          <span className="brand-mark">
            <ShieldCheck size={20} />
          </span>
          OneLoyal
        </div>
        <div style={{ height: 42 }} />
        <h1>Admin Console</h1>
        <p>Sign in to manage loyalty operations.</p>
        <div style={{ height: 24 }} />
        <form className="form-grid" onSubmit={submit}>
          {error ? <Notice kind="error">{error}</Notice> : null}
          <Field label="Email">
            <input
              className="input"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              autoComplete="email"
              required
            />
          </Field>
          <Field label="Password">
            <input
              className="input"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="current-password"
              required
            />
          </Field>
          <Button icon={LogOut} disabled={loading}>
            {loading ? "Signing in" : "Sign in"}
          </Button>
        </form>
      </section>
      <section className="login-art">
        <div className="metric-wall">
          <div className="metric-tile">
            <span>Campaigns</span>
            <strong>16.4</strong>
          </div>
          <div className="metric-tile">
            <span>Gift stock</span>
            <strong>16.5</strong>
          </div>
          <div className="metric-tile">
            <span>Customer progress</span>
            <strong>16.6</strong>
          </div>
          <div className="metric-tile">
            <span>Reports</span>
            <strong>16.10</strong>
          </div>
        </div>
      </section>
    </main>
  );
}

function Shell({
  session,
  route,
  setRoute,
  onLogout,
  children,
}: {
  session: MeResponse;
  route: RouteKey;
  setRoute: (route: RouteKey) => void;
  onLogout: () => void;
  children: ReactNode;
}) {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">
            <ShieldCheck size={20} />
          </span>
          OneLoyal
        </div>
        <nav className="nav">
          {routeMeta.map((item) => {
            const Icon = item.icon;
            const labelKey = `nav.${item.key.replace("-", ".")}`;
            return (
              <button
                key={item.key}
                className={`nav-button ${route === item.key ? "active" : ""}`}
                onClick={() => setRoute(item.key)}
              >
                <Icon size={18} />
                {t(labelKey) || item.label}
              </button>
            );
          })}
        </nav>
        <div className="sidebar-footer">
          <div className="user-block">
            <strong>{session.user.full_name}</strong>
            <span>{session.company?.name ?? session.user.email}</span>
            <span>{titleCase(session.role)}</span>
          </div>
          <div style={{ marginBottom: 12 }}>
            <label style={{ display: "block", fontSize: 12, marginBottom: 6, color: "#999" }}>
              Language
            </label>
            <select
              className="select"
              value={getLanguage()}
              onChange={(e) => {
                setLanguage(e.target.value as "en" | "uz" | "ru");
                window.location.reload();
              }}
              style={{ width: "100%" }}
            >
              <option value="en">English</option>
              <option value="uz">Oʻzbekcha</option>
              <option value="ru">Русский</option>
            </select>
          </div>
          <Button icon={LogOut} variant="secondary" onClick={onLogout}>
            {t("auth.logout")}
          </Button>
        </div>
      </aside>
      <main className="main">{children}</main>
    </div>
  );
}

function DashboardScreen() {
  const dashboard = useResource(
    async () => {
      const [campaigns, customers, claims, sync] = await Promise.all([
        apiRequest<Paginated<Campaign>>("/campaigns?limit=100"),
        apiRequest<Paginated<Customer>>("/customers?limit=1"),
        apiRequest<RewardClaimsReport>("/reports/reward-claims?limit=5"),
        apiRequest<SyncHealthReport>("/reports/sync-health?limit=5"),
      ]);
      let overview: CampaignOverview | null = null;
      if (campaigns.items[0]) {
        overview = await apiRequest<CampaignOverview>(
          `/reports/campaigns/${campaigns.items[0].id}/overview`,
        );
      }
      return { campaigns, customers, claims, sync, overview };
    },
    [],
    {
      campaigns: emptyPage<Campaign>(),
      customers: emptyPage<Customer>(),
      claims: null as RewardClaimsReport | null,
      sync: null as SyncHealthReport | null,
      overview: null as CampaignOverview | null,
    },
  );

  const activeCampaigns = dashboard.data.campaigns.items.filter(
    (campaign) => campaign.status === "active",
  ).length;

  return (
    <>
      <PageHeader
        title="Dashboard"
        subtitle="Company activity at a glance"
        actions={
          <IconButton
            icon={RefreshCw}
            label="Refresh"
            onClick={dashboard.reload}
          />
        }
      />
      {dashboard.error ? <Notice kind="error">{dashboard.error}</Notice> : null}
      <div className="grid four">
        <Stat label="Campaigns" value={dashboard.data.campaigns.pagination.total ?? 0} />
        <Stat label="Active" value={activeCampaigns} />
        <Stat
          label="Customers"
          value={dashboard.data.customers.pagination.total ?? 0}
        />
        <Stat
          label="Pending claims"
          value={dashboard.data.claims?.summary.pending ?? 0}
        />
      </div>
      <div style={{ height: 14 }} />
      <div className="grid two">
        <Panel title="Current Campaign">
          {dashboard.loading ? <Loading /> : null}
          {dashboard.data.overview ? (
            <div className="grid three">
              <Stat
                label="Customers"
                value={dashboard.data.overview.total_customers_with_progress}
              />
              <Stat
                label="Purchase amount"
                value={money(
                  dashboard.data.overview.total_purchase_amount_minor,
                  dashboard.data.overview.currency,
                )}
              />
              <Stat
                label="Fulfilled claims"
                value={dashboard.data.overview.total_fulfilled_claims}
              />
            </div>
          ) : (
            <Empty>No campaign data.</Empty>
          )}
        </Panel>
        <Panel title="Sync Health">
          {dashboard.data.sync ? (
            <div className="grid three">
              <Stat
                label="Integrations"
                value={dashboard.data.sync.summary.total_integrations}
              />
              <Stat
                label="Failed"
                value={dashboard.data.sync.summary.failed_runs}
              />
              <Stat
                label="Partial"
                value={dashboard.data.sync.summary.partially_failed_runs}
              />
            </div>
          ) : (
            <Empty>No sync data.</Empty>
          )}
        </Panel>
      </div>
      <div style={{ height: 14 }} />
      <div className="grid two">
        <Panel title="Recent Campaigns">
          <Table headers={["Title", "Status", "Dates", "Currency"]}>
            {dashboard.data.campaigns.items.slice(0, 6).map((campaign) => (
              <tr key={campaign.id}>
                <td>{campaign.title}</td>
                <td>
                  <StatusPill value={campaign.status} />
                </td>
                <td>
                  {shortDate(campaign.start_date)} - {shortDate(campaign.end_date)}
                </td>
                <td>{campaign.currency}</td>
              </tr>
            ))}
          </Table>
        </Panel>
        <Panel title="Recent Claims">
          {dashboard.data.claims?.items.length ? (
            <Table headers={["Customer", "Campaign", "Gift", "Status"]}>
              {dashboard.data.claims.items.map((claim) => (
                <tr key={claim.claim_id}>
                  <td>{claim.customer_name}</td>
                  <td>{claim.campaign_title}</td>
                  <td>{claim.gift_tier_title}</td>
                  <td>
                    <StatusPill value={claim.status} />
                  </td>
                </tr>
              ))}
            </Table>
          ) : (
            <Empty>No claims.</Empty>
          )}
        </Panel>
      </div>
    </>
  );
}

function CampaignsScreen() {
  const campaigns = useResource(
    () => apiRequest<Paginated<Campaign>>("/campaigns?limit=100"),
    [],
    emptyPage<Campaign>(),
  );
  const [form, setForm] = useState({
    title: "",
    description: "",
    start_date: "2026-01-01",
    end_date: "2026-12-31",
    currency: "UZS",
    allow_claims: true,
  });
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function createCampaign(event: FormEvent) {
    event.preventDefault();
    setNotice(null);
    setError(null);
    try {
      await apiRequest<Campaign>("/campaigns", {
        method: "POST",
        body: JSON.stringify(form),
      });
      setForm((current) => ({ ...current, title: "", description: "" }));
      setNotice("Campaign created.");
      campaigns.reload();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  async function campaignAction(campaign: Campaign, action: string) {
    setError(null);
    setNotice(null);
    try {
      await apiRequest<Campaign>(`/campaigns/${campaign.id}/${action}`, {
        method: "POST",
      });
      setNotice(`${campaign.title} ${action}d.`);
      campaigns.reload();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <>
      <PageHeader
        title="Campaigns"
        subtitle="Lifecycle, dates, currency, and claim availability"
        actions={
          <IconButton icon={RefreshCw} label="Refresh" onClick={campaigns.reload} />
        }
      />
      <div className="split">
        <Panel title="Campaign List">
          {campaigns.loading ? <Loading /> : null}
          {campaigns.error ? <Notice kind="error">{campaigns.error}</Notice> : null}
          {notice ? <Notice kind="success">{notice}</Notice> : null}
          {error ? <Notice kind="error">{error}</Notice> : null}
          <Table headers={["Title", "Status", "Dates", "Claims", "Actions"]}>
            {campaigns.data.items.map((campaign) => (
              <tr key={campaign.id}>
                <td>
                  <strong>{campaign.title}</strong>
                  <div className="muted">{campaign.description}</div>
                </td>
                <td>
                  <StatusPill value={campaign.status} />
                </td>
                <td>
                  {shortDate(campaign.start_date)} - {shortDate(campaign.end_date)}
                  <div className="muted">{campaign.currency}</div>
                </td>
                <td>{campaign.allow_claims ? "Enabled" : "Disabled"}</td>
                <td>
                  <div className="actions">
                    {["draft", "paused"].includes(campaign.status) ? (
                      <IconButton
                        icon={Play}
                        label="Activate"
                        onClick={() => campaignAction(campaign, "activate")}
                      />
                    ) : null}
                    {campaign.status === "active" ? (
                      <IconButton
                        icon={Pause}
                        label="Pause"
                        onClick={() => campaignAction(campaign, "pause")}
                      />
                    ) : null}
                    {["active", "paused"].includes(campaign.status) ? (
                      <IconButton
                        icon={Check}
                        label="Complete"
                        onClick={() => campaignAction(campaign, "complete")}
                      />
                    ) : null}
                    {["draft", "completed"].includes(campaign.status) ? (
                      <IconButton
                        icon={Archive}
                        label="Archive"
                        onClick={() => campaignAction(campaign, "archive")}
                      />
                    ) : null}
                  </div>
                </td>
              </tr>
            ))}
          </Table>
        </Panel>
        <Panel title="New Campaign">
          <form className="form-grid" onSubmit={createCampaign}>
            <Field label="Title">
              <input
                className="input"
                value={form.title}
                onChange={(event) =>
                  setForm({ ...form, title: event.target.value })
                }
                required
              />
            </Field>
            <Field label="Description">
              <textarea
                className="textarea"
                value={form.description}
                onChange={(event) =>
                  setForm({ ...form, description: event.target.value })
                }
              />
            </Field>
            <div className="form-grid two">
              <Field label="Start">
                <input
                  className="input"
                  type="date"
                  value={form.start_date}
                  onChange={(event) =>
                    setForm({ ...form, start_date: event.target.value })
                  }
                  required
                />
              </Field>
              <Field label="End">
                <input
                  className="input"
                  type="date"
                  value={form.end_date}
                  onChange={(event) =>
                    setForm({ ...form, end_date: event.target.value })
                  }
                  required
                />
              </Field>
            </div>
            <div className="form-grid two">
              <Field label="Currency">
                <input
                  className="input"
                  value={form.currency}
                  onChange={(event) =>
                    setForm({ ...form, currency: event.target.value.toUpperCase() })
                  }
                  maxLength={3}
                />
              </Field>
              <Field label="Claims">
                <select
                  className="select"
                  value={form.allow_claims ? "true" : "false"}
                  onChange={(event) =>
                    setForm({
                      ...form,
                      allow_claims: event.target.value === "true",
                    })
                  }
                >
                  <option value="true">Enabled</option>
                  <option value="false">Disabled</option>
                </select>
              </Field>
            </div>
            <Button icon={Plus}>Create campaign</Button>
          </form>
        </Panel>
      </div>
    </>
  );
}

function GiftTiersScreen() {
  const campaigns = useResource(
    () => apiRequest<Paginated<Campaign>>("/campaigns?limit=100"),
    [],
    emptyPage<Campaign>(),
  );
  const [campaignId, setCampaignId] = useState("");
  const [editingId, setEditingId] = useState<ID | null>(null);
  const [form, setForm] = useState({
    title: "",
    required_amount_minor: "1000000",
    stock_tracking_mode: "none",
    stock_quantity: "",
    is_active: true,
  });
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    if (!campaignId && campaigns.data.items[0]) {
      setCampaignId(campaigns.data.items[0].id);
    }
  }, [campaigns.data.items, campaignId]);

  const tiers = useResource(
    async () => {
      if (!campaignId) {
        return [] as GiftTier[];
      }
      return apiRequest<GiftTier[]>(`/campaigns/${campaignId}/gift-tiers`);
    },
    [campaignId],
    [] as GiftTier[],
  );
  const selectedCampaign = campaigns.data.items.find((item) => item.id === campaignId);

  function resetForm() {
    setEditingId(null);
    setForm({
      title: "",
      required_amount_minor: "1000000",
      stock_tracking_mode: "none",
      stock_quantity: "",
      is_active: true,
    });
  }

  function editTier(tier: GiftTier) {
    setEditingId(tier.id);
    setForm({
      title: tier.title,
      required_amount_minor: String(tier.required_amount_minor),
      stock_tracking_mode: tier.stock_tracking_mode,
      stock_quantity: tier.stock_quantity === null ? "" : String(tier.stock_quantity),
      is_active: tier.is_active,
    });
  }

  async function saveTier(event: FormEvent) {
    event.preventDefault();
    if (!campaignId) {
      return;
    }
    const payload = {
      title: form.title,
      required_amount_minor: Number(form.required_amount_minor),
      stock_tracking_mode: form.stock_tracking_mode,
      stock_quantity: form.stock_quantity ? Number(form.stock_quantity) : null,
      is_active: form.is_active,
    };
    setError(null);
    setNotice(null);
    try {
      if (editingId) {
        await apiRequest<GiftTier>(
          `/campaigns/${campaignId}/gift-tiers/${editingId}`,
          { method: "PATCH", body: JSON.stringify(payload) },
        );
        setNotice("Gift tier updated.");
      } else {
        await apiRequest<GiftTier>(`/campaigns/${campaignId}/gift-tiers`, {
          method: "POST",
          body: JSON.stringify(payload),
        });
        setNotice("Gift tier created.");
      }
      resetForm();
      tiers.reload();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  async function deleteTier(tier: GiftTier) {
    setError(null);
    setNotice(null);
    try {
      await apiRequest(`/campaigns/${campaignId}/gift-tiers/${tier.id}`, {
        method: "DELETE",
      });
      setNotice("Gift tier deleted.");
      tiers.reload();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <>
      <PageHeader
        title="Gift Tiers"
        subtitle={selectedCampaign?.title ?? "Select a campaign"}
        actions={
          <div className="actions">
            <CampaignPicker
              campaigns={campaigns.data.items}
              value={campaignId}
              onChange={setCampaignId}
            />
            <IconButton icon={RefreshCw} label="Refresh" onClick={tiers.reload} />
          </div>
        }
      />
      <div className="split">
        <Panel title="Tiers">
          {tiers.loading ? <Loading /> : null}
          {notice ? <Notice kind="success">{notice}</Notice> : null}
          {error ?? tiers.error ? (
            <Notice kind="error">{error ?? tiers.error}</Notice>
          ) : null}
          {tiers.data.length ? (
            <Table
              headers={[
                "Title",
                "Required",
                "Stock",
                "Reserved",
                "Available",
                "Actions",
              ]}
            >
              {tiers.data.map((tier) => (
                <tr key={tier.id}>
                  <td>
                    <strong>{tier.title}</strong>
                    <div className="muted">{titleCase(tier.stock_tracking_mode)}</div>
                  </td>
                  <td>{money(tier.required_amount_minor, tier.currency)}</td>
                  <td>{tier.stock_quantity ?? "-"}</td>
                  <td>{tier.reserved_quantity}</td>
                  <td>{tier.available_quantity ?? "-"}</td>
                  <td>
                    <div className="actions">
                      <IconButton
                        icon={ChevronRight}
                        label="Edit"
                        onClick={() => editTier(tier)}
                      />
                      <IconButton
                        icon={Trash2}
                        label="Delete"
                        onClick={() => deleteTier(tier)}
                      />
                    </div>
                  </td>
                </tr>
              ))}
            </Table>
          ) : (
            <Empty>No gift tiers.</Empty>
          )}
        </Panel>
        <Panel title={editingId ? "Edit Tier" : "New Tier"}>
          <form className="form-grid" onSubmit={saveTier}>
            <Field label="Title">
              <input
                className="input"
                value={form.title}
                onChange={(event) =>
                  setForm({ ...form, title: event.target.value })
                }
                required
              />
            </Field>
            <Field label="Required amount">
              <input
                className="input"
                type="number"
                min={1}
                value={form.required_amount_minor}
                onChange={(event) =>
                  setForm({ ...form, required_amount_minor: event.target.value })
                }
                required
              />
            </Field>
            <div className="form-grid two">
              <Field label="Tracking">
                <select
                  className="select"
                  value={form.stock_tracking_mode}
                  onChange={(event) =>
                    setForm({ ...form, stock_tracking_mode: event.target.value })
                  }
                >
                  <option value="none">None</option>
                  <option value="soft">Soft</option>
                  <option value="strict">Strict</option>
                </select>
              </Field>
              <Field label="Stock">
                <input
                  className="input"
                  type="number"
                  min={0}
                  value={form.stock_quantity}
                  onChange={(event) =>
                    setForm({ ...form, stock_quantity: event.target.value })
                  }
                />
              </Field>
            </div>
            <Field label="Active">
              <select
                className="select"
                value={form.is_active ? "true" : "false"}
                onChange={(event) =>
                  setForm({ ...form, is_active: event.target.value === "true" })
                }
              >
                <option value="true">Active</option>
                <option value="false">Inactive</option>
              </select>
            </Field>
            <div className="actions">
              <Button icon={Check}>{editingId ? "Save tier" : "Create tier"}</Button>
              {editingId ? (
                <Button type="button" variant="secondary" onClick={resetForm}>
                  Cancel
                </Button>
              ) : null}
            </div>
          </form>
        </Panel>
      </div>
    </>
  );
}

function CustomersProgressScreen() {
  const campaigns = useResource(
    () => apiRequest<Paginated<Campaign>>("/campaigns?limit=100"),
    [],
    emptyPage<Campaign>(),
  );
  const [campaignId, setCampaignId] = useState("");
  const [search, setSearch] = useState("");
  const [form, setForm] = useState({ name: "", phone: "", email: "", tax_id: "" });
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!campaignId && campaigns.data.items[0]) {
      setCampaignId(campaigns.data.items[0].id);
    }
  }, [campaignId, campaigns.data.items]);

  const customers = useResource(
    () =>
      apiRequest<Paginated<Customer>>(
        `/customers${query({ limit: 100, search })}`,
      ),
    [search],
    emptyPage<Customer>(),
  );
  const progress = useResource(
    async () => {
      if (!campaignId) {
        return emptyPage<Progress>();
      }
      return apiRequest<Paginated<Progress>>(
        `/progress/campaigns/${campaignId}${query({ limit: 100, search })}`,
      );
    },
    [campaignId, search],
    emptyPage<Progress>(),
  );

  async function createCustomer(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setNotice(null);
    try {
      await apiRequest<Customer>("/customers", {
        method: "POST",
        body: JSON.stringify({
          name: form.name,
          phone: form.phone || null,
          email: form.email || null,
          tax_id: form.tax_id || null,
        }),
      });
      setForm({ name: "", phone: "", email: "", tax_id: "" });
      setNotice("Customer created.");
      customers.reload();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  async function recalculate(customerId?: ID) {
    if (!campaignId) {
      return;
    }
    setError(null);
    setNotice(null);
    try {
      const path = customerId
        ? `/progress/campaigns/${campaignId}/customers/${customerId}/recalculate`
        : `/progress/campaigns/${campaignId}/recalculate`;
      await apiRequest(path, { method: "POST" });
      setNotice("Progress recalculated.");
      progress.reload();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  const progressByCustomer = new Map(
    progress.data.items.map((item) => [item.customer_id, item]),
  );

  return (
    <>
      <PageHeader
        title="Customers"
        subtitle="Customer records and campaign progress"
        actions={
          <div className="actions">
            <CampaignPicker
              campaigns={campaigns.data.items}
              value={campaignId}
              onChange={setCampaignId}
            />
            <div className="field" style={{ minWidth: 220 }}>
              <input
                className="input"
                value={search}
                placeholder="Search"
                onChange={(event) => setSearch(event.target.value)}
              />
            </div>
            <Button
              icon={RefreshCw}
              variant="secondary"
              onClick={() => recalculate()}
              type="button"
            >
              Recalculate
            </Button>
          </div>
        }
      />
      <div className="split">
        <Panel title="Customers & Progress">
          {customers.loading || progress.loading ? <Loading /> : null}
          {notice ? <Notice kind="success">{notice}</Notice> : null}
          {error ?? customers.error ?? progress.error ? (
            <Notice kind="error">
              {error ?? customers.error ?? progress.error}
            </Notice>
          ) : null}
          <Table
            headers={[
              "Customer",
              "Contact",
              "Total",
              "Current",
              "Next",
              "Progress",
              "Actions",
            ]}
          >
            {customers.data.items.map((customer) => {
              const item = progressByCustomer.get(customer.id);
              return (
                <tr key={customer.id}>
                  <td>
                    <strong>{customer.name}</strong>
                    <div className="muted">{customer.tax_id ?? "-"}</div>
                  </td>
                  <td>
                    <div>{customer.phone ?? "-"}</div>
                    <div className="muted">{customer.email ?? "-"}</div>
                  </td>
                  <td>{item ? money(item.total_amount_minor, item.currency) : "-"}</td>
                  <td>{item?.current_tier_title ?? "-"}</td>
                  <td>
                    {item?.next_tier_title ?? "-"}
                    {item ? (
                      <div className="muted">
                        Left {money(item.amount_left_minor, item.currency)}
                      </div>
                    ) : null}
                  </td>
                  <td>
                    {item ? (
                      <>
                        <div className="progress-bar">
                          <div
                            className="progress-fill"
                            style={{
                              width: `${Math.min(
                                Number(item.progress_percent),
                                100,
                              )}%`,
                            }}
                          />
                        </div>
                        <div className="muted">{item.progress_percent}%</div>
                      </>
                    ) : (
                      "-"
                    )}
                  </td>
                  <td>
                    <IconButton
                      icon={RefreshCw}
                      label="Recalculate"
                      onClick={() => recalculate(customer.id)}
                    />
                  </td>
                </tr>
              );
            })}
          </Table>
        </Panel>
        <Panel title="New Customer">
          <form className="form-grid" onSubmit={createCustomer}>
            <Field label="Name">
              <input
                className="input"
                value={form.name}
                onChange={(event) =>
                  setForm({ ...form, name: event.target.value })
                }
                required
              />
            </Field>
            <Field label="Phone">
              <input
                className="input"
                value={form.phone}
                onChange={(event) =>
                  setForm({ ...form, phone: event.target.value })
                }
              />
            </Field>
            <Field label="Email">
              <input
                className="input"
                type="email"
                value={form.email}
                onChange={(event) =>
                  setForm({ ...form, email: event.target.value })
                }
              />
            </Field>
            <Field label="Tax ID">
              <input
                className="input"
                value={form.tax_id}
                onChange={(event) =>
                  setForm({ ...form, tax_id: event.target.value })
                }
              />
            </Field>
            <Button icon={Plus}>Create customer</Button>
          </form>
        </Panel>
      </div>
    </>
  );
}

function ImportsScreen() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [selectedBatchId, setSelectedBatchId] = useState<ID>("");
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const batches = useResource(
    () => apiRequest<Paginated<ImportBatch>>("/imports?limit=50"),
    [],
    emptyPage<ImportBatch>(),
  );
  const rows = useResource(
    async () => {
      if (!selectedBatchId) {
        return emptyPage<ImportRow>();
      }
      return apiRequest<Paginated<ImportRow>>(
        `/imports/${selectedBatchId}/rows?limit=50`,
      );
    },
    [selectedBatchId],
    emptyPage<ImportRow>(),
  );

  async function previewCsv(event: FormEvent) {
    event.preventDefault();
    if (!selectedFile) {
      return;
    }
    setError(null);
    setNotice(null);
    const body = new FormData();
    body.append("file", selectedFile);
    try {
      const response = await apiRequest<ImportPreview>("/imports/csv/preview", {
        method: "POST",
        body,
      });
      setPreview(response);
      setSelectedBatchId(response.import_batch_id);
      setNotice("CSV preview created.");
      batches.reload();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  async function batchAction(batchId: ID, action: "commit" | "cancel") {
    setError(null);
    setNotice(null);
    try {
      await apiRequest(`/imports/${batchId}/${action}`, { method: "POST" });
      setNotice(`Import ${action} complete.`);
      batches.reload();
      rows.reload();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <>
      <PageHeader
        title="Imports"
        subtitle="CSV preview, rows, commit, and cancellation"
        actions={<IconButton icon={RefreshCw} label="Refresh" onClick={batches.reload} />}
      />
      <div className="split">
        <div className="grid">
          <Panel title="Upload CSV">
            <form className="form-grid" onSubmit={previewCsv}>
              {notice ? <Notice kind="success">{notice}</Notice> : null}
              {error ?? batches.error ? (
                <Notice kind="error">{error ?? batches.error}</Notice>
              ) : null}
              <Field label="File">
                <input
                  className="input"
                  type="file"
                  accept=".csv,text/csv"
                  onChange={(event) =>
                    setSelectedFile(event.target.files?.[0] ?? null)
                  }
                />
              </Field>
              <Button icon={Upload} disabled={!selectedFile}>
                Preview CSV
              </Button>
            </form>
          </Panel>
          <Panel title="Import Batches">
            <Table
              headers={[
                "File",
                "Status",
                "Rows",
                "Committed",
                "Created",
                "Actions",
              ]}
            >
              {batches.data.items.map((batch) => (
                <tr key={batch.id}>
                  <td>
                    <button
                      className="button ghost"
                      onClick={() => setSelectedBatchId(batch.id)}
                    >
                      <FileText size={15} />
                      {batch.original_filename ?? batch.id.slice(0, 8)}
                    </button>
                  </td>
                  <td>
                    <StatusPill value={batch.status} />
                  </td>
                  <td>
                    {batch.valid_rows}/{batch.total_rows}
                    {batch.invalid_rows ? (
                      <div className="muted">{batch.invalid_rows} invalid</div>
                    ) : null}
                  </td>
                  <td>{batch.committed_rows}</td>
                  <td>{shortDateTime(batch.created_at)}</td>
                  <td>
                    <div className="actions">
                      <IconButton
                        icon={Check}
                        label="Commit"
                        onClick={() => batchAction(batch.id, "commit")}
                      />
                      <IconButton
                        icon={X}
                        label="Cancel"
                        onClick={() => batchAction(batch.id, "cancel")}
                      />
                    </div>
                  </td>
                </tr>
              ))}
            </Table>
          </Panel>
        </div>
        <Panel title="Preview & Rows">
          {preview ? (
            <div className="grid">
              <div className="grid three">
                <Stat label="Total" value={preview.total_rows} />
                <Stat label="Valid" value={preview.valid_rows} />
                <Stat label="Invalid" value={preview.invalid_rows} />
              </div>
              {preview.errors.length ? (
                <Table headers={["Row", "Errors"]}>
                  {preview.errors.map((row) => (
                    <tr key={row.row_number}>
                      <td>{row.row_number}</td>
                      <td>{row.errors.join(", ")}</td>
                    </tr>
                  ))}
                </Table>
              ) : null}
            </div>
          ) : null}
          {rows.loading ? <Loading /> : null}
          {rows.data.items.length ? (
            <Table headers={["Row", "Status", "Messages"]}>
              {rows.data.items.map((row) => (
                <tr key={row.id}>
                  <td>{row.row_number}</td>
                  <td>
                    <StatusPill value={row.status} />
                  </td>
                  <td>{row.error_messages_json.join(", ") || "-"}</td>
                </tr>
              ))}
            </Table>
          ) : (
            <Empty>Select an import batch.</Empty>
          )}
        </Panel>
      </div>
    </>
  );
}

function IntegrationsSyncScreen() {
  const [form, setForm] = useState({
    provider: "fake",
    name: "Fake ERP",
    settings_json: '{\n  "customers": [],\n  "sales": []\n}',
    credentials_json: "",
  });
  const [selectedIntegrationId, setSelectedIntegrationId] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const integrations = useResource(
    () => apiRequest<Integration[]>("/integrations"),
    [],
    [] as Integration[],
  );
  const syncHealth = useResource(
    () => apiRequest<SyncHealthReport>("/reports/sync-health?limit=20"),
    [],
    null as SyncHealthReport | null,
  );
  const syncRuns = useResource(
    async () => {
      const qs = query({ limit: 50, integration_id: selectedIntegrationId });
      return apiRequest<Paginated<SyncRun>>(`/sync-runs${qs}`);
    },
    [selectedIntegrationId],
    emptyPage<SyncRun>(),
  );

  useEffect(() => {
    if (!selectedIntegrationId && integrations.data[0]) {
      setSelectedIntegrationId(integrations.data[0].id);
    }
  }, [integrations.data, selectedIntegrationId]);

  async function createIntegration(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setNotice(null);
    try {
      const payload: Record<string, unknown> = {
        provider: form.provider,
        name: form.name,
        settings_json: parseJsonObject(form.settings_json),
      };
      if (form.credentials_json.trim()) {
        payload.credentials_json = parseJsonObject(form.credentials_json);
      }
      await apiRequest<Integration>("/integrations", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setNotice("Integration created.");
      integrations.reload();
      syncHealth.reload();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  async function integrationAction(
    integration: Integration,
    action: "test" | "sync" | "activate" | "disable",
  ) {
    setError(null);
    setNotice(null);
    try {
      if (action === "test") {
        const result = await apiRequest<{ ok: boolean; message: string }>(
          `/integrations/${integration.id}/test`,
          { method: "POST" },
        );
        setNotice(result.message);
      } else if (action === "sync") {
        await apiRequest(`/integrations/${integration.id}/sync`, {
          method: "POST",
        });
        setNotice("Sync queued.");
      } else {
        await apiRequest<Integration>(`/integrations/${integration.id}`, {
          method: "PATCH",
          body: JSON.stringify({
            status: action === "activate" ? "active" : "disabled",
          }),
        });
        setNotice(`Integration ${action}d.`);
      }
      integrations.reload();
      syncHealth.reload();
      syncRuns.reload();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <>
      <PageHeader
        title="Integrations"
        subtitle="Provider setup, connection checks, sync queueing, and health"
        actions={
          <div className="actions">
            <select
              className="select"
              value={selectedIntegrationId}
              onChange={(event) => setSelectedIntegrationId(event.target.value)}
            >
              <option value="">All integrations</option>
              {integrations.data.map((integration) => (
                <option key={integration.id} value={integration.id}>
                  {integration.name}
                </option>
              ))}
            </select>
            <IconButton
              icon={RefreshCw}
              label="Refresh"
              onClick={() => {
                integrations.reload();
                syncHealth.reload();
                syncRuns.reload();
              }}
            />
          </div>
        }
      />
      <div className="split">
        <div className="grid">
          <Panel title="Integrations">
            {notice ? <Notice kind="success">{notice}</Notice> : null}
            {error ?? integrations.error ? (
              <Notice kind="error">{error ?? integrations.error}</Notice>
            ) : null}
            <Table
              headers={["Name", "Provider", "Status", "Last Sync", "Actions"]}
            >
              {integrations.data.map((integration) => (
                <tr key={integration.id}>
                  <td>
                    <strong>{integration.name}</strong>
                    <div className="muted">
                      Credentials {integration.has_active_credentials ? "set" : "empty"}
                    </div>
                  </td>
                  <td>{titleCase(integration.provider)}</td>
                  <td>
                    <StatusPill value={integration.status} />
                  </td>
                  <td>{shortDateTime(integration.last_attempted_sync_at)}</td>
                  <td>
                    <div className="actions">
                      <IconButton
                        icon={Activity}
                        label="Test"
                        onClick={() => integrationAction(integration, "test")}
                      />
                      <IconButton
                        icon={RefreshCw}
                        label="Sync"
                        onClick={() => integrationAction(integration, "sync")}
                      />
                      <IconButton
                        icon={Play}
                        label="Activate"
                        onClick={() => integrationAction(integration, "activate")}
                      />
                      <IconButton
                        icon={Pause}
                        label="Disable"
                        onClick={() => integrationAction(integration, "disable")}
                      />
                    </div>
                  </td>
                </tr>
              ))}
            </Table>
          </Panel>
          <Panel title="Sync Runs">
            <Table headers={["Type", "Status", "Started", "Stats", "Error"]}>
              {syncRuns.data.items.map((run) => (
                <tr key={run.id}>
                  <td>{titleCase(run.sync_type)}</td>
                  <td>
                    <StatusPill value={run.status} />
                  </td>
                  <td>{shortDateTime(run.started_at ?? run.enqueued_at)}</td>
                  <td className="mono">{asJson(run.stats_json)}</td>
                  <td>{run.error_summary ?? "-"}</td>
                </tr>
              ))}
            </Table>
          </Panel>
          <Panel title="Sync Health">
            {syncHealth.data ? (
              <div className="grid three">
                <Stat
                  label="Successful"
                  value={syncHealth.data.summary.successful_runs}
                />
                <Stat label="Failed" value={syncHealth.data.summary.failed_runs} />
                <Stat
                  label="Partial"
                  value={syncHealth.data.summary.partially_failed_runs}
                />
              </div>
            ) : (
              <Empty>No sync health data.</Empty>
            )}
          </Panel>
        </div>
        <Panel title="New Integration">
          <form className="form-grid" onSubmit={createIntegration}>
            <Field label="Provider">
              <select
                className="select"
                value={form.provider}
                onChange={(event) =>
                  setForm({ ...form, provider: event.target.value })
                }
              >
                <option value="fake">Fake</option>
                <option value="moysklad">MoySklad</option>
                <option value="csv">CSV</option>
                <option value="manual">Manual</option>
              </select>
            </Field>
            <Field label="Name">
              <input
                className="input"
                value={form.name}
                onChange={(event) =>
                  setForm({ ...form, name: event.target.value })
                }
                required
              />
            </Field>
            <Field label="Settings JSON">
              <textarea
                className="textarea"
                value={form.settings_json}
                onChange={(event) =>
                  setForm({ ...form, settings_json: event.target.value })
                }
              />
            </Field>
            <Field label="Credentials JSON">
              <textarea
                className="textarea"
                value={form.credentials_json}
                onChange={(event) =>
                  setForm({ ...form, credentials_json: event.target.value })
                }
              />
            </Field>
            <Button icon={Plus}>Create integration</Button>
          </form>
        </Panel>
      </div>
    </>
  );
}

function RewardClaimsScreen() {
  const campaigns = useResource(
    () => apiRequest<Paginated<Campaign>>("/campaigns?limit=100"),
    [],
    emptyPage<Campaign>(),
  );
  const customers = useResource(
    () => apiRequest<Paginated<Customer>>("/customers?limit=100"),
    [],
    emptyPage<Customer>(),
  );
  const [campaignId, setCampaignId] = useState("");
  const [status, setStatus] = useState("");
  const [customerId, setCustomerId] = useState("");
  const [tierId, setTierId] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!campaignId && campaigns.data.items[0]) {
      setCampaignId(campaigns.data.items[0].id);
    }
  }, [campaignId, campaigns.data.items]);

  const tiers = useResource(
    async () => {
      if (!campaignId) {
        return [] as GiftTier[];
      }
      return apiRequest<GiftTier[]>(`/campaigns/${campaignId}/gift-tiers`);
    },
    [campaignId],
    [] as GiftTier[],
  );
  const claims = useResource(
    () =>
      apiRequest<Paginated<RewardClaim>>(
        `/reward-claims${query({
          limit: 100,
          campaign_id: campaignId,
          status,
        })}`,
      ),
    [campaignId, status],
    emptyPage<RewardClaim>(),
  );

  async function createClaim(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setNotice(null);
    try {
      await apiRequest<RewardClaim>("/reward-claims", {
        method: "POST",
        body: JSON.stringify({
          campaign_id: campaignId,
          customer_id: customerId,
          gift_tier_id: tierId,
        }),
      });
      setNotice("Reward claim created.");
      claims.reload();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  async function claimAction(claim: RewardClaim, action: string) {
    setError(null);
    setNotice(null);
    try {
      await apiRequest<RewardClaim>(`/reward-claims/${claim.id}/${action}`, {
        method: "POST",
        body: JSON.stringify({}),
      });
      setNotice(`Claim ${action} complete.`);
      claims.reload();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <>
      <PageHeader
        title="Reward Claims"
        subtitle="Claim queues, approvals, fulfillment, and cancellations"
        actions={
          <div className="actions">
            <CampaignPicker
              campaigns={campaigns.data.items}
              value={campaignId}
              onChange={setCampaignId}
            />
            <select
              className="select"
              value={status}
              onChange={(event) => setStatus(event.target.value)}
            >
              <option value="">All statuses</option>
              <option value="pending">Pending</option>
              <option value="approved">Approved</option>
              <option value="rejected">Rejected</option>
              <option value="fulfilled">Fulfilled</option>
              <option value="cancelled">Cancelled</option>
            </select>
            <IconButton icon={RefreshCw} label="Refresh" onClick={claims.reload} />
          </div>
        }
      />
      <div className="split">
        <Panel title="Claims">
          {notice ? <Notice kind="success">{notice}</Notice> : null}
          {error ?? claims.error ? (
            <Notice kind="error">{error ?? claims.error}</Notice>
          ) : null}
          <Table
            headers={["Customer", "Campaign", "Gift", "Status", "Dates", "Actions"]}
          >
            {claims.data.items.map((claim) => (
              <tr key={claim.id}>
                <td>{claim.customer_name ?? claim.customer_id.slice(0, 8)}</td>
                <td>{claim.campaign_title ?? claim.campaign_id.slice(0, 8)}</td>
                <td>{claim.gift_tier_title ?? claim.gift_tier_id.slice(0, 8)}</td>
                <td>
                  <StatusPill value={claim.status} />
                </td>
                <td>
                  <div>{shortDateTime(claim.created_at)}</div>
                  <div className="muted">
                    Fulfilled {shortDateTime(claim.fulfilled_at)}
                  </div>
                </td>
                <td>
                  <div className="actions">
                    <IconButton
                      icon={Check}
                      label="Approve"
                      onClick={() => claimAction(claim, "approve")}
                    />
                    <IconButton
                      icon={X}
                      label="Reject"
                      onClick={() => claimAction(claim, "reject")}
                    />
                    <IconButton
                      icon={Gift}
                      label="Fulfill"
                      onClick={() => claimAction(claim, "fulfill")}
                    />
                    <IconButton
                      icon={Archive}
                      label="Cancel"
                      onClick={() => claimAction(claim, "cancel")}
                    />
                  </div>
                </td>
              </tr>
            ))}
          </Table>
        </Panel>
        <Panel title="New Claim">
          <form className="form-grid" onSubmit={createClaim}>
            <Field label="Customer">
              <select
                className="select"
                value={customerId}
                onChange={(event) => setCustomerId(event.target.value)}
                required
              >
                <option value="">Select customer</option>
                {customers.data.items.map((customer) => (
                  <option key={customer.id} value={customer.id}>
                    {customer.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Gift tier">
              <select
                className="select"
                value={tierId}
                onChange={(event) => setTierId(event.target.value)}
                required
              >
                <option value="">Select gift tier</option>
                {tiers.data.map((tier) => (
                  <option key={tier.id} value={tier.id}>
                    {tier.title} - {money(tier.required_amount_minor, tier.currency)}
                  </option>
                ))}
              </select>
            </Field>
            <Button icon={Plus}>Create claim</Button>
          </form>
        </Panel>
      </div>
    </>
  );
}

type ReportsTab =
  | "overview"
  | "top"
  | "close"
  | "liability"
  | "claims"
  | "sync"
  | "sales";

function ReportsScreen() {
  const campaigns = useResource(
    () => apiRequest<Paginated<Campaign>>("/campaigns?limit=100"),
    [],
    emptyPage<Campaign>(),
  );
  const [campaignId, setCampaignId] = useState("");
  const [tab, setTab] = useState<ReportsTab>("overview");

  useEffect(() => {
    if (!campaignId && campaigns.data.items[0]) {
      setCampaignId(campaigns.data.items[0].id);
    }
  }, [campaignId, campaigns.data.items]);

  const reports = useResource(
    async () => {
      const [sync, claims, sales] = await Promise.all([
        apiRequest<SyncHealthReport>("/reports/sync-health?limit=10"),
        apiRequest<RewardClaimsReport>(
          `/reports/reward-claims${query({ limit: 10, campaign_id: campaignId })}`,
        ),
        apiRequest<SalesManagerReportItem[]>(
          `/reports/sales-managers${query({ campaign_id: campaignId })}`,
        ),
      ]);
      if (!campaignId) {
        return {
          overview: null as CampaignOverview | null,
          top: [] as TopCustomerReportItem[],
          close: [] as CloseToNextReportItem[],
          liability: null as GiftLiabilityReport | null,
          sync,
          claims,
          sales,
        };
      }
      const [overview, top, close, liability] = await Promise.all([
        apiRequest<CampaignOverview>(
          `/reports/campaigns/${campaignId}/overview`,
        ),
        apiRequest<TopCustomerReportItem[]>(
          `/reports/campaigns/${campaignId}/top-customers?limit=20`,
        ),
        apiRequest<CloseToNextReportItem[]>(
          `/reports/campaigns/${campaignId}/close-to-next-tier?limit=20`,
        ),
        apiRequest<GiftLiabilityReport>(
          `/reports/campaigns/${campaignId}/gift-liability`,
        ),
      ]);
      return { overview, top, close, liability, sync, claims, sales };
    },
    [campaignId],
    {
      overview: null as CampaignOverview | null,
      top: [] as TopCustomerReportItem[],
      close: [] as CloseToNextReportItem[],
      liability: null as GiftLiabilityReport | null,
      sync: null as SyncHealthReport | null,
      claims: null as RewardClaimsReport | null,
      sales: [] as SalesManagerReportItem[],
    },
  );

  const tabs: Array<{ key: ReportsTab; label: string }> = [
    { key: "overview", label: "Overview" },
    { key: "top", label: "Top Customers" },
    { key: "close", label: "Close to Tier" },
    { key: "liability", label: "Gift Liability" },
    { key: "claims", label: "Claims" },
    { key: "sync", label: "Sync Health" },
    { key: "sales", label: "Sales Managers" },
  ];

  return (
    <>
      <PageHeader
        title="Reports"
        subtitle="Campaign, claims, sync, and sales manager reporting"
        actions={
          <div className="actions">
            <CampaignPicker
              campaigns={campaigns.data.items}
              value={campaignId}
              onChange={setCampaignId}
            />
            <IconButton icon={RefreshCw} label="Refresh" onClick={reports.reload} />
          </div>
        }
      />
      {reports.error ? <Notice kind="error">{reports.error}</Notice> : null}
      {reports.loading ? <Loading /> : null}
      <section className="panel">
        <div className="tabs">
          {tabs.map((item) => (
            <button
              key={item.key}
              className={`tab ${tab === item.key ? "active" : ""}`}
              onClick={() => setTab(item.key)}
            >
              {item.label}
            </button>
          ))}
        </div>
        <div className="panel-body">{renderReportTab(tab, reports.data)}</div>
      </section>
    </>
  );
}

function renderReportTab(
  tab: ReportsTab,
  data: {
    overview: CampaignOverview | null;
    top: TopCustomerReportItem[];
    close: CloseToNextReportItem[];
    liability: GiftLiabilityReport | null;
    sync: SyncHealthReport | null;
    claims: RewardClaimsReport | null;
    sales: SalesManagerReportItem[];
  },
) {
  if (tab === "overview") {
    if (!data.overview) {
      return <Empty>Select a campaign.</Empty>;
    }
    return (
      <div className="grid">
        <div className="grid four">
          <Stat
            label="Customers"
            value={data.overview.total_customers_with_progress}
          />
          <Stat
            label="Purchase amount"
            value={money(
              data.overview.total_purchase_amount_minor,
              data.overview.currency,
            )}
          />
          <Stat
            label="Reached any tier"
            value={data.overview.customers_reached_any_tier}
          />
          <Stat
            label="Active claims"
            value={data.overview.total_active_claims}
          />
        </div>
        <Table headers={["Tier", "Required", "Current customers", "Claims"]}>
          {data.overview.gift_tier_breakdown.map((tier) => (
            <tr key={tier.tier_id}>
              <td>{tier.tier_title}</td>
              <td>{money(tier.required_amount_minor, data.overview!.currency)}</td>
              <td>{tier.customers_currently_at_tier}</td>
              <td>
                {tier.claims_count}
                <div className="muted">{tier.fulfilled_count} fulfilled</div>
              </td>
            </tr>
          ))}
        </Table>
      </div>
    );
  }

  if (tab === "top") {
    return (
      <Table headers={["Customer", "Amount", "Current", "Next", "Progress", "Claim"]}>
        {data.top.map((item) => (
          <tr key={item.customer_id}>
            <td>{item.customer_name}</td>
            <td>{money(item.total_amount_minor)}</td>
            <td>{item.current_tier_title ?? "-"}</td>
            <td>{item.next_tier_title ?? "-"}</td>
            <td>{item.progress_percent}%</td>
            <td>{item.claim_status ? <StatusPill value={item.claim_status} /> : "-"}</td>
          </tr>
        ))}
      </Table>
    );
  }

  if (tab === "close") {
    return (
      <Table headers={["Customer", "Contact", "Amount", "Next", "Left", "Progress"]}>
        {data.close.map((item) => (
          <tr key={item.customer_id}>
            <td>{item.customer_name}</td>
            <td>
              <div>{item.phone ?? "-"}</div>
              <div className="muted">{item.email ?? "-"}</div>
            </td>
            <td>{money(item.total_amount_minor)}</td>
            <td>{item.next_tier_title}</td>
            <td>{money(item.amount_left_minor)}</td>
            <td>{item.progress_percent}%</td>
          </tr>
        ))}
      </Table>
    );
  }

  if (tab === "liability") {
    if (!data.liability) {
      return <Empty>Select a campaign.</Empty>;
    }
    return (
      <div className="grid">
        <div className="grid four">
          <Stat
            label="Qualified"
            value={data.liability.total_qualified_customers}
          />
          <Stat label="Claims" value={data.liability.total_claims} />
          <Stat label="Pending" value={data.liability.total_pending_claims} />
          <Stat label="Fulfilled" value={data.liability.total_fulfilled_claims} />
        </div>
        <Table
          headers={[
            "Tier",
            "Qualified",
            "Current",
            "Claims",
            "Stock",
            "Available",
          ]}
        >
          {data.liability.tiers.map((tier) => (
            <tr key={tier.tier_id}>
              <td>{tier.tier_title}</td>
              <td>{tier.customers_qualified_for_tier}</td>
              <td>{tier.customers_currently_at_tier}</td>
              <td>
                {tier.pending_claims} pending
                <div className="muted">
                  {tier.approved_claims} approved, {tier.fulfilled_claims} fulfilled
                </div>
              </td>
              <td>{tier.stock_quantity ?? "-"}</td>
              <td>{tier.available_quantity ?? "-"}</td>
            </tr>
          ))}
        </Table>
      </div>
    );
  }

  if (tab === "claims") {
    if (!data.claims) {
      return <Empty>No claim report.</Empty>;
    }
    return (
      <div className="grid">
        <div className="grid four">
          <Stat label="Total" value={data.claims.summary.total} />
          <Stat label="Pending" value={data.claims.summary.pending} />
          <Stat label="Approved" value={data.claims.summary.approved} />
          <Stat label="Fulfilled" value={data.claims.summary.fulfilled} />
        </div>
        <Table headers={["Customer", "Campaign", "Gift", "Status", "Created"]}>
          {data.claims.items.map((claim) => (
            <tr key={claim.claim_id}>
              <td>{claim.customer_name}</td>
              <td>{claim.campaign_title}</td>
              <td>{claim.gift_tier_title}</td>
              <td>
                <StatusPill value={claim.status} />
              </td>
              <td>{shortDateTime(claim.created_at)}</td>
            </tr>
          ))}
        </Table>
      </div>
    );
  }

  if (tab === "sync") {
    if (!data.sync) {
      return <Empty>No sync health report.</Empty>;
    }
    return (
      <div className="grid">
        <div className="grid four">
          <Stat
            label="Integrations"
            value={data.sync.summary.total_integrations}
          />
          <Stat label="Active" value={data.sync.summary.active_integrations} />
          <Stat label="Failed" value={data.sync.summary.failed_runs} />
          <Stat label="Success" value={data.sync.summary.successful_runs} />
        </div>
        <Table headers={["Integration", "Status", "Recent", "Last error"]}>
          {data.sync.integrations.map((integration) => (
            <tr key={integration.integration_id}>
              <td>
                <strong>{integration.name}</strong>
                <div className="muted">{integration.provider}</div>
              </td>
              <td>
                <StatusPill value={integration.status} />
              </td>
              <td>
                {integration.recent_success_count} success
                <div className="muted">
                  {integration.recent_failed_count} failed,{" "}
                  {integration.recent_partially_failed_count} partial
                </div>
              </td>
              <td>{integration.last_error_summary ?? "-"}</td>
            </tr>
          ))}
        </Table>
      </div>
    );
  }

  return (
    <Table
      headers={[
        "Manager",
        "Assigned",
        "Purchase amount",
        "Reached",
        "Close",
        "Fulfilled",
      ]}
    >
      {data.sales.map((manager) => (
        <tr key={manager.user_id}>
          <td>
            <strong>{manager.full_name}</strong>
            <div className="muted">{manager.email}</div>
          </td>
          <td>{manager.assigned_customer_count}</td>
          <td>{money(manager.total_purchase_amount_minor)}</td>
          <td>{manager.customers_reached_any_tier}</td>
          <td>{manager.customers_close_to_next_tier_count}</td>
          <td>{manager.fulfilled_claims_count}</td>
        </tr>
      ))}
    </Table>
  );
}

function OpsScreen() {
  const ops = useResource(
    () => apiRequest<OpsStatusResponse>("/ops/status"),
    [],
    null as OpsStatusResponse | null,
  );

  const [recoveringSyncs, setRecoveringSyncs] = useState(false);
  const [recoveringNotifs, setRecoveringNotifs] = useState(false);
  const [recoveryResult, setRecoveryResult] = useState<string | null>(null);

  async function recoverSyncs() {
    setRecoveringSyncs(true);
    setRecoveryResult(null);
    try {
      const result = await apiRequest<RecoverStuckSyncsResponse>(
        "/ops/recover-stuck-syncs",
        { method: "POST" },
      );
      setRecoveryResult(
        `Recovered ${result.recovered_queued_count} queued and ${result.recovered_running_count} running syncs.`,
      );
      ops.reload();
    } catch (err) {
      setRecoveryResult(errorMessage(err));
    } finally {
      setRecoveringSyncs(false);
    }
  }

  async function recoverNotifs() {
    setRecoveringNotifs(true);
    setRecoveryResult(null);
    try {
      const result = await apiRequest<RecoverNotificationsResponse>(
        "/ops/recover-notifications",
        { method: "POST" },
      );
      setRecoveryResult(`Recovered ${result.failed_count} notifications.`);
      ops.reload();
    } catch (err) {
      setRecoveryResult(errorMessage(err));
    } finally {
      setRecoveringNotifs(false);
    }
  }

  if (!ops.data && ops.loading) return <Loading />;
  if (ops.error) return <Notice kind="error">{ops.error}</Notice>;

  const data = ops.data!;

  return (
    <>
      <PageHeader
        title="Operations"
        subtitle="System health and maintenance"
        actions={
          <IconButton icon={RefreshCw} label="Refresh" onClick={ops.reload} />
        }
      />
      {recoveryResult ? <Notice kind="success">{recoveryResult}</Notice> : null}

      <div className="grid two">
        <Panel title="Sync Status">
          <div className="grid two" style={{ marginBottom: 16 }}>
            <Stat label="Queued" value={data.queued_sync_count} />
            <Stat label="Running" value={data.running_sync_count} />
          </div>
          {data.stuck_queued_sync_count > 0 || data.stuck_running_sync_count > 0 ? (
            <Notice kind="error">
              Detected {data.stuck_queued_sync_count} stuck queued and{" "}
              {data.stuck_running_sync_count} stuck running syncs.
            </Notice>
          ) : (
            <Notice kind="success">No stuck syncs detected.</Notice>
          )}
          <div style={{ marginTop: 16 }}>
            <Button
              icon={RefreshCw}
              onClick={recoverSyncs}
              disabled={recoveringSyncs}
            >
              {recoveringSyncs ? "Recovering..." : "Recover Stuck Syncs"}
            </Button>
          </div>
        </Panel>

        <Panel title="Notifications & Events">
          <div className="grid two" style={{ marginBottom: 16 }}>
            <Stat
              label="Pending Notifs"
              value={data.pending_notification_events_count}
            />
            <Stat
              label="Failed Notifs"
              value={data.failed_notification_events_count}
            />
            <Stat
              label="Pending Events"
              value={data.pending_domain_events_count}
            />
            <Stat
              label="Failed Events"
              value={data.failed_domain_events_count}
            />
          </div>
          <div style={{ marginTop: 16 }}>
            <Button
              icon={RefreshCw}
              onClick={recoverNotifs}
              disabled={recoveringNotifs}
            >
              {recoveringNotifs ? "Recovering..." : "Recover Notifications"}
            </Button>
          </div>
        </Panel>
      </div>

      <div className="grid two" style={{ marginTop: 24 }}>
        <Panel title="Integrations Health">
          <div className="grid two">
            <Stat label="Active" value={data.active_integrations_count} />
            <Stat label="Scheduled" value={data.scheduled_integrations_count} />
          </div>
          <div className="muted" style={{ marginTop: 16 }}>
            Last successful sync:{" "}
            {shortDateTime(data.last_successful_sync_time) || "Never"}
            <br />
            Last failed sync: {shortDateTime(data.last_failed_sync_time) || "None"}
          </div>
        </Panel>
        <Panel title="Recent Errors">
          <Stat
            label="Errors (24h)"
            value={data.recent_failed_sync_errors_count}
          />
          <div className="muted" style={{ marginTop: 16 }}>
            Go to Reports &gt; Sync Health for more details.
          </div>
        </Panel>
      </div>
    </>
  );
}

function currentRoute(): RouteKey {
  const value = window.location.hash.replace("#", "") as RouteKey;
  return routeMeta.some((route) => route.key === value) ? value : "dashboard";
}

function AdminApp() {
  const [route, setRouteState] = useState<RouteKey>(currentRoute);
  const [session, setSession] = useState<MeResponse | null>(null);
  const [checkingSession, setCheckingSession] = useState(true);
  const [langKey, setLangKey] = useState(0); // Force re-render on language change

  useEffect(() => {
    loadLanguage();
    setLangKey((k) => k + 1);
  }, []);

  useEffect(() => {
    const onHash = () => setRouteState(currentRoute());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  useEffect(() => {
    if (!getStoredAccessToken()) {
      setCheckingSession(false);
      return;
    }
    me()
      .then(setSession)
      .catch(() => {
        clearTokens();
        setSession(null);
      })
      .finally(() => setCheckingSession(false));
  }, []);

  function setRoute(nextRoute: RouteKey) {
    window.location.hash = nextRoute;
    setRouteState(nextRoute);
  }

  async function handleLogout() {
    await logout();
    setSession(null);
  }

  const screen = useMemo(() => {
    if (route === "campaigns") {
      return <CampaignsScreen />;
    }
    if (route === "gift-tiers") {
      return <GiftTiersScreen />;
    }
    if (route === "customers") {
      return <CustomersProgressScreen />;
    }
    if (route === "imports") {
      return <ImportsScreen />;
    }
    if (route === "integrations") {
      return <IntegrationsSyncScreen />;
    }
    if (route === "claims") {
      return <RewardClaimsScreen />;
    }
    if (route === "reports") {
      return <ReportsScreen />;
    }
    if (route === "ops") {
      return <OpsScreen />;
    }
    return <DashboardScreen />;
  }, [route]);

  if (checkingSession) {
    return (
      <div className="login-shell">
        <section className="login-panel">
          <div className="brand">
            <span className="brand-mark">
              <ShieldCheck size={20} />
            </span>
            OneLoyal
          </div>
          <div style={{ height: 24 }} />
          <Loading />
        </section>
      </div>
    );
  }

  if (!session) {
    return <LoginScreen onLogin={setSession} />;
  }

  return (
    <Shell
      session={session}
      route={route}
      setRoute={setRoute}
      onLogout={handleLogout}
    >
      {screen}
    </Shell>
  );
}

export default function App() {
  if (window.location.pathname.startsWith("/portal")) {
    return <PortalApp />;
  }
  return <AdminApp />;
}
