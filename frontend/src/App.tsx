import {
  ArrowLeft,
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
  platformLogin,
  logout,
  me,
  query,
} from "./api";
import { t, loadLanguage, setLanguage, getLanguage, type Language } from "./i18n";
import type {
  Company,
  Campaign,
  CampaignOverview,
  CompanyProvisionResponse,
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
  PlatformBillingResponse,
  PlatformOverviewResponse,
  User,
} from "./types";
import {
  asJson,
  money,
  parseJsonObject,
  shortDate,
  shortDateTime,
  titleCase,
} from "./utils";
import PortalApp from "./PortalApp";

// TENANT BUSINESS ROUTES (company-admin dashboard)
type TenantRouteKey =
  | "dashboard"
  | "campaigns"
  | "gift-tiers"
  | "customers"
  | "imports"
  | "integrations"
  | "claims"
  | "reports"
  | "ops";

// PLATFORM ROUTES (platform-admin system control)
type PlatformRouteKey = "admin" | "companies" | "billing" | "ops" | "settings";

type AppMode =
  | { kind: "platform-admin" }
  | { kind: "company-admin"; companySlug: string | null }
  | { kind: "portal"; companySlug: string | null };

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

const supportedLocales: Language[] = ["en", "uz", "ru"];

function emptyTranslationMap(baseValue = ""): Record<Language, string> {
  return {
    en: baseValue,
    uz: "",
    ru: "",
  };
}

function normalizeTranslationMap(
  translations: Record<string, string> | null | undefined,
  fallback = "",
): Record<Language, string> {
  return {
    en: translations?.en?.trim() || fallback,
    uz: translations?.uz?.trim() || "",
    ru: translations?.ru?.trim() || "",
  };
}

function TranslationEditorBlock({
  label,
  value,
  locale,
  onLocaleChange,
  onValueChange,
}: {
  label: string;
  value: Record<Language, string>;
  locale: Language;
  onLocaleChange: (locale: Language) => void;
  onValueChange: (value: Record<Language, string>) => void;
}) {
  return (
    <div className="field">
      <label>{label}</label>
      <div className="form-grid two" style={{ gap: 12 }}>
        <select
          className="select"
          value={locale}
          onChange={(event) => onLocaleChange(event.target.value as Language)}
        >
          <option value="en">English</option>
          <option value="uz">Oʻzbekcha</option>
          <option value="ru">Русский</option>
        </select>
        <input
          className="input"
          value={value[locale] ?? ""}
          onChange={(event) =>
            onValueChange({ ...value, [locale]: event.target.value })
          }
          placeholder={`${label} (${locale})`}
        />
      </div>
    </div>
  );
}

// TENANT BUSINESS MODULES - ONLY for company admins
const tenantRouteMeta: Array<{
  key: TenantRouteKey;
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

// PLATFORM SYSTEM ROUTES - ONLY for platform admin
const platformRouteMeta: Array<{
  key: PlatformRouteKey;
  labelKey: string;
  icon: LucideIcon;
}> = [
  { key: "admin", labelKey: "platform.nav.admin", icon: LayoutDashboard },
  { key: "companies", labelKey: "platform.nav.companies", icon: Users },
  { key: "billing", labelKey: "platform.nav.billing", icon: BarChart3 },
  { key: "ops", labelKey: "platform.nav.ops", icon: Activity },
  { key: "settings", labelKey: "platform.nav.settings", icon: Archive },
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

function companyAdminPath(companySlug: string | null, route: TenantRouteKey): string {
  const basePath = companySlug ? `/${companySlug}` : "";
  if (route === "dashboard") {
    return `${basePath}/admin`;
  }
  if (route === "ops") {
    return `${basePath}/operations`;
  }
  return `${basePath}/${route}`;
}

function parseCompanyRoute(pathname: string): TenantRouteKey {
  const segments = pathname.split("/").filter(Boolean);
  const lastSegment = segments[segments.length - 1];
  if (lastSegment === "campaigns") return "campaigns";
  if (lastSegment === "gift-tiers") return "gift-tiers";
  if (lastSegment === "customers") return "customers";
  if (lastSegment === "imports") return "imports";
  if (lastSegment === "integrations") return "integrations";
  if (lastSegment === "claims") return "claims";
  if (lastSegment === "reports") return "reports";
  if (lastSegment === "operations") return "ops";
  return "dashboard";
}

function LoginScreen({
  onLogin,
  title = "Admin Console",
  subtitle = "Sign in to manage loyalty operations.",
  buttonLabel = "Sign in",
  expectedRole,
  roleMismatchMessage = "You do not have access to this panel.",
  externalError,
  companySlug,
  loginMode = "tenant",
}: {
  onLogin: (session: MeResponse) => void;
  title?: string;
  subtitle?: string;
  buttonLabel?: string;
  expectedRole?: string;
  roleMismatchMessage?: string;
  externalError?: string | null;
  companySlug?: string | null;
  loginMode?: "tenant" | "platform";
}) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const metricTiles =
    loginMode === "platform"
      ? [
          { label: "Companies", value: "SaaS" },
          { label: "Plans", value: "Ops" },
          { label: "Queues", value: "Health" },
          { label: "Support", value: "Control" },
        ]
      : [
          { label: "Campaigns", value: "Loyalty" },
          { label: "Gift stock", value: "Rewards" },
          { label: "Customers", value: "Progress" },
          { label: "Reports", value: "Insights" },
        ];

  async function submit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const auth =
        loginMode === "platform"
          ? await platformLogin(email, password)
          : await login(email, password, companySlug ?? undefined);
      if (expectedRole && auth.user.role !== expectedRole) {
        clearTokens();
        setError(roleMismatchMessage);
        return;
      }
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
        <h1>{title}</h1>
        <p>{subtitle}</p>
        <div style={{ height: 24 }} />
        <form className="form-grid" onSubmit={submit}>
          {externalError ? <Notice kind="error">{externalError}</Notice> : null}
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
            {loading ? "Signing in" : buttonLabel}
          </Button>
        </form>
      </section>
      <section className="login-art">
        <div className="metric-wall">
          {metricTiles.map((tile) => (
            <div key={tile.label} className="metric-tile">
              <span>{tile.label}</span>
              <strong>{tile.value}</strong>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}

function LanguageSelector() {
  return (
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
  );
}

function PlatformLayout({
  session,
  route,
  setRoute,
  onLogout,
  children,
}: {
  session: MeResponse;
  route: PlatformRouteKey;
  setRoute: (route: PlatformRouteKey) => void;
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
        <div className="muted" style={{ padding: "0 20px 16px" }}>
          SaaS control center
        </div>
        <nav className="nav">
          {platformRouteMeta.map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.key}
                className={`nav-button ${route === item.key ? "active" : ""}`}
                onClick={() => setRoute(item.key)}
              >
                <Icon size={18} />
                {t(item.labelKey)}
              </button>
            );
          })}
        </nav>
        <div className="sidebar-footer">
          <div className="user-block">
            <strong>{session.user.full_name}</strong>
            <span>{session.user.email}</span>
            <span>Platform admin</span>
          </div>
          <LanguageSelector />
          <Button icon={LogOut} variant="secondary" onClick={onLogout}>
            {t("auth.logout")}
          </Button>
        </div>
      </aside>
      <main className="main">{children}</main>
    </div>
  );
}

function TenantLayout({
  session,
  route,
  setRoute,
  onLogout,
  children,
}: {
  session: MeResponse;
  route: TenantRouteKey;
  setRoute: (route: TenantRouteKey) => void;
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
        <div className="muted" style={{ padding: "0 20px 16px" }}>
          Company loyalty workspace
        </div>
        <nav className="nav">
          {tenantRouteMeta.map((item) => {
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
          <LanguageSelector />
          <Button icon={LogOut} variant="secondary" onClick={onLogout}>
            {t("auth.logout")}
          </Button>
        </div>
      </aside>
      <main className="main">{children}</main>
    </div>
  );
}

function currentPlatformRoute(): PlatformRouteKey {
  const { pathname } = window.location;
  const lastSegment = pathname.split("/").filter(Boolean).pop();
  if (lastSegment === "billing") return "billing";
  if (lastSegment === "companies") return "companies";
  if (lastSegment === "ops") return "ops";
  if (lastSegment === "settings") return "settings";
  return "admin";
}

function platformPath(route: PlatformRouteKey): string {
  if (route === "admin") return "/platform/admin";
  if (route === "companies") return "/platform/companies";
  if (route === "billing") return "/platform/billing";
  if (route === "ops") return "/platform/ops";
  if (route === "settings") return "/platform/settings";
  return "/platform/admin";
}

function PlatformAdminApp() {
  const [route, setRouteState] = useState<PlatformRouteKey>(currentPlatformRoute);
  const [session, setSession] = useState<MeResponse | null>(null);
  const [checkingSession, setCheckingSession] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadLanguage();
    if (window.location.pathname === "/admin") {
      window.history.replaceState(null, "", "/platform/admin");
      setRouteState("admin");
    }
  }, []);

  useEffect(() => {
    const onNavigation = () => setRouteState(currentPlatformRoute());
    window.addEventListener("popstate", onNavigation);
    return () => window.removeEventListener("popstate", onNavigation);
  }, []);

  useEffect(() => {
    if (!getStoredAccessToken()) {
      setCheckingSession(false);
      return;
    }
    me()
      .then((current) => {
        if (current.role !== "platform_admin") {
          clearTokens();
          setSession(null);
          setError("Platform admin access is required.");
          return;
        }
        setSession(current);
      })
      .catch(() => {
        clearTokens();
        setSession(null);
      })
      .finally(() => setCheckingSession(false));
  }, []);

  function setRoute(nextRoute: PlatformRouteKey) {
    window.history.pushState(null, "", platformPath(nextRoute));
    setRouteState(nextRoute);
  }

  async function handleLogin(nextSession: MeResponse) {
    setError(null);
    setSession(nextSession);
    setRouteState("admin");
    window.history.replaceState(null, "", "/platform/admin");
  }

  async function handleLogout() {
    await logout();
    setSession(null);
    setRouteState("admin");
    window.history.replaceState(null, "", "/platform/admin");
  }

  const screen = useMemo(() => {
    if (route === "admin") return <PlatformOverviewScreen />;
    if (route === "companies") return <PlatformCompaniesScreen />;
    if (route === "billing") return <PlatformBillingScreen />;
    if (route === "ops") return <PlatformOpsScreen />;
    if (route === "settings") return <PlatformSettingsScreen />;
    return <PlatformOverviewScreen />;
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
    return (
      <LoginScreen
        onLogin={handleLogin}
        title={t("platform.title")}
        subtitle={t("platform.subtitle")}
        buttonLabel={t("auth.login_button")}
        expectedRole="platform_admin"
        roleMismatchMessage="Platform admin access is required."
        externalError={error}
        loginMode="platform"
      />
    );
  }

  return (
    <PlatformLayout
      session={session}
      route={route}
      setRoute={setRoute}
      onLogout={handleLogout}
    >
      {screen}
    </PlatformLayout>
  );
}

const emptyPlatformOverview = (): PlatformOverviewResponse => ({
  generated_at: "",
  summary: {
    company_count: 0,
    active_tenant_count: 0,
    suspended_tenant_count: 0,
    archived_tenant_count: 0,
    subscription_count: 0,
    active_subscription_count: 0,
    trialing_subscription_count: 0,
    past_due_subscription_count: 0,
    cancelled_subscription_count: 0,
    expired_subscription_count: 0,
  },
  plans: [],
  ops: {
    total_integrations: 0,
    active_integrations: 0,
    queued_sync_runs: 0,
    running_sync_runs: 0,
    failed_sync_runs_24h: 0,
    partially_failed_sync_runs_24h: 0,
    successful_sync_runs_24h: 0,
    failed_sync_errors_24h: 0,
  },
  queues: {
    pending_notifications: 0,
    failed_notifications: 0,
    pending_domain_events: 0,
    failed_domain_events: 0,
  },
  recent_failures: [],
});

const emptyPlatformBilling = (): PlatformBillingResponse => ({
  generated_at: "",
  summary: emptyPlatformOverview().summary,
  plans: [],
  subscriptions: [],
});

function PlatformOverviewScreen() {
  const overview = useResource(
    () => apiRequest<PlatformOverviewResponse>("/platform/overview"),
    [],
    emptyPlatformOverview(),
  );

  return (
    <>
      <PageHeader
        title={t("platform.overview.title")}
        subtitle={t("platform.overview.subtitle")}
        actions={<IconButton icon={RefreshCw} label={t("common.refresh")} onClick={overview.reload} />}
      />
      {overview.loading ? <Loading /> : null}
      {overview.error ? <Notice kind="error">{overview.error}</Notice> : null}
      <div className="grid four">
        <Stat label={t("platform.overview.companies")} value={overview.data.summary.company_count} />
        <Stat label={t("platform.overview.activeTenants")} value={overview.data.summary.active_tenant_count} />
        <Stat
          label={t("platform.overview.subscriptions")}
          value={overview.data.summary.subscription_count}
        />
        <Stat
          label="Failed syncs (24h)"
          value={overview.data.ops.failed_sync_runs_24h}
        />
      </div>
      <div style={{ height: 14 }} />
      <div className="grid two">
        <Panel title="Platform Ops Snapshot">
          <div className="grid two">
            <Stat label="Queued runs" value={overview.data.ops.queued_sync_runs} />
            <Stat label="Running runs" value={overview.data.ops.running_sync_runs} />
            <Stat
              label="Active integrations"
              value={overview.data.ops.active_integrations}
            />
            <Stat
              label="Failed errors (24h)"
              value={overview.data.ops.failed_sync_errors_24h}
            />
          </div>
        </Panel>
        <Panel title="Queue Health">
          <div className="grid two">
            <Stat
              label="Pending notifications"
              value={overview.data.queues.pending_notifications}
            />
            <Stat
              label="Failed notifications"
              value={overview.data.queues.failed_notifications}
            />
            <Stat
              label="Pending domain events"
              value={overview.data.queues.pending_domain_events}
            />
            <Stat
              label="Failed domain events"
              value={overview.data.queues.failed_domain_events}
            />
          </div>
        </Panel>
      </div>
      <div style={{ height: 14 }} />
      <div className="grid two">
        <Panel title="Plan Coverage">
          {overview.data.plans.length ? (
            <Table headers={["Plan", "Companies", "Active", "Trialing", "Past Due"]}>
              {overview.data.plans.map((plan) => (
                <tr key={plan.plan_id}>
                  <td>
                    <strong>{plan.name}</strong>
                    <div className="muted">{plan.code}</div>
                  </td>
                  <td>{plan.company_count}</td>
                  <td>{plan.active_subscription_count}</td>
                  <td>{plan.trialing_subscription_count}</td>
                  <td>{plan.past_due_subscription_count}</td>
                </tr>
              ))}
            </Table>
          ) : (
            <Empty>No plans assigned yet.</Empty>
          )}
        </Panel>
        <Panel title="Recent Failed Jobs">
          {overview.data.recent_failures.length ? (
            <Table headers={["Company", "Integration", "Status", "Finished"]}>
              {overview.data.recent_failures.map((failure) => (
                <tr key={failure.sync_run_id}>
                  <td>
                    <strong>{failure.company_name}</strong>
                    <div className="muted">/{failure.company_slug}</div>
                  </td>
                  <td>{failure.integration_name}</td>
                  <td>
                    <StatusPill value={failure.status} />
                  </td>
                  <td>{shortDateTime(failure.finished_at ?? failure.started_at)}</td>
                </tr>
              ))}
            </Table>
          ) : (
            <Empty>No failed jobs recorded.</Empty>
          )}
        </Panel>
      </div>
    </>
  );
}

function PlatformOpsScreen() {
  const overview = useResource(
    () => apiRequest<PlatformOverviewResponse>("/platform/overview"),
    [],
    emptyPlatformOverview(),
  );

  return (
    <>
      <PageHeader
        title={t("platform.ops.title")}
        subtitle={t("platform.ops.subtitle")}
        actions={<IconButton icon={RefreshCw} label={t("common.refresh")} onClick={overview.reload} />}
      />
      {overview.loading ? <Loading /> : null}
      {overview.error ? <Notice kind="error">{overview.error}</Notice> : null}
      <Panel title="Worker & Sync Health">
        <div className="grid four">
          <Stat label="Queued runs" value={overview.data.ops.queued_sync_runs} />
          <Stat label="Running runs" value={overview.data.ops.running_sync_runs} />
          <Stat
            label="Failed runs (24h)"
            value={overview.data.ops.failed_sync_runs_24h}
          />
          <Stat
            label="Partial runs (24h)"
            value={overview.data.ops.partially_failed_sync_runs_24h}
          />
        </div>
      </Panel>
      <div style={{ height: 14 }} />
      <div className="grid two">
        <Panel title="Platform Metrics">
          <div className="grid two">
            <Stat label="Companies" value={overview.data.summary.company_count} />
            <Stat
              label="Active tenants"
              value={overview.data.summary.active_tenant_count}
            />
            <Stat
              label="Total integrations"
              value={overview.data.ops.total_integrations}
            />
            <Stat
              label="Failed errors (24h)"
              value={overview.data.ops.failed_sync_errors_24h}
            />
          </div>
        </Panel>
        <Panel title="Queue Backlog">
          <div className="grid two">
            <Stat
              label="Pending notifications"
              value={overview.data.queues.pending_notifications}
            />
            <Stat
              label="Failed notifications"
              value={overview.data.queues.failed_notifications}
            />
            <Stat
              label="Pending events"
              value={overview.data.queues.pending_domain_events}
            />
            <Stat
              label="Failed events"
              value={overview.data.queues.failed_domain_events}
            />
          </div>
        </Panel>
      </div>
      <div style={{ height: 14 }} />
      <Panel title="Failed Job Overview">
        {overview.data.recent_failures.length ? (
          <Table headers={["Company", "Integration", "Type", "Error", "Finished"]}>
            {overview.data.recent_failures.map((failure) => (
              <tr key={failure.sync_run_id}>
                <td>{failure.company_name}</td>
                <td>{failure.integration_name}</td>
                <td>{titleCase(failure.sync_type)}</td>
                <td>{failure.error_summary ?? "-"}</td>
                <td>{shortDateTime(failure.finished_at ?? failure.started_at)}</td>
              </tr>
            ))}
          </Table>
        ) : (
          <Empty>No failed jobs recorded.</Empty>
        )}
      </Panel>
    </>
  );
}

function PlatformBillingScreen() {
  const billing = useResource(
    () => apiRequest<PlatformBillingResponse>("/platform/billing"),
    [],
    emptyPlatformBilling(),
  );

  return (
    <>
      <PageHeader
        title={t("platform.billing.title")}
        subtitle={t("platform.billing.subtitle")}
        actions={<IconButton icon={RefreshCw} label={t("common.refresh")} onClick={billing.reload} />}
      />
      {billing.loading ? <Loading /> : null}
      {billing.error ? <Notice kind="error">{billing.error}</Notice> : null}
      <div className="grid four">
        <Stat label={t("platform.overview.subscriptions")} value={billing.data.summary.subscription_count} />
        <Stat
          label={t("platform.overview.activeSubscriptions")}
          value={billing.data.summary.active_subscription_count}
        />
        <Stat
          label={t("platform.overview.trialingSubscriptions")}
          value={billing.data.summary.trialing_subscription_count}
        />
        <Stat label={t("platform.overview.pastDueSubscriptions")} value={billing.data.summary.past_due_subscription_count} />
      </div>
      <div style={{ height: 14 }} />
      <div className="grid two">
        <Panel title="Plans">
          {billing.data.plans.length ? (
            <Table headers={["Plan", "Companies", "Active", "Trialing", "Past Due"]}>
              {billing.data.plans.map((plan) => (
                <tr key={plan.plan_id}>
                  <td>
                    <strong>{plan.name}</strong>
                    <div className="muted">{plan.code}</div>
                  </td>
                  <td>{plan.company_count}</td>
                  <td>{plan.active_subscription_count}</td>
                  <td>{plan.trialing_subscription_count}</td>
                  <td>{plan.past_due_subscription_count}</td>
                </tr>
              ))}
            </Table>
          ) : (
            <Empty>No plans found.</Empty>
          )}
        </Panel>
        <Panel title="Company Subscriptions">
          {billing.data.subscriptions.length ? (
            <Table headers={["Company", "Plan", "Status", "Ends", "Created"]}>
              {billing.data.subscriptions.map((subscription) => (
                <tr key={subscription.subscription_id}>
                  <td>
                    <strong>{subscription.company_name}</strong>
                    <div className="muted">/{subscription.company_slug}</div>
                  </td>
                  <td>{subscription.plan_name}</td>
                  <td>
                    <StatusPill value={subscription.status} />
                  </td>
                  <td>
                    {subscription.current_period_ends_at
                      ? shortDate(subscription.current_period_ends_at)
                      : subscription.trial_ends_at
                        ? shortDate(subscription.trial_ends_at)
                        : "-"}
                  </td>
                  <td>{shortDate(subscription.created_at)}</td>
                </tr>
              ))}
            </Table>
          ) : (
            <Empty>No subscriptions found.</Empty>
          )}
        </Panel>
      </div>
    </>
  );
}

function PlatformSettingsScreen() {
  const now = new Date().toISOString();

  return (
    <>
      <PageHeader
        title={t("platform.settings.title")}
        subtitle={t("platform.settings.subtitle")}
      />
      <div className="grid two">
        <Panel title="Boundary Rules">
          <Table headers={["Area", "Scope"]}>
            <tr>
              <td>Platform admin</td>
              <td>Companies, plans, billing, sync health, queue health, support tooling</td>
            </tr>
            <tr>
              <td>Tenant admin</td>
              <td>Campaigns, gifts, customers, imports, integrations, claims, reports</td>
            </tr>
          </Table>
        </Panel>
        <Panel title="Runtime">
          <div className="grid two">
            <Stat label="Mode" value="Platform" />
            <Stat label="Snapshot" value={shortDateTime(now)} />
          </div>
          <div className="muted" style={{ marginTop: 16 }}>
            Platform pages intentionally exclude tenant business navigation and tenant-only
            data widgets.
          </div>
        </Panel>
      </div>
    </>
  );
}

function PlatformCompaniesScreen() {
  const companies = useResource(() => apiRequest<Company[]>("/companies"), [], []);
  const [form, setForm] = useState({
    company_name: "",
    company_slug: "",
    owner_full_name: "",
    owner_email: "",
    owner_password: "",
  });
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editingCompanyId, setEditingCompanyId] = useState<ID | null>(null);
  const [companyEditLocale, setCompanyEditLocale] = useState<Language>(getLanguage());
  const [companyTranslations, setCompanyTranslations] = useState<Record<Language, string>>(
    emptyTranslationMap(),
  );

  const activeCount = companies.data.filter(
    (company) => company.status === "active",
  ).length;
  const editingCompany = companies.data.find((company) => company.id === editingCompanyId) ?? null;

  function openCompanyTranslations(company: Company) {
    setEditingCompanyId(company.id);
    setCompanyEditLocale(getLanguage());
    setCompanyTranslations(normalizeTranslationMap(company.name_i18n, company.name));
    setError(null);
    setNotice(null);
  }

  function cancelCompanyTranslations() {
    setEditingCompanyId(null);
    setCompanyTranslations(emptyTranslationMap());
  }

  async function saveCompanyTranslations(event: FormEvent) {
    event.preventDefault();
    if (!editingCompanyId) {
      return;
    }
    setError(null);
    setNotice(null);
    try {
      await apiRequest<Company>(`/companies/${editingCompanyId}/translations`, {
        method: "PATCH",
        body: JSON.stringify({ name_i18n: companyTranslations }),
      });
      setNotice("Company translations updated.");
      cancelCompanyTranslations();
      companies.reload();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  async function createCompany(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setNotice(null);
    try {
      const response = await apiRequest<CompanyProvisionResponse>("/companies", {
        method: "POST",
        body: JSON.stringify({
          company_name: form.company_name,
          company_slug: form.company_slug || null,
          owner_full_name: form.owner_full_name || null,
          owner_email: form.owner_email,
          owner_password: form.owner_password,
        }),
      });
      setNotice(
        `${response.company.name} provisioned. Tenant admin login: ${response.login_path}`,
      );
      setForm({
        company_name: "",
        company_slug: "",
        owner_full_name: "",
        owner_email: "",
        owner_password: "",
      });
      companies.reload();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <>
      <PageHeader
        title={t("platform.companies.title")}
        subtitle={t("platform.companies.subtitle")}
        actions={<IconButton icon={RefreshCw} label={t("common.refresh")} onClick={companies.reload} />}
      />
      {error ? <Notice kind="error">{error}</Notice> : null}
      {notice ? <Notice kind="success">{notice}</Notice> : null}
      <div className="grid four">
        <Stat label={t("platform.overview.companies")} value={companies.data.length} />
        <Stat label={t("campaigns.active")} value={activeCount} />
        <Stat label="Disabled" value={companies.data.length - activeCount} />
        <Stat label="Total" value={companies.data.length} />
      </div>
      <div style={{ height: 14 }} />
      <div className="grid two">
        <Panel title="Company Accounts">
          {companies.loading ? <Loading /> : null}
          {companies.error ? <Notice kind="error">{companies.error}</Notice> : null}
          <Table headers={["Name", "Slug", "Status", "Access"]}>
            {companies.data.map((company) => (
              <tr key={company.id}>
                <td>
                  <strong>{company.name}</strong>
                </td>
                <td>{company.slug}</td>
                <td>
                  <StatusPill value={company.status} />
                </td>
                <td>
                  <div className="actions">
                    <IconButton
                      icon={FileText}
                      label={t("common.editTranslations")}
                      onClick={() => openCompanyTranslations(company)}
                    />
                    <IconButton
                      icon={ChevronRight}
                      label="Open tenant login"
                      onClick={() => window.location.assign(`/${company.slug}/login`)}
                    />
                    <IconButton
                      icon={ArrowLeft}
                      label="Open customer portal"
                      onClick={() => window.location.assign(`/${company.slug}/portal`)}
                    />
                  </div>
                </td>
              </tr>
            ))}
          </Table>
        </Panel>
        <Panel title="Create Company">
          <form className="form-grid" onSubmit={createCompany}>
            <Field label="Company Name">
              <input
                className="input"
                value={form.company_name}
                onChange={(event) =>
                  setForm({ ...form, company_name: event.target.value })
                }
                required
              />
            </Field>
            <Field label="Company Slug">
              <input
                className="input"
                value={form.company_slug}
                onChange={(event) =>
                  setForm({ ...form, company_slug: event.target.value.toLowerCase() })
                }
                placeholder="acme-loyalty"
              />
            </Field>
            <Field label="Owner Full Name">
              <input
                className="input"
                value={form.owner_full_name}
                onChange={(event) =>
                  setForm({ ...form, owner_full_name: event.target.value })
                }
              />
            </Field>
            <Field label="Admin Email">
              <input
                className="input"
                type="email"
                value={form.owner_email}
                onChange={(event) =>
                  setForm({ ...form, owner_email: event.target.value })
                }
                required
              />
            </Field>
            <Field label="Admin Password">
              <input
                className="input"
                type="password"
                value={form.owner_password}
                onChange={(event) =>
                  setForm({ ...form, owner_password: event.target.value })
                }
                required
              />
            </Field>
            <Button icon={Plus}>Create company</Button>
          </form>
        </Panel>
      </div>
      {editingCompany ? (
        <>
          <div style={{ height: 14 }} />
          <Panel title={t("company.translations.title")}>
            <form className="form-grid" onSubmit={saveCompanyTranslations}>
              <div className="muted">{t("company.translations.subtitle")}</div>
              <TranslationEditorBlock
                label={t("company.translations.field")}
                value={companyTranslations}
                locale={companyEditLocale}
                onLocaleChange={setCompanyEditLocale}
                onValueChange={setCompanyTranslations}
              />
              <div className="actions">
                <Button icon={Check}>{t("common.saveTranslations")}</Button>
                <Button icon={X} type="button" variant="secondary" onClick={cancelCompanyTranslations}>
                  {t("common.cancel")}
                </Button>
              </div>
            </form>
          </Panel>
        </>
      ) : null}
    </>
  );
}

function UsersScreen() {
  const users = useResource(() => apiRequest<User[]>("/users"), [], []);
  const [form, setForm] = useState({
    email: "",
    full_name: "",
    password: "",
    role: "admin",
  });
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function createUser(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setNotice(null);
    try {
      await apiRequest<User>("/users", {
        method: "POST",
        body: JSON.stringify(form),
      });
      setNotice(`User ${form.email} created.`);
      setForm({ email: "", full_name: "", password: "", role: "admin" });
      users.reload();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <>
      <PageHeader
        title="Users"
        subtitle="Manage company admin and sales accounts."
        actions={<IconButton icon={RefreshCw} label="Refresh" onClick={users.reload} />}
      />
      {error ? <Notice kind="error">{error}</Notice> : null}
      {notice ? <Notice kind="success">{notice}</Notice> : null}
      <Panel title="Create user">
        <form className="form-grid" onSubmit={createUser}>
          <Field label="Email">
            <input
              className="input"
              type="email"
              value={form.email}
              onChange={(event) => setForm({ ...form, email: event.target.value })}
              required
            />
          </Field>
          <Field label="Full name">
            <input
              className="input"
              value={form.full_name}
              onChange={(event) => setForm({ ...form, full_name: event.target.value })}
              required
            />
          </Field>
          <Field label="Password">
            <input
              className="input"
              type="password"
              value={form.password}
              onChange={(event) => setForm({ ...form, password: event.target.value })}
              required
            />
          </Field>
          <Field label="Role">
            <select
              className="select"
              value={form.role}
              onChange={(event) => setForm({ ...form, role: event.target.value })}
            >
              <option value="admin">Admin</option>
              <option value="owner">Owner</option>
              <option value="sales_manager">Sales manager</option>
            </select>
          </Field>
          <Button icon={Plus}>Create user</Button>
        </form>
      </Panel>
      <Panel title="Company users">
        {users.loading ? <Loading /> : null}
        {users.error ? <Notice kind="error">{users.error}</Notice> : null}
        {users.data.length ? (
          <Table headers={["Email", "Name", "Role", "Status"]}>
            {users.data.map((user) => (
              <tr key={user.id}>
                <td>{user.email}</td>
                <td>{user.full_name}</td>
                <td>{titleCase(user.role)}</td>
                <td>{titleCase(user.status)}</td>
              </tr>
            ))}
          </Table>
        ) : (
          <Empty>No company users yet.</Empty>
        )}
      </Panel>
    </>
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
        title={t("nav.dashboard")}
        subtitle={t("dashboard.subtitle")}
        actions={
          <IconButton
            icon={RefreshCw}
            label={t("common.refresh")}
            onClick={dashboard.reload}
          />
        }
      />
      {dashboard.error ? <Notice kind="error">{dashboard.error}</Notice> : null}
      <div className="grid four">
        <Stat label={t("campaigns.title")} value={dashboard.data.campaigns.pagination.total ?? 0} />
        <Stat label={t("campaigns.active")} value={activeCampaigns} />
        <Stat
          label={t("customers.title")}
          value={dashboard.data.customers.pagination.total ?? 0}
        />
        <Stat
          label={t("dashboard.pendingClaims")}
          value={dashboard.data.claims?.summary.pending ?? 0}
        />
      </div>
      <div style={{ height: 14 }} />
      <div className="grid two">
        <Panel title={t("dashboard.currentCampaign")}>
          {dashboard.loading ? <Loading /> : null}
          {dashboard.data.overview ? (
            <div className="grid three">
              <Stat
                label={t("customers.title")}
                value={dashboard.data.overview.total_customers_with_progress}
              />
              <Stat
                label={t("campaigns.purchaseAmount")}
                value={money(
                  dashboard.data.overview.total_purchase_amount_minor,
                  dashboard.data.overview.currency,
                )}
              />
              <Stat
                label={t("dashboard.fulfilledClaims")}
                value={dashboard.data.overview.total_fulfilled_claims}
              />
            </div>
          ) : (
            <Empty>{t("dashboard.noCampaignData")}</Empty>
          )}
        </Panel>
        <Panel title={t("campaigns.syncHealth")}>
          {dashboard.data.sync ? (
            <div className="grid three">
              <Stat
                label={t("integrations.title")}
                value={dashboard.data.sync.summary.total_integrations}
              />
              <Stat
                label={t("campaigns.failed")}
                value={dashboard.data.sync.summary.failed_runs}
              />
              <Stat
                label={t("campaigns.partial")}
                value={dashboard.data.sync.summary.partially_failed_runs}
              />
            </div>
          ) : (
            <Empty>{t("dashboard.noSyncData")}</Empty>
          )}
        </Panel>
      </div>
      <div style={{ height: 14 }} />
      <div className="grid two">
        <Panel title={t("campaigns.recentCampaigns")}>
          <Table headers={[t("campaigns.titleColumn"), t("campaigns.statusColumn"), t("campaigns.datesColumn"), t("campaigns.currencyColumn")] }>
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
        <Panel title={t("campaigns.recentClaims")}>
          {dashboard.data.claims?.items.length ? (
            <Table headers={[t("customers.title"), t("campaigns.title"), t("gift_tiers.title"), t("common.status")] }>
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
            <Empty>{t("dashboard.noClaims")}</Empty>
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
      setNotice(t("campaigns.created"));
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
        title={t("campaigns.dashTitle")}
        subtitle={t("campaigns.subtitle")}
        actions={
          <IconButton icon={RefreshCw} label={t("common.refresh")} onClick={campaigns.reload} />
        }
      />
      <div className="split">
        <Panel title={t("campaigns.list")}>
          {campaigns.loading ? <Loading /> : null}
          {campaigns.error ? <Notice kind="error">{campaigns.error}</Notice> : null}
          {notice ? <Notice kind="success">{notice}</Notice> : null}
          {error ? <Notice kind="error">{error}</Notice> : null}
          <Table headers={[
            t("campaigns.titleColumn"),
            t("campaigns.statusColumn"),
            t("campaigns.datesColumn"),
            t("campaigns.claimsColumn"),
            t("campaigns.actionsColumn"),
          ]}>
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
                <td>{campaign.allow_claims ? t("campaigns.claimsEnabled") : t("campaigns.claimsDisabled")}</td>
                <td>
                  <div className="actions">
                    {["draft", "paused"].includes(campaign.status) ? (
                      <IconButton
                        icon={Play}
                        label={t("campaigns.activate")}
                        onClick={() => campaignAction(campaign, "activate")}
                      />
                    ) : null}
                    {campaign.status === "active" ? (
                      <IconButton
                        icon={Pause}
                        label={t("campaigns.pause")}
                        onClick={() => campaignAction(campaign, "pause")}
                      />
                    ) : null}
                    {["active", "paused"].includes(campaign.status) ? (
                      <IconButton
                        icon={Check}
                        label={t("campaigns.complete")}
                        onClick={() => campaignAction(campaign, "complete")}
                      />
                    ) : null}
                    {["draft", "completed"].includes(campaign.status) ? (
                      <IconButton
                        icon={Archive}
                        label={t("campaigns.archive")}
                        onClick={() => campaignAction(campaign, "archive")}
                      />
                    ) : null}
                  </div>
                </td>
              </tr>
            ))}
          </Table>
        </Panel>
        <Panel title={t("campaigns.newCampaign")}>
          <form className="form-grid" onSubmit={createCampaign}>
            <Field label={t("campaigns.titleColumn")}>
              <input
                className="input"
                value={form.title}
                onChange={(event) =>
                  setForm({ ...form, title: event.target.value })
                }
                required
              />
            </Field>
            <Field label={t("common.translationValue")}>
              <textarea
                className="textarea"
                value={form.description}
                onChange={(event) =>
                  setForm({ ...form, description: event.target.value })
                }
              />
            </Field>
            <div className="form-grid two">
              <Field label={t("campaigns.startDate")}>
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
              <Field label={t("campaigns.endDate")}>
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
              <Field label={t("campaigns.currency")}>
                <input
                  className="input"
                  value={form.currency}
                  onChange={(event) =>
                    setForm({ ...form, currency: event.target.value.toUpperCase() })
                  }
                  maxLength={3}
                />
              </Field>
              <Field label={t("campaigns.claimsColumn")}>
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
                  <option value="true">{t("campaigns.claimsEnabled")}</option>
                  <option value="false">{t("campaigns.claimsDisabled")}</option>
                </select>
              </Field>
            </div>
            <Button icon={Plus}>{t("campaigns.create")}</Button>
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
  const [editLocale, setEditLocale] = useState(getLanguage());
  const [form, setForm] = useState({
    title: "",
    // translations map
    title_i18n: { en: "", uz: "", ru: "" } as Record<string, string>,
    description_i18n: { en: "", uz: "", ru: "" } as Record<string, string>,
    required_amount: "10", // amount in major currency units (e.g., dollars)
    required_amount_minor: "1000000",
    selected_currency: "UZS", // currency selector
    stock_tracking_mode: "none",
    stock_quantity: "",
    is_active: true,
  });
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  
  // Convert major amount to minor (e.g., 10.50 -> 1050 for cents)
  const majorToMinor = (major: string) => {
    const num = parseFloat(major) || 0;
    return Math.max(1, Math.floor(num * 100)).toString();
  };
  
  // Convert minor amount to major (e.g., 1050 -> 10.50)
  const minorToMajor = (minor: string) => {
    const num = parseInt(minor) || 0;
    return (num / 100).toFixed(2);
  };
  
  // Format amount with dot thousands separator (e.g., 1000000 -> 1.000.000)
  const formatAmount = (amount: string): string => {
    if (!amount || amount === "") return "";
    const num = parseFloat(amount) || 0;
    return num.toFixed(2).replace(/(\d)(?=(\d{3})+(?!\d))/g, "$1.");
  };

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
      title_i18n: { en: "", uz: "", ru: "" },
      description_i18n: { en: "", uz: "", ru: "" },
      required_amount: "10",
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
      title_i18n: tier.title_i18n ?? { en: tier.title, uz: "", ru: "" },
      description_i18n: tier.description_i18n ?? { en: tier.description ?? "", uz: "", ru: "" },
      required_amount: minorToMajor(String(tier.required_amount_minor)),
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
    const payload: any = {
      title: form.title,
      required_amount_minor: Number(majorToMinor(form.required_amount)),
      stock_tracking_mode: form.stock_tracking_mode,
      stock_quantity: form.stock_quantity ? Number(form.stock_quantity) : null,
      is_active: form.is_active,
    };
    // include translations if any provided
    if (form.title_i18n && Object.values(form.title_i18n).some((v) => v && v.trim() !== "")) {
      payload.title_i18n = form.title_i18n;
    }
    if (form.description_i18n && Object.values(form.description_i18n).some((v) => v && v.trim() !== "")) {
      payload.description_i18n = form.description_i18n;
    }
    setError(null);
    setNotice(null);
    try {
      if (editingId) {
        await apiRequest<GiftTier>(
          `/campaigns/${campaignId}/gift-tiers/${editingId}`,
          { method: "PATCH", body: JSON.stringify(payload) },
        );
        setNotice(t("gift_tiers.notice.updated"));
      } else {
        await apiRequest<GiftTier>(`/campaigns/${campaignId}/gift-tiers`, {
          method: "POST",
          body: JSON.stringify(payload),
        });
        setNotice(t("gift_tiers.notice.created"));
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
      setNotice(t("gift_tiers.notice.deleted"));
      tiers.reload();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <>
      <PageHeader
        title={t("gift_tiers.title")}
        subtitle={selectedCampaign?.title ?? t("gift_tiers.selectCampaign")}
        actions={
          <div className="actions">
            <CampaignPicker
              campaigns={campaigns.data.items}
              value={campaignId}
              onChange={setCampaignId}
            />
            <IconButton icon={RefreshCw} label={t("common.refresh")} onClick={tiers.reload} />
          </div>
        }
      />
      <div className="split">
        <Panel title={t("gift_tiers.tiers")}>
          {tiers.loading ? <Loading /> : null}
          {notice ? <Notice kind="success">{notice}</Notice> : null}
          {error ?? tiers.error ? (
            <Notice kind="error">{error ?? tiers.error}</Notice>
          ) : null}
          {tiers.data.length ? (
            <Table
              headers={[
                t("gift_tiers.table.title"),
                t("gift_tiers.table.required"),
                t("gift_tiers.table.stock"),
                t("gift_tiers.table.reserved"),
                t("gift_tiers.table.available"),
                t("common.actions"),
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
                        label={t("common.edit")}
                        onClick={() => editTier(tier)}
                      />
                      <IconButton
                        icon={Trash2}
                        label={t("common.delete")}
                        onClick={() => deleteTier(tier)}
                      />
                    </div>
                  </td>
                </tr>
              ))}
            </Table>
          ) : (
            <Empty>{t("gift_tiers.no_tiers")}</Empty>
          )}
        </Panel>
        <Panel title={editingId ? t("gift_tiers.edit_tier") : t("gift_tiers.new_tier") }>
          <form className="form-grid" onSubmit={saveTier}>
            <Field label={t("gift_tiers.field.title")}>
                  <input
                    className="input"
                    value={form.title}
                    onChange={(event) =>
                      setForm({ ...form, title: event.target.value })
                    }
                    required
                  />
                  <div style={{ marginTop: 8 }}>
                    <label style={{ display: "block", fontSize: 12, marginBottom: 6, color: "#999" }}>Edit translation locale</label>
                    <select
                      className="select"
                      value={editLocale}
                      onChange={(e) => setEditLocale(e.target.value as "en" | "uz" | "ru")}
                      style={{ width: 160 }}
                    >
                      <option value="en">English</option>
                      <option value="uz">Oʻzbekcha</option>
                      <option value="ru">Русский</option>
                    </select>
                  </div>
                  <div style={{ marginTop: 8 }}>
                    <input
                      className="input"
                      placeholder={`Title (${editLocale})`}
                      value={form.title_i18n[editLocale] ?? ""}
                      onChange={(e) =>
                        setForm({ ...form, title_i18n: { ...form.title_i18n, [editLocale]: e.target.value } })
                      }
                    />
                  </div>
            </Field>
                <Field label="Description (translation)">
                  <textarea
                    className="textarea"
                    placeholder={`Description (${editLocale})`}
                    value={form.description_i18n[editLocale] ?? ""}
                    onChange={(e) =>
                      setForm({ ...form, description_i18n: { ...form.description_i18n, [editLocale]: e.target.value } })
                    }
                  />
                </Field>
            <Field label={t("gift_tiers.field.required_amount")}>
              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <input
                  className="input"
                  type="number"
                  step="0.01"
                  min="0.01"
                  placeholder="Enter amount"
                  value={form.required_amount}
                  onChange={(event) => {
                    const major = event.target.value;
                    setForm({ 
                      ...form, 
                      required_amount: major,
                      required_amount_minor: majorToMinor(major)
                    });
                  }}
                  required
                  style={{ flex: 1 }}
                />
                {selectedCampaign?.currency && (
                  <div style={{ 
                    padding: "8px 12px", 
                    background: "#f5f5f5", 
                    borderRadius: 4, 
                    fontSize: 14,
                    fontWeight: 500,
                    minWidth: 70,
                    textAlign: "center",
                    whiteSpace: "nowrap"
                  }}>
                    {selectedCampaign.currency}
                  </div>
                )}
              </div>
              {form.required_amount && form.required_amount !== "" && (
                <div style={{ marginTop: 4, fontSize: 12, color: "#666" }}>
                  {formatAmount(form.required_amount)}
                </div>
              )}
            </Field>
            <div className="form-grid two">
              <Field label={t("gift_tiers.field.tracking")}>
                <select
                  className="select"
                  value={form.stock_tracking_mode}
                  onChange={(event) =>
                    setForm({ ...form, stock_tracking_mode: event.target.value })
                  }
                >
                  <option value="none">{t("gift_tiers.option.none")}</option>
                  <option value="soft">{t("gift_tiers.option.soft")}</option>
                  <option value="strict">{t("gift_tiers.option.strict")}</option>
                </select>
              </Field>
              <Field label={t("gift_tiers.field.stock")}>
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
            <Field label={t("gift_tiers.field.active")}>
              <select
                className="select"
                value={form.is_active ? "true" : "false"}
                onChange={(event) =>
                  setForm({ ...form, is_active: event.target.value === "true" })
                }
              >
                <option value="true">{t("gift_tiers.option.active")}</option>
                <option value="false">{t("gift_tiers.option.inactive")}</option>
              </select>
            </Field>
            <div className="actions">
              <Button icon={Check}>{editingId ? t("gift_tiers.action.save") : t("gift_tiers.action.create")}</Button>
              {editingId ? (
                <Button type="button" variant="secondary" onClick={resetForm}>
                  {t("common.cancel")}
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
  const [editingIntegrationId, setEditingIntegrationId] = useState<ID | null>(null);
  const [integrationEditLocale, setIntegrationEditLocale] = useState<Language>(getLanguage());
  const [integrationTranslations, setIntegrationTranslations] = useState<
    Record<Language, string>
  >(emptyTranslationMap());
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

  const editingIntegration =
    integrations.data.find((integration) => integration.id === editingIntegrationId) ?? null;

  function openIntegrationTranslations(integration: Integration) {
    setEditingIntegrationId(integration.id);
    setIntegrationEditLocale(getLanguage());
    setIntegrationTranslations(normalizeTranslationMap(integration.name_i18n, integration.name));
    setError(null);
    setNotice(null);
  }

  function cancelIntegrationTranslations() {
    setEditingIntegrationId(null);
    setIntegrationTranslations(emptyTranslationMap());
  }

  async function saveIntegrationTranslations(event: FormEvent) {
    event.preventDefault();
    if (!editingIntegrationId) {
      return;
    }
    setError(null);
    setNotice(null);
    try {
      await apiRequest<Integration>(`/integrations/${editingIntegrationId}/translations`, {
        method: "PATCH",
        body: JSON.stringify({ name_i18n: integrationTranslations }),
      });
      setNotice("Integration translations updated.");
      cancelIntegrationTranslations();
      integrations.reload();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

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
                        icon={FileText}
                        label={t("common.editTranslations")}
                        onClick={() => openIntegrationTranslations(integration)}
                      />
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
        {editingIntegration ? (
          <Panel title={t("integration.translations.title")}>
            <form className="form-grid" onSubmit={saveIntegrationTranslations}>
              <div className="muted">{t("integration.translations.subtitle")}</div>
              <TranslationEditorBlock
                label={t("integration.translations.field")}
                value={integrationTranslations}
                locale={integrationEditLocale}
                onLocaleChange={setIntegrationEditLocale}
                onValueChange={setIntegrationTranslations}
              />
              <div className="actions">
                <Button icon={Check}>{t("common.saveTranslations")}</Button>
                <Button
                  icon={X}
                  type="button"
                  variant="secondary"
                  onClick={cancelIntegrationTranslations}
                >
                  {t("common.cancel")}
                </Button>
              </div>
            </form>
          </Panel>
        ) : null}
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

function currentRoute(): TenantRouteKey {
  const value = parseCompanyRoute(window.location.pathname);
  return tenantRouteMeta.some((route) => route.key === value) ? value : "dashboard";
}

function getAppMode(): AppMode {
  const { pathname } = window.location;
  if (pathname.startsWith("/platform") || pathname === "/admin") {
    return { kind: "platform-admin" };
  }

  const companyAdminMatch = pathname.match(
    /^\/([^/]+)\/(login|admin|campaigns|gift-tiers|customers|imports|integrations|claims|reports|operations)(?:\/.*)?$/,
  );
  if (companyAdminMatch?.[1]) {
    return { kind: "company-admin", companySlug: companyAdminMatch[1] };
  }

  const portalMatch = pathname.match(/^\/([^/]+)\/portal(?:\/.*)?$/);
  if (portalMatch?.[1]) {
    return { kind: "portal", companySlug: portalMatch[1] };
  }

  if (pathname.startsWith("/portal")) {
    return { kind: "portal", companySlug: null };
  }

  return { kind: "company-admin", companySlug: null };
}

function CompanyAdminApp({ companySlug }: { companySlug: string | null }) {
  const [route, setRouteState] = useState<TenantRouteKey>(currentRoute);
  const [session, setSession] = useState<MeResponse | null>(null);
  const [checkingSession, setCheckingSession] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [langKey, setLangKey] = useState(0); // Force re-render on language change

  useEffect(() => {
    loadLanguage();
    setLangKey((k) => k + 1);
  }, []);

  useEffect(() => {
    const onNavigation = () => setRouteState(currentRoute());
    window.addEventListener("popstate", onNavigation);
    return () => window.removeEventListener("popstate", onNavigation);
  }, []);

  useEffect(() => {
    if (!getStoredAccessToken()) {
      setCheckingSession(false);
      return;
    }
    me()
      .then((current) => {
        if (current.role === "platform_admin") {
          clearTokens();
          setSession(null);
          setError("Tenant admin access is required for company dashboards.");
          return;
        }
        if (!companySlug && current.company?.slug) {
          window.history.replaceState(null, "", `/${current.company.slug}/admin`);
          setRouteState("dashboard");
        }
        if (companySlug && current.company?.slug && current.company.slug !== companySlug) {
          window.history.replaceState(null, "", `/${current.company.slug}/admin`);
          setRouteState("dashboard");
        }
        setSession(current);
      })
      .catch(() => {
        clearTokens();
        setSession(null);
      })
      .finally(() => setCheckingSession(false));
  }, []);

  function setRoute(nextRoute: TenantRouteKey) {
    window.history.pushState(
      null,
      "",
      companyAdminPath(companySlug, nextRoute),
    );
    setRouteState(nextRoute);
  }

  async function handleLogout() {
    await logout();
    setSession(null);
    window.history.replaceState(null, "", companySlug ? `/${companySlug}/login` : "/login");
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
    const loginPath = companySlug ? `/${companySlug}/login` : "/login";
    if (companySlug && window.location.pathname !== loginPath) {
      window.history.replaceState(null, "", loginPath);
    }
    return (
      <LoginScreen
        onLogin={(nextSession) => {
          setError(null);
          setSession(nextSession);
          const targetSlug = nextSession.company?.slug ?? companySlug;
          if (targetSlug) {
            window.history.replaceState(null, "", `/${targetSlug}/admin`);
          }
        }}
        title={companySlug ? `${companySlug} admin console` : "Company Admin Console"}
        subtitle={
          companySlug
            ? `Sign in to manage ${companySlug} operations.`
            : "Sign in to manage company operations."
        }
        externalError={error}
        companySlug={companySlug}
      />
    );
  }

  return (
    <TenantLayout
      session={session}
      route={route}
      setRoute={setRoute}
      onLogout={handleLogout}
    >
      {screen}
    </TenantLayout>
  );
}

export default function App() {
  const mode = getAppMode();
  if (mode.kind === "portal") {
    return <PortalApp />;
  }
  if (mode.kind === "platform-admin") {
    return <PlatformAdminApp />;
  }
  return <CompanyAdminApp companySlug={mode.companySlug} />;
}
