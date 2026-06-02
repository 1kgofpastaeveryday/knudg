create or replace function knudg_private.card_payload_v1_is_valid(row_payload jsonb)
returns boolean
language sql
immutable
set search_path = pg_catalog, knudg_private, pg_temp
as $$
  select (
    jsonb_typeof(row_payload) = 'object'
    and not knudg_private.jsonb_has_non_ascii_keys(row_payload)
    and not knudg_private.jsonb_has_non_portable_numbers(row_payload)
    and not (row_payload ?| array['card_id','tenant_id','namespace_id','visibility_view','status','current_version_id','created_at','updated_at','quality_score','card_schema_version'])
    and not exists (
      select 1
      from jsonb_object_keys(row_payload) as key
      where key not in (
        'source_class','visibility','sharing_state','publication_state',
        'outcome_type','goal','symptom','environment','context_fingerprint',
        'successful_path','failed_paths','known_unknowns','scope_limits',
        'evidence_strength','twist','quality_state','safety','privacy','provenance',
        'deprecation','supersession','contradictions','embedding_refs'
      )
    )
    and row_payload->>'source_class' = 'local_private_dogfood'
    and row_payload->>'visibility' = 'local_private'
    and row_payload->>'sharing_state' = 'not_shared'
    and row_payload->>'publication_state' = 'never_publishable'
    and row_payload->>'outcome_type' = 'solved'
    and row_payload->>'goal' = 'local private dogfood card'
    and row_payload->>'symptom' = 'structured local private card captured for local search'
    and jsonb_typeof(row_payload->'environment') = 'object'
    and jsonb_typeof(row_payload->'context_fingerprint') = 'object'
    and knudg_private.jsonb_string_array_is_nonempty_strings(row_payload->'successful_path', true)
    and knudg_private.jsonb_string_array_is_nonempty_strings(row_payload->'failed_paths')
    and knudg_private.jsonb_string_array_is_nonempty_strings(row_payload->'known_unknowns')
    and knudg_private.jsonb_string_array_is_nonempty_strings(row_payload->'scope_limits')
    and row_payload->>'evidence_strength' = 'operator_judgment'
    and row_payload->>'quality_state' = 'unreviewed'
    and jsonb_typeof(row_payload->'safety') = 'object'
    and not exists (
      select 1
      from jsonb_object_keys(row_payload->'safety') as key
      where key not in (
        'safety_class','review_state','executable_advice','mentions_urls',
        'mentions_packages','mentions_repositories','credential_risk','billing_risk',
        'deletion_risk','network_call_risk','verification_state','withheld_reason'
      )
    )
    and row_payload->'safety' ?& array[
      'safety_class','review_state','executable_advice','mentions_urls',
      'mentions_packages','mentions_repositories','credential_risk','billing_risk',
      'deletion_risk','network_call_risk','verification_state','withheld_reason'
    ]
    and row_payload->'safety'->>'safety_class' in ('low','medium','high')
    and row_payload->'safety'->>'review_state' in ('unreviewed','quarantined','cleared','blocked')
    and jsonb_typeof(row_payload->'safety'->'executable_advice') = 'boolean'
    and jsonb_typeof(row_payload->'safety'->'mentions_urls') = 'boolean'
    and jsonb_typeof(row_payload->'safety'->'mentions_packages') = 'boolean'
    and jsonb_typeof(row_payload->'safety'->'mentions_repositories') = 'boolean'
    and jsonb_typeof(row_payload->'safety'->'credential_risk') = 'boolean'
    and jsonb_typeof(row_payload->'safety'->'billing_risk') = 'boolean'
    and jsonb_typeof(row_payload->'safety'->'deletion_risk') = 'boolean'
    and jsonb_typeof(row_payload->'safety'->'network_call_risk') = 'boolean'
    and row_payload->'safety'->>'verification_state' in ('unverified','single_session','reproduced','external_reference')
    and (row_payload->'safety'->'withheld_reason' = 'null'::jsonb or jsonb_typeof(row_payload->'safety'->'withheld_reason') = 'string')
    and jsonb_typeof(row_payload->'privacy') = 'object'
    and row_payload->'privacy'->>'source_class' = 'local_private_dogfood'
    and row_payload->'privacy'->>'visibility' = 'local_private'
    and row_payload->'privacy'->>'sharing_state' = 'not_shared'
    and row_payload->'privacy'->>'publication_state' = 'never_publishable'
    and row_payload->'privacy'->>'local_private_body_table' = 'local_private_card_bodies'
    and row_payload->'privacy'->>'body_digest' ~ '^[0-9a-f]{64}$'
    and jsonb_typeof(row_payload->'provenance') = 'object'
    and row_payload->'provenance'->>'source_class' = 'local_private_dogfood'
    and (not (row_payload ? 'twist') or row_payload->'twist' = 'null'::jsonb or jsonb_typeof(row_payload->'twist') = 'string')
    and (not (row_payload ? 'deprecation') or jsonb_typeof(row_payload->'deprecation') = 'object')
    and (not (row_payload ? 'supersession') or jsonb_typeof(row_payload->'supersession') = 'object')
    and (not (row_payload ? 'contradictions') or knudg_private.jsonb_string_array_is_nonempty_strings(row_payload->'contradictions'))
    and (
      not (row_payload ? 'embedding_refs')
      or (
        jsonb_typeof(row_payload->'embedding_refs') = 'array'
        and jsonb_array_length(row_payload->'embedding_refs') = 0
      )
    )
  ) or (
    jsonb_typeof(row_payload) = 'object'
    and not knudg_private.jsonb_has_non_ascii_keys(row_payload)
    and not knudg_private.jsonb_has_non_portable_numbers(row_payload)
    and not (row_payload ?| array['card_id','tenant_id','namespace_id','visibility','visibility_view','status','current_version_id','created_at','updated_at','quality_score','card_schema_version'])
    and not exists (
      select 1
      from jsonb_object_keys(row_payload) as key
      where key not in (
        'outcome_type','goal','symptom','environment','context_fingerprint',
        'successful_path','failed_paths','known_unknowns','scope_limits',
        'evidence_strength','twist','quality_state','safety','privacy','provenance',
        'deprecation','supersession','contradictions','embedding_refs'
      )
    )
    and row_payload ? 'outcome_type'
    and row_payload ? 'goal'
    and row_payload ? 'symptom'
    and row_payload ? 'environment'
    and row_payload ? 'context_fingerprint'
    and row_payload ? 'failed_paths'
    and row_payload ? 'known_unknowns'
    and row_payload ? 'scope_limits'
    and row_payload ? 'evidence_strength'
    and row_payload ? 'quality_state'
    and row_payload ? 'safety'
    and row_payload ? 'privacy'
    and row_payload ? 'provenance'
    and row_payload->>'outcome_type' in ('solved','failed_only','inconclusive','unknown_clarified')
    and row_payload->>'evidence_strength' in ('single_session','multi_session','reproduced','external_reference','operator_judgment')
    and row_payload->>'quality_state' in ('unreviewed','solved_once','solved_many','verified','disputed')
    and jsonb_typeof(row_payload->'goal') = 'string'
    and jsonb_typeof(row_payload->'symptom') = 'string'
    and nullif(row_payload->>'goal', '') is not null
    and nullif(row_payload->>'symptom', '') is not null
    and jsonb_typeof(row_payload->'environment') = 'object'
    and jsonb_typeof(row_payload->'context_fingerprint') = 'object'
    and (not (row_payload ? 'successful_path') or row_payload->'successful_path' = 'null'::jsonb or knudg_private.jsonb_string_array_is_nonempty_strings(row_payload->'successful_path', row_payload->>'outcome_type' = 'solved'))
    and (row_payload->>'outcome_type' <> 'solved' or knudg_private.jsonb_string_array_is_nonempty_strings(row_payload->'successful_path', true))
    and (row_payload->>'outcome_type' <> 'failed_only' or (
      (not (row_payload ? 'successful_path') or row_payload->'successful_path' = 'null'::jsonb or (jsonb_typeof(row_payload->'successful_path') = 'array' and jsonb_array_length(row_payload->'successful_path') = 0))
      and knudg_private.jsonb_string_array_is_nonempty_strings(row_payload->'failed_paths', true)
    ))
    and (row_payload->>'outcome_type' <> 'unknown_clarified' or knudg_private.jsonb_string_array_is_nonempty_strings(row_payload->'known_unknowns', true))
    and knudg_private.jsonb_string_array_is_nonempty_strings(row_payload->'failed_paths')
    and knudg_private.jsonb_string_array_is_nonempty_strings(row_payload->'known_unknowns')
    and knudg_private.jsonb_string_array_is_nonempty_strings(row_payload->'scope_limits')
    and jsonb_typeof(row_payload->'safety') = 'object'
    and not exists (
      select 1
      from jsonb_object_keys(row_payload->'safety') as key
      where key not in (
        'safety_class','review_state','executable_advice','mentions_urls',
        'mentions_packages','mentions_repositories','credential_risk','billing_risk',
        'deletion_risk','network_call_risk','verification_state','withheld_reason'
      )
    )
    and row_payload->'safety' ?& array[
      'safety_class','review_state','executable_advice','mentions_urls',
      'mentions_packages','mentions_repositories','credential_risk','billing_risk',
      'deletion_risk','network_call_risk','verification_state','withheld_reason'
    ]
    and row_payload->'safety'->>'safety_class' in ('low','medium','high')
    and row_payload->'safety'->>'review_state' in ('unreviewed','quarantined','cleared','blocked')
    and jsonb_typeof(row_payload->'safety'->'executable_advice') = 'boolean'
    and jsonb_typeof(row_payload->'safety'->'mentions_urls') = 'boolean'
    and jsonb_typeof(row_payload->'safety'->'mentions_packages') = 'boolean'
    and jsonb_typeof(row_payload->'safety'->'mentions_repositories') = 'boolean'
    and jsonb_typeof(row_payload->'safety'->'credential_risk') = 'boolean'
    and jsonb_typeof(row_payload->'safety'->'billing_risk') = 'boolean'
    and jsonb_typeof(row_payload->'safety'->'deletion_risk') = 'boolean'
    and jsonb_typeof(row_payload->'safety'->'network_call_risk') = 'boolean'
    and row_payload->'safety'->>'verification_state' in ('unverified','single_session','reproduced','external_reference')
    and (row_payload->'safety'->'withheld_reason' = 'null'::jsonb or jsonb_typeof(row_payload->'safety'->'withheld_reason') = 'string')
    and jsonb_typeof(row_payload->'privacy') = 'object'
    and jsonb_typeof(row_payload->'provenance') = 'object'
    and row_payload->'privacy'->>'source_class' = 'synthetic'
    and row_payload->'provenance'->>'source_class' = 'synthetic'
    and (not (row_payload ? 'twist') or row_payload->'twist' = 'null'::jsonb or jsonb_typeof(row_payload->'twist') = 'string')
    and (not (row_payload ? 'deprecation') or jsonb_typeof(row_payload->'deprecation') = 'object')
    and (not (row_payload ? 'supersession') or jsonb_typeof(row_payload->'supersession') = 'object')
    and (not (row_payload ? 'contradictions') or knudg_private.jsonb_string_array_is_nonempty_strings(row_payload->'contradictions'))
    and (
      not (row_payload ? 'embedding_refs')
      or (
        jsonb_typeof(row_payload->'embedding_refs') = 'array'
        and not exists (
          select 1
          from jsonb_array_elements(row_payload->'embedding_refs') as item(value)
          where jsonb_typeof(item.value) <> 'object'
        )
      )
    )
  );
$$;
