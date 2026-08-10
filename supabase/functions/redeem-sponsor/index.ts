// Bite -- Sponsor redemption verification page.
//
// Why this exists: the "Redeem" button on a sponsor card (home_view.py)
// shows a QR code that encodes a link to *this* function
// (`{SUPABASE_URL}/functions/v1/redeem-sponsor?code=...`). Sponsor staff
// scan it with any phone camera -- no Bite account, no app -- and land
// here.
//
// Two-step flow (GET then POST), not a single auto-redeeming GET: the QR
// can be scanned by anyone who sees it on the customer's screen, not just
// staff, so simply loading the page must never count as a redemption.
//   - GET  shows the offer + current usage via the read-only
//     get_sponsor_redemption_status() RPC, with a "Mark as Used" button
//     staff tap themselves.
//   - POST (that button's form submit) is the only thing that actually
//     writes anything, via redeem_sponsor_code() (SECURITY DEFINER, see
//     supabase_circles_schema.sql -- there's deliberately no update policy
//     for authenticated users on that table). It also takes a row lock
//     (`for update`) while it checks the count, so two near-simultaneous
//     taps can't both slip past sponsors.max_redemptions_per_user.
//
// Public by design: verify_jwt is turned off for this function alone (see
// supabase/config.toml) -- unlike gemini-proxy/delete-account, which
// require a live session -- since staff have no Bite login to present.
// `code` is a long random token (see app/database.py's
// get_or_create_sponsor_redemption), so this is the same "unguessable
// capability URL" trust model as an emailed unsubscribe link -- not a
// security boundary, just enough friction that no one stumbles into it by
// accident. The POST step on top of that means even someone who does open
// the link can't silently burn the customer's redemption themselves.
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

function htmlPage(heading: string, bodyHtml: string, tone: "ok" | "warn" | "error", status = 200): Response {
  const color = tone === "ok" ? "#4F7942" : tone === "warn" ? "#C1652F" : "#B3261E";
  const html = `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Bite Redemption</title>
<style>
  body { margin:0; padding:32px 16px; display:flex; justify-content:center; align-items:center; min-height:100vh; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; background:#FAF3EA; color:#2B2622; }
  .card { max-width:360px; width:100%; text-align:center; background:#FFFFFF; border:1px solid #EAE0D3; border-radius:16px; padding:28px 24px; box-shadow:0 4px 16px rgba(43,38,34,0.06); }
  h1 { font-size:20px; margin:0 0 8px; color:${color}; }
  .body { font-size:14px; color:#75695A; line-height:1.5; }
  .badge { display:inline-block; font-size:12px; font-weight:600; letter-spacing:0.02em; color:${color}; background:${tone === "ok" ? "#EAF1E4" : tone === "warn" ? "#FBEADD" : "#FBE7E5"}; border-radius:999px; padding:4px 12px; margin-bottom:14px; }
  form { margin-top:20px; }
  button { font:inherit; font-weight:600; font-size:15px; color:#FFFFFF; background:#4F7942; border:none; border-radius:10px; padding:13px 20px; width:100%; cursor:pointer; }
  button:active { opacity:0.85; }
</style>
</head>
<body>
  <div class="card">
    <h1>${escapeHtml(heading)}</h1>
    <div class="body">${bodyHtml}</div>
  </div>
</body>
</html>`;
  return new Response(html, {
    status,
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
  redeemed_at: string | null;
}

function usageLine(result: RedeemResult): string {
  return result.max_redemptions_per_user != null
    ? `Used ${result.redemption_count} of ${result.max_redemptions_per_user}.`
    : `Used ${result.redemption_count} time${result.redemption_count === 1 ? "" : "s"}.`;
}

function offerLine(result: RedeemResult): string {
  return `${escapeHtml(result.sponsor_title)} — ${escapeHtml(result.sponsor_subtitle)}`;
}

Deno.serve(async (req) => {
  const url = new URL(req.url);
  let code = (url.searchParams.get("code") ?? "").trim();

  if (req.method === "POST" && !code) {
    const form = await req.formData();
    code = String(form.get("code") ?? "").trim();
  }

  if (!code) {
    return htmlPage("Missing code", "This link is missing a redemption code.", "error", 404);
  }

  const admin = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY);

  if (req.method === "POST") {
    const { data, error } = await admin.rpc("redeem_sponsor_code", { p_code: code });

    if (error) {
      console.error("[redeem-sponsor] redeem_sponsor_code failed:", error);
      return htmlPage("Something went wrong", "Please try again.", "error", 500);
    }

    const result = (data as RedeemResult[] | null)?.[0];
    if (!result) {
      return htmlPage("Invalid code", "This redemption code doesn't match any offer.", "error", 404);
    }

    if (result.outcome === "limit_reached") {
      return htmlPage(
        "Redemption limit reached",
        `${offerLine(result)}<br>${escapeHtml(usageLine(result))}`,
        "warn",
      );
    }

    return htmlPage("Marked as used ✓", `${offerLine(result)}<br>${escapeHtml(usageLine(result))}`, "ok");
  }

  // GET: read-only lookup -- never writes, so simply opening this link
  // (which anyone who sees the QR can do) doesn't burn a redemption.
  const { data, error } = await admin.rpc("get_sponsor_redemption_status", { p_code: code });

  if (error) {
    console.error("[redeem-sponsor] get_sponsor_redemption_status failed:", error);
    return htmlPage("Something went wrong", "Please try scanning again.", "error", 500);
  }

  const result = (data as RedeemResult[] | null)?.[0];
  if (!result) {
    return htmlPage("Invalid code", "This redemption code doesn't match any offer.", "error", 404);
  }

  if (result.outcome === "limit_reached") {
    return htmlPage(
      "Redemption limit reached",
      `${offerLine(result)}<br>${escapeHtml(usageLine(result))}`,
      "warn",
    );
  }

  const escapedCode = escapeHtml(code);
  return htmlPage(
    "Bite sponsor offer",
    `<span class="badge">SCAN VERIFIED</span><br>${offerLine(result)}<br>${escapeHtml(usageLine(result))}` +
      // Deliberately NOT url.pathname: Supabase's gateway strips the
      // "/functions/v1" prefix before the function ever sees the request,
      // so url.pathname here is just "/redeem-sponsor" -- posting a form
      // to that from a real browser 404s, since the public path (what the
      // QR itself encodes) is "/functions/v1/redeem-sponsor". Caught by
      // testing the GET response's rendered action attribute directly,
      // not just curling the POST endpoint by hand.
      `<form method="POST" action="/functions/v1/redeem-sponsor">` +
      `<input type="hidden" name="code" value="${escapedCode}">` +
      `<button type="submit">Mark as Used</button>` +
      `</form>`,
    "ok",
  );
});
