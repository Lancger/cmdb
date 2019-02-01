# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.shortcuts import render, render_to_response, redirect, HttpResponse, get_object_or_404, Http404
from django.core.exceptions import PermissionDenied
from django.contrib.auth.decorators import login_required

from django.views.generic import TemplateView, ListView, View, DetailView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin

from django.core.cache import cache
import json
import threading
import time

from django.contrib.auth.models import User, Group

from cmdb.models import ES, Host
# from cmdb.models import Host, Balance
# from forms import HostForm, BalanceForm,

from elasticsearch import Elasticsearch
from conf import RedisTimeOut
from django.urls import reverse_lazy

import sys
reload(sys)
sys.setdefaultencoding('UTF-8')


class ESList(LoginRequiredMixin, ListView):
    template_name = "eslist.html"
    model = ES

    def get_context_data(self, **kwargs):
        kwargs['cmdb_es_active'] = 'active'
        return super(self.__class__, self).get_context_data(**kwargs)


class ESView(LoginRequiredMixin, UpdateView):
    template_name = "es.html"
    model = ES
    fields = ['cluster', 'node', 'host', 'port']

    def get_context_data(self, **kwargs):
        kwargs['cmdb_es_active'] = 'active'
        user = self.request.user
        if not self.object.host.chk_user_prem(user, 'other_do'):
            # 无主机操作权限时只读
            kwargs['readonly'] = 'readonly'
        return super(self.__class__, self).get_context_data(**kwargs)


class ESIndices(LoginRequiredMixin, DetailView):
    template_name = "esindices.html"
    model = ES
    indices_objs = []

    def get_indices(self, es, refresh=0, only_open=1):
        # 获取ES节点所有索引信息

        h = 'i,s,h,dc,ss'  # 指定所需获取的Elasticsearch API参数，_cat/indices?help
        # http://10.5.0.55:9201/_cat/indices?v&h=i,s,h,dc,dd,tm,ss
        hs = h.split(',')
        indices = cache.get('es_%d' % es.id)
        if refresh or not indices:
            url = 'http://%s:%s' % (es.host.ip, es.port)
            conn = Elasticsearch(hosts=[url], timeout=30)
            try:
                data = conn.cat.indices(params={'h': h})
                # print data,8989
            except Exception as e:
                print u'Error: connect failed', url, e
                self.indices_objs = str(e)
                return

            # 开始数据处理、格式化
            indices = []
            # print type(data),333
            if type(data) in (str, unicode):
                # Elasticsearch 5.*
                datas = data.splitlines()
                for i in datas:
                    line = i.split(' ')
                    index_datas = [l for l in line if l] + [''] * len(hs)
                    # index_key = index_datas[0]
                    # index_val = index_datas[1:]
                    indices.append(index_datas)

            else:
                # Elasticsearch 2.* 为字典列表
                datas = data
                for i in datas:
                    index_datas = [i[z] if i[z] else '' for z in hs]
                    indices.append(index_datas)

            # indices.sort(key=lambda x: (x[1], x[0]), reverse=True)  # 按第二列(打开/关闭)、第一列(索引名) 进行倒序排序
            # indices.sort(key=lambda x:x[0], reverse=True ) #按索引名进行倒序排序
            cache.set('es_%d' % es.id, indices, timeout=RedisTimeOut)
            # print indices

        class Obj:
            pass
        indices_objs = []
        for index in indices:
            # print index, 444
            if only_open and index[1] != 'open':
                # 显示开启项
                continue

            index_obj = Obj()
            n = 0
            for item in hs:
                setattr(index_obj, item, index[n])
                n += 1

            indices_objs.append(index_obj)

        self.indices_objs = indices_objs if indices_objs else '{"msg": "无符合条件的索引"}'

    # cache.iter_keys("*")

    def get_context_data(self, **kwargs):
        # import ipdb;ipdb.set_trace()
        try:
            refresh = int(self.request.GET.get('refresh', '0'))  # 是否使用缓存
            only_open = int(self.request.GET.get('o', '1'))  # 只显示开启的索引
        except:
            refresh = 0
            only_open = 1
        # indices = self.get_indices(self.object, refresh)
        th = threading.Thread(target=self.get_indices, args=(self.object, refresh, only_open))
        th.setDaemon(True)
        th.start()
        # print indices,777
        n = 0
        while not self.indices_objs:
            if n > 100:
                break
            time.sleep(1)
            # print n, '...'
            n += 1
        kwargs['indices'] = self.indices_objs if self.indices_objs else 'Error: TimeOut!'

        user = self.request.user
        if not self.object.host.chk_user_prem(user, 'other_do'):
            # 无主机操作权限时只读
            kwargs['readonly'] = 'readonly'
        return super(self.__class__, self).get_context_data(**kwargs)

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        context = self.get_context_data(object=self.object)
        indices = context.get('indices')
        if type(indices) != list:
            # 从ES节点获取索引信息失败
            # print indices, 1111
            # print type(indices), 2222
            # import ipdb;ipdb.set_trace()
            return HttpResponse(indices)

        return self.render_to_response(context)


@login_required(login_url="/login")
def do_indices(request, pk, do, index):
    # ES索引 打开/关闭

    # print  pk, index, do, 9999
    # if request.method not in ('POST', 'PUT') :
    #     return HttpResponse('??')

    es = get_object_or_404(ES, id=pk)
    if do not in ('open', 'close'):
        if not (request.user.is_superuser and es.host.ip in ['10.2.21.21', '10.7.21.10', '10.5.0.55']):
            ret = {'status': '?', 'msg': '%s, 想要干什么??!!' % do, }
            return HttpResponse(json.dumps(ret))

    if not es.host.chk_user_prem(request.user, 'other_do'):
        msg = u'当前登陆用户没有ES主机other_do_host操作权限'
        return HttpResponse(json.dumps({'status': '?', 'msg': msg, }))

    ES_URL = 'http://%s:%s' % (es.host.ip, es.port)
    # print ES_URL
    conn = Elasticsearch(hosts=[ES_URL], timeout=30)

    try:
        msg = getattr(conn.indices, do)(index)
        try:
            result = int(msg['acknowledged'])
        except:
            result = '?'
        # import ipdb;ipdb.set_trace()
    except Exception as e:
        result = '0'
        msg = e

    # import ipdb;ipdb.set_trace()
    ret = {'status': str(result), 'msg': str(msg), }
    return HttpResponse(json.dumps(ret))


class UserList(LoginRequiredMixin, ListView):
    template_name = 'userlist.html'
    model = User
    # context_object_name = 'user_list'

    def get_context_data(self, **kwargs):
        kwargs['cmdb_user_active'] = 'active'
        kwargs['group_list'] = Group.objects.all().order_by('name')

        return super(self.__class__, self).get_context_data(**kwargs)

    def get(self, request, *args, **kwargs):
        if not self.request.user.has_perm('auth.view_user'):
            raise PermissionDenied
        return super(self.__class__, self).get(request, *args, **kwargs)


class UserEdit(LoginRequiredMixin, UpdateView):
    template_name = "user.html"
    model = User
    fields = ['username', 'email', 'is_superuser', 'is_staff']
    success_url = reverse_lazy('cmdb:user')
    perm_model = 'auth.change_user'

    def get(self, request, *args, **kwargs):
        if not self.request.user.has_perm(self.perm_model):
            raise PermissionDenied
        return UpdateView.get(self, request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        # print self.object, 898989
        kwargs['hosts_on'] = self.object.host_set.all()
        kwargs['hosts_off'] = set(Host.objects.all()) - set(kwargs['hosts_on'])  # 差集
        # kwargs['apps_on'] = self.object.app_set.all()
        # kwargs['apps_off'] = set(App.objects.all()) - set(kwargs['apps_on'])  # 差集
        return UpdateView.get_context_data(self, **kwargs)

    def post(self, request, *args, **kwargs):

        # print args, kwargs, 8888888, request.POST
        host_ids = request.POST.getlist('host', [])
        app_ids = request.POST.getlist('app', [])
        self.object = self.get_object()
        form = self.get_form()
        # import ipdb;ipdb.set_trace()
        if form.is_valid():
            return self.form_valid(form, host_ids, app_ids)
        else:
            return self.form_invalid(form)

    def form_valid(self, form, host_ids=[], app_ids=[]):
        self.object = form.save()

        # 添加m2m关联
        hosts_new = Host.objects.filter(id__in=host_ids)
        try:
            self.object.host_set.set(hosts_new)
        except:
            print 'Error: host：%s, 出现未知异常情况，有主机刚被删除？！' % host_ids

        apps_new = App.objects.filter(id__in=app_ids)
        try:
            self.object.app_set.set(apps_new)
        except:
            print 'Error: host：%s, 出现未知异常情况，有APP刚被删除？！' % app_ids

        return redirect(self.get_success_url())
        # return super(self.__class__, self).form_valid(form)


class UserGroupEdit(UserEdit):
    template_name = "usergroup.html"
    model = Group
    fields = ['name', ]
    perm_model = 'auth.change_group'

# from django.http import HttpRequest
