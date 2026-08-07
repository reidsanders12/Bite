// Bite -- Sponsor redemption verification page.
//
// Why this exists: the "Redeem" button on a sponsor card (home_view.py)
// shows a QR code that encodes a link to *this* function
// (`{SUPABASE_URL}/functions/v1/redeem-sponsor?code=...`). Sponsor staff
// scan it with any phone camera -- no Bite account, no app -- and land
// here. This is the only place `sponsor_redemptions.redeemed_at` ever gets
// written (see supabase_circles_schema.sql: there's deliberately no update
// policy for authenticated users), so a redemption count sponsors are
// shown actually reflects someone scanning the code in person, not just a
// user opening the dialog on their own phone.
//
// Public by design: deploy with `--no-verify-jwt` (unlike gemini-proxy/
// delete-account, which require a live session) since staff have no Bite
// login to present. `code` is a long random token (see
// app/database.py's create_sponsor_redemption), so this is the same
// "unguessable capability URL" trust model as an emailed unsubscribe link
// -- not a security boundary, just enough friction that no one stumbles
// into it by accident.
//
// Deploy: supabase functions deploy redeem-sponsor --no-verify-jwt

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
    headers: { "Content-Type": "text/html; charset=utf-8" },
  });
}

Deno.serve(async (req) => {
  const url = new URL(req.url);
  const code = (url.searchParams.get("code") ?? "").trim();

  if (!code) {
    return htmlPage("Missing code", "This link is missing a redemption code.", "error");
  }

  const admin = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY);

  const { data: redemption, error: fetchErr } = await admin
    .from("sponsor_redemptions")
    .select("id, redeemed_at, sponsors(title, subtitle)")
    .eq("code", code)
    .maybeSingle();

  if (fetchErr) {
    console.error("[redeem-sponsor] lookup failed:", fetchErr);
    return htmlPage("Something went wrong", "Please try scanning again.", "error");
  }
  if (!redemption) {
    return htmlPage("Invalid code", "This redemption code doesn't match any offer.", "error");
  }

  const sponsor = redemption.sponsors as unknown as { title: string; subtitle: string } | null;
  const offerLine = sponsor
    ? `${escapeHtml(sponsor.title)} — ${escapeHtml(sponsor.subtitle)}`
    : "This offer";

  if (redemption.redeemed_at) {
    const when = new Date(redemption.redeemed_at as string).toLocaleString();
    return htmlPage(
      "Already redeemed",
      `${offerLine}<br>First redeemed ${escapeHtml(when)}.`,
      "warn",
    );
  }

  const { error: updateErr } = await admin
    .from("sponsor_redemptions")
    .update({ redeemed_at: new Date().toISOString() })
    .eq("id", redemption.id)
    .is("redeemed_at", null);

  if (updateErr) {
    console.error("[redeem-sponsor] update failed:", updateErr);
    return htmlPage("Something went wrong", "Please try scanning again.", "error");
  }

  return htmlPage("Valid — redeemed just now", offerLine, "ok");
});
