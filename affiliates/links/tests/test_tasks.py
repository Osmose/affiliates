from datetime import date

from mock import patch
from nose.tools import eq_

from affiliates.base.tests import TestCase, waffle_switch
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

    @waffle_switch('fraud_detection', True)
    def test_fraud_detection_create_linkclick(self):
        """
        If the "fraud_detection" switch is on, create a LinkClick object
        for this click.
        """
        link = LinkFactory.create()
        DataPointFactory.create(link=link, date=date(2014, 1, 1), link_clicks=7)

        add_click(link.id, date(2014, 1, 1), '127.0.0.1', 'Firefox')
        eq_(LinkClick.objects
            .filter(ip='127.0.0.1', ip_group='127.0.0', user_agent='Firefox', datapoint__link=link)
            .exists(), True)

    @waffle_switch('fraud_detection', False)
    def test_fraud_detection_off(self):
        """If fraud detection is disabled, do not create a LinkClick."""
        link = LinkFactory.create()
        DataPointFactory.create(link=link, date=date(2014, 1, 1), link_clicks=7)

        add_click(link.id, date(2014, 1, 1), '127.0.0.1', 'Firefox')
        eq_(LinkClick.objects.count(), 0)

    @waffle_switch('fraud_detection', True)
    def test_fraud_detection_ipv6(self):
        """
        If the given IP address is an ipv6 address, store the full
        version for the IP and the /48 prefix for the group.
        """
        link = LinkFactory.create()
        DataPointFactory.create(link=link, date=date(2014, 1, 1), link_clicks=7)

        add_click(link.id, date(2014, 1, 1), '2001:db8:85a3::8a2e:370:7334', 'Firefox')
        eq_(LinkClick.objects
            .filter(ip='2001:db8:85a3::8a2e:370:7334', ip_group='2001:0db8:85a3',
                    user_agent='Firefox', datapoint__link=link)
            .exists(), True)

    @waffle_switch('fraud_detection', True)
    def test_fraud_detection_invalid_ip(self):
        """
        If the given IP is invalid, store None for the IP and IP group.
        """
        link = LinkFactory.create()
        DataPointFactory.create(link=link, date=date(2014, 1, 1), link_clicks=7)

        # Invalid IP
        add_click(link.id, date(2014, 1, 1), 'asdfasoajb9', 'Firefox')
        eq_(LinkClick.objects
            .filter(ip=None, ip_group=None, user_agent='Firefox', datapoint__link=link)
            .exists(), True)

        # Empty IP
        LinkClick.objects.all().delete()
        add_click(link.id, date(2014, 1, 1), '', 'Firefox')
        eq_(LinkClick.objects
            .filter(ip=None, ip_group=None, user_agent='Firefox', datapoint__link=link)
            .exists(), True)
