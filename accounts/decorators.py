import os
from functools import wraps

from django.contrib import messages
from django.core.cache import cache
from django.shortcuts import redirect


def user_not_authenticated(function=None, redirect_url='/'):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if request.user.is_authenticated:
                return redirect(redirect_url)

            return view_func(request, *args, **kwargs)

        return _wrapped_view

    if function:
        return decorator(function)

    return decorator


# Number of reverse-proxy hops in front of the app (e.g. Render's own
# proxy = 1). Each hop APPENDS the address it saw to X-Forwarded-For, so
# only the last NUM_PROXIES entries are trustworthy — anything earlier in
# the list can be forged freely by the client. Set to 0 if the app is
# reachable directly (no reverse proxy), which ignores the header
# entirely and prevents IP spoofing from bypassing the rate limiter below.
_NUM_TRUSTED_PROXIES = int(os.getenv("NUM_PROXIES", "1"))


def _client_ip(request):
    if _NUM_TRUSTED_PROXIES > 0:
        forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if forwarded_for:
            hops = [ip.strip() for ip in forwarded_for.split(',') if ip.strip()]
            if len(hops) >= _NUM_TRUSTED_PROXIES:
                return hops[-_NUM_TRUSTED_PROXIES]
    return request.META.get('REMOTE_ADDR', 'unknown')


def ratelimit_post(key_prefix, limit=10, period_seconds=300):
    """Throttle POST requests per client IP. Best-effort protection against
    scripted brute force; relies on Django's cache backend (per-process by
    default), so a shared cache (e.g. Redis) is recommended for multi-worker
    deployments."""
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if request.method == 'POST':
                cache_key = f"ratelimit:{key_prefix}:{_client_ip(request)}"
                attempts = cache.get(cache_key, 0)
                if attempts >= limit:
                    messages.error(request, "Too many attempts. Please try again in a few minutes.")
                    return redirect(request.path)
                cache.set(cache_key, attempts + 1, period_seconds)

            return view_func(request, *args, **kwargs)

        return _wrapped_view

    return decorator