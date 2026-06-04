create or replace function knudg_private.local_private_card_body_v0_is_valid(row_body jsonb)
returns boolean
language sql
immutable
set search_path = pg_catalog, knudg_private, pg_temp
as $$
  select jsonb_typeof(row_body) = 'object'
    and not knudg_private.jsonb_has_non_ascii_keys(row_body)
    and not knudg_private.jsonb_has_non_portable_numbers(row_body)
    and not exists (
      select 1
      from jsonb_object_keys(row_body) as key
      where key not in (
        'source_class','title','problem_summary','solution_summary',
        'public_packages','environment_tags','public_reference_urls',
        'command_labels','error_fingerprints','lessons'
      )
    )
    and row_body ?& array[
      'source_class','title','problem_summary','solution_summary',
      'public_packages','environment_tags','public_reference_urls',
      'command_labels','error_fingerprints','lessons'
    ]
    and row_body->>'source_class' = 'local_private_dogfood'
    and jsonb_typeof(row_body->'title') = 'string'
    and length(row_body->>'title') between 8 and 120
    and knudg_private.local_private_text_is_sanitized(row_body->>'title')
    and jsonb_typeof(row_body->'problem_summary') = 'string'
    and length(row_body->>'problem_summary') between 20 and 600
    and knudg_private.local_private_text_is_sanitized(row_body->>'problem_summary')
    and jsonb_typeof(row_body->'solution_summary') = 'string'
    and length(row_body->>'solution_summary') between 20 and 900
    and knudg_private.local_private_text_is_sanitized(row_body->>'solution_summary')
    and knudg_private.local_private_jsonb_string_array_is_valid(row_body->'public_packages', 8, 80)
    and knudg_private.local_private_jsonb_string_array_is_valid(row_body->'environment_tags', 12, 40)
    and knudg_private.local_private_public_urls_are_valid(row_body->'public_reference_urls')
    and knudg_private.local_private_command_labels_are_valid(row_body->'command_labels')
    and knudg_private.local_private_jsonb_string_array_is_valid(row_body->'error_fingerprints', 6, 120)
    and knudg_private.local_private_jsonb_string_array_is_valid(row_body->'lessons', 6, 200);
$$;

drop function if exists knudg_private.local_private_human_summary_is_valid(jsonb);
