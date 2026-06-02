revoke select on experience_domain_policies, candidate_domain_facets from knudg_app, knudg_worker, knudg_readonly_ops;
drop table if exists candidate_domain_facets;
drop table if exists experience_domain_policies;
