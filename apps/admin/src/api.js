const API_BASE_URL = (import.meta.env.VITE_API_URL || `${window.location.origin}/api/v1`).replace(/\/$/, "");

export class APIError extends Error {
  constructor(message, status, body) {
    super(message);
    this.name = "APIError";
    this.status = status;
    this.body = body;
  }
}

async function request(path, { token, storeId, ...options } = {}) {
  const headers = new Headers(options.headers || {});
  if (options.body && !(options.body instanceof FormData) && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (storeId) headers.set("X-Store-ID", storeId);
  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers, credentials: "include" });
  const contentType = response.headers.get("content-type") || "";
  const body = contentType.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    const detail = typeof body === "object" && body?.detail ? body.detail : `Request failed (${response.status})`;
    throw new APIError(detail, response.status, body);
  }
  return body;
}

const json = (method, body) => ({ method, body: JSON.stringify(body) });

export const api = {
  baseUrl: API_BASE_URL,
  register: (body) => request("/auth/register", json("POST", body)),
  verifyEmail: (token) => request("/auth/verify-email", json("POST", { token })),
  login: (body) => request("/auth/login", json("POST", body)),
  refreshSession: () => request("/auth/refresh", { method: "POST" }),
  logout: () => request("/auth/logout", { method: "POST" }),
  requestPasswordReset: (email) => request("/auth/request-password-reset", json("POST", { email })),
  resetPassword: (body) => request("/auth/reset-password", json("POST", body)),
  me: (token) => request("/auth/me", { token }),
  updateProfile: (token, body) => request("/auth/me", { ...json("PATCH", body), token }),
  updatePreferences: (token, preferences) => request("/auth/me/preferences", { ...json("PATCH", { preferences }), token }),
  changePassword: (token, body) => request("/auth/change-password", { ...json("POST", body), token }),
  setupWorkspace: (token, body) => request("/workspaces/setup", { ...json("POST", body), token }),
  currentWorkspace: (token, storeId) => request("/workspaces/current", { token, storeId }),
  updateCompany: (token, body) => request("/company", { ...json("PATCH", body), token }),
  stores: (token, params = {}) => {
    const query = new URLSearchParams(Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== ""));
    return request(`/stores${query.toString() ? `?${query}` : ""}`, { token });
  },
  updateStore: (token, storeId, body) => request(`/stores/${storeId}`, { ...json("PATCH", body), token }),
  createStore: (token, body) => request("/stores", { ...json("POST", body), token }),
  plans: () => request("/plans"),
  currencies: () => request("/currencies"),
  companyCurrencies: (token) => request("/settings/currencies", { token }),
  updateCompanyCurrencies: (token, body) => request("/settings/currencies", { ...json("PUT", body), token }),
  exchangeRates: (token, params = {}) => {
    const query = new URLSearchParams(Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== ""));
    return request(`/exchange-rates${query.toString() ? `?${query}` : ""}`, { token });
  },
  quoteExchangeRate: (token, params) => {
    const { storeId, ...queryParams } = params;
    return request(`/exchange-rates/quote?${new URLSearchParams(queryParams)}`, { token, storeId });
  },
  createExchangeRate: (token, body) => request("/exchange-rates", { ...json("POST", body), token }),
  updateExchangeRate: (token, id, body) => request(`/exchange-rates/${id}`, { ...json("PATCH", body), token }),
  categories: (token) => request("/categories", { token }),
  createCategory: (token, body) => request("/categories", { ...json("POST", body), token }),
  updateCategory: (token, id, body) => request(`/categories/${id}`, { ...json("PATCH", body), token }),
  deleteCategory: (token, id) => request(`/categories/${id}`, { method: "DELETE", token }),
  products: (token, storeId, params = {}) => {
    const query = new URLSearchParams(Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== ""));
    return request(`/products${query.toString() ? `?${query}` : ""}`, { token, storeId });
  },
  createProduct: (token, storeId, body) => request("/products", { ...json("POST", body), token, storeId }),
  updateProduct: (token, storeId, id, body) => request(`/products/${id}`, { ...json("PATCH", body), token, storeId }),
  deleteProduct: (token, storeId, id) => request(`/products/${id}`, { method: "DELETE", token, storeId }),
  inventory: (token, storeId, lowStock = false) => request(`/inventory${lowStock ? "?low_stock=true" : ""}`, { token, storeId }),
  transferStock: (token, storeId, body) => request("/inventory/transfers", { ...json("POST", body), token, storeId }),
  adjustInventory: (token, storeId, productId, body) => request(`/inventory/${productId}`, { ...json("PATCH", body), token, storeId }),
  restockInventory: (token, storeId, productId, body) => request(`/inventory/${productId}/restock`, { ...json("POST", body), token, storeId }),
  createOrder: (token, storeId, body) => request("/orders", { ...json("POST", body), token, storeId }),
  orders: (token, storeId, params = {}) => {
    const query = new URLSearchParams(Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== ""));
    return request(`/orders${query.toString() ? `?${query}` : ""}`, { token, storeId });
  },
  cancelOrder: (token, storeId, id) => request(`/orders/${id}/cancel`, { ...json("POST", {}), token, storeId }),
  order: (token, storeId, id) => request(`/orders/${id}`, { token, storeId }),
  completeMockPayment: (externalId) => request(`/mock/chamabapay/${externalId}/complete`, { ...json("POST", {}) }),
  heldOrders: (token, storeId) => request("/held-orders", { token, storeId }),
  createHeldOrder: (token, storeId, body) => request("/held-orders", { ...json("POST", body), token, storeId }),
  deleteHeldOrder: (token, storeId, id) => request(`/held-orders/${id}`, { method: "DELETE", token, storeId }),
  orderRefunds: (token, storeId, orderId) => request(`/orders/${orderId}/refunds`, { token, storeId }),
  refundOrder: (token, storeId, orderId, body) => request(`/orders/${orderId}/refund`, { ...json("POST", body), token, storeId }),
  emailReceipt: (token, storeId, orderId) => request(`/orders/${orderId}/email-receipt`, { ...json("POST", {}), token, storeId }),
  customers: (token, params = {}) => {
    const query = new URLSearchParams(Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== ""));
    return request(`/customers${query.toString() ? `?${query}` : ""}`, { token });
  },
  currentShift: (token, storeId) => request("/shifts/open", { token, storeId }),
  openShift: (token, storeId, body) => request("/shifts/open", { ...json("POST", body), token, storeId }),
  closeShift: (token, storeId, id, body) => request(`/shifts/${id}/close`, { ...json("POST", body), token, storeId }),
  shifts: (token, storeId) => request("/shifts", { token, storeId }),
  notifications: (token) => request("/notifications", { token }),
  markNotificationRead: (token, id) => request(`/notifications/${id}/read`, { ...json("PATCH", {}), token }),
  markAllNotificationsRead: (token) => request("/notifications/read-all", { ...json("POST", {}), token }),
  createCustomer: (token, body) => request("/customers", { ...json("POST", body), token }),
  updateCustomer: (token, id, body) => request(`/customers/${id}`, { ...json("PATCH", body), token }),
  deleteCustomer: (token, id) => request(`/customers/${id}`, { method: "DELETE", token }),
  customerDetail: (token, id) => request(`/customers/${id}`, { token }),
  reportSummary: (token, storeId, params = {}) => {
    const query = new URLSearchParams(Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== ""));
    return request(`/reports/summary${query.toString() ? `?${query}` : ""}`, { token, storeId });
  },
  consolidatedReport: (token, params = {}) => {
    const query = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value === undefined || value === null || value === "") return;
      if (Array.isArray(value)) value.forEach((item) => query.append(key, item));
      else query.append(key, value);
    });
    const queryString = query.toString();
    return request(`/reports/consolidated${queryString ? `?${queryString}` : ""}`, { token });
  },
  team: (token) => request("/team", { token }),
  invite: (token, body) => request("/team/invitations", { ...json("POST", body), token }),
  teamInvitations: (token) => request("/team/invitations", { token }),
  deleteInvitation: (token, id) => request(`/team/invitations/${id}`, { method: "DELETE", token }),
  acceptTeamInvitation: (token, id) => request(`/team/invitations/${id}/accept-by-owner`, { ...json("POST", {}), token }),
  acceptInvitation: (body) => request("/team/invitations/accept", json("POST", body)),
  updateTeamMember: (token, membershipId, body) => request(`/team/${membershipId}`, { ...json("PATCH", body), token }),
  removeTeamMember: (token, membershipId) => request(`/team/${membershipId}`, { method: "DELETE", token }),
  subscription: (token) => request("/billing/subscription", { token }),
  billingPayments: (token) => request("/billing/payments", { token }),
  billingCheckout: (token, body) => request("/billing/checkout", { ...json("POST", body), token }),
  adminOverview: (token) => request("/admin/overview", { token }),
  adminFunnel: (token, days) => request(`/admin/funnel${days ? `?days=${days}` : ""}`, { token }),
  adminSalesAnalytics: (token, days) => request(`/admin/sales-analytics${days ? `?days=${days}` : ""}`, { token }),
  adminRetention: (token, weeks) => request(`/admin/retention${weeks ? `?weeks=${weeks}` : ""}`, { token }),
  adminAttention: (token) => request("/admin/attention", { token }),
  adminSearch: (token, q) => request(`/admin/search?q=${encodeURIComponent(q)}`, { token }),
  adminExportUsersCsv: (token) => request("/admin/export/users.csv", { token }),
  adminExportCompaniesCsv: (token) => request("/admin/export/companies.csv", { token }),
  adminUsers: (token, params = {}) => {
    const query = new URLSearchParams(Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== ""));
    return request(`/admin/users${query.toString() ? `?${query}` : ""}`, { token });
  },
  adminUpdateUser: (token, id, body) => request(`/admin/users/${id}`, { ...json("PATCH", body), token }),
  adminUserDetail: (token, id) => request(`/admin/users/${id}`, { token }),
  adminCompanies: (token, params = {}) => {
    const query = new URLSearchParams(Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== ""));
    return request(`/admin/companies${query.toString() ? `?${query}` : ""}`, { token });
  },
  adminUpdateCompany: (token, id, body) => request(`/admin/companies/${id}`, { ...json("PATCH", body), token }),
  adminCompanyDetail: (token, id) => request(`/admin/companies/${id}`, { token }),
  adminStores: (token, params = {}) => {
    const query = new URLSearchParams(Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== ""));
    return request(`/admin/stores${query.toString() ? `?${query}` : ""}`, { token });
  },
  adminUpdateStore: (token, id, body) => request(`/admin/stores/${id}`, { ...json("PATCH", body), token }),
  adminSubscriptions: (token, params = {}) => {
    const query = new URLSearchParams(Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== ""));
    return request(`/admin/subscriptions${query.toString() ? `?${query}` : ""}`, { token });
  },
  adminBillingPayments: (token, params = {}) => {
    const query = new URLSearchParams(Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== ""));
    return request(`/admin/billing-payments${query.toString() ? `?${query}` : ""}`, { token });
  },
  adminBillingAnalytics: (token) => request("/admin/billing-analytics", { token }),
  adminPaymentLinks: (token, params = {}) => {
    const query = new URLSearchParams(Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== ""));
    return request(`/admin/payment-links${query.toString() ? `?${query}` : ""}`, { token });
  },
  adminUpdatePaymentLink: (token, scope, id, body) => request(`/admin/payment-links/${scope}/${id}`, { ...json("PATCH", body), token }),
  chamabapaySettings: (token) => request("/admin/chamabapay-settings", { token }),
  updateChamabapaySettings: (token, body) => request("/admin/chamabapay-settings", { ...json("PATCH", body), token }),
  revealChamabapaySecret: (token, field) => request("/admin/chamabapay-settings/reveal", { ...json("POST", { field }), token }),
  auditLogs: (token) => request("/audit-logs", { token }),
  gdtCsv: (token, storeId, params = {}) => {
    const query = new URLSearchParams(Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== ""));
    return request(`/reports/gdt-csv${query.toString() ? `?${query}` : ""}`, { token, storeId });
  },  suppliers: (token) => request("/suppliers", { token }),
  updateSupplier: (token, id, body) => request(`/suppliers/${id}`, { ...json("PATCH", body), token }),
  deleteSupplier: (token, id) => request(`/suppliers/${id}`, { method: "DELETE", token }),  purchases: (token, storeId) => request("/purchases", { token, storeId }),  createPurchase: (token, storeId, body) => request("/purchases", { ...json("POST", body), token, storeId }),  receivePurchase: (token, storeId, id) => request(`/purchases/${id}/receive`, { ...json("POST", {}), token, storeId }),
  cancelPurchase: (token, storeId, id) => request(`/purchases/${id}/cancel`, { ...json("POST", {}), token, storeId }),
  deletePurchase: (token, storeId, id) => request(`/purchases/${id}`, { method: "DELETE", token, storeId }),  createSupplier: (token, body) => request("/suppliers", { ...json("POST", body), token }),  adminActivity: (token, params = {}) => {
    const query = new URLSearchParams(Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== ""));
    return request(`/admin/activity${query.toString() ? `?${query}` : ""}`, { token });
  },
  adminPlans: (token, params = {}) => {
    const query = new URLSearchParams(Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== ""));
    return request(`/admin/plans${query.toString() ? `?${query}` : ""}`, { token });
  },
  adminCreatePlan: (token, body) => request("/admin/plans", { ...json("POST", body), token }),
  adminUpdatePlan: (token, code, body) => request(`/admin/plans/${code}`, { ...json("PATCH", body), token }),
  adminMailSettings: (token) => request("/admin/mail-settings", { token }),
  adminUpdateMailSettings: (token, body) => request("/admin/mail-settings", { ...json("PATCH", body), token }),
  adminSessionSettings: (token) => request("/admin/session-settings", { token }),
  adminUpdateSessionSettings: (token, body) => request("/admin/session-settings", { ...json("PATCH", body), token }),
  adminRevealMailSecret: (token, field = "api_key") => request("/admin/mail-settings/reveal", { ...json("POST", { field }), token }),
  adminTestMail: (token, to) => request("/admin/mail-settings/test", { ...json("POST", { to }), token }),
  adminAiSettings: (token) => request("/admin/ai-settings", { token }),
  adminUpdateAiSettings: (token, body) => request("/admin/ai-settings", { ...json("PATCH", body), token }),
  adminRevealAiSecret: (token) => request("/admin/ai-settings/reveal", { ...json("POST", {}), token }),
  adminTestAi: (token) => request("/admin/ai-settings/test", { ...json("POST", {}), token }),
  adminMailingDraft: (token, body) => request("/admin/mailing/draft", { ...json("POST", body), token }),
  adminMailingAudience: (token, params = {}) => {
    const query = new URLSearchParams(Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== ""));
    return request(`/admin/mailing/audience${query.toString() ? `?${query}` : ""}`, { token });
  },
  adminMailingDrip: (token) => request("/admin/mailing/drip", { token }),
  adminUpdateMailingDrip: (token, body) => request("/admin/mailing/drip", { ...json("PUT", body), token }),
  adminRunMailingDrip: (token) => request("/admin/mailing/drip/run", { ...json("POST", {}), token }),
  adminRunMailingQueue: (token) => request("/admin/mailing/queue/run", { ...json("POST", {}), token }),
  adminMailingTokens: (token) => request("/admin/mailing/tokens", { token }),
  adminUploadMailingImage: (token, file) => {
    const body = new FormData();
    body.append("file", file);
    return request("/admin/mailing/images", { method: "POST", body, token });
  },
  adminMailingTemplates: (token) => request("/admin/mailing/templates", { token }),
  adminCreateMailingTemplate: (token, body) => request("/admin/mailing/templates", { ...json("POST", body), token }),
  adminUpdateMailingTemplate: (token, id, body) => request(`/admin/mailing/templates/${id}`, { ...json("PATCH", body), token }),
  adminDeleteMailingTemplate: (token, id) => request(`/admin/mailing/templates/${id}`, { method: "DELETE", token }),
  adminSendMailing: (token, body) => request("/admin/mailing/send", { ...json("POST", body), token }),
  adminMailingSends: (token, limit = 50) => request(`/admin/mailing/sends?limit=${limit}`, { token }),
  adminMailingSuppressions: (token, limit = 100) => request(`/admin/mailing/suppressions?limit=${limit}`, { token }),
  adminDeleteMailingSuppression: (token, id) => request(`/admin/mailing/suppressions/${id}`, { method: "DELETE", token }),
  adminSupportInsights: (token, windowDays = 30) => request(`/admin/support/insights?window_days=${windowDays}`, { token }),
  adminHelpArticles: (token) => request("/admin/help/articles", { token }),
  adminCreateHelpArticle: (token, body) => request("/admin/help/articles", { ...json("POST", body), token }),
  adminUpdateHelpArticle: (token, id, body) => request(`/admin/help/articles/${id}`, { ...json("PATCH", body), token }),
  adminDeleteHelpArticle: (token, id) => request(`/admin/help/articles/${id}`, { method: "DELETE", token }),
};
