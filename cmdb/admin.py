# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib import admin
from django.forms import widgets

from cmdb import models
from forms import HostForm

from readonly.addreadonly import ReadOnlyAdmin, ReadOnlyEditAdmin, MyAdmin as MyAdmin
from suit import apps
# 表单编辑界面input等默认宽度为col-lg-7，有些窄，改为col-lg-9
apps.DjangoSuitConfig.form_size['default'] = apps.SUIT_FORM_SIZE_XXX_LARGE

# import types
# @classmethod
# def addMethod(cls, func):
#     return setattr(cls, func.__name__, types.MethodType(func, cls))


# from django.contrib import auth
# admin.site.unregister(auth.models.User)


# @admin.register(auth.models.User)
# class MyUserAdmin(auth.admin.UserAdmin):
#     # 自定义auth.User后台版面
#     def __init__(self, model, admin_site):
#         self.suit_form_tabs = [('/tab_1', 'name1'), ('/tab_2', 'name2'), ]
#         super(self.__class__, self).__init__(model, admin_site)


@admin.register(models.HostGroup)
class HostGroup_admin(MyAdmin):

    list_display = ('name', 'ip', 'desc')


# class Host_User_Inline(admin.TabularInline):
#     model = models.Host_User


@admin.register(models.Host)
class Host_admin(MyAdmin):
    # inlines = [
    #     Host_User_Inline,
    # ]
    form = HostForm
    list_display = ('name', 'hostname', 'ip', 'group', 'tomcat_ver', 'jdk_ver', 'changetime')
    search_fields = ('name', 'hostname', 'ip', 'tomcat_ver', 'jdk_ver')

    list_filter = ('group', 'asset_type', 'tomcat_ver', 'jdk_ver')
    # filter_horizontal = ('app',)
    fieldsets = [
        ('基础信息', {'fields': ['name', 'hostname', 'ip', 'other_ip', 'port', 'group', 'usergroup', 'tomcat_ver', 'jdk_ver', 'app', 'ssh_user', 'ports']}),
        ('软硬件信息', {'fields': ['os', 'kernel', 'cpu_model', 'cpu_num', 'memory', 'disk', 'vendor', 'sn'], }),
        ('业务信息', {'fields': ['status', 'asset_type', 'machine', 'buydate', 'position', 'sernumb', 'sercode', 'admin', ], 'classes': ['collapse'], }),
        ('其它信息', {'fields': ['createtime', 'agenttime', 'tomcat', 'text', ], }),
    ]

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = list(super(self.__class__, self).get_readonly_fields(request, obj=None))
        # print readonly_fields,33333333333

        readonly_fields.append('createtime')
        readonly_fields.append('agenttime')
        # print readonly_fields
        return readonly_fields


from forms import SshUserForm


@admin.register(models.SshUser)
class SshUser_admin(MyAdmin):
    form = SshUserForm
    list_display = ('name', 'username', 'password', 'changetime', 'text')
    search_fields = ('name', 'username')


@admin.register(models.ES)
class ES_admin(MyAdmin):
    list_display = ('name', 'cluster', 'node', 'host', 'port')
    search_fields = ('name', 'host__name', 'host__ip')


@admin.register(models.CMD)
class CMD_admin(ReadOnlyAdmin):
    list_display = ('cmd', 'ctype', 'createtime', 'end')
    search_fields = ('cmd', )
    filter_horizontal = ('host',)
    list_filter = ('ctype', )


@admin.register(models.CMD_Log)
class CMD_Log_admin(ReadOnlyAdmin):
    list_display = ('cmd', 'host', 'createtime')
    search_fields = ('cmd__cmd', 'host__ip')
    suit_form_size = {'default': apps.SUIT_FORM_SIZE_FULL}  # 加宽表单编辑界面input等宽度


@admin.register(models.SH)
class SH_admin(MyAdmin):
    list_display = ('name', 'fname', 'sh', 'createtime')
    search_fields = ('fname', 'name')

    list_filter = ('sh',)


from django.contrib import auth


class UserProfileInline(admin.StackedInline):
    model = models.UserProfile
    max_num = 1
    can_delete = False


class UserAdmin(auth.admin.UserAdmin):
    inlines = [UserProfileInline, ]

admin.site.unregister(auth.models.User)
admin.site.register(auth.models.User, UserAdmin)


@admin.register(models.DockerHost)
class DockerHost_admin(MyAdmin):
    list_display = ('name', 'ip', 'port', 'tls', )
    search_fields = ('ip', 'name')


@admin.register(models.DockerYmlGroup)
class DockerYmlGroup_admin(MyAdmin):
    list_display = ('name', 'path', 'desc')


@admin.register(models.DockerYml)
class DockerYml_admin(MyAdmin):
    list_display = ('name', 'group', 'file')
    search_fields = ('name', )
    list_filter = ('group',)


@admin.register(models.DockerCompose)
class DockerCompose_admin(MyAdmin):
    list_display = ('name', 'dockerhost', 'yml', 'scale', )
    search_fields = ('name', 'yml')
    list_filter = ('dockerhost',)

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = list(super(self.__class__, self).get_readonly_fields(request, obj=None))
        readonly_fields.append('dockerhost')
        readonly_fields.append('yml')
        return readonly_fields


@admin.register(models.SshUserCheck)
class SshUserCheck_admin(MyAdmin):
    list_display = ('host', 'password', 'error', 'createtime', )
    search_fields = ('host',)
