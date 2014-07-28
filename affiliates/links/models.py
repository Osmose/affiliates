from django.contrib.auth.models import User
from django.contrib.contenttypes import generic
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone

from caching.base import CachingManager, CachingMixin
from funfactory.urlresolvers import reverse

from affiliates.base.utils import absolutify


class LinkManager(CachingManager):
    def total_link_clicks(self):
        """Return total number of clicks across the entire service."""
        aggregate_clicks = self.aggregate(a=models.Sum('aggregate_link_clicks'))['a'] or 0
        datapoint_clicks = DataPoint.objects.aggregate(d=models.Sum('link_clicks'))['d'] or 0
        return aggregate_clicks + datapoint_clicks


class Link(CachingMixin, models.Model):
    """Affiliate link that banners link to."""
    user = models.ForeignKey(User)
    html = models.TextField()

    banner_variation_content_type = models.ForeignKey(ContentType)
    banner_variation_id = models.PositiveIntegerField()
    banner_variation = generic.GenericForeignKey('banner_variation_content_type',
                                                 'banner_variation_id')

    # Denormalized metrics. The true source of these are the aggregate
    # counts plus the sum of counts on the DataPoints.
    link_clicks = models.PositiveIntegerField(default=0, editable=False)
    firefox_downloads = models.PositiveIntegerField(default=0, editable=False)
    firefox_os_referrals = models.PositiveIntegerField(default=0, editable=False)

    # Aggregates do not include data currently stored in the DataPoint
    # model. After a retention period, DataPoint data is added to these
    # aggregate counts and removed from the database.
    aggregate_link_clicks = models.PositiveIntegerField(default=0)
    aggregate_firefox_downloads = models.PositiveIntegerField(default=0)
    aggregate_firefox_os_referrals = models.PositiveIntegerField(default=0)

    # Ids for supporting old Affiliates URLs
    legacy_banner_instance_id = models.IntegerField(default=None, null=True)
    legacy_banner_image_id = models.IntegerField(default=None, null=True)

    created = models.DateTimeField(default=timezone.now)
    modified = models.DateTimeField(auto_now=True)

    objects = LinkManager()

    @property
    def banner(self):
        return self.banner_variation.banner if self.banner_variation else None

    @property
    def destination(self):
        return self.banner.destination

    @property
    def is_upgrade_link(self):
        from affiliates.banners.models import FirefoxUpgradeBanner
        return isinstance(self.banner, FirefoxUpgradeBanner)

    @property
    def is_image_link(self):
        from affiliates.banners.models import ImageBanner
        return isinstance(self.banner, ImageBanner)

    @property
    def is_text_link(self):
        from affiliates.banners.models import TextBanner
        return isinstance(self.banner, TextBanner)

    def preview_html(self, href):
        return self.banner.preview_html(href)

    def get_referral_url(self):
        return absolutify(reverse('links.referral', args=[self.pk]))

    def get_absolute_url(self):
        return reverse('links.detail', args=[self.pk])


class DataPoint(CachingMixin, models.Model):
    """Stores the metric totals for a specific day, for a link."""
    link = models.ForeignKey(Link)
    date = models.DateField()

    link_clicks = models.PositiveIntegerField(default=0)
    firefox_downloads = models.PositiveIntegerField(default=0)
    firefox_os_referrals = models.PositiveIntegerField(default=0)

    objects = CachingManager()

    class Meta:
        unique_together = ('link', 'date')

    def add_metric(self, metric, count, save=False):
        """
        Add to a metric count for this datapoint, including denormalized
        counts stored on related objects.
        """
        updated_count = models.F(metric) + count
        setattr(self, metric, updated_count)
        setattr(self.link, metric, updated_count)
        setattr(self.link.banner, metric, updated_count)
        setattr(self.link.banner.category, metric, updated_count)

        if save:
            self.save()
            self.link.save()
            self.link.banner.save()
            self.link.banner.category.save()

    def __unicode__(self):
        return u'<DataPoint: {0}>'.format(self.pk)


class Event(models.Model):
    """A single event for a certain metric. Used for fraud analysis."""
    datapoint = models.ForeignKey(DataPoint)
    ip = models.GenericIPAddressField(blank=True, null=True)
    ip_group = models.CharField(max_length=255, blank=True, null=True)
    user_agent = models.CharField(max_length=255, blank=True)

    class Meta:
        abstract = True

    @property
    def attr_name(self):
        """
        Name of the attribute on DataPoints that tracks events of this
        type.
        """
        raise NotImplementedError()


class LinkClick(Event):
    attr_name = 'link_clicks'


class FirefoxDownload(Event):
    attr_name = 'firefox_downloads'


class FirefoxOSReferral(Event):
    attr_name = 'firefox_os_referrals'


class LeaderboardStanding(CachingMixin, models.Model):
    """Ranking in a leaderboard for a specific metric."""
    ranking = models.PositiveIntegerField()
    user = models.ForeignKey(User)
    value = models.PositiveIntegerField(default=0)
    metric = models.CharField(max_length=255, choices=(
        ('link_clicks', 'Link Clicks'),
        ('firefox_downloads', 'Firefox Downloads'),
        ('firefox_os_referrals', ('Firefox OS Referrals'))
    ))

    objects = CachingManager()

    class Meta:
        unique_together = ('ranking', 'metric')

    def __unicode__(self):
        return u'{metric}: {ranking}'.format(metric=self.metric, ranking=self.ranking)


class FraudAction(models.Model):
    """
    An automated action taken in response to suspected fraud. Admins are
    able to review and reverse these actions.
    """
    datapoint = models.ForeignKey(DataPoint)
    count = models.IntegerField()
    metric = models.CharField(max_length=255)
    reason = models.CharField(max_length=255)

    executed_on = models.DateTimeField(default=None, null=True)
    reversed_on = models.DateTimeField(default=None, null=True)

    def execute(self):
        if self.executed_on is None:
            self.datapoint.add_metric(self.metric, self.count, save=True)
            self.executed_on = timezone.now()
            self.save()
        else:
            raise RuntimeError('Cannot execute action; it is already executed.')

    def reverse(self):
        if self.reversed_on is None:
            self.datapoint.add_metric(self.metric, -self.count, save=True)
            self.reversed_on = timezone.now()
            self.save()
        else:
            raise RuntimeError('Cannot reverse action; it is already reversed.')
