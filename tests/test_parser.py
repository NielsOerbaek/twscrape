import json
import os
from typing import Callable

from twscrape import API, gather
from twscrape.logger import set_log_level
from twscrape.models import PollCard, SummaryCard, Tweet, User, UserRef, parse_tweet

BASE_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(BASE_DIR, "mocked-data")
os.makedirs(DATA_DIR, exist_ok=True)

set_log_level("DEBUG")


class FakeRep:
    text: str

    def __init__(self, text: str):
        self.text = text

    def json(self):
        return json.loads(self.text)


def fake_rep(filename: str):
    filename = filename if filename.endswith(".json") else f"{filename}.json"
    filename = filename if filename.startswith("/") else os.path.join(DATA_DIR, filename)

    with open(filename) as fp:
        return FakeRep(fp.read())


def mock_rep(fn: Callable, filename: str, as_generator=False):
    rep = fake_rep(filename)

    async def cb_rep(*args, **kwargs):
        return rep

    async def cb_gen(*args, **kwargs):
        yield rep

    assert "__self__" in dir(fn)
    cb = cb_gen if as_generator else cb_rep
    cb.__name__ = fn.__name__
    cb.__self__ = fn.__self__  # pyright: ignore
    setattr(fn.__self__, fn.__name__, cb)  # pyright: ignore


def check_tweet(doc: Tweet | None):
    assert doc is not None
    assert isinstance(doc.id, int)
    assert isinstance(doc.id_str, str)
    assert str(doc.id) == doc.id_str

    assert doc.url is not None
    assert doc.id_str in doc.url
    assert doc.user is not None

    assert isinstance(doc.conversationId, int)
    assert isinstance(doc.conversationIdStr, str)
    assert str(doc.conversationId) == doc.conversationIdStr

    if doc.inReplyToTweetId is not None:
        assert isinstance(doc.inReplyToTweetId, int)
        assert isinstance(doc.inReplyToTweetIdStr, str)
        assert str(doc.inReplyToTweetId) == doc.inReplyToTweetIdStr

    if doc.inReplyToUser:
        check_user_ref(doc.inReplyToUser)

    if doc.mentionedUsers:
        for x in doc.mentionedUsers:
            check_user_ref(x)

    obj = doc.dict()
    assert doc.id == obj["id"]
    assert doc.id_str == obj["id_str"]
    assert doc.user.id == obj["user"]["id"]

    assert "url" in obj
    assert "_type" in obj
    assert obj["_type"] == "snscrape.modules.twitter.Tweet"

    assert "url" in obj["user"]
    assert "_type" in obj["user"]
    assert obj["user"]["_type"] == "snscrape.modules.twitter.User"

    txt = doc.json()
    assert isinstance(txt, str)
    assert str(doc.id) in txt

    if doc.media is not None:
        if len(doc.media.photos) > 0:
            assert doc.media.photos[0].url is not None

        if len(doc.media.videos) > 0:
            for x in doc.media.videos:
                assert x.thumbnailUrl is not None
                assert x.duration is not None
                for v in x.variants:
                    assert v.url is not None
                    assert v.bitrate is not None
                    assert v.contentType is not None

    if doc.retweetedTweet is not None:
        try:
            assert doc.rawContent.endswith(doc.retweetedTweet.rawContent), "content should be full"
        except AssertionError as e:
            print("\n" + "-" * 60)
            print(doc.url)
            print("1:", doc.rawContent)
            print("2:", doc.retweetedTweet.rawContent)
            print("-" * 60)
            raise e

    check_user(doc.user)


def check_user(doc: User):
    assert doc.id is not None
    assert isinstance(doc.id, int)
    assert isinstance(doc.id_str, str)
    assert str(doc.id) == doc.id_str

    assert doc.username is not None
    assert doc.descriptionLinks is not None

    if len(doc.descriptionLinks) > 0:
        for x in doc.descriptionLinks:
            assert x.url is not None
            assert x.text is not None
            assert x.tcourl is not None

    obj = doc.dict()
    assert doc.id == obj["id"]
    assert doc.username == obj["username"]

    txt = doc.json()
    assert isinstance(txt, str)
    assert str(doc.id) in txt


def check_user_ref(doc: UserRef):
    assert isinstance(doc.id, int)
    assert isinstance(doc.id_str, str)
    assert str(doc.id) == doc.id_str

    assert doc.username is not None
    assert doc.displayname is not None

    obj = doc.dict()
    assert doc.id == obj["id"]
    assert doc.id_str == obj["id_str"]


async def test_search():
    api = API()
    mock_rep(api.search_raw, "raw_search", as_generator=True)

    items = await gather(api.search("elon musk lang:en", limit=20))
    assert len(items) > 0

    for doc in items:
        check_tweet(doc)


async def test_user_by_id():
    api = API()
    mock_rep(api.user_by_id_raw, "raw_user_by_id")

    doc = await api.user_by_id(2244994945)
    assert doc is not None
    assert doc.id == 2244994945
    assert doc.username == "XDevelopers"

    obj = doc.dict()
    assert doc.id == obj["id"]
    assert doc.username == obj["username"]

    txt = doc.json()
    assert isinstance(txt, str)
    assert str(doc.id) in txt


async def test_user_by_login():
    api = API()
    mock_rep(api.user_by_login_raw, "raw_user_by_login")

    doc = await api.user_by_login("xdevelopers")
    assert doc is not None
    assert doc.id == 2244994945
    assert doc.username == "XDevelopers"

    obj = doc.dict()
    assert doc.id == obj["id"]
    assert doc.username == obj["username"]

    txt = doc.json()
    assert isinstance(txt, str)
    assert str(doc.id) in txt


async def test_tweet_details():
    api = API()
    mock_rep(api.tweet_details_raw, "raw_tweet_details")

    doc = await api.tweet_details(1649191520250245121)
    assert doc is not None, "tweet should not be None"
    check_tweet(doc)

    assert doc.id == 1649191520250245121
    assert doc.user is not None, "tweet.user should not be None"


async def test_tweet_replies():
    api = API()
    mock_rep(api.tweet_replies_raw, "raw_tweet_replies", as_generator=True)

    twid = 1649191520250245121
    tweets = await gather(api.tweet_replies(twid, limit=20))
    assert len(tweets) > 0

    for doc in tweets:
        check_tweet(doc)
        assert doc.inReplyToTweetId == twid


async def test_followers():
    api = API()
    mock_rep(api.followers_raw, "raw_followers", as_generator=True)

    users = await gather(api.followers(2244994945))
    assert len(users) > 0

    for doc in users:
        check_user(doc)


async def test_verified_followers():
    api = API()
    mock_rep(api.verified_followers_raw, "raw_verified_followers", as_generator=True)

    users = await gather(api.verified_followers(2244994945))
    assert len(users) > 0

    for doc in users:
        check_user(doc)
        assert doc.blue is True, "snould be only Blue users"


async def test_subscriptions():
    api = API()
    mock_rep(api.subscriptions_raw, "raw_subscriptions", as_generator=True)

    users = await gather(api.subscriptions(44196397))
    assert len(users) > 0

    for doc in users:
        check_user(doc)


async def test_following():
    api = API()
    mock_rep(api.following_raw, "raw_following", as_generator=True)

    users = await gather(api.following(2244994945))
    assert len(users) > 0

    for doc in users:
        check_user(doc)


async def test_retweters():
    api = API()
    mock_rep(api.retweeters_raw, "raw_retweeters", as_generator=True)

    users = await gather(api.retweeters(1649191520250245121))
    assert len(users) > 0

    for doc in users:
        check_user(doc)


async def test_favoriters():
    api = API()
    mock_rep(api.favoriters_raw, "raw_favoriters", as_generator=True)

    users = await gather(api.favoriters(1649191520250245121))
    assert len(users) > 0

    for doc in users:
        check_user(doc)


async def test_user_tweets():
    api = API()
    mock_rep(api.user_tweets_raw, "raw_user_tweets", as_generator=True)

    tweets = await gather(api.user_tweets(2244994945))
    assert len(tweets) > 0

    for doc in tweets:
        check_tweet(doc)


async def test_user_tweets_and_replies():
    api = API()
    mock_rep(api.user_tweets_and_replies_raw, "raw_user_tweets_and_replies", as_generator=True)

    tweets = await gather(api.user_tweets_and_replies(2244994945))
    assert len(tweets) > 0

    for doc in tweets:
        check_tweet(doc)


async def test_list_timeline():
    api = API()
    mock_rep(api.list_timeline_raw, "raw_list_timeline", as_generator=True)

    tweets = await gather(api.list_timeline(1494877848087187461))
    assert len(tweets) > 0

    for doc in tweets:
        check_tweet(doc)


async def test_likes():
    api = API()
    mock_rep(api.liked_tweets_raw, "raw_likes", as_generator=True)

    tweets = await gather(api.liked_tweets(2244994945))
    assert len(tweets) > 0

    for doc in tweets:
        check_tweet(doc)


async def test_tweet_with_video():
    api = API()

    files = [
        ("manual_tweet_with_video_1.json", 1671508600538161153),
        ("manual_tweet_with_video_2.json", 1671753569412820992),
    ]

    for file, twid in files:
        mock_rep(api.tweet_details_raw, file)
        doc = await api.tweet_details(twid)
        assert doc is not None
        check_tweet(doc)


async def test_issue_28():
    api = API()

    mock_rep(api.tweet_details_raw, "_issue_28_1")
    doc = await api.tweet_details(1658409412799737856)
    assert doc is not None
    check_tweet(doc)

    assert doc.id == 1658409412799737856
    assert doc.user is not None

    assert doc.retweetedTweet is not None
    assert doc.retweetedTweet.viewCount is not None
    assert doc.viewCount is not None  # views should come from retweetedTweet
    assert doc.viewCount == doc.retweetedTweet.viewCount
    check_tweet(doc.retweetedTweet)

    mock_rep(api.tweet_details_raw, "_issue_28_2")
    doc = await api.tweet_details(1658421690001502208)
    assert doc is not None
    check_tweet(doc)
    assert doc.id == 1658421690001502208
    assert doc.viewCount is not None

    assert doc.quotedTweet is not None
    assert doc.quotedTweet.id != doc.id
    check_tweet(doc.quotedTweet)
    assert doc.quotedTweet.viewCount is not None


async def test_issue_42():
    raw = fake_rep("_issue_42").json()
    doc = parse_tweet(raw, 1665951747842641921)
    assert doc is not None
    assert doc.retweetedTweet is not None
    assert doc.rawContent is not None
    assert doc.retweetedTweet.rawContent is not None
    assert doc.rawContent.endswith(doc.retweetedTweet.rawContent)


async def test_issue_56():
    raw = fake_rep("_issue_56").json()
    doc = parse_tweet(raw, 1682072224013099008)
    assert doc is not None
    assert len(set([x.tcourl for x in doc.links])) == len(doc.links)
    assert len(doc.links) == 5


async def test_issue_72():
    # Check SummaryCard
    raw = fake_rep("_issue_72").json()
    doc = parse_tweet(raw, 1696922210588410217)
    assert doc is not None
    assert doc.card is not None
    assert isinstance(doc.card, SummaryCard)
    assert doc.card._type == "summary"
    assert doc.card.title is not None
    assert doc.card.description is not None
    assert doc.card.url is not None

    # Check PoolCard
    raw = fake_rep("_issue_72_poll").json()
    doc = parse_tweet(raw, 1780666831310877100)
    assert doc is not None
    assert doc.card is not None
    assert isinstance(doc.card, PollCard)
    assert doc.card._type == "poll"
    assert doc.card.finished is not None
    assert doc.card.options is not None
    assert len(doc.card.options) > 0
    for x in doc.card.options:
        assert x.label is not None
        assert x.votesCount is not None
