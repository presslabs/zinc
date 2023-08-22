"""zinc URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.9/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
from django.conf import settings
from django.urls import include, path
from django.contrib import admin

from zinc.views import HealtchCheck

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('zinc.urls')),
    path('_health', HealtchCheck.as_view())
]

if settings.SOCIAL_AUTH_GOOGLE_OAUTH2_KEY:
    urlpatterns.append(
        path('_auth/', include('social_django.urls', namespace='social', app_name='social_django'))
    )

if settings.SERVE_STATIC:
    from django.conf.urls.static import static
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

try:
    from rest_framework_swagger.views import get_swagger_view
except ImportError:
    pass
else:
    schema_view = get_swagger_view(title='API')
    urlpatterns.append(path('^swagger/$', schema_view))

if settings.DEBUG:
    try:
        import debug_toolbar
    except ImportError:
        pass
    else:
        urlpatterns.insert(0, path(r'^__debug__/', include(debug_toolbar.urls)))
