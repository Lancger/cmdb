# coding=utf-8
from django import template
# from cmdb.models import AppFiles, AppConf

register = template.Library()


@register.filter
def appfiles(ip, field):
    # 获取AppFiles项
    af = AppFiles.objects.filter(host__ip=ip)
    if af:
        return getattr(af[0], field)
    else:
        return '??'


@register.filter
def var(text, appsh):
    # 将脚本文本变量替换为对应值

    return AppConf.get_format_sh(text, {'app': appsh.app.name, 'apppath': appsh.app.appname})


@register.filter
def debug(mm, nn):
    # 模板调试
    import ipdb; ipdb.set_trace()
    print dir(mm)
    print nn, 777
    return
