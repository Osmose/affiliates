from django.conf import settings

from commonware.response.middleware import FrameOptionsHeader as CommonwareFrameOptionsHeader


class ExceptionLoggingMiddleware(object):
    """
    Small middleware that logs exceptions to the console. Useful in local
    development.
    """
    def process_exception(self, request, exception):
        import traceback
        print traceback.format_exc()


class PrivacyMiddleware(object):
    """Adds P3P policy headers to responses."""
    def process_response(self, request, response):
        response['P3P'] = ('CP="Mozilla\'s privacy practices are described at '
                           'https://mozilla.org/privacy"')
        return response


class FrameOptionsHeader(CommonwareFrameOptionsHeader):
    # Disables X-Frame-Options when DEV = True.
    def process_response(self, request, response):
        if settings.DEV:
            return response
        else:
            return super(FrameOptionsHeader, self).process_response(request, response)
