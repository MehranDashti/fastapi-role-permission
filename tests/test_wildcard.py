from fastapi_role_permission.wildcard import WildcardPermission


def test_exact_match():
    assert WildcardPermission.check("posts.read", ["posts.read"])


def test_no_match():
    assert not WildcardPermission.check("posts.write", ["posts.read"])


def test_wildcard_all():
    assert WildcardPermission.check("posts.read", ["*"])
    assert WildcardPermission.check("anything.whatever", ["*"])


def test_wildcard_namespace():
    assert WildcardPermission.check("posts.read", ["posts.*"])
    assert WildcardPermission.check("posts.write", ["posts.*"])
    assert not WildcardPermission.check("articles.read", ["posts.*"])


def test_wildcard_deep():
    assert WildcardPermission.check("posts.comments.read", ["posts.*"])
    assert WildcardPermission.check("posts.comments.read", ["posts.comments.*"])
    assert not WildcardPermission.check("posts.comments.read", ["posts.tags.*"])


def test_multiple_grants():
    granted = ["posts.read", "articles.*", "comments.write"]
    assert WildcardPermission.check("posts.read", granted)
    assert WildcardPermission.check("articles.edit", granted)
    assert WildcardPermission.check("comments.write", granted)
    assert not WildcardPermission.check("posts.write", granted)
    assert not WildcardPermission.check("comments.read", granted)


def test_empty_grants():
    assert not WildcardPermission.check("posts.read", [])


def test_wildcard_at_top():
    assert WildcardPermission.check("any.deep.nested.perm", ["*"])
