"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from library.views import robots_txt_view, service_worker, sitemap_xml_view

urlpatterns = [
    path('heaven/', admin.site.urls),
    path('service-worker.js', service_worker, name='service-worker'),
    path('robots.txt', robots_txt_view, name='robots_txt'),
    path('sitemap.xml', sitemap_xml_view, name='sitemap'),
    path('', include('library.urls')),
]

if settings.DEBUG:
    # В проде картинки постов (media/) отдаёт nginx напрямую - см. deploy-заметки.
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
