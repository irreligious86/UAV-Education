/*
 * Multi-user backend switch (docs/MULTIUSER-PLAN.md, section 8 "Going live").
 * enabled: false  → the site works exactly as before (progress only in this browser).
 * enabled: true   → accounts, server progress, admin page. Put the Supabase Project URL and the
 *                   *anon* public key here. Never the service_role key: it bypasses all access rules.
 */
window.UAV_BACKEND = window.UAV_BACKEND || {
  enabled: false,
  url: "",
  anonKey: ""
};
