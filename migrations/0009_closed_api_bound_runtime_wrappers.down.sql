revoke all on function knudg_closed_api_publication_candidate(text, uuid) from knudg_api_app;
revoke all on function knudg_closed_api_purge(text, uuid, text) from knudg_api_app;
revoke all on function knudg_closed_api_revoke(text, uuid, text) from knudg_api_app;
revoke all on function knudg_closed_api_search(text, text[], text, integer) from knudg_api_app;
revoke all on function knudg_closed_api_publish(text, jsonb, jsonb) from knudg_api_app;

drop function if exists knudg_closed_api_publication_candidate(text, uuid);
drop function if exists knudg_closed_api_purge(text, uuid, text);
drop function if exists knudg_closed_api_revoke(text, uuid, text);
drop function if exists knudg_closed_api_search(text, text[], text, integer);
drop function if exists knudg_closed_api_publish(text, jsonb, jsonb);
drop function if exists knudg_private.closed_api_runtime_binding();
drop table if exists knudg_private.closed_api_runtime_bindings;

grant execute on function knudg_closed_private_publish(uuid, uuid, uuid, text, text, text, jsonb, jsonb) to knudg_api_app;
grant execute on function knudg_closed_private_search(uuid, uuid[], uuid, text, text[], text, integer) to knudg_api_app;
grant execute on function knudg_closed_private_revoke(uuid, uuid[], uuid, text, uuid, text) to knudg_api_app;
grant execute on function knudg_closed_private_purge(uuid, uuid[], uuid, text, uuid, text) to knudg_api_app;
grant execute on function knudg_closed_private_publication_candidate(uuid, uuid[], uuid, text, uuid) to knudg_api_app;
