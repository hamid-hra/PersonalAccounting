export interface Summary {
  year: number; month: number; label: string;
  month_income_rial: number; month_expense_rial: number; month_net_rial: number;
  month_count: number;
  total_income_rial: number; total_expense_rial: number; total_count: number;
  self_transfer_out_rial: number; pending_review: number;
  latest_transaction: string | null;
  // واریزی‌هایی که هنوز مشخص نشده درآمد هستند یا نه
  pending_income_rial: number; pending_income_count: number;
}

export interface MonthPoint {
  year: number; month: number; label: string;
  income_rial: number; expense_rial: number; net_rial: number; count: number;
}

export interface CategorySlice {
  category_id: number | null; name: string; color: string;
  parent_id: number | null; total_rial: number; count: number;
}

export interface Category {
  id: number; slug: string; name_fa: string; parent_id: number | null;
  kind: string; color: string; icon: string | null; is_system: boolean;
  sort_order: number; transaction_count: number;
}

export interface Transaction {
  id: number; account_id: number; jalali_datetime: string;
  jalali_year: number; jalali_month: number; occurred_at: string;
  amount_rial: number; direction: "in" | "out"; balance_after_rial: number | null;
  bank_tx_type: string | null; description_raw: string;
  counterparty_name: string | null; counterparty_bank: string | null;
  terminal_id: string | null; terminal_kind: string | null;
  counterparty_card: string | null; counterparty_iban: string | null;
  deposit_no: string | null; phone_number: string | null; biller_id: string | null;
  loan_ref: string | null;
  category_id: number | null; category_name: string | null; category_color: string | null;
  contact_id: number | null; contact_name: string | null;
  categorized_by: string; is_self_transfer: boolean; is_transfer: boolean;
  needs_review: boolean; note: string | null;
}

export interface TxPage {
  items: Transaction[]; total: number; page: number; page_size: number;
  sum_in_rial: number; sum_out_rial: number;
}

export interface ReviewGroup {
  kind: string; kind_label: string; value: string; count: number;
  total_rial: number; first_seen: string; last_seen: string;
  suggested_name: string | null; bank_tx_type: string | null;
  sample: string; labelable: boolean;
}

export interface Contact {
  id: number; name_fa: string; kind: string; kind_label: string;
  category_id: number | null; category_name: string | null;
  income_category_id: number | null; income_category_name: string | null;
  phone: string | null; is_favorite: boolean; note: string | null;
  transaction_count: number; total_rial: number;
  identifiers: { id: number; kind: string; kind_label: string; value: string }[];
}

export interface Recurring {
  key_kind: string; key_value: string; name: string; category_name: string | null;
  occurrences: number; median_gap_days: number; cadence: string;
  avg_amount_rial: number; last_amount_rial: number; total_paid_rial: number;
  estimated_annual_rial: number; first_seen: string; last_seen: string;
  sample_description: string; amount_stability: number;
  // تعهد ثابت (قسط وام، اجاره) در برابر اشتراک قابل‌قطع
  is_commitment: boolean;
}

export interface MicroSpend {
  threshold_rial: number; count: number; total_rial: number;
  share_of_expense: number;
  by_category: { name: string; color: string; count: number; total_rial: number }[];
}

export interface MomReport {
  current_period: { year: number; month: number; label: string } | null;
  lookback_months: number; factor: number;
  categories: {
    category_id: number | null; name: string; color: string;
    current_rial: number; baseline_rial: number; ratio: number | null;
    is_spike: boolean; delta_rial: number;
  }[];
}

export interface BudgetStatus {
  budget_id: number; category_id: number; category_name: string; color: string;
  amount_rial: number; spent_rial: number; remaining_rial: number;
  ratio: number; is_over: boolean; scope: string;
}

export interface Installment {
  id: number; loan_id: number; seq: number; due_jalali: string; due_date: string;
  days_left: number; amount_rial: number; status: "pending" | "paid" | "overdue";
  paid_jalali: string | null; paid_amount_rial: number | null;
  transaction_id: number | null; note: string | null;
  attachments: Attachment[];
}

export interface Attachment {
  id: number; loan_id: number; installment_id: number | null; url: string;
  original_name: string; mime_type: string; size_bytes: number;
  caption: string | null; uploaded_at: string | null;
}

export interface Loan {
  id: number; title: string; lender: string | null; loan_ref: string | null;
  account_id: number | null; principal_rial: number | null;
  interest_rate: number | null; installment_count: number;
  installment_amount_rial: number; first_due_jalali: string;
  status: string; note: string | null;
  paid_count: number; overdue_count: number; pending_count: number;
  total_rial: number; paid_rial: number; remaining_rial: number; progress: number;
  next_due_jalali: string | null; next_due_days: number | null;
  next_due_amount_rial: number | null;
  installments?: Installment[]; attachments?: Attachment[];
}

export interface Account {
  id: number; bank: string; bank_label: string; title: string;
  iban: string | null; account_number: string | null;
  owner_name: string | null; opened_at_jalali: string | null;
  transaction_count: number;
}

export interface ImportResult {
  import_id: number; account_id: number; bank: string;
  rows_total: number; rows_inserted: number; rows_duplicate: number;
  validation: {
    ok: boolean; rows: number;
    sum_deposit_rial: number; sum_withdraw_rial: number;
    warnings: string[];
    checks: { name: string; status: string; expected?: number; actual?: number; detail?: string }[];
  };
}

// ---------------------------------------------------------------- قرض
export interface DebtEntry {
  id: number; kind: string; kind_label: string; amount_rial: number;
  entry_jalali: string; transaction_id: number | null; note: string | null;
}

export interface DebtSuggestion {
  id: number; jalali_datetime: string; amount_rial: number;
  account_title: string | null; description: string; exact_match: boolean;
}

export interface Debt {
  id: number; contact_id: number | null; person_name: string;
  account_id: number | null; account_title: string | null; is_cash: boolean;
  direction: "i_lent" | "i_borrowed"; direction_label: string;
  principal_rial: number; repaid_rial: number; outstanding_rial: number;
  progress: number; opened_jalali: string; due_jalali: string | null;
  status: string; note: string | null; entries?: DebtEntry[];
}

export interface DebtSummary {
  i_am_owed_rial: number; i_owe_rial: number;
  lent_count: number; borrowed_count: number; net_rial: number;
}

// ---------------------------------------------------------------- پیوندها
export interface TxBrief {
  id: number; account_id: number; account_title: string | null;
  jalali_datetime: string; amount_rial: number; direction: string;
  bank_tx_type: string | null; description_raw: string;
}

export interface TxLink {
  id: number; kind: string; kind_label: string; amount_rial: number;
  seconds_apart: number; confidence: number; matched_by: string;
  is_confirmed: boolean; primary: TxBrief | null; secondary: TxBrief | null;
}

export type LinkSummary = Record<
  string,
  { count: number; total_rial: number; confirmed: number }
>;

// ---------------------------------------------------------------- بازار
export interface Quota {
  provider: string; provider_label: string;
  window: string; window_label: string;
  used: number; limit: number; reserve: number;
  remaining: number; usable: number; configured: boolean;
}

export interface MarketItem {
  code: string; label_fa: string; kind: string; unit_fa: string;
  is_tracked: boolean; latest_rial: number | null; latest_date: string | null;
  change_percent: number | null;
}

export interface PricePoint {
  date: string; jalali_date: string; close_rial: number;
  open_rial: number | null; high_rial: number | null; low_rial: number | null;
}

export interface ItemStats {
  code: string; has_data: boolean;
  latest_rial?: number; latest_date?: string; points?: number;
  change_7d: number | null; change_30d: number | null;
  change_90d: number | null; change_365d: number | null;
  ma_7: number | null; ma_30: number | null; ma_90: number | null;
  high_rial?: number; high_date?: string;
  low_rial?: number; low_date?: string;
  from_high: number | null; volatility_annual: number | null;
}

export interface Observation {
  item_code: string;
  item_label: string;
  tone: "gain" | "loss" | "neutral";
  text: string;
}

export interface PriceAlert {
  id: number;
  item_code: string;
  item_label: string;
  direction: "above" | "below";
  direction_label: string;
  threshold_rial: number;
  current_rial: number | null;
  is_active: boolean;
  is_triggered: boolean;
  note: string | null;
}

export interface ImportPreview {
  bank: string;
  bank_label: string;
  account_id: number | null;
  account_title: string | null;
  creates_account: boolean;
  owner_name: string | null;
  iban: string | null;
  account_number: string | null;
  period_from_jalali: string | null;
  period_to_jalali: string | null;
  rows_total: number;
  rows_new: number;
  rows_duplicate: number;
  validation: { checks: { name: string; status: string; expected?: number; actual?: number }[] };
  warnings: { level: string; text: string }[];
}

export interface IncomeGroup {
  kind: string;
  value: string;
  label: string;
  count: number;
  total_rial: number;
  first_jalali: string;
  last_jalali: string;
  sample_note: string | null;
  bank_tx_type: string | null;
  transaction_ids: number[];
}

export interface Holding {
  id: number; item_code: string; item_label: string; unit_fa: string;
  change_percent: number | null;
  quantity: number; acquired_jalali: string;
  cost_rial: number | null; unit_price_rial: number | null;
  value_rial: number | null; profit_rial: number | null;
  profit_ratio: number | null; price_date: string | null; note: string | null;
}

export interface Portfolio {
  holdings: Holding[]; total_value_rial: number; total_cost_rial: number;
  today_change_rial: number;
  total_profit_rial: number | null; total_profit_ratio: number | null;
}

// ---------------------------------------------------------------- تنظیمات
export interface MarketSettings {
  market_provider: string;
  brsapi_key_set: boolean;
  brsapi_key_hint: string | null;
  navasan_key_set: boolean;
  navasan_key_hint: string | null;
  password_is_custom: boolean;
  providers: { name: string; label_fa: string; key_setting: string }[];
}

// ---------------------------------------------------------------- لیست نیازها
export interface WishItem {
  id: number; title: string;
  estimated_rial: number | null; actual_rial: number | null;
  difference_rial: number | null;
  priority: string; priority_label: string;
  category_id: number | null; category_name: string | null;
  deadline_jalali: string | null; days_left: number | null;
  is_overdue: boolean; is_soon: boolean;
  url: string | null; image_url: string | null;
  is_bought: boolean; bought_jalali: string | null;
  bought_transaction_id: number | null; note: string | null;
}

export interface WishList {
  items: WishItem[]; open_count: number;
  open_total_rial: number; overdue_count: number;
}

export interface WishSuggestion {
  id: number; jalali_datetime: string; amount_rial: number;
  description: string; category_name: string | null;
}
