drop table if exists local_private_value_events cascade;
drop table if exists local_private_search_documents cascade;
drop table if exists local_private_card_bodies cascade;

drop function if exists knudg_private.local_private_event_json_is_valid(jsonb) cascade;
drop function if exists knudg_private.local_private_card_body_v0_is_valid(jsonb) cascade;
drop function if exists knudg_private.local_private_command_labels_are_valid(jsonb) cascade;
drop function if exists knudg_private.local_private_public_urls_are_valid(jsonb) cascade;
drop function if exists knudg_private.local_private_jsonb_string_array_is_valid(jsonb, integer, integer) cascade;
drop function if exists knudg_private.local_private_text_is_sanitized(text) cascade;
