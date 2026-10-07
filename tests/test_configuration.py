from core.policy import load_policy
from core.profile import load_profile,sensitive_fields_present
from core.sources import load_registry

def test_public_profile_has_no_sensitive_values():
    profile=load_profile()
    assert sensitive_fields_present(profile)==[]

def test_registry_has_enabled_domains():
    for source in load_registry():
        if source.get("enabled"):
            assert source.get("domain")

def test_policy_has_human_gates():
    gates=set(load_policy()["human_gates"])
    assert {"captcha","mfa","signature","payment","unknown_fact","untrusted_destination"}<=gates
