drop schema if exists knudg_private cascade;
drop schema if exists knudg_crypto cascade;

drop table if exists job_attempts cascade;
drop table if exists jobs cascade;
drop table if exists outbox_events cascade;
drop table if exists audit_events cascade;
drop table if exists idempotency_keys cascade;
drop table if exists consent_records cascade;
drop table if exists approval_challenges cascade;
drop table if exists revocation_tombstones cascade;
drop table if exists card_state_transitions cascade;
drop table if exists card_edges cascade;
drop table if exists event_stream_positions cascade;
drop table if exists card_events cascade;
drop table if exists domain_events cascade;
drop table if exists verification_records cascade;
alter table if exists experience_cards drop constraint if exists experience_cards_current_version_fk;
drop table if exists card_versions cascade;
drop table if exists experience_cards cascade;
drop table if exists break_glass_cases cascade;
drop table if exists tenant_revocation_epochs cascade;
drop table if exists worker_identities cascade;
drop table if exists namespace_grants cascade;
drop table if exists namespaces cascade;
drop table if exists tenant_memberships cascade;
drop table if exists request_claim_contexts cascade;
drop table if exists claim_signing_keys cascade;
drop table if exists external_identities cascade;
drop table if exists principals cascade;
drop table if exists tenants cascade;

drop table if exists card_edge_types cascade;
drop table if exists artifact_types cascade;
drop table if exists consent_scopes cascade;
drop table if exists revocation_subject_types cascade;
drop table if exists namespace_visibilities cascade;
drop table if exists evidence_strengths cascade;
drop table if exists verification_statuses cascade;
drop table if exists quality_states cascade;
drop table if exists outcome_types cascade;
drop table if exists actor_roles cascade;
drop table if exists domain_event_types cascade;
drop table if exists card_event_types cascade;
drop table if exists card_statuses cascade;
drop table if exists lookup_catalog cascade;

drop sequence if exists event_stream_position_seq;

drop function if exists knudg_set_claims(jsonb) cascade;
drop function if exists knudg_current_claims() cascade;

do $$
begin
  if exists (select 1 from pg_roles where rolname = 'knudg_app') then
    execute 'revoke all privileges on all tables in schema public from knudg_app';
    execute 'revoke all privileges on all sequences in schema public from knudg_app';
    execute 'revoke all privileges on all functions in schema public from knudg_app';
    execute 'revoke all privileges on schema public from knudg_app';
  end if;
  if exists (select 1 from pg_roles where rolname = 'knudg_worker') then
    execute 'revoke all privileges on all tables in schema public from knudg_worker';
    execute 'revoke all privileges on all sequences in schema public from knudg_worker';
    execute 'revoke all privileges on all functions in schema public from knudg_worker';
    execute 'revoke all privileges on schema public from knudg_worker';
  end if;
  if exists (select 1 from pg_roles where rolname = 'knudg_readonly_ops') then
    execute 'revoke all privileges on all tables in schema public from knudg_readonly_ops';
    execute 'revoke all privileges on all sequences in schema public from knudg_readonly_ops';
    execute 'revoke all privileges on all functions in schema public from knudg_readonly_ops';
    execute 'revoke all privileges on schema public from knudg_readonly_ops';
  end if;
end
$$;
