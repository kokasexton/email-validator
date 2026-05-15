import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "npm:@supabase/supabase-js@2";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Client-Info, Apikey",
};

// ---------------------------------------------------------------------------
// Validation logic (Deno/TS port of the Python email_validator package)
// ---------------------------------------------------------------------------

const EMAIL_RE =
  /^(?:[a-zA-Z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-zA-Z0-9!#$%&'*+/=?^_`{|}~-]+)*|"(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21\x23-\x5b\x5d-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])*")@(?:(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?\.)+[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?)$/;

const GIBBERISH_PATTERNS = [
  /^[a-z]{1,3}\d{4,}@/i,
  /^test\d*@/i,
  /^[a-z]{1,2}\d{6,}@/i,
  /^[a-z]{20,}@/i,
  /@[a-z0-9]{30,}\./i,
  /^[a-z]+\.\d{3,}@/i,
];

const ROLE_PREFIXES = new Set([
  "admin","info","support","sales","contact","hello","help","marketing",
  "billing","team","jobs","careers","hr","service","office","mail",
  "postmaster","abuse","noreply","no-reply","webmaster","hostmaster",
  "root","news","press","media","accounts","enquiries","enquiry",
  "inquiries","inquiry","orders","customerservice","customer","cs",
  "feedback","donotreply","do-not-reply","mailer-daemon","mailer",
]);

const WEBMAIL_DOMAINS = new Set([
  "gmail.com","googlemail.com","yahoo.com","yahoo.co.uk","hotmail.com",
  "hotmail.co.uk","outlook.com","live.com","msn.com","aol.com","aim.com",
  "icloud.com","me.com","mac.com","protonmail.com","proton.me","pm.me",
  "mail.com","gmx.com","yandex.com","yandex.ru","zoho.com","fastmail.com",
  "fastmail.fm","tutanota.com","tuta.io","hey.com","duck.com","inbox.com",
  "hushmail.com","runbox.com","mailfence.com","startmail.com",
]);

const DISPOSABLE_DOMAINS = new Set([
  "mailinator.com","guerrillamail.com","tempmail.com","10minutemail.com",
  "yopmail.com","throwaway.email","sharklasers.com","trashmail.com",
  "maildrop.cc","harakirimail.com","dispostable.com","getnada.com",
  "tempmail.net","fakeinbox.com","temp-mail.org","guerrillamail.org",
  "guerrillamail.net","guerrillamail.biz","mailcatch.com","spamgourmet.com",
  "spam4.me","moakt.com","mytemp.email","emailondeck.com","tempinbox.com",
  "smailpro.com","tempmail.ninja","burnermail.io","emailfake.com",
  "mailnull.com","discard.email","trashmail.at","filzmail.com",
  "wegwerfmail.de","spamfree24.org","spamgourmet.net","jetable.fr.nf",
]);

function validateSyntax(email: string) {
  if (!email || !email.includes("@")) return { valid: false, regexp: false, gibberish: true };
  const valid = EMAIL_RE.test(email);
  const gibberish = GIBBERISH_PATTERNS.some(p => p.test(email));
  const [local, domain] = email.rsplit?.("@", 1) ?? [email.slice(0, email.lastIndexOf("@")), email.slice(email.lastIndexOf("@") + 1)];
  const finalValid = valid && local.length <= 64 && domain.length <= 255 && !email.includes("..") && !domain.startsWith(".") && !domain.endsWith(".");
  return { valid: finalValid, regexp: finalValid, gibberish };
}

function getDomain(email: string) { return email.slice(email.lastIndexOf("@") + 1).toLowerCase(); }
function getLocal(email: string) { return email.slice(0, email.lastIndexOf("@")).toLowerCase(); }

function isDisposable(email: string) { return DISPOSABLE_DOMAINS.has(getDomain(email)); }
function isWebmail(email: string) { return WEBMAIL_DOMAINS.has(getDomain(email)); }
function isRoleBased(email: string) {
  const local = getLocal(email);
  if (ROLE_PREFIXES.has(local)) return true;
  const base = local.split(/[-._+]/)[0];
  return ROLE_PREFIXES.has(base);
}

async function checkMx(domain: string): Promise<{ hasMx: boolean; hosts: string[]; error?: string }> {
  try {
    const res = await fetch(`https://dns.google/resolve?name=${encodeURIComponent(domain)}&type=MX`);
    const data = await res.json();
    if (data.Status !== 0) return { hasMx: false, hosts: [], error: "domain_not_found" };
    const answers: { data: string }[] = data.Answer ?? [];
    const mxAnswers = answers.filter((a: { type?: number }) => a.type === 15 || !a.type);
    if (mxAnswers.length === 0) {
      // Check A record fallback
      const aRes = await fetch(`https://dns.google/resolve?name=${encodeURIComponent(domain)}&type=A`);
      const aData = await aRes.json();
      if (aData.Status === 0 && (aData.Answer ?? []).length > 0) {
        return { hasMx: true, hosts: [domain] };
      }
      return { hasMx: false, hosts: [], error: "no_dns_mail_route" };
    }
    const hosts = mxAnswers.map((a) => a.data.replace(/\s+\S+$/, "").replace(/\.$/, "").trim());
    return { hasMx: true, hosts };
  } catch (e) {
    return { hasMx: false, hosts: [], error: "dns_timeout" };
  }
}

function computeScore(r: {
  regexp: boolean; gibberish: boolean; disposable: boolean;
  mx_records: boolean; smtp_check: boolean; block: boolean; accept_all: boolean;
}): number {
  let score = 0;
  if (r.regexp) score += 20;
  if (!r.gibberish) score += 10;
  if (!r.disposable) score += 10;
  if (r.mx_records) score += 20;
  if (r.smtp_check) score += 30;
  if (!r.block) score += 10;
  if (r.accept_all) score -= 10;
  return Math.max(0, Math.min(100, score));
}

async function validateEmail(email: string, skipSmtp = false) {
  const syntax = validateSyntax(email);

  if (!syntax.valid) {
    return {
      email, status: "invalid", failure_reason: "syntax_invalid",
      regexp: false, gibberish: syntax.gibberish, disposable: false,
      webmail: false, role_based: false, mx_records: false, smtp_check: false,
      accept_all: false, block: false, smtp_server: null, error: null,
      score: 0,
    };
  }

  const domain = getDomain(email);
  const disposable = isDisposable(email);
  const webmail = isWebmail(email);
  const role_based = isRoleBased(email);

  const mx = await checkMx(domain);

  if (!mx.hasMx) {
    const reason = mx.error ?? "no_dns_mail_route";
    const result = {
      email, status: "invalid" as const, failure_reason: reason,
      regexp: syntax.regexp, gibberish: syntax.gibberish,
      disposable, webmail, role_based,
      mx_records: false, smtp_check: false, accept_all: false, block: false,
      smtp_server: null, error: null, score: 0,
    };
    result.score = computeScore(result);
    return result;
  }

  // Skip SMTP — return valid with DNS-only confidence
  if (skipSmtp) {
    const result = {
      email, status: "valid" as const, failure_reason: null,
      regexp: syntax.regexp, gibberish: syntax.gibberish,
      disposable, webmail, role_based,
      mx_records: true, smtp_check: false, accept_all: false, block: false,
      smtp_server: mx.hosts[0] ?? null, error: null, score: 0,
    };
    result.score = computeScore(result);
    return result;
  }

  // For edge functions we can't open raw TCP port 25, so we return
  // mx_records=true with smtp_check=false and status="unknown" when in
  // the edge runtime. Callers can override with skip_smtp=true for DNS-only.
  const result = {
    email,
    status: "unknown" as const,
    failure_reason: "smtp_disabled",
    regexp: syntax.regexp,
    gibberish: syntax.gibberish,
    disposable,
    webmail,
    role_based,
    mx_records: true,
    smtp_check: false,
    accept_all: false,
    block: false,
    smtp_server: mx.hosts[0] ?? null,
    error: "SMTP checks require direct server access (port 25). Use skip_smtp=true for DNS-only validation or run the local API for full SMTP.",
    score: 0,
  };
  result.score = computeScore(result);
  return result;
}

// ---------------------------------------------------------------------------
// Supabase client
// ---------------------------------------------------------------------------
function getDb() {
  return createClient(
    Deno.env.get("SUPABASE_URL")!,
    Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
  );
}

async function saveJob(results: ReturnType<typeof computeScore extends infer _ ? any : any>[], jobType: string, filename?: string) {
  const db = getDb();
  const counts = results.reduce(
    (a: Record<string, number>, r: { status: string }) => { a[r.status] = (a[r.status] || 0) + 1; return a; },
    {} as Record<string, number>
  );
  const job = await db.from("validation_jobs").insert({
    job_type: jobType,
    status: "completed",
    total_emails: results.length,
    processed_emails: results.length,
    valid_count: counts["valid"] ?? 0,
    invalid_count: counts["invalid"] ?? 0,
    accept_all_count: counts["accept_all"] ?? 0,
    unknown_count: counts["unknown"] ?? 0,
    ...(filename ? { original_filename: filename } : {}),
  }).select("id").single();

  const jobId = job.data?.id as string;
  if (jobId && results.length > 0) {
    const rows = results.map((r: Record<string, unknown>) => ({
      job_id: jobId,
      email: r.email, status: r.status, score: r.score,
      failure_reason: r.failure_reason ?? null,
      regexp: r.regexp, gibberish: r.gibberish, disposable: r.disposable,
      webmail: r.webmail, role_based: r.role_based,
      mx_records: r.mx_records, smtp_check: r.smtp_check,
      accept_all: r.accept_all, block: r.block, smtp_server: r.smtp_server ?? null,
    }));
    await db.from("validation_results").insert(rows);
  }
  return jobId;
}

// ---------------------------------------------------------------------------
// Router
// ---------------------------------------------------------------------------
function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
}

function err(msg: string, status = 400) {
  return json({ detail: msg }, status);
}

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response(null, { status: 200, headers: corsHeaders });

  const url = new URL(req.url);
  // strip /validate prefix added by supabase routing
  const path = url.pathname.replace(/^\/validate/, "") || "/";

  try {
    // GET /health
    if (req.method === "GET" && path === "/health") {
      return json({ status: "ok", version: "2.0.0" });
    }

    // GET /jobs
    if (req.method === "GET" && path === "/jobs") {
      const limit = parseInt(url.searchParams.get("limit") ?? "20");
      const offset = parseInt(url.searchParams.get("offset") ?? "0");
      const db = getDb();
      const { data } = await db.from("validation_jobs").select("*")
        .order("created_at", { ascending: false }).range(offset, offset + limit - 1);
      return json({ jobs: data ?? [] });
    }

    // GET /jobs/:id
    const jobMatch = path.match(/^\/jobs\/([a-f0-9-]+)$/);
    if (req.method === "GET" && jobMatch) {
      const jobId = jobMatch[1];
      const db = getDb();
      const { data: job } = await db.from("validation_jobs").select("*").eq("id", jobId).maybeSingle();
      if (!job) return err("Job not found", 404);
      const { data: results } = await db.from("validation_results").select("*").eq("job_id", jobId);
      return json({ job, results: results ?? [] });
    }

    // GET /jobs/:id/download  (CSV)
    const dlMatch = path.match(/^\/jobs\/([a-f0-9-]+)\/download$/);
    if (req.method === "GET" && dlMatch) {
      const jobId = dlMatch[1];
      const db = getDb();
      const { data } = await db.from("validation_results").select("*").eq("job_id", jobId);
      if (!data?.length) return err("No results found", 404);
      const fields = ["email","status","score","failure_reason","regexp","gibberish","disposable","webmail","role_based","mx_records","smtp_check","accept_all","block","smtp_server"];
      const header = fields.join(",");
      const rows = data.map(r => fields.map(f => {
        const v = (r as Record<string, unknown>)[f];
        return v === null || v === undefined ? "" : String(v).includes(",") ? `"${v}"` : String(v);
      }).join(","));
      const csv = [header, ...rows].join("\n");
      return new Response(csv, {
        headers: {
          ...corsHeaders,
          "Content-Type": "text/csv",
          "Content-Disposition": `attachment; filename=results-${jobId.slice(0, 8)}.csv`,
        },
      });
    }

    // POST /validate/single
    if (req.method === "POST" && path === "/validate/single") {
      const body = await req.json();
      const email = (body.email as string)?.trim();
      if (!email) return err("email is required");
      const skipSmtp = body.skip_smtp === true;
      const result = await validateEmail(email, skipSmtp);
      const jobId = await saveJob([result], "single");
      return json({ job_id: jobId, result });
    }

    // POST /validate/bulk
    if (req.method === "POST" && path === "/validate/bulk") {
      const body = await req.json();
      const emails: string[] = body.emails ?? [];
      if (!emails.length) return err("emails array is required");
      if (emails.length > 500) return err("Maximum 500 emails per bulk request");
      const skipSmtp = body.skip_smtp === true;
      const results = await Promise.all(emails.map(e => validateEmail(e.trim(), skipSmtp)));
      const jobId = await saveJob(results, "batch");
      const summary = { valid: 0, invalid: 0, accept_all: 0, unknown: 0 };
      results.forEach(r => { (summary as Record<string, number>)[r.status]++; });
      return json({ job_id: jobId, total: results.length, results, summary });
    }

    // POST /validate/csv
    if (req.method === "POST" && path === "/validate/csv") {
      const skipSmtp = url.searchParams.get("skip_smtp") === "true";
      const emailColumnHint = url.searchParams.get("email_column") ?? null;
      const formData = await req.formData();
      const file = formData.get("file") as File | null;
      if (!file) return err("file is required");

      const text = await file.text();
      const lines = text.split(/\r?\n/).filter(l => l.trim());
      if (!lines.length) return err("CSV is empty");

      const headers = lines[0].split(",").map(h => h.trim().replace(/^"|"$/g, "").toLowerCase());
      const EMAIL_COL_ALIASES = ["email","e-mail","email address","business_email","emailaddress","mail"];
      const colIdx = emailColumnHint
        ? headers.indexOf(emailColumnHint.toLowerCase())
        : headers.findIndex(h => EMAIL_COL_ALIASES.includes(h));

      if (colIdx === -1) return err(`Could not find email column. Pass ?email_column=<name>. Headers found: ${headers.join(", ")}`);

      const emails = lines.slice(1)
        .map(l => l.split(",")[colIdx]?.trim().replace(/^"|"$/g, "") ?? "")
        .filter(e => e.includes("@"));

      if (emails.length > 10000) return err("Maximum 10,000 rows per CSV upload");
      if (!emails.length) return err("No valid email addresses found in CSV");

      const results = await Promise.all(emails.map(e => validateEmail(e, skipSmtp)));
      const jobId = await saveJob(results, "batch", file.name);
      const summary = { valid: 0, invalid: 0, accept_all: 0, unknown: 0 };
      results.forEach(r => { (summary as Record<string, number>)[r.status]++; });
      return json({ job_id: jobId, total: results.length, filename: file.name, results, summary });
    }

    return err("Not found", 404);
  } catch (e) {
    console.error(e);
    return err(`Internal error: ${e instanceof Error ? e.message : String(e)}`, 500);
  }
});
