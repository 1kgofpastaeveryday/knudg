revoke all on function knudg_closed_api_merge_update(text, uuid, jsonb, jsonb, jsonb) from knudg_api_app;
drop function if exists knudg_closed_api_merge_update(text, uuid, jsonb, jsonb, jsonb);

revoke all on function knudg_closed_private_merge_update(uuid, uuid[], uuid, text, uuid, jsonb, jsonb, jsonb) from knudg_api_app;
drop function if exists knudg_closed_private_merge_update(uuid, uuid[], uuid, text, uuid, jsonb, jsonb, jsonb);

alter table local_private_value_events
  drop constraint if exists local_private_value_events_event_name_check;

alter table local_private_value_events
  add constraint local_private_value_events_event_name_check check (event_name in (
    'capture_attempt','capture_rejected','search_completed','suggestion_shown',
    'suggestion_accepted','suggestion_ignored','revoke_completed',
    'purge_completed','leakage_check_completed','publication_candidate_prepared'
  ));
