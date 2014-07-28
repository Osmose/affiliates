from django.conf import settings
from django.db.models import Count

import waffle

from affiliates.base.management.commands import QuietCommand
from affiliates.links.models import DataPoint, FirefoxDownload, FirefoxOSReferral, LinkClick


class Command(QuietCommand):
    help = ('Analyze metric event logs for fraud.')

    def handle_quiet(self, *args, **kwargs):
        if not waffle.switch_is_active('fraud_detection'):
            self.output('Fraud detection is disabled, aborting.')
            return

        for Event in (FirefoxDownload, FirefoxOSReferral, LinkClick):
            self.output('Analyzing {0}s...'.format(Event.__name__))

            self.check_user_agent_patterns(Event)
            self.check_ip_address_patterns(Event)

            # Clean out table now that analysis is done.
            Event.objects.all().delete()

        self.output('Done!')

    def check_user_agent_patterns(self, Event):
        """
        Search for known-bad user agents and remove those events. Not
        the strongest anti-fraud measure by any means, but we've seen it
        in the past.
        """
        related_name = Event.datapoint.field.related_query_name()
        filter_name = '{0}__user_agent__icontains'.format(related_name)

        for user_agent in settings.BAD_USER_AGENTS:
            matching_datapoints = (DataPoint.objects
                                   .filter(**{filter_name: user_agent})
                                   .annotate(fraud_count=Count(related_name)))

            for datapoint in matching_datapoints:
                reason = 'Invalid user agent: ' + user_agent
                self.remove_fraudulent_events(datapoint, datapoint.fraud_count, Event.attr_name,
                                              reason)

    def check_ip_address_patterns(self, Event):
        """
        Search for suspiciously large click counts from single IPs or
        IP blocks.
        """
        # Check for events from the same IP address.
        self.check_for_matching_attribute(Event, 'ip', settings.SINGLE_IP_THRESHOLD)

        # Check for events from the same IP group.
        self.check_for_matching_attribute(Event, 'ip_group', settings.IP_GROUP_THRESHOLD)

    def check_for_matching_attribute(self, Event, attr_name, threshold):
        """
        Search for events that all share the same value in an attribute.
        If the number of events sharing the same value is over a certain
        threshold, remove them as fraudulent events.

        :param Event:
            Event class to check.

        :param attr_name:
            Name of the attribute to group events by.

        :param threshold:
            Number of events that a group count needs to surpass in
            order to get removed.
        """
        null_filter = {'{0}__isnull'.format(attr_name): False}
        matching_events = (Event.objects
                           .values_list(attr_name, 'datapoint_id')
                           .annotate(count=Count('id'))
                           .filter(count__gte=threshold, **null_filter))

        for attr_value, datapoint_id, count in matching_events:
            reason = 'More than {count} {event_name}s from {attr_value}'.format(
                count=count, event_name=Event.__name__, attr_value=(attr_value + '.*'))

            datapoint = DataPoint.objects.get(pk=datapoint_id)
            self.remove_fraudulent_events(datapoint, count - 1, Event.attr_name, reason)

    def remove_fraudulent_events(self, datapoint, count, metric, reason):
        msg = 'Removing {count} {metric} from link {pk}: {reason}'
        self.output(msg, count=count, metric=metric, pk=datapoint.link.pk, reason=reason)

        datapoint.add_metric(metric, -count, save=True)
