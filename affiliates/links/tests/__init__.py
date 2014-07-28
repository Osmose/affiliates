from factory import DjangoModelFactory, Sequence, SubFactory

from affiliates.banners.tests import TextBannerVariationFactory
from affiliates.links import models
from affiliates.users.tests import UserFactory


class LinkFactory(DjangoModelFactory):
    FACTORY_FOR = models.Link

    user = SubFactory(UserFactory)
    html = '<a href="{href}">Test!</a>'
    banner_variation = SubFactory(TextBannerVariationFactory)


class DataPointFactory(DjangoModelFactory):
    FACTORY_FOR = models.DataPoint

    link = SubFactory(LinkFactory)


class LeaderboardStandingFactory(DjangoModelFactory):
    FACTORY_FOR = models.LeaderboardStanding

    ranking = Sequence(lambda n: n)
    user = SubFactory(UserFactory)
    metric = 'link_clicks'


class MetricFactory(DjangoModelFactory):
    ABSTRACT_FACTORY = True

    datapoint = SubFactory(DataPointFactory)
    ip = '68.0.0.1'
    user_agent = 'Firefox'


class LinkClickFactory(MetricFactory):
    FACTORY_FOR = models.LinkClick


class FirefoxDownloadFactory(MetricFactory):
    FACTORY_FOR = models.FirefoxDownload


class FirefoxOSReferralFactory(MetricFactory):
    FACTORY_FOR = models.FirefoxOSReferral


class FraudActionFactory(DjangoModelFactory):
    FACTORY_FOR = models.FraudAction

    datapoint = SubFactory(DataPointFactory)
    count = 1
    metric = 'link_clicks'
    reason = 'just because'
