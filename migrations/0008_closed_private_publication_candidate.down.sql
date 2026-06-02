revoke all on function knudg_closed_private_publication_candidate(uuid, uuid[], uuid, text, uuid) from knudg_api_app;
revoke all on function knudg_closed_private_publication_candidate(uuid, uuid[], uuid, text, uuid) from knudg_app;
drop function if exists knudg_closed_private_publication_candidate(uuid, uuid[], uuid, text, uuid);

delete from local_private_value_events
where event_name = 'publication_candidate_prepared';

alter table local_private_value_events
  drop constraint if exists local_private_value_events_event_name_check;

alter table local_private_value_events
  add constraint local_private_value_events_event_name_check check (event_name in (
    'capture_attempt','capture_rejected','search_completed','suggestion_shown',
    'suggestion_accepted','suggestion_ignored','revoke_completed',
    'purge_completed','leakage_check_completed'
  ));
