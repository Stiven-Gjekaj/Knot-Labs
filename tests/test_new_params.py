from Mesh.tools.gen_user import make_user, GENDERS, COUNTRIES as USER_COUNTRIES
from Mesh.tools.gen_videos import make_post, COUNTRIES as POST_COUNTRIES


def test_make_user_gender_param():
    u = make_user(username="z", gender="female")
    assert u["Gender"] == "female"
    # Invalid gender falls back to one of known
    u2 = make_user(username="y", gender="invalid")
    assert u2["Gender"] in GENDERS


def test_make_user_country_param():
    u = make_user(username="country_tester", gender="male", country="US")
    assert u["country"] == "US"
    u2 = make_user(username="rand_country", country="ZZ")
    assert u2["country"] in USER_COUNTRIES


def test_make_post_country_param():
    p = make_post("c1", ["cats"], country="US")
    assert p["country"] == "US"
    assert p["Category"]["macro"]
    p2 = make_post("c1", ["cats"], country="ZZ")
    assert p2["country"] in POST_COUNTRIES
