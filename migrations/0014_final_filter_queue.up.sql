create table if not exists final_filter_jobs (
  id uuid primary key,
  request_digest text not null unique,
  status text not null default 'queued' check (status in ('queued','leased','succeeded','dead')),
  candidate_json jsonb not null,
  policy_context_json jsonb not null,
  result_json jsonb null,
  attempts integer not null default 0 check (attempts >= 0),
  max_attempts integer not null default 5 check (max_attempts > 0),
  priority integer not null default 0,
  available_at timestamptz not null default now(),
  leased_until timestamptz null,
  started_at timestamptz null,
  completed_at timestamptz null,
  last_error_class text null,
  last_error_detail text null check (last_error_detail is null or knudg_private.audit_detail_is_sanitized(last_error_detail)),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (jsonb_typeof(candidate_json) = 'object'),
  check (jsonb_typeof(policy_context_json) = 'object'),
  check (result_json is null or jsonb_typeof(result_json) = 'object'),
  check (request_digest like 'sha256:%'),
  check (
    (status = 'leased' and leased_until is not null)
    or (status <> 'leased' and leased_until is null)
  )
);

create index if not exists final_filter_jobs_ready_idx
  on final_filter_jobs(priority desc, available_at, created_at)
  where status = 'queued';

create index if not exists final_filter_jobs_leased_expiry_idx
  on final_filter_jobs(leased_until)
  where status = 'leased';

grant select, insert, update on final_filter_jobs to knudg_api_app;
