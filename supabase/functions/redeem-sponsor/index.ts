// Bite -- Sponsor redemption verification page.
//
// Why this exists: the "Redeem" button on a sponsor card (home_view.py)
// shows a QR code that encodes a link to *this* function
// (`{SUPABASE_URL}/functions/v1/redeem-sponsor?code=...`). Sponsor staff
// scan it with any phone camera -- no Bite account, no app -- and land
// here. This is the only place `sponsor_redemptions.redemption_count`
// ever gets written, via the redeem_sponsor_code() RPC (SECURITY DEFINER,
// see supabase_circles_schema.sql -- there's deliberately no update policy
// for authenticated users on that table), so a redemption count sponsors
// are shown actually reflects someone scanning the code in person, not
// just a user opening the dialog on their own phone. The RPC also takes a
// row lock (`for update`) while it checks the count, so two near-
// simultaneous scans of the same code can't both slip past
// sponsors.max_redemptions_per_user.
//
// Public by design: verify_jwt is turned off for this function alone (see
// supabase/config.toml) -- unlike gemini-proxy/delete-account, which
// require a live session -- since staff have no Bite login to present.
// `code` is a long random token (see app/database.py's
// get_or_create_sponsor_redemption), so this is the same "unguessable
// capability URL" trust model as an emailed unsubscribe link -- not a
// security boundary, just enough friction that no one stumbles into it by
// accident.
//
// Deploy: supabase functions deploy redeem-sponsor
// (config.toml's [functions.redeem-sponsor] verify_jwt=false covers the
// --no-verify-jwt flag automatically -- no need to pass it by hand.)

import { createClient } from "jsr:@supabase/supabase-js@2";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SUPABASE_SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function htmlPage(heading: string, body: string, tone: "ok" | "warn" | "error"): Response {
  const color = tone === "ok" ? "#4F7942" : tone === "warn" ? "#C1652F" : "#B3261E";
  const html = `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Bite Redemption</title>
<style>
  body { margin:0; padding:32px 16px; display:flex; justify-content:center; align-items:center; min-height:100vh; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; background:#FAF3EA; color:#2B2622; }
  .card { max-width:360px; width:100%; text-align:center; }
  h1 { font-size:20px; margin:0 0 8px; color:${color}; }
  p { font-size:14px; color:#75695A; line-height:1.5; margin:0; }
</style>
</head>
<body>
  <div class="card">
    <h1>${escapeHtml(heading)}</h1>
    <p>${body}</p>
  </div>
</body>
</html>`;
  return new Response(html, {
    status: tone === "error" ? 404 : 200,
    headers: {
      "Content-Type": "text/html; charset=utf-8",
      // Every outcome here reflects live per-request state (valid/limit
      // reached/invalid, current redemption count) -- without this, a
      // CDN or the browser itself can cache one outcome and keep serving
      // it on a later scan. Observed in practice: the same URL flip-
      // flopping between a correct text/html response and a stale
      // gateway-level text/plain 404 with x-content-type-options:nosniff
      // (which is what made Safari show raw HTML source instead of
      // rendering it -- nosniff stops it from guessing past a stale
      // plain-text header).
      "Cache-Control": "no-store",
    },
  });
}

interface RedeemResult {
  outcome: "ok" | "limit_reached";
  sponsor_title: string;
  sponsor_subtitle: string;
  redemption_count: number;
  max_redemptions_per_user: number | null;
  redeemed_at: string;
}

Deno.serve(async (req) => {
  const url = new URL(req.url);
  const code = (url.searchParams.get("code") ?? "").trim();

  if (!code) {
    return htmlPage("Missing code", "This link is missing a redemption code.", "error");
  }

  const admin = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY);

  const { data, error } = await admin.rpc("redeem_sponsor_code", { p_code: code });

  if (error) {
    console.error("[redeem-sponsor] redeem_sponsor_code failed:", error);
    return htmlPage("Something went wrong", "Please try scanning again.", "error");
  }

  const result = (data as RedeemResult[] | null)?.[0];
  if (!result) {
    return htmlPage("Invalid code", "This redemption code doesn't match any offer.", "error");
  }

  const offerLine = `${escapeHtml(result.sponsor_title)} — ${escapeHtml(result.sponsor_subtitle)}`;
  const usageLine = result.max_redemptions_per_user != null
    ? `Used ${result.redemption_count} of ${result.max_redemptions_per_user}.`
    : `Used ${result.redemption_count} time${result.redemption_count === 1 ? "" : "s"}.`;

  if (result.outcome === "limit_reached") {
    return htmlPage(
      "Redemption limit reached",
      `${offerLine}<br>${escapeHtml(usageLine)}`,
      "warn",
    );
  }

  return htmlPage("Valid — redeemed just now", `${offerLine}<br>${escapeHtml(usageLine)}`, "ok");
});
