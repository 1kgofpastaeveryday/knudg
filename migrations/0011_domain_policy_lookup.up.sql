create table if not exists experience_domain_policies (
  domain text primary key check (domain in (
    'technical_work',
    'personal_reasoning',
    'career_private',
    'place_service_experience',
    'public_experience_candidate',
    'public_aggregate_signal'
  )),
  allowed_intents text[] not null check (array_length(allowed_intents, 1) >= 1),
  default_visibility text not null check (default_visibility in ('private', 'candidate_only', 'public')),
  default_retrieval_policy text not null check (default_retrieval_policy in (
    'automatic_technical_only',
    'explicit_or_contextual',
    'never_public_until_published',
    'public_after_gates'
  )),
  ingest_enablement text not null check (ingest_enablement in (
    'closed_launch_structured_only',
    'disabled_until_gate',
    'reviewer_only_after_gate'
  )),
  public_eligible boolean not null,
  redaction_class text not null check (redaction_class in (
    'technical',
    'personal_reasoning',
    'career',
    'place_service',
    'public_candidate',
    'public_aggregate'
  )),
  ttl_class text not null check (ttl_class in ('default', 'short', 'long', 'policy_defined')),
  cross_domain_search text not null check (cross_domain_search in (
    'deny_by_default',
    'explicit_authorization_required',
    'public_only'
  )),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists candidate_domain_facets (
  tenant_id uuid not null references tenants(id) on delete restrict,
  id uuid not null,
  namespace_id uuid not null,
  created_by uuid not null references principals(id) on delete restrict,
  schema_version text not null default 'candidate-domain-facets-v0' check (schema_version = 'candidate-domain-facets-v0'),
  domain text not null references experience_domain_policies(domain) on delete restrict,
  experience_intent text not null check (experience_intent ~ '^[a-z][a-z0-9_]*$'),
  claim_type text not null check (claim_type in (
    'factual_observation',
    'subjective_impression',
    'inference',
    'aggregate_summary',
    'unverified_report'
  )),
  subject_type text not null check (subject_type in (
    'technical_environment',
    'company',
    'place',
    'service',
    'product',
    'person_private',
    'aggregate_subject'
  )),
  subject_public_name text null check (
    subject_public_name is null
    or (
      char_length(subject_public_name) between 1 and 160
      and subject_public_name !~ '[@\\\\]'
      and subject_public_name !~* '(password|secret|token|api[_-]?key|credential|private[_-]?key)'
    )
  ),
  payload_digest text not null check (payload_digest ~ '^sha256:[a-f0-9]{64}$'),
  policy_version text not null check (policy_version ~ '^[A-Za-z0-9_.:-]{3,120}$'),
  retrieval_policy text not null check (retrieval_policy in (
    'automatic_technical_only',
    'explicit_or_contextual',
    'never_public_until_published',
    'public_after_gates'
  )),
  raw_source_retention text not null check (raw_source_retention in ('none', 'escrow_only', 'policy_defined')),
  publication_eligible boolean not null,
  evidence_strength text not null check (evidence_strength in (
    'single_observation',
    'repeated_personal_observation',
    'corroborated',
    'public_source_supported',
    'operator_judgment'
  )),
  sensitivity text not null check (sensitivity in ('low', 'medium', 'high')),
  ingest_enablement text not null check (ingest_enablement in (
    'closed_launch_structured_only',
    'disabled_until_gate',
    'reviewer_only_after_gate'
  )),
  creates_card boolean not null default false,
  indexes boolean not null default false,
  stores_raw_body boolean not null default false,
  created_at timestamptz not null default now(),
  primary key (tenant_id, id),
  foreign key (tenant_id, namespace_id) references namespaces(tenant_id, id) on delete restrict,
  check (stores_raw_body = false),
  check (indexes = false),
  check (creates_card = false),
  check (
    (domain = 'technical_work' and retrieval_policy = 'automatic_technical_only' and ingest_enablement = 'closed_launch_structured_only' and publication_eligible = false)
    or (domain in ('personal_reasoning','career_private','place_service_experience') and retrieval_policy = 'explicit_or_contextual' and ingest_enablement = 'disabled_until_gate' and publication_eligible = false)
    or (domain = 'public_experience_candidate' and retrieval_policy = 'never_public_until_published' and ingest_enablement = 'disabled_until_gate' and publication_eligible = false)
    or (domain = 'public_aggregate_signal' and retrieval_policy = 'public_after_gates' and ingest_enablement = 'reviewer_only_after_gate' and publication_eligible = true)
  ),
  check (
    (domain = 'technical_work' and experience_intent = any(array['solved_path','failed_path','environment_trap','deprecated_approach','unknown']::text[]))
    or (domain = 'personal_reasoning' and experience_intent = any(array['decision_revisited','repeated_pattern','personal_constraint']::text[]))
    or (domain = 'career_private' and experience_intent = any(array['career_positioning','company_experience','interview_experience']::text[]))
    or (domain = 'place_service_experience' and experience_intent = any(array['place_experience','service_quality_signal']::text[]))
    or (domain = 'public_experience_candidate' and experience_intent = any(array['company_experience','place_experience','service_quality_signal']::text[]))
    or (domain = 'public_aggregate_signal' and experience_intent = 'public_aggregate_signal')
  ),
  check (
    domain not in ('public_experience_candidate','public_aggregate_signal')
    or subject_type <> 'person_private'
  ),
  check (
    raw_source_retention = 'none'
  ),
  check (
    (subject_type in ('company','place','service','product') and subject_public_name is not null)
    or (subject_type in ('technical_environment','person_private','aggregate_subject') and subject_public_name is null)
  )
);

insert into experience_domain_policies(
  domain,
  allowed_intents,
  default_visibility,
  default_retrieval_policy,
  ingest_enablement,
  public_eligible,
  redaction_class,
  ttl_class,
  cross_domain_search
)
values
  (
    'technical_work',
    array['solved_path','failed_path','environment_trap','deprecated_approach','unknown']::text[],
    'private',
    'automatic_technical_only',
    'closed_launch_structured_only',
    false,
    'technical',
    'default',
    'deny_by_default'
  ),
  (
    'personal_reasoning',
    array['decision_revisited','repeated_pattern','personal_constraint']::text[],
    'private',
    'explicit_or_contextual',
    'disabled_until_gate',
    false,
    'personal_reasoning',
    'policy_defined',
    'explicit_authorization_required'
  ),
  (
    'career_private',
    array['career_positioning','company_experience','interview_experience']::text[],
    'private',
    'explicit_or_contextual',
    'disabled_until_gate',
    false,
    'career',
    'policy_defined',
    'explicit_authorization_required'
  ),
  (
    'place_service_experience',
    array['place_experience','service_quality_signal']::text[],
    'private',
    'explicit_or_contextual',
    'disabled_until_gate',
    false,
    'place_service',
    'policy_defined',
    'explicit_authorization_required'
  ),
  (
    'public_experience_candidate',
    array['company_experience','place_experience','service_quality_signal']::text[],
    'candidate_only',
    'never_public_until_published',
    'disabled_until_gate',
    false,
    'public_candidate',
    'short',
    'deny_by_default'
  ),
  (
    'public_aggregate_signal',
    array['public_aggregate_signal']::text[],
    'public',
    'public_after_gates',
    'reviewer_only_after_gate',
    true,
    'public_aggregate',
    'policy_defined',
    'public_only'
  )
on conflict (domain) do update
set allowed_intents = excluded.allowed_intents,
    default_visibility = excluded.default_visibility,
    default_retrieval_policy = excluded.default_retrieval_policy,
    ingest_enablement = excluded.ingest_enablement,
    public_eligible = excluded.public_eligible,
    redaction_class = excluded.redaction_class,
    ttl_class = excluded.ttl_class,
    cross_domain_search = excluded.cross_domain_search,
    updated_at = now();

alter table candidate_domain_facets enable row level security;
alter table candidate_domain_facets force row level security;

drop policy if exists candidate_domain_facets_isolation on candidate_domain_facets;
create policy candidate_domain_facets_isolation on candidate_domain_facets
  for select to knudg_app, knudg_worker
  using (
    tenant_id = knudg_private.current_tenant_id()
    and namespace_id = any(knudg_private.current_namespace_ids())
  );

grant select on experience_domain_policies, candidate_domain_facets to knudg_app, knudg_worker, knudg_readonly_ops;
