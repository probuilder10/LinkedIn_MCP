def test_my_recent_posts(tools):
    posts = tools["my_recent_posts"](post_count=5)
    assert posts and posts[0]["urn"].startswith("urn:li:activity:")


def test_post_reactions_and_comments(tools):
    r = tools["post_reactions"]("urn:li:activity:p1")
    c = tools["post_comments"]("urn:li:activity:p1")
    assert len(r) == 2
    assert len(c) == 1


def test_warm_leads_from_post(tools):
    out = tools["warm_leads_from_post"]("urn:li:activity:p1")
    assert out["n_reactions"] == 2
    assert out["n_comments"] == 1
    pids = {e["public_id"] for e in out["engagers"]}
    assert pids == {"alice", "bob", "carol"}


def test_content_performance(tools):
    perf = tools["content_performance"](post_count=5)
    assert perf["total_posts"] == 2
    assert perf["avg_reactions"] == 26.0
    # weighted keyword ranking should at least surface something
    assert isinstance(perf["top_words"], list)
