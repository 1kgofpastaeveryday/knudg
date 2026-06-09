drop function if exists knudg_closed_api_vector_search(text, text, integer);
drop function if exists knudg_closed_api_set_embedding(text, uuid, uuid, text);
drop function if exists knudg_closed_private_vector_search(uuid, uuid[], uuid, text, vector, integer);
drop function if exists knudg_closed_private_set_embedding(uuid, uuid[], uuid, uuid, uuid, vector);
