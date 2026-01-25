from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),

    path("auth/", include("accounts.urls")),
    path("", include("pages.urls")),
#    path("", include("money.urls")),
path("app/", include("budget.urls")),

]

from django.conf import settings
from django.conf.urls.static import static

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)