revoke all on function knudg_closed_private_purge(uuid, uuid[], uuid, text, uuid, text) from knudg_app;
revoke all on function knudg_closed_private_revoke(uuid, uuid[], uuid, text, uuid, text) from knudg_app;
revoke all on function knudg_closed_private_search(uuid, uuid[], uuid, text, text[], text, integer) from knudg_app;

drop function if exists knudg_closed_private_purge(uuid, uuid[], uuid, text, uuid, text);
drop function if exists knudg_closed_private_revoke(uuid, uuid[], uuid, text, uuid, text);
drop function if exists knudg_closed_private_search(uuid, uuid[], uuid, text, text[], text, integer);
drop function if exists knudg_private.closed_private_require_namespace_scope(uuid, uuid[], uuid, text[]);
