revoke all on function knudg_closed_private_purge(uuid, uuid[], uuid, text, uuid, text) from knudg_api_app;
revoke all on function knudg_closed_private_revoke(uuid, uuid[], uuid, text, uuid, text) from knudg_api_app;
revoke all on function knudg_closed_private_search(uuid, uuid[], uuid, text, text[], text, integer) from knudg_api_app;
revoke all on function knudg_closed_private_publish(uuid, uuid, uuid, text, text, text, jsonb, jsonb) from knudg_api_app;
revoke select on schema_migrations from knudg_api_app;
revoke usage on schema public from knudg_api_app;

do $$
begin
  execute format('revoke connect on database %I from knudg_api_app', current_database());
end;
$$;
