// Bite -- Gemini proxy Edge Function.
//
// Why this exists: every AI call used to run straight from the Flet app to
// Gemini using a GEMINI_API_KEY baked into the shipped app's .env. Anyone
// who installed the compiled app could pull that key back out and use it
// outside the app entirely -- unbounded cost, zero per-user throttling.
//
// This function is the fix: it's the *only* thing that holds the real
// Gemini key now (set via `supabase secrets set GEMINI_API_KEY=...`, never
// committed, never shipped to a client). The app builds the exact same
// request payload it always did (system instruction, contents, generation
// config, response schema) and POSTs it here instead of calling Gemini
// directly; this function checks the caller is a real signed-in user,
// enforces a per-user daily cap, forwards the request to Gemini with the
// server-only key, and relays the response back unchanged.
//
// Deploy: supabase functions deploy gemini-proxy
// Secrets needed (supabase secrets set NAME=value):
//   GEMINI_API_KEY  -- your real Gemini key (never in the app's .env anymore)
// SUPABASE_URL / SUPABASE_ANON_KEY / SUPABASE_SERVICE_ROLE_KEY are injected
// automatically by the platform -- you don't set those yourself.
//
// Requires gemini_usage table + increment_gemini_usage() RPC from
// supabase_gemini_proxy_schema.sql (run that once before deploying this).

import { createClient } from "jsr:@supabase/supabase-js@2";

const GEMINI_API_KEY = Deno.env.get("GEMINI_API_KEY")!;
const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SUPABASE_ANON_KEY = Deno.env.get("SUPABASE_ANON_KEY")!;
const SUPABASE_SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;

const GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models";
const DAILY_REQUEST_LIMIT = 100;
// Allow-list, not just a default -- the client picks the model name in its
// request body, and it can't be trusted to only ever send an expected value
// even though it can no longer reach Gemini (or spend your quota) directly.
const ALLOWED_MODELS = new Set(["gemini-2.5-flash"]);

interface ProxyRequestBody {
  model?: string;
  contents?: unknown;
  system_instruction?: string;
  temperature?: number;
  response_mime_type?: string;
  response_schema?: unknown;
}

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

  // The platform's own `verify_jwt` gate (on by default) already rejects
  // malformed/expired tokens before this code runs at all -- this second
  // check is what actually gets us the caller's user id for rate limiting,
  // and is cheap insurance if that platform default is ever turned off.
  const authClient = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
    global: { headers: { Authorization: authHeader } },
  });
  const { data: userData, error: userErr } = await authClient.auth.getUser(jwt);
  if (userErr || !userData?.user) {
    return jsonResponse({ error: "Invalid or expired session -- please sign in again." }, 401);
  }
  const userId = userData.user.id;

  // Service-role client for the usage-counter table only -- that table has
  // zero anon/authenticated policies on purpose (see
  // supabase_gemini_proxy_schema.sql), so only this trusted server code can
  // touch it. Atomic upsert-increment via RPC avoids a read-then-write race
  // between two concurrent requests from the same user.
  const admin = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY);
  const today = new Date().toISOString().slice(0, 10);
  const { data: newCount, error: usageErr } = await admin.rpc("increment_gemini_usage", {
    p_user_id: userId,
    p_usage_date: today,
  });
  if (usageErr) {
    console.error("[gemini-proxy] usage counter failed:", usageErr);
    return jsonResponse({ error: "Rate limit check failed -- please try again." }, 500);
  }
  if ((newCount as number) > DAILY_REQUEST_LIMIT) {
    return jsonResponse(
      { error: `Daily AI request limit reached (${DAILY_REQUEST_LIMIT}/day). Try again tomorrow.` },
      429,
    );
  }

  let body: ProxyRequestBody;
  try {
    body = await req.json();
  } catch {
    return jsonResponse({ error: "Invalid JSON body" }, 400);
  }

  const model = body.model ?? "gemini-2.5-flash";
  if (!ALLOWED_MODELS.has(model)) {
    return jsonResponse({ error: "Unsupported model" }, 400);
  }
  if (!body.contents) {
    return jsonResponse({ error: "Missing 'contents'" }, 400);
  }

  const generationConfig: Record<string, unknown> = {
    temperature: body.temperature ?? 0.2,
  };
  if (body.response_mime_type) generationConfig.responseMimeType = body.response_mime_type;
  if (body.response_schema) generationConfig.responseSchema = body.response_schema;

  const geminiPayload: Record<string, unknown> = {
    contents: body.contents,
    generationConfig,
  };
  if (body.system_instruction) {
    geminiPayload.systemInstruction = { parts: [{ text: body.system_instruction }] };
  }

  let geminiRes: Response;
  try {
    geminiRes = await fetch(`${GEMINI_ENDPOINT}/${model}:generateContent`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-goog-api-key": GEMINI_API_KEY,
      },
      body: JSON.stringify(geminiPayload),
    });
  } catch (err) {
    console.error("[gemini-proxy] upstream fetch failed:", err);
    return jsonResponse({ error: "Couldn't reach Gemini -- please try again." }, 502);
  }

  // Relay Gemini's response body/status through as-is -- the app already
  // knows how to parse Gemini's native response shape, no translation
  // layer needed here.
  const text = await geminiRes.text();
  return new Response(text, {
    status: geminiRes.status,
    headers: { "Content-Type": "application/json" },
  });
});
