# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.apps import AppConfig

from suit.apps import DjangoSuitConfig


class CmdbConfig(AppConfig):
    name = 'cmdb'
    verbose_name = '资产管理'


class SuitConfig(DjangoSuitConfig):
    layout = 'vertical'  # 垂直样式
    # layout = 'horizontal' #水平样式
