do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'knudg_api_app') then
    create role knudg_api_app noinherit nologin;
  end if;
end;
$$;

alter role knudg_api_app
  noinherit
  nosuperuser
  nocreatedb
  nocreaterole
  noreplication
  nobypassrls;

do $$
begin
  execute format('grant connect on database %I to knudg_api_app', current_database());
end;
$$;

grant usage on schema public to knudg_api_app;

revoke all privileges on all tables in schema public from knudg_api_app;
revoke all privileges on all sequences in schema public from knudg_api_app;
revoke all privileges on all functions in schema public from knudg_api_app;

grant select on schema_migrations to knudg_api_app;
grant execute on function knudg_closed_private_publish(uuid, uuid, uuid, text, text, text, jsonb, jsonb) to knudg_api_app;
grant execute on function knudg_closed_private_search(uuid, uuid[], uuid, text, text[], text, integer) to knudg_api_app;
grant execute on function knudg_closed_private_revoke(uuid, uuid[], uuid, text, uuid, text) to knudg_api_app;
grant execute on function knudg_closed_private_purge(uuid, uuid[], uuid, text, uuid, text) to knudg_api_app;
