from django.db.models import Count

from affiliates.base.management.commands import QuietCommand
from affiliates.links.models import DataPoint, FirefoxDownload, FirefoxOSReferral, LinkClick


class Command(QuietCommand):
    help = ('Collect metrics into datapoints, and analyze them for fraud.')

    def handle_quiet(self, *args, **kwargs):
        for Metric in (FirefoxDownload, FirefoxOSReferral, LinkClick):
            self.output('Analyzing {0}s...'.format(Metric.__name__))
            related_name = Metric.datapoint.field.related_query_name()

            self.check_user_agent_patterns(related_name, Metric.attr_name)

            # Clean out table now that analysis is done.
            Metric.objects.all().delete()

        self.output('Done!')

    def check_user_agent_patterns(self, related_name, attr_name):
        """
        Search for known-bad user agents and remove those events. Not
        the strongest anti-fraud measure by any means, but we've seen it
        in the past.
        """
        # TODO: Find a list of these rather than just relying on what
        # we've seen.
        bad_user_agents = ('wget', 'curl', 'phantomjs')
        filter_name = '{0}__user_agent__icontains'.format(related_name)

        for user_agent in bad_user_agents:
            matching_datapoints = (DataPoint.objects
                                   .filter(**{filter_name: user_agent})
                                   .annotate(fraud_count=Count(related_name)))

            for datapoint in matching_datapoints:
                msg = ('Removing {count} {attr_name} from datapoint {pk} due to invalid user '
                       'agent: {user_agent}')
                self.output(msg, attr_name=attr_name, count=datapoint.fraud_count, pk=datapoint.pk,
                            user_agent=user_agent)

                datapoint.add_metric(attr_name, -datapoint.fraud_count, save=True)
