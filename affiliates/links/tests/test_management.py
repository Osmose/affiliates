from datetime import date, timedelta

from django.core.management.base import CommandError
from django.test.utils import override_settings

from mock import ANY, call, Mock, patch
from nose.tools import eq_, ok_

from affiliates.banners.models import TextBanner, Category
from affiliates.banners.tests import CategoryFactory, TextBannerFactory
from affiliates.base.tests import aware_date, aware_datetime, CONTAINS, TestCase, waffle_switch
from affiliates.links.google_analytics import AnalyticsError
from affiliates.links.management.commands import (aggregate_old_datapoints, analyze_events,
                                                  collect_ga_data, denormalize_metrics,
                                                  update_leaderboard)
from affiliates.links.models import (DataPoint, FirefoxDownload, FirefoxOSReferral,
                                     LeaderboardStanding, Link, LinkClick)
from affiliates.links.tests import (DataPointFactory, FirefoxDownloadFactory,
                                    FirefoxOSReferralFactory, LeaderboardStandingFactory,
                                    LinkClickFactory, LinkFactory)
from affiliates.users.tests import UserFactory


class CollectGADataTests(TestCase):
    def setUp(self):
        self.command = collect_ga_data.Command()

        # Mock AnalyticsService to prevent API requests during tests.
        patcher = patch.object(collect_ga_data, 'AnalyticsService')
        self.addCleanup(patcher.stop)

        self.AnalyticsService = patcher.start()
        self.service = self.AnalyticsService.return_value

    def test_error_creating_service(self):
        """
        If there's an error creating the service, raise a CommandError.
        """
        self.AnalyticsService.side_effect = AnalyticsError
        with self.assertRaises(CommandError):
            self.command.handle()

    def test_error_downloading_click_counts(self):
        """
        If there's an error downloading click counts, raise a
        CommandError.
        """
        self.service.get_clicks_for_date.side_effect = AnalyticsError
        with self.assertRaises(CommandError):
            self.command.handle()

    def test_default_yesterday(self):
        """When no date is given, fetch data for the two days ago."""
        link1, link2 = LinkFactory.create_batch(2)
        self.service.get_clicks_for_date.return_value = {
            unicode(link1.pk): '4',
            unicode(link2.pk): '7'
        }
        two_days_ago = aware_date(2014, 1, 1)

        with patch.object(collect_ga_data, 'timezone') as mock_timezone:
            mock_timezone.now.return_value = aware_date(2014, 1, 3)
            self.command.execute()

        self.service.get_clicks_for_date.assert_called_with(two_days_ago)
        eq_(link1.datapoint_set.get(date=two_days_ago).link_clicks, 4)
        eq_(link2.datapoint_set.get(date=two_days_ago).link_clicks, 7)

    def test_date_argument(self):
        """
        If a date argument is given, parse it as DD-MM-YYYY and use it
        as the query date.
        """
        link1, link2 = LinkFactory.create_batch(2)
        self.service.get_clicks_for_date.return_value = {
            unicode(link1.pk): '4',
            unicode(link2.pk): '7'
        }
        query_date = aware_datetime(2014, 1, 1).date()

        # Create pre-existing data to check that it is replaced.
        DataPointFactory.create(link=link1, date=query_date, link_clicks=18)
        DataPointFactory.create(link=link2, date=query_date, link_clicks=14)

        self.command.execute('01-01-2014')

        # There must only be one datapoint for the query date, and the
        # link_clicks must match the new data.
        self.service.get_clicks_for_date.assert_called_with(query_date)
        eq_(link1.datapoint_set.get(date=query_date).link_clicks, 4)
        eq_(link2.datapoint_set.get(date=query_date).link_clicks, 7)

    def test_date_argument_today(self):
        """
        If the date argument is the word 'today', set the query date to
        the current date.
        """
        link1, link2 = LinkFactory.create_batch(2)
        self.service.get_clicks_for_date.return_value = {
            unicode(link1.pk): '4',
            unicode(link2.pk): '7'
        }
        today = aware_datetime(2014, 1, 2).date()

        with patch.object(collect_ga_data, 'timezone') as mock_timezone:
            mock_timezone.now.return_value = aware_datetime(2014, 1, 2)
            self.command.execute('today')

        self.service.get_clicks_for_date.assert_called_with(today)
        eq_(link1.datapoint_set.get(date=today).link_clicks, 4)
        eq_(link2.datapoint_set.get(date=today).link_clicks, 7)

    def test_invalid_date_argument(self):
        """If the date argument is invalid, raise a CommandError."""
        with self.assertRaises(CommandError):
            self.command.execute('asdgasdihg')


class UpdateLeaderboardTests(TestCase):
    def setUp(self):
        self.command = update_leaderboard.Command()

    def _link_with_clicks(self, user, aggregate_link_clicks, link_click_counts):
        """
        Create a link with a specific number of aggregate links and
        datapoints with the given click counts.
        """
        start_date = aware_date(2014, 4, 1)
        link = LinkFactory.create(user=user, aggregate_link_clicks=aggregate_link_clicks)
        for link_clicks in link_click_counts:
            DataPointFactory.create(link=link, link_clicks=link_clicks, date=start_date)
            start_date += timedelta(1)

    def test_basic(self):
        # Create users and links with the noted number of clicks.

        # User with clicks in both aggregate and datapoints across many
        # links.
        user1 = UserFactory.create() # Total: 38 clicks
        self._link_with_clicks(user1, 5, [4, 6, 3]) # 18 clicks
        self._link_with_clicks(user1, 1, [8, 9, 2]) # 20 clicks

        # User with clicks in both aggregate and datapoints in 1 link.
        user2 = UserFactory.create() # Total: 49 clicks
        self._link_with_clicks(user2, 13, [12, 11, 13]) # 49 clicks

        # User with no links.
        user3 = UserFactory.create() # Total: 0 clicks

        # User with links that have no aggregate clicks or no datapoint
        # clicks.
        user4 = UserFactory.create() # Total: 9 clicks
        self._link_with_clicks(user4, 1, [2, 2]) # 5 clicks
        self._link_with_clicks(user4, 0, [2]) # 2 clicks
        self._link_with_clicks(user4, 2, []) # 2 clicks

        # This one just sort've rounds out the set I guess.
        user5 = UserFactory.create() # Total: 9 clicks
        self._link_with_clicks(user5, 1, [2, 2, 2]) # 7 clicks
        self._link_with_clicks(user5, 0, [2]) # 2 clicks

        self.command.handle()
        eq_([s.user for s in LeaderboardStanding.objects.order_by('ranking')],
            [user2, user1, user4, user5, user3])

    def test_clear_old(self):
        """
        When the leaderboard is updated, old standings should be
        cleared.
        """
        user1 = UserFactory.create() # Total: 38 clicks
        self._link_with_clicks(user1, 5, [4, 6, 3]) # 18 clicks
        self._link_with_clicks(user1, 1, [8, 9, 2]) # 20 clicks

        user2 = UserFactory.create() # Total: 49 clicks
        self._link_with_clicks(user2, 13, [12, 11, 13]) # 49 clicks

        # Create existing leaderboard with users in opposite order.
        LeaderboardStandingFactory.create(user=user1, ranking=1, metric='link_clicks')
        LeaderboardStandingFactory.create(user=user2, ranking=2, metric='link_clicks')

        self.command.handle()
        ok_(not (LeaderboardStanding.objects
                 .filter(user=user1, ranking=1, metric='link_clicks')
                 .exists()))
        ok_(not (LeaderboardStanding.objects
                 .filter(user=user2, ranking=2, metric='link_clicks')
                 .exists()))


class AggregateOldDataPointsTests(TestCase):
    def setUp(self):
        self.command = aggregate_old_datapoints.Command()

    def test_basic(self):
        """
        Aggregate any datapoints older than 90 days into the totals
        stored on their links.
        """
        link1 = LinkFactory.create(aggregate_link_clicks=7, aggregate_firefox_downloads=10)
        link1_old_datapoint = DataPointFactory.create(link=link1, date=aware_date(2014, 1, 1),
                                                      link_clicks=8, firefox_downloads=4)
        link1_new_datapoint = DataPointFactory.create(link=link1, date=aware_date(2014, 3, 1),
                                                      link_clicks=2, firefox_downloads=7)

        link2 = LinkFactory.create(aggregate_link_clicks=7, aggregate_firefox_downloads=10)
        link2_old_datapoint1 = DataPointFactory.create(link=link2, date=aware_date(2014, 1, 1),
                                                       link_clicks=8, firefox_downloads=4)
        link2_old_datapoint2 = DataPointFactory.create(link=link2, date=aware_date(2013, 12, 30),
                                                       link_clicks=2, firefox_downloads=7)

        path = 'affiliates.links.management.commands.aggregate_old_datapoints.timezone'
        with patch(path) as mock_timezone:
            mock_timezone.now.return_value = aware_datetime(2014, 4, 2)
            self.command.handle()

        # link1 should have 7+8=15 clicks, 10+4=14 downloads, and the
        # new datapoint should still exist.
        link1 = Link.objects.get(pk=link1.pk)
        eq_(link1.aggregate_link_clicks, 15)
        eq_(link1.aggregate_firefox_downloads, 14)
        ok_(not DataPoint.objects.filter(pk=link1_old_datapoint.pk).exists())
        ok_(DataPoint.objects.filter(pk=link1_new_datapoint.pk).exists())

        # link2 should have 7+8+2=17 clicks, 10+4+7=21 downloads, and the
        # old datapoints should not exist.
        link2 = Link.objects.get(pk=link2.pk)
        eq_(link2.aggregate_link_clicks, 17)
        eq_(link2.aggregate_firefox_downloads, 21)
        ok_(not DataPoint.objects.filter(pk=link2_old_datapoint1.pk).exists())
        ok_(not DataPoint.objects.filter(pk=link2_old_datapoint2.pk).exists())


class DenormalizeMetricsTests(TestCase):
    _date = date(2014, 1, 1)

    def setUp(self):
        self.command = denormalize_metrics.Command()
        self.command.METRICS = ('link_clicks',)

    def _datapoint(self, link, clicks):
        DataPointFactory.create(link_clicks=clicks, link=link, date=self._date)
        self._date += timedelta(days=1)

    def test_basic(self):
        category = CategoryFactory.create()
        banner1, banner2 = TextBannerFactory.create_batch(2, category=category)
        link1, link2 = LinkFactory.create_batch(2, banner_variation__banner=banner1)
        link3, link4 = LinkFactory.create_batch(2, banner_variation__banner=banner2)

        # Set datapoint totals.
        self._datapoint(link1, 4)
        self._datapoint(link1, 4)
        self._datapoint(link2, 3)
        self._datapoint(link2, 3)
        self._datapoint(link3, 2)
        self._datapoint(link3, 2)
        self._datapoint(link4, 1)
        self._datapoint(link4, 1)

        # Assert that data hasn't been denormalized yet.
        eq_(link1.link_clicks, 0)
        eq_(link2.link_clicks, 0)
        eq_(link3.link_clicks, 0)
        eq_(link4.link_clicks, 0)
        eq_(banner1.link_clicks, 0)
        eq_(banner2.link_clicks, 0)
        eq_(category.link_clicks, 0)

        self.command.handle()

        # Re-fetch data now that is has updated
        category = Category.objects.get(pk=category.pk)
        banner1, banner2 = TextBanner.objects.order_by('id')
        link1, link2, link3, link4 = Link.objects.order_by('id')

        # Assert that counts are now denormalized.
        eq_(link1.link_clicks, 8)
        eq_(link2.link_clicks, 6)
        eq_(link3.link_clicks, 4)
        eq_(link4.link_clicks, 2)
        eq_(banner1.link_clicks, 14)
        eq_(banner2.link_clicks, 6)
        eq_(category.link_clicks, 20)


class AnalyzeEventsTests(TestCase):
    def setUp(self):
        self.command = analyze_events.Command()
        self.command.quiet = False

    @waffle_switch('fraud_detection', False)
    def test_handle_quiet_fraud_off(self):
        """If fraud detection is off, do not run analysis."""
        LinkClickFactory.create_batch(2, datapoint__date=date(2014, 1, 1))

        self.command.check_user_agent_patterns = Mock()
        self.command.check_ip_address_patterns = Mock()
        self.command.handle_quiet()

        ok_(not self.command.check_user_agent_patterns.called)
        ok_(not self.command.check_ip_address_patterns.called)

    @waffle_switch('fraud_detection', True)
    def test_handle_quiet(self):
        """
        handle_quiet should run the analysis functions for each metric
        and then clear out their tables.
        """
        LinkClickFactory.create_batch(2, datapoint__date=date(2014, 1, 1))
        FirefoxDownloadFactory.create_batch(2, datapoint__date=date(2014, 1, 1))
        FirefoxOSReferralFactory.create_batch(2, datapoint__date=date(2014, 1, 1))

        self.command.check_user_agent_patterns = Mock()
        self.command.check_ip_address_patterns = Mock()
        self.command.handle_quiet()

        expected_calls = [call(FirefoxDownload), call(FirefoxOSReferral), call(LinkClick)]
        for expected_call in expected_calls:
            ok_(expected_call in self.command.check_user_agent_patterns.call_args_list)
            ok_(expected_call in self.command.check_ip_address_patterns.call_args_list)

        eq_(LinkClick.objects.count(), 0)
        eq_(FirefoxDownload.objects.count(), 0)
        eq_(FirefoxOSReferral.objects.count(), 0)

    @override_settings(BAD_USER_AGENTS=('wget', 'curl', 'phantomjs'))
    def test_check_user_agent_patterns(self):
        """
        check_user_agent_patterns should remove clicks for each
        user-agent matching a known-bad user-agent.
        """
        datapoint1, datapoint2 = DataPointFactory.create_batch(2, date=date(2014, 1, 1))

        curl = 'curl/7.9.8 (i686-pc-linux-gnu) libcurl 7.9.8 (OpenSSL 0.9.6b) (ipv6 enabled)'
        wget = 'Wget/1.9.1'
        phantomjs = ('Mozilla/5.0 (Unknown; Linux i686) AppleWebKit/534.34 (KHTML, like Gecko) '
                     'PhantomJS/1.9.1 Safari/534.34')

        LinkClickFactory.create(datapoint=datapoint1, user_agent='Firefox')
        LinkClickFactory.create(datapoint=datapoint1, user_agent=curl)
        LinkClickFactory.create(datapoint=datapoint2, user_agent=wget)
        LinkClickFactory.create(datapoint=datapoint2, user_agent=phantomjs)

        self.command.remove_fraudulent_events = Mock()
        self.command.check_user_agent_patterns(LinkClick)

        expected_calls = [
            call(datapoint1, 1, 'link_clicks', CONTAINS('curl')),
            call(datapoint2, 1, 'link_clicks', CONTAINS('wget')),
            call(datapoint2, 1, 'link_clicks', CONTAINS('phantomjs')),
        ]
        for expected_call in expected_calls:
            ok_(expected_call in self.command.remove_fraudulent_events.call_args_list)

    @override_settings(SINGLE_IP_THRESHOLD=10, IP_GROUP_THRESHOLD=2000)
    def test_check_ip_address_patterns(self):
        self.command.check_for_matching_attribute = Mock()
        self.command.check_ip_address_patterns(LinkClick)

        expected_calls = [call(LinkClick, 'ip', 10), call(LinkClick, 'ip_group', 2000)]
        for expected_call in expected_calls:
            ok_(expected_call in self.command.check_for_matching_attribute.call_args_list)

    def test_check_for_matching_attribute(self):
        """
        If a group of events with the same non-null attribute value is
        over the given threshold, check_for_matching_attribute should
        remove them.
        """
        datapoint1 = DataPointFactory.create(date=date(2014, 1, 1))
        LinkClickFactory.create_batch(11, ip='127.0.0.1', datapoint=datapoint1)
        LinkClickFactory.create_batch(9, ip='127.0.0.2', datapoint__date=date(2014, 1, 1))
        LinkClickFactory.create_batch(11, ip=None, datapoint__date=date(2014, 1, 1))

        self.command.remove_fraudulent_events = Mock()
        self.command.check_for_matching_attribute(LinkClick, 'ip', 10)

        eq_(self.command.remove_fraudulent_events.call_count, 1)
        self.command.remove_fraudulent_events.assert_called_with(datapoint1, 10, 'link_clicks',
                                                                 ANY)

    def test_remove_fraudulent_events(self):
        datapoint = Mock()

        self.command.remove_fraudulent_events(datapoint, 5, 'link_clicks', 'just because')
        datapoint.add_metric.assert_called_with('link_clicks', -5, save=True)
