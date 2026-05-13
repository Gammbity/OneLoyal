export type ID = string;

export type PaginationMeta = {
  limit: number;
  offset: number;
  total: number | null;
  has_more: boolean | null;
};

export type Paginated<T> = {
  items: T[];
  pagination: PaginationMeta;
};

export type Company = {
  id: ID;
  name: string;
  name_i18n?: Record<string, string> | null;
  slug: string;
  base_currency: string;
  timezone: string;
  status: string;
  created_at: string;
  updated_at: string;
};

export type User = {
  id: ID;
  company_id: ID | null;
  email: string;
  full_name: string;
  role: string;
  status: string;
};

export type AuthTokenResponse = {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: User;
  company: Company | null;
};

export type MeResponse = {
  user: User;
  company: Company | null;
  role: string;
  company_id: ID | null;
};

export type Campaign = {
  id: ID;
  company_id: ID;
  title: string;
  description: string | null;
  start_date: string;
  end_date: string;
  status: string;
  currency: string;
  allow_claims: boolean;
  created_at: string;
  updated_at: string;
};

export type GiftTier = {
  id: ID;
  company_id: ID;
  campaign_id: ID;
  title: string;
  description: string | null;
  required_amount_minor: number;
  currency: string;
  image_url: string | null;
  stock_tracking_mode: string;
  stock_quantity: number | null;
  reserved_quantity: number;
  fulfilled_quantity: number;
  available_quantity: number | null;
  sort_order: number;
  is_active: boolean;
  title_i18n?: Record<string, string> | null;
  description_i18n?: Record<string, string> | null;
};

export type Customer = {
  id: ID;
  company_id: ID;
  name: string;
  phone: string | null;
  email: string | null;
  tax_id: string | null;
  status: string;
  created_at: string;
  updated_at: string;
};

export type Progress = {
  id: ID;
  campaign_id: ID;
  customer_id: ID;
  customer_name: string | null;
  total_amount_minor: number;
  currency: string;
  current_tier_id: ID | null;
  current_tier_title: string | null;
  next_tier_id: ID | null;
  next_tier_title: string | null;
  amount_left_minor: number;
  progress_percent: string;
  progress_percent_basis_points: number;
  calculated_at: string;
};

export type ImportBatch = {
  id: ID;
  source_type: string;
  provider: string;
  status: string;
  original_filename: string | null;
  total_rows: number;
  valid_rows: number;
  invalid_rows: number;
  committed_rows: number;
  skipped_rows: number;
  error_summary: string | null;
  committed_at: string | null;
  created_at: string;
};

export type ImportPreview = {
  import_batch_id: ID;
  total_rows: number;
  valid_rows: number;
  invalid_rows: number;
  columns_detected: string[];
  errors: Array<{
    row_number: number;
    errors: string[];
    raw_row_json: Record<string, unknown>;
  }>;
  stats_json: Record<string, unknown>;
};

export type ImportRow = {
  id: ID;
  row_number: number;
  raw_row_json: Record<string, unknown>;
  normalized_row_json: Record<string, unknown>;
  status: string;
  error_messages_json: string[];
};

export type Integration = {
  id: ID;
  provider: string;
  name: string;
  name_i18n?: Record<string, string> | null;
  status: string;
  settings_json: Record<string, unknown>;
  last_attempted_sync_at: string | null;
  last_successful_sync_at: string | null;
  last_scheduled_sync_at: string | null;
  next_sync_at: string | null;
  has_active_credentials: boolean;
};

export type SyncRun = {
  id: ID;
  integration_id: ID;
  sync_type: string;
  status: string;
  task_id: string | null;
  enqueued_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  stats_json: Record<string, unknown>;
  error_summary: string | null;
};

export type RewardClaim = {
  id: ID;
  campaign_id: ID;
  customer_id: ID;
  gift_tier_id: ID;
  status: string;
  customer_comment: string | null;
  admin_comment: string | null;
  decided_at: string | null;
  fulfilled_at: string | null;
  cancelled_at: string | null;
  customer_name: string | null;
  campaign_title: string | null;
  gift_tier_title: string | null;
  created_at: string;
};

export type CampaignOverview = {
  campaign_id: ID;
  campaign_title: string;
  campaign_status: string;
  campaign_start_date: string;
  campaign_end_date: string;
  currency: string;
  total_customers_with_progress: number;
  total_purchase_amount_minor: number;
  average_purchase_amount_minor: number;
  customers_reached_any_tier: number;
  customers_reached_highest_tier: number;
  total_active_claims: number;
  total_fulfilled_claims: number;
  gift_tier_breakdown: Array<{
    tier_id: ID;
    tier_title: string;
    required_amount_minor: number;
    customers_currently_at_tier: number;
    claims_count: number;
    fulfilled_count: number;
  }>;
};

export type TopCustomerReportItem = {
  customer_id: ID;
  customer_name: string;
  total_amount_minor: number;
  current_tier_id: ID | null;
  current_tier_title: string | null;
  next_tier_id: ID | null;
  next_tier_title: string | null;
  amount_left_minor: number;
  progress_percent: string;
  claim_status: string | null;
};

export type CloseToNextReportItem = {
  customer_id: ID;
  customer_name: string;
  phone: string | null;
  email: string | null;
  total_amount_minor: number;
  current_tier_title: string | null;
  next_tier_title: string;
  amount_left_minor: number;
  progress_percent: string;
};

export type GiftLiabilityReport = {
  campaign: {
    campaign_id: ID;
    campaign_title: string;
    campaign_status: string;
    campaign_start_date: string;
    campaign_end_date: string;
    currency: string;
  };
  total_qualified_customers: number;
  total_claims: number;
  total_pending_claims: number;
  total_approved_claims: number;
  total_fulfilled_claims: number;
  tiers: Array<{
    tier_id: ID;
    tier_title: string;
    required_amount_minor: number;
    customers_qualified_for_tier: number;
    customers_currently_at_tier: number;
    pending_claims: number;
    approved_claims: number;
    fulfilled_claims: number;
    stock_quantity: number | null;
    reserved_quantity: number;
    fulfilled_quantity: number;
    available_quantity: number | null;
  }>;
};

export type RewardClaimsReport = {
  items: Array<{
    claim_id: ID;
    campaign_id: ID;
    campaign_title: string;
    customer_id: ID;
    customer_name: string;
    gift_tier_id: ID;
    gift_tier_title: string;
    status: string;
    created_at: string;
    decided_at: string | null;
    fulfilled_at: string | null;
  }>;
  summary: {
    total: number;
    pending: number;
    approved: number;
    rejected: number;
    fulfilled: number;
    cancelled: number;
  };
};

export type SyncHealthReport = {
  integrations: Array<{
    integration_id: ID;
    provider: string;
    name: string;
    status: string;
    last_attempted_sync_at: string | null;
    last_successful_sync_at: string | null;
    next_sync_at: string | null;
    recent_success_count: number;
    recent_failed_count: number;
    recent_partially_failed_count: number;
    last_error_summary: string | null;
  }>;
  recent_runs: Array<{
    sync_run_id: ID;
    integration_id: ID;
    provider: string;
    sync_type: string;
    status: string;
    started_at: string | null;
    finished_at: string | null;
    stats_json: Record<string, unknown>;
    error_summary: string | null;
  }>;
  summary: {
    total_integrations: number;
    active_integrations: number;
    failed_runs: number;
    partially_failed_runs: number;
    successful_runs: number;
  };
};

export type SalesManagerReportItem = {
  user_id: ID;
  full_name: string;
  email: string;
  assigned_customer_count: number;
  total_purchase_amount_minor: number;
  customers_reached_any_tier: number;
  customers_close_to_next_tier_count: number;
  fulfilled_claims_count: number;
};

export type PortalSessionResponse = {
  portal_access_token: string;
  token_type: string;
  expires_in: number;
  customer: Customer;
  company: Company;
};

export type PortalMeResponse = {
  customer: Customer;
  company: Company;
};

export type PortalCampaign = {
  id: ID;
  company_id: ID;
  title: string;
  description: string | null;
  start_date: string;
  end_date: string;
  status: string;
  currency: string;
  allow_claims: boolean;
};

export type PortalGiftTier = {
  id: ID;
  campaign_id: ID;
  title: string;
  description: string | null;
  required_amount_minor: number;
  currency: string;
  image_url: string | null;
  stock_tracking_mode: string;
  stock_quantity: number | null;
  sort_order: number;
  is_active: boolean;
};

export type PortalProgressSnapshot = {
  is_snapshot_available: boolean;
  total_amount_minor: number;
  currency: string;
  current_tier_id: ID | null;
  current_tier_title: string | null;
  next_tier_id: ID | null;
  next_tier_title: string | null;
  amount_left_minor: number;
  progress_percent: string;
  progress_percent_basis_points: number;
  calculated_at: string | null;
};

export type PortalProgressResponse = {
  campaign: PortalCampaign;
  customer: Customer;
  progress: PortalProgressSnapshot;
  gift_tiers: PortalGiftTier[];
};

export type PortalPurchaseHistoryItem = {
  document_date: string;
  effective_date: string;
  document_kind: string;
  external_document_number: string | null;
  gross_amount_minor: number;
  amount_sign: number;
  currency: string;
  payment_status: string;
  document_status: string;
};

export type OpsStatusResponse = {
  company_id: ID;
  sync_runs: Record<string, number>;
  queued_sync_count: number;
  running_sync_count: number;
  stuck_queued_sync_count: number;
  stuck_running_sync_count: number;
  pending_notification_events_count: number;
  failed_notification_events_count: number;
  pending_domain_events_count: number;
  failed_domain_events_count: number;
  recent_failed_sync_errors_count: number;
  active_integrations_count: number;
  scheduled_integrations_count: number;
  last_successful_sync_time: string | null;
  last_failed_sync_time: string | null;
};

export type RecoverStuckSyncsResponse = {
  checked_count: number;
  recovered_queued_count: number;
  recovered_running_count: number;
};

export type RecoverNotificationsResponse = {
  checked_count: number;
  failed_count: number;
  retried_count: number;
};

export type CompanyProvisionResponse = {
  company: Company;
  owner: User;
  login_path: string;
};

export type PlatformPlanSummary = {
  plan_id: ID;
  code: string;
  name: string;
  is_active: boolean;
  company_count: number;
  active_subscription_count: number;
  trialing_subscription_count: number;
  past_due_subscription_count: number;
  cancelled_subscription_count: number;
  expired_subscription_count: number;
};

export type PlatformOverviewSummary = {
  company_count: number;
  active_tenant_count: number;
  suspended_tenant_count: number;
  archived_tenant_count: number;
  subscription_count: number;
  active_subscription_count: number;
  trialing_subscription_count: number;
  past_due_subscription_count: number;
  cancelled_subscription_count: number;
  expired_subscription_count: number;
};

export type PlatformOpsSummary = {
  total_integrations: number;
  active_integrations: number;
  queued_sync_runs: number;
  running_sync_runs: number;
  failed_sync_runs_24h: number;
  partially_failed_sync_runs_24h: number;
  successful_sync_runs_24h: number;
  failed_sync_errors_24h: number;
};

export type PlatformQueueSummary = {
  pending_notifications: number;
  failed_notifications: number;
  pending_domain_events: number;
  failed_domain_events: number;
};

export type PlatformRecentFailure = {
  sync_run_id: ID;
  company_id: ID;
  company_name: string;
  company_slug: string;
  integration_id: ID;
  integration_name: string;
  sync_type: string;
  status: string;
  error_summary: string | null;
  started_at: string | null;
  finished_at: string | null;
};

export type PlatformOverviewResponse = {
  generated_at: string;
  summary: PlatformOverviewSummary;
  plans: PlatformPlanSummary[];
  ops: PlatformOpsSummary;
  queues: PlatformQueueSummary;
  recent_failures: PlatformRecentFailure[];
};

export type PlatformSubscriptionItem = {
  subscription_id: ID;
  company_id: ID;
  company_name: string;
  company_slug: string;
  plan_id: ID;
  plan_code: string;
  plan_name: string;
  status: string;
  created_at: string;
  current_period_ends_at: string | null;
  trial_ends_at: string | null;
};

export type PlatformBillingResponse = {
  generated_at: string;
  summary: PlatformOverviewSummary;
  plans: PlatformPlanSummary[];
  subscriptions: PlatformSubscriptionItem[];
};
