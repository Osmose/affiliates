from datetime import date

from django.core.management import call_command

from nose.tools import eq_

from affiliates.banners.models import Category, TextBanner
from affiliates.banners.tests import TextBannerFactory
from affiliates.base.tests import TestCase
from affiliates.links.models import DataPoint, Link
from affiliates.links.tests import DataPointFactory, LinkFactory


class LinkTests(TestCase):
    def test_manager_total_link_clicks(self):
        for clicks in (4, 6, 9, 10):  # = 29 clicks
            DataPointFactory.create(link_clicks=clicks, date=date(2014, 4, 26))
        for clicks in (25, 5, 5):  # = 35 clicks
            LinkFactory.create(aggregate_link_clicks=clicks)

        # Create a link with multiple datapoints to test for a faulty
        # join that would screw up the totals.
        link = LinkFactory.create()
        DataPointFactory.create(link_clicks=7, link=link, date=date(2014, 4, 26))
        DataPointFactory.create(link_clicks=7, link=link, date=date(2014, 4, 27))


        # 29 + 35 + 7 + 7 = 78 clicks
        eq_(Link.objects.total_link_clicks(), 78)


class DataPointTests(TestCase):
    def test_add_metric(self):
        """
        add_metric should update the metric count for the datapoint and
        all of it's parents that have denormalized counts.
        """
        banner = TextBannerFactory.create()
        datapoint = DataPointFactory.create(date=date(2014, 1, 1), link_clicks=7,
                                            link__banner_variation__banner=banner)
        call_command('denormalize_metrics')

        datapoint.add_metric('link_clicks', -2, save=True)

        # Re-query from database to ensure new values.
        eq_(DataPoint.objects.get(pk=datapoint.pk).link_clicks, 5)
        eq_(Link.objects.get(pk=datapoint.link.pk).link_clicks, 5)
        eq_(TextBanner.objects.get(pk=banner.pk).link_clicks, 5)
        eq_(Category.objects.get(pk=banner.category.pk).link_clicks, 5)
