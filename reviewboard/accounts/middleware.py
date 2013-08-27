import pytz

from django.conf import settings
from django.contrib.auth import authenticate, login
from django.utils import timezone

from reviewboard.accounts.models import Profile


class TimezoneMiddleware(object):
    """Middleware that activates the user's local timezone"""
    def process_request(self, request):
        if request.user.is_authenticated():
            try:
                user = Profile.objects.get(user=request.user)
                timezone.activate(pytz.timezone(user.timezone))
            except Profile.DoesNotExist:
                pass


class BugzillaCookieAuthMiddleware(object):
    """Set Bugzilla login cookies from auth backend."""
    def process_response(self, request, response):
        if ('reviewboard.accounts.backends.BugzillaBackend'
            not in settings.AUTHENTICATION_BACKENDS):
            return response
        if not request.user.is_authenticated():
            return response
        try:
            bzlogin = getattr(request.user, 'bzlogin')
            bzcookie = getattr(request.user, 'bzcookie')
        except AttributeError:
            return response
        if not bzlogin or not bzcookie:
            return response
        response.set_cookie('Bugzilla_login', bzlogin)
        response.set_cookie('Bugzilla_logincookie', bzcookie)
        return response
