import waffle
from celery.decorators import task
from ipaddress import ip_address

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
        try:
            ip = ip_address(unicode(ip))
            full_ip = ip.exploded
            ip_group = _get_ip_group(ip)
        except ValueError:
            full_ip = None
            ip_group = None

        LinkClick.objects.create(datapoint=datapoint, ip=full_ip, ip_group=ip_group,
                                 user_agent=user_agent)


def _get_ip_group(ip):
    if ip.version == 4:
        return ip.exploded.rsplit('.', 1)[0]  # C Block
    elif ip.version == 6:
        return ip.exploded.rsplit(':', 5)[0]  # /48
    else:
        return None
