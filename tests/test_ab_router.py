from recsys_lite.model import ModelConfig, RankingModel
from recsys_lite.serving.ab import ABRouter


def _dummy_triple(tag: str):
    config = ModelConfig(item_num=10, embed_dim=4)
    return RankingModel(config), config, tag


def test_router_always_returns_champion_when_no_candidate_is_configured():
    router = ABRouter(champion=_dummy_triple("v1"))
    for user_id in range(50):
        routed = router.route(user_id)
        assert routed.variant == "champion"
        assert routed.version == "v1"


def test_router_is_sticky_for_the_same_user(monkeypatch):
    router = ABRouter(champion=_dummy_triple("v1"), candidate=_dummy_triple("v2"), candidate_weight_pct=50)
    first = router.route(4242)
    second = router.route(4242)
    assert first.variant == second.variant
    assert first.version == second.version


def test_router_respects_zero_weight_even_with_a_candidate_present():
    router = ABRouter(champion=_dummy_triple("v1"), candidate=_dummy_triple("v2"), candidate_weight_pct=0)
    for user_id in range(50):
        assert router.route(user_id).variant == "champion"


def test_router_routes_roughly_the_configured_split_across_many_users():
    router = ABRouter(champion=_dummy_triple("v1"), candidate=_dummy_triple("v2"), candidate_weight_pct=50)
    variants = [router.route(user_id).variant for user_id in range(2000)]
    candidate_share = variants.count("candidate") / len(variants)
    assert 0.4 < candidate_share < 0.6
