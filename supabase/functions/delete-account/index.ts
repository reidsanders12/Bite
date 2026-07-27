// Bite -- Account deletion Edge Function.
//
// Why this exists: deleting a Supabase auth user requires the service-role
// key (`auth.admin.deleteUser`), which must never live in the shipped app --
// same reasoning as gemini-proxy holding the real Gemini key server-side.
// This function checks the caller is a real signed-in user, deletes their
// rows from every table that references auth.users(id) *without* an
// `on delete cascade` (profiles and gemini_usage already cascade, see
// supabase_circles_schema.sql / supabase_gemini_proxy_schema.sql -- this
// function still deletes everything else explicitly, before deleting the
// user), then deletes the auth user itself.
//
// Deploy: supabase functions deploy delete-account
// No new secrets needed -- reuses the same SUPABASE_URL/SUPABASE_ANON_KEY/
// SUPABASE_SERVICE_ROLE_KEY already injected for every function.

import { createClient } from "jsr:@supabase/supabase-js@2";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SUPABASE_ANON_KEY = Deno.env.get("SUPABASE_ANON_KEY")!;
const SUPABASE_SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;

function jsonResponse(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

Deno.serve(async (req) => {
  if (req.method !== "POST") {
    return jsonResponse({ error: "Method not allowed" }, 405);
  }

  const authHeader = req.headers.get("Authorization") ?? "";
  const jwt = authHeader.replace(/^Bearer\s+/i, "").trim();
  if (!jwt) {
    return jsonResponse({ error: "Missing bearer token" }, 401);
  }

  // Same pattern as gemini-proxy: the platform's own verify_jwt gate already
  // rejects malformed/expired tokens, but this is what actually gets us the
  // caller's user id, and is cheap insurance if that gate is ever disabled.
  const authClient = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
    global: { headers: { Authorization: authHeader } },
  });
  const { data: userData, error: userErr } = await authClient.auth.getUser(jwt);
  if (userErr || !userData?.user) {
    return jsonResponse({ error: "Invalid or expired session -- please sign in again." }, 401);
  }
  const userId = userData.user.id;

  const admin = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY);

  // Order matters: circle_members/circle_checkins rows for circles this user
  // merely belongs to (not owns) are cleared first, then circles they
  // created -- which cascades away any *remaining* circle_members/
  // circle_checkins rows for those circles (that FK -> circles.id already
  // has on delete cascade), i.e. the circle disappears for every member,
  // same as the existing manual "delete circle" flow already does.
  const cleanupSteps: Array<{ table: string; column: string }> = [
    { table: "circle_checkins", column: "user_id" },
    { table: "circle_members", column: "user_id" },
    { table: "circles", column: "created_by" },
    { table: "workout_logs", column: "user_id" },
    { table: "weight_logs", column: "user_id" },
    { table: "food_logs", column: "user_id" },
    { table: "user_goals", column: "user_id" },
  ];

  for (const step of cleanupSteps) {
    const { error } = await admin.from(step.table).delete().eq(step.column, userId);
    if (error) {
      console.error(`[delete-account] cleanup failed on ${step.table}:`, error);
      return jsonResponse({ error: `Couldn't delete account data (${step.table}). Please try again.` }, 500);
    }
  }

  const { error: deleteUserErr } = await admin.auth.admin.deleteUser(userId);
  if (deleteUserErr) {
    console.error("[delete-account] deleteUser failed:", deleteUserErr);
    return jsonResponse({ error: "Couldn't delete your account. Please try again." }, 500);
  }

  return jsonResponse({ ok: true }, 200);
});
