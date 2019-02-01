# coding=utf-8
"""dj URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.11/topics/http/urls/
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
from django.conf.urls import url, include
from django.contrib import admin
from views import index, login, logout, password_change, test
from django.conf import settings
from django.views.static import serve
# from django.contrib.auth.views import login,logout

from django.views.generic.base import RedirectView

from django.contrib.staticfiles.urls import staticfiles_urlpatterns

urlpatterns = [
    url(r'^admin/login', RedirectView.as_view(pattern_name="login"), ),  # 增加了otp验证
    url(r'^admin/password_change', RedirectView.as_view(pattern_name="password_change"), ),  # 增加了密码过期验证
    url(r'^admin/', admin.site.urls, name="admin"),
    url(r'^login', login, name="login"),
    url(r'^password_change', password_change, name="password_change"),
    # url(r'^otp', otp, name="otp"),
    url(r'^logout', logout, name="logout"),
    url(r'^cmdb/', include('cmdb.urls', namespace="cmdb", app_name='cmdb')),

    url(r'^favicon\.ico$', RedirectView.as_view(url='/static/img/favicon.ico', permanent=True), ),
    url(r'^elfinder/', include('elfinder.urls')),
    url(r'^test$', test),
    url(r'^$', index),

]


urlpatterns += staticfiles_urlpatterns()
urlpatterns += [
    url(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT, }, name="media"),
]

import mimetypes
if '.svg' not in mimetypes.types_map:
    # CentOS7默认安装的python2.7.5版本偏旧，mime不含svg，导致svg图片不显示
    # 也可使用nginx，mime支持svg
    mimetypes.types_map['.svg'] = 'image/svg+xml'
