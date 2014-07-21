import waffle
from celery.decorators import task

from affiliates.links.models import Link, LinkClick


@task
def add_click(link_id, date_today, ip, user_agent):
    """Increment the click count for a link."""
    try:
        link = Link.objects.get(id=link_id)
    except Link.DoesNotExist:
        return

    datapoint, created = link.datapoint_set.get_or_create(date=date_today)
    datapoint.add_metric('link_clicks', 1, save=True)

    # Add link click entry for this click.
    if waffle.switch_is_active('fraud_detection'):
        LinkClick.objects.create(datapoint=datapoint, ip=ip, user_agent=user_agent)
