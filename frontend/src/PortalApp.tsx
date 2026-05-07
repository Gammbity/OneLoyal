import {
  ArrowLeft,
  CalendarDays,
  Check,
  ChevronRight,
  Gift,
  History,
  Loader2,
  LogOut,
  RefreshCw,
  TicketCheck,
  Trophy,
  WalletCards,
  X,
} from "lucide-react";
import type { FormEvent, ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";

import {
  clearPortalToken,
  createPortalSession,
  getStoredPortalToken,
  portalApiRequest,
} from "./api";
import type {
  ID,
  PortalCampaign,
  PortalMeResponse,
  PortalProgressResponse,
  PortalPurchaseHistoryItem,
  RewardClaim,
} from "./types";
import { money, shortDate, shortDateTime, titleCase } from "./utils";

type PortalRoute =
  | { name: "access" }
  | { name: "home" }
  | { name: "campaign"; campaignId: ID }
  | { name: "claims" };

type PortalBundle = {
  me: PortalMeResponse | null;
  campaigns: PortalCampaign[];
  claims: RewardClaim[];
};

function parsePortalRoute(): PortalRoute {
  const path = window.location.pathname;
  if (path === "/portal/access") {
    return { name: "access" };
  }
  if (path === "/portal/claims") {
    return { name: "claims" };
  }
  const campaignMatch = path.match(/^\/portal\/campaigns\/([^/]+)$/);
  if (campaignMatch?.[1]) {
    return { name: "campaign", campaignId: campaignMatch[1] };
  }
  return { name: "home" };
}

function portalNavigate(path: string, replace = false): void {
  if (replace) {
    window.history.replaceState(null, "", path);
  } else {
    window.history.pushState(null, "", path);
  }
  window.dispatchEvent(new PopStateEvent("popstate"));
}

function portalErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return "Something went wrong.";
}

function PortalStatus({ value }: { value: string }) {
  return <span className={`pill ${value}`}>{titleCase(value)}</span>;
}

function PortalButton({
  children,
  variant = "primary",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "danger" | "ghost";
}) {
  return (
    <button className={`button ${variant}`} {...props}>
      {children}
    </button>
  );
}

function PortalNotice({
  kind,
  children,
}: {
  kind: "error" | "success" | "info";
  children: ReactNode;
}) {
  const className = kind === "info" ? "notice" : `notice ${kind}`;
  return <div className={className}>{children}</div>;
}

function PortalLoading({ label = "Loading" }: { label?: string }) {
  return (
    <div className="portal-centered">
      <Loader2 size={22} />
      <span>{label}</span>
    </div>
  );
}

function PortalEmpty({ children }: { children: ReactNode }) {
  return <div className="empty">{children}</div>;
}

function PortalShell({
  bundle,
  children,
  onLogout,
}: {
  bundle: PortalBundle;
  children: ReactNode;
  onLogout: () => void;
}) {
  return (
    <main className="portal-shell">
      <header className="portal-topbar">
        <button
          className="portal-brand"
          onClick={() => portalNavigate("/portal")}
          aria-label="Portal home"
        >
          <span className="brand-mark">
            <Trophy size={18} />
          </span>
          <span>OneLoyal</span>
        </button>
        <nav className="portal-nav">
          <button onClick={() => portalNavigate("/portal")}>Campaigns</button>
          <button onClick={() => portalNavigate("/portal/claims")}>Claims</button>
          <button onClick={onLogout}>
            <LogOut size={16} />
            Logout
          </button>
        </nav>
      </header>
      <section className="portal-hero">
        <div>
          <p>{bundle.me?.company.name ?? "Customer portal"}</p>
          <h1>{bundle.me?.customer.name ?? "Your rewards"}</h1>
        </div>
        <div className="portal-hero-stat">
          <span>Campaigns</span>
          <strong>{bundle.campaigns.length}</strong>
        </div>
      </section>
      {children}
    </main>
  );
}

function PortalAccessScreen() {
  const [state, setState] = useState<"loading" | "idle" | "error" | "success">(
    "loading",
  );
  const [message, setMessage] = useState<string>("");

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const token = params.get("token");

    if (!token) {
      setState("idle");
      setMessage(
        getStoredPortalToken()
          ? "You already have an active portal session."
          : "Open your secure magic link to access your rewards.",
      );
      return;
    }

    let cancelled = false;
    setState("loading");
    createPortalSession(token)
      .then(() => {
        if (cancelled) {
          return;
        }
        setState("success");
        portalNavigate("/portal", true);
      })
      .catch((error: unknown) => {
        if (cancelled) {
          return;
        }
        setState("error");
        setMessage(
          portalErrorMessage(error) ||
            "This magic link is invalid, expired, or revoked.",
        );
        window.history.replaceState(null, "", "/portal/access");
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main className="portal-access">
      <section className="portal-access-card">
        <div className="brand">
          <span className="brand-mark">
            <Trophy size={20} />
          </span>
          OneLoyal
        </div>
        <h1>Rewards Portal</h1>
        {state === "loading" || state === "success" ? (
          <PortalLoading label="Opening your secure portal" />
        ) : null}
        {state === "error" ? (
          <PortalNotice kind="error">
            {message || "This magic link is invalid, expired, or revoked."}
          </PortalNotice>
        ) : null}
        {state === "idle" ? (
          <PortalNotice kind="info">{message}</PortalNotice>
        ) : null}
        {getStoredPortalToken() && state !== "loading" ? (
          <PortalButton type="button" onClick={() => portalNavigate("/portal")}>
            <Gift size={16} />
            Continue to rewards
          </PortalButton>
        ) : null}
      </section>
    </main>
  );
}

function PortalHome({ bundle }: { bundle: PortalBundle }) {
  const activeClaims = bundle.claims.filter((claim) =>
    ["pending", "approved"].includes(claim.status),
  ).length;

  return (
    <section className="portal-content">
      <div className="portal-stats">
        <div className="portal-stat-card">
          <WalletCards size={20} />
          <span>Available campaigns</span>
          <strong>{bundle.campaigns.length}</strong>
        </div>
        <div className="portal-stat-card">
          <TicketCheck size={20} />
          <span>Active claims</span>
          <strong>{activeClaims}</strong>
        </div>
      </div>
      {bundle.campaigns.length ? (
        <div className="portal-card-list">
          {bundle.campaigns.map((campaign) => (
            <article className="portal-campaign-card" key={campaign.id}>
              <div>
                <PortalStatus value={campaign.status} />
                <h2>{campaign.title}</h2>
                {campaign.description ? <p>{campaign.description}</p> : null}
              </div>
              <div className="portal-card-meta">
                <CalendarDays size={16} />
                {shortDate(campaign.start_date)} - {shortDate(campaign.end_date)}
              </div>
              <PortalButton
                type="button"
                onClick={() => portalNavigate(`/portal/campaigns/${campaign.id}`)}
              >
                View progress
                <ChevronRight size={16} />
              </PortalButton>
            </article>
          ))}
        </div>
      ) : (
        <PortalEmpty>No active campaigns are available right now.</PortalEmpty>
      )}
    </section>
  );
}

function PortalClaimsPage({
  claims,
  onRefresh,
}: {
  claims: RewardClaim[];
  onRefresh: () => void;
}) {
  const [cancellingId, setCancellingId] = useState<ID | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function cancelClaim(claimId: ID) {
    setError(null);
    setCancellingId(claimId);
    try {
      await portalApiRequest<RewardClaim>(`/portal/claims/${claimId}/cancel`, {
        method: "POST",
      });
      onRefresh();
    } catch (err) {
      setError(portalErrorMessage(err));
    } finally {
      setCancellingId(null);
    }
  }

  return (
    <section className="portal-content">
      <div className="portal-section-heading">
        <div>
          <h2>Your claims</h2>
          <p>Gift requests and their current status.</p>
        </div>
        <PortalButton variant="secondary" onClick={onRefresh}>
          <RefreshCw size={16} />
          Refresh
        </PortalButton>
      </div>
      {error ? <PortalNotice kind="error">{error}</PortalNotice> : null}
      {claims.length ? (
        <div className="portal-list">
          {claims.map((claim) => (
            <article className="portal-list-row" key={claim.id}>
              <div>
                <h3>{claim.gift_tier_title ?? "Gift"}</h3>
                <p>{claim.campaign_title ?? "Campaign"}</p>
                <span>{shortDateTime(claim.created_at)}</span>
              </div>
              <div className="portal-row-actions">
                <PortalStatus value={claim.status} />
                {claim.status === "pending" ? (
                  <PortalButton
                    variant="secondary"
                    disabled={cancellingId === claim.id}
                    onClick={() => cancelClaim(claim.id)}
                  >
                    <X size={16} />
                    Cancel
                  </PortalButton>
                ) : null}
              </div>
            </article>
          ))}
        </div>
      ) : (
        <PortalEmpty>You have not claimed a gift yet.</PortalEmpty>
      )}
    </section>
  );
}

function PortalCampaignPage({
  campaignId,
  claims,
  onClaimsChanged,
}: {
  campaignId: ID;
  claims: RewardClaim[];
  onClaimsChanged: () => void;
}) {
  const [progress, setProgress] = useState<PortalProgressResponse | null>(null);
  const [history, setHistory] = useState<PortalPurchaseHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [comment, setComment] = useState("");
  const [claimingTierId, setClaimingTierId] = useState<ID | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const [progressResponse, historyResponse] = await Promise.all([
        portalApiRequest<PortalProgressResponse>(
          `/portal/campaigns/${campaignId}/progress`,
        ),
        portalApiRequest<PortalPurchaseHistoryItem[]>(
          `/portal/campaigns/${campaignId}/purchase-history`,
        ),
      ]);
      setProgress(progressResponse);
      setHistory(historyResponse);
    } catch (err) {
      setError(portalErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [campaignId]);

  const campaignClaims = claims.filter((claim) => claim.campaign_id === campaignId);
  const activeClaim = campaignClaims.find((claim) =>
    ["pending", "approved"].includes(claim.status),
  );

  async function claimGift(giftTierId: ID) {
    if (claimingTierId || activeClaim) {
      return;
    }
    setNotice(null);
    setError(null);
    setClaimingTierId(giftTierId);
    try {
      await portalApiRequest<RewardClaim>(`/portal/campaigns/${campaignId}/claims`, {
        method: "POST",
        body: JSON.stringify({
          gift_tier_id: giftTierId,
          customer_comment: comment.trim() || null,
        }),
      });
      setNotice("Your gift claim was submitted.");
      setComment("");
      onClaimsChanged();
    } catch (err) {
      setError(portalErrorMessage(err));
    } finally {
      setClaimingTierId(null);
    }
  }

  async function cancelActiveClaim() {
    if (!activeClaim) {
      return;
    }
    setError(null);
    setClaimingTierId(activeClaim.gift_tier_id);
    try {
      await portalApiRequest<RewardClaim>(`/portal/claims/${activeClaim.id}/cancel`, {
        method: "POST",
      });
      setNotice("Your pending claim was cancelled.");
      onClaimsChanged();
    } catch (err) {
      setError(portalErrorMessage(err));
    } finally {
      setClaimingTierId(null);
    }
  }

  if (loading) {
    return <PortalLoading label="Loading campaign progress" />;
  }

  if (error && !progress) {
    return (
      <section className="portal-content">
        <PortalNotice kind="error">{error}</PortalNotice>
      </section>
    );
  }

  if (!progress) {
    return (
      <section className="portal-content">
        <PortalEmpty>Campaign progress was not found.</PortalEmpty>
      </section>
    );
  }

  const percent = Math.min(Number(progress.progress.progress_percent), 100);
  const reachedTiers = progress.gift_tiers.filter(
    (tier) => progress.progress.total_amount_minor >= tier.required_amount_minor,
  );
  const currency = progress.progress.currency || progress.campaign.currency;

  return (
    <section className="portal-content">
      <button className="portal-back" onClick={() => portalNavigate("/portal")}>
        <ArrowLeft size={16} />
        Back to campaigns
      </button>
      {notice ? <PortalNotice kind="success">{notice}</PortalNotice> : null}
      {error ? <PortalNotice kind="error">{error}</PortalNotice> : null}
      {!progress.progress.is_snapshot_available ? (
        <PortalNotice kind="info">
          Your purchase progress has not been calculated yet. Please check back later.
        </PortalNotice>
      ) : null}
      <article className="portal-progress-card">
        <div className="portal-progress-header">
          <div>
            <PortalStatus value={progress.campaign.status} />
            <h2>{progress.campaign.title}</h2>
            <p>
              {shortDate(progress.campaign.start_date)} -{" "}
              {shortDate(progress.campaign.end_date)}
            </p>
          </div>
          <div className="portal-total">
            <span>Total purchases</span>
            <strong>{money(progress.progress.total_amount_minor, currency)}</strong>
          </div>
        </div>
        <div className="portal-progress-meter">
          <div className="portal-progress-fill" style={{ width: `${percent}%` }} />
        </div>
        <div className="portal-progress-copy">
          {progress.progress.next_tier_title ? (
            <strong>
              You need {money(progress.progress.amount_left_minor, currency)} more to
              reach {progress.progress.next_tier_title}.
            </strong>
          ) : progress.progress.current_tier_title ? (
            <strong>You have reached the highest available gift.</strong>
          ) : (
            <strong>Your first gift is waiting on the ladder below.</strong>
          )}
          <span>{progress.progress.progress_percent}% progress</span>
        </div>
        {activeClaim ? (
          <div className="portal-active-claim">
            <TicketCheck size={18} />
            <div>
              <strong>Current claim: {titleCase(activeClaim.status)}</strong>
              <span>{activeClaim.gift_tier_title ?? "Gift"}</span>
            </div>
            {activeClaim.status === "pending" ? (
              <PortalButton
                variant="secondary"
                disabled={claimingTierId === activeClaim.gift_tier_id}
                onClick={cancelActiveClaim}
              >
                Cancel claim
              </PortalButton>
            ) : null}
          </div>
        ) : null}
      </article>

      <div className="portal-two-column">
        <section className="portal-panel">
          <div className="portal-section-heading">
            <div>
              <h2>Gift ladder</h2>
              <p>Rewards unlock as your purchase amount grows.</p>
            </div>
          </div>
          <div className="portal-tier-list">
            {progress.gift_tiers.map((tier) => {
              const reached =
                progress.progress.total_amount_minor >= tier.required_amount_minor;
              return (
                <article
                  className={`portal-tier ${reached ? "reached" : ""}`}
                  key={tier.id}
                >
                  <div className="portal-tier-marker">
                    {reached ? <Check size={16} /> : <Gift size={16} />}
                  </div>
                  <div>
                    <h3>{tier.title}</h3>
                    <p>{money(tier.required_amount_minor, tier.currency)}</p>
                    <span>
                      {reached
                        ? "You have reached this gift"
                        : `You need ${money(
                            Math.max(
                              tier.required_amount_minor -
                                progress.progress.total_amount_minor,
                              0,
                            ),
                            tier.currency,
                          )} more`}
                    </span>
                  </div>
                  {reached && !activeClaim ? (
                    <PortalButton
                      disabled={claimingTierId === tier.id}
                      onClick={() => claimGift(tier.id)}
                    >
                      <Gift size={16} />
                      Claim gift
                    </PortalButton>
                  ) : null}
                </article>
              );
            })}
          </div>
          {reachedTiers.length && !activeClaim ? (
            <div className="field">
              <label>Claim note</label>
              <textarea
                className="textarea"
                value={comment}
                onChange={(event) => setComment(event.target.value)}
                placeholder="Optional note for the sales team"
              />
            </div>
          ) : null}
        </section>
        <section className="portal-panel">
          <div className="portal-section-heading">
            <div>
              <h2>Purchase history</h2>
              <p>Sales counted toward this campaign.</p>
            </div>
            <History size={18} />
          </div>
          {history.length ? (
            <div className="portal-history-list">
              {history.map((sale, index) => {
                const amount = sale.gross_amount_minor * sale.amount_sign;
                return (
                  <article className="portal-history-row" key={`${sale.document_date}-${index}`}>
                    <div>
                      <strong>{sale.external_document_number ?? "Document"}</strong>
                      <span>{shortDate(sale.document_date)}</span>
                    </div>
                    <div>
                      <strong>{money(amount, sale.currency)}</strong>
                      <span>
                        {titleCase(sale.document_kind)} ·{" "}
                        {titleCase(sale.payment_status)} ·{" "}
                        {titleCase(sale.document_status)}
                      </span>
                    </div>
                  </article>
                );
              })}
            </div>
          ) : (
            <PortalEmpty>No purchase history for this campaign yet.</PortalEmpty>
          )}
        </section>
      </div>
    </section>
  );
}

export default function PortalApp() {
  const [route, setRoute] = useState<PortalRoute>(parsePortalRoute);
  const [bundle, setBundle] = useState<PortalBundle>({
    me: null,
    campaigns: [],
    claims: [],
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    const onPop = () => setRoute(parsePortalRoute());
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  useEffect(() => {
    if (route.name === "access") {
      setLoading(false);
      return;
    }
    if (!getStoredPortalToken()) {
      portalNavigate("/portal/access", true);
      setLoading(false);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);
    Promise.all([
      portalApiRequest<PortalMeResponse>("/portal/me"),
      portalApiRequest<PortalCampaign[]>("/portal/campaigns"),
      portalApiRequest<RewardClaim[]>("/portal/claims"),
    ])
      .then(([me, campaigns, claims]) => {
        if (!cancelled) {
          setBundle({ me, campaigns, claims });
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(portalErrorMessage(err));
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
  }, [route.name, revision]);

  function refreshBundle() {
    setRevision((value) => value + 1);
  }

  function logout() {
    clearPortalToken();
    portalNavigate("/portal/access", true);
  }

  const content = useMemo(() => {
    if (route.name === "access") {
      return <PortalAccessScreen />;
    }
    if (loading && !bundle.me) {
      return <PortalLoading label="Loading your rewards" />;
    }
    if (error && !bundle.me) {
      return (
        <section className="portal-content">
          <PortalNotice kind="error">{error}</PortalNotice>
        </section>
      );
    }
    if (route.name === "claims") {
      return <PortalClaimsPage claims={bundle.claims} onRefresh={refreshBundle} />;
    }
    if (route.name === "campaign") {
      return (
        <PortalCampaignPage
          campaignId={route.campaignId}
          claims={bundle.claims}
          onClaimsChanged={refreshBundle}
        />
      );
    }
    return <PortalHome bundle={bundle} />;
  }, [route, loading, bundle, error]);

  if (route.name === "access") {
    return content;
  }

  return (
    <PortalShell bundle={bundle} onLogout={logout}>
      {error && bundle.me ? <PortalNotice kind="error">{error}</PortalNotice> : null}
      {content}
    </PortalShell>
  );
}
