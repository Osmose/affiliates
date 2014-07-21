from datetime import date

from mock import patch
from nose.tools import eq_

from affiliates.base.tests import TestCase
from affiliates.links.models import DataPoint, LinkClick
from affiliates.links.tasks import add_click
from affiliates.links.tests import DataPointFactory, LinkFactory


class AddClickTests(TestCase):
    def test_link_does_not_exist(self):
        """If the link does not exist, do nothing (but don't fail!)."""
        eq_(add_click(99999999, date(2014, 4, 1), '127.0.0.1', 'Firefox'), None)

    def test_link_exists_no_datapoint(self):
        """If no datapoint for the given date exists, create one."""
        link = LinkFactory.create()
        add_click(link.id, date(2014, 4, 1), '127.0.0.1', 'Firefox')
        datapoint = link.datapoint_set.get(date=date(2014, 4, 1))
        eq_(datapoint.link_clicks, 1)

    def test_link_exists_datapoint_exists(self):
        """
        If a datapoint exists for the given date, increment it's
        link_clicks value.
        """
        link = LinkFactory.create()
        DataPointFactory.create(link=link, date=date(2014, 1, 1), link_clicks=7)

        with patch.object(DataPoint, 'add_metric') as add_metric:
            add_click(link.id, date(2014, 1, 1), '127.0.0.1', 'Firefox')
            add_metric.assert_called_with('link_clicks', 1, save=True)

    def test_waffle_fraud_detection_create_linkclick(self):
        """
        If the "fraud_detection" switch is on, create a LinkClick object
        for this click.
        """
        link = LinkFactory.create()
        DataPointFactory.create(link=link, date=date(2014, 1, 1), link_clicks=7)

        with patch('affiliates.links.tasks.waffle.switch_is_active') as switch_is_active:
            switch_is_active.return_value = True
            add_click(link.id, date(2014, 1, 1), '127.0.0.1', 'Firefox')

            eq_(LinkClick.objects
                .filter(ip='127.0.0.1', user_agent='Firefox', datapoint__link=link)
                .exists(), True)
            switch_is_active.assert_called_with('fraud_detection')
