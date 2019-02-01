# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.shortcuts import render, render_to_response, redirect, HttpResponse, get_object_or_404, Http404
from django.core.exceptions import PermissionDenied
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.decorators import login_required
from django.views.generic import TemplateView, ListView, View
from django.http.request import QueryDict
# from django.db.models import Q
# from django.conf import settings

from django.http.response import HttpResponseRedirect

from cmdb.models import *
from forms import HostForm2, HostForm

from . import conf
import random

import json
import threading
import time
import sys
reload(sys)
sys.setdefaultencoding('UTF-8')


@login_required(login_url="/login")
def host(request):
    # 获取服务器清单

    active = 'cmdb_host_active'
    context = {}
    t = request.GET.get('t', '')  # 资产类型ID
    m = request.GET.get('m', '')  # 物理机ID
    b = request.GET.get('b', '')  # 负载均衡ID
    html = 'hostlist_1.html'

    if not request.user.has_perm('cmdb.view_host'):
        raise PermissionDenied

    if m.isdigit():
        # 物理机名下主机
        html = 'hostlist_2.html'
        active = 'cmdb_host_2_active'
        hosts = Host.objects.filter(machine=m)
        parent_name = hosts.first().machine if hosts else 'None'
        context.update({'parent_name': parent_name})
    elif b.isdigit():
        # 负载均衡名下主机
        html = 'hostlist_2.html'
        active = 'cmdb_host_2_active'
        hosts = Host.objects.filter(balance=b)
        # import ipdb;ipdb.set_trace()
        parent_name = get_object_or_404(Balance, id=b).name
        context.update({'parent_name': parent_name})

    else:  # if t.isdigit():
        if t not in ('1', '2', '4'):
            t = '1'
        html = 'hostlist_%s.html' % t
        active = 'cmdb_host_%s_active' % t

        hosts = Host.objects.filter(asset_type=t)

    context.update({'hosts': hosts, active: 'active'})

    return render(request, html, context)


def host_edit(request, id):
    if not request.user.has_perm('cmdb.change_host'):
        raise PermissionDenied

    host = get_object_or_404(Host, id=id)
    context = {}
    html = 'host_%d.html' % host.asset_type

    if request.method == 'POST':
        # print 1111,request.POST,3333
        # import ipdb;ipdb.set_trace()
        form = HostForm2(request.POST, instance=host)
        if form.is_valid():
            if host.asset_type == 1:
                host_ids_new = request.POST.getlist('host')  # 若为物理机编辑页面，会提交此字段
                # 若host_ids为空，有二种情况，一是(正常/异常)本身就没POST数据；二是设置当前物理机名下虚拟机为空
                # print type(host_ids_new),99999999,host_ids_new
                # print host_ids,8888
                Host.objects.filter(machine=id).update(machine=None)
                hosts = Host.objects.filter(id__in=host_ids_new).exclude(asset_type=1)
                hosts.update(machine=id)  # 设置虚拟机/容器所属物理机

            form.save()
            return redirect(request.get_full_path())
    else:
        if host.asset_type == 1:
            # 物理机，显示设置名下虚拟机清单
            # hosts = Host.objects.exclude(asset_type=1).filter( Q(machine__isnull=True)|Q(machine=id), )
            vhosts = Host.objects.exclude(asset_type=1)
            hosts_on = vhosts.filter(machine=id, )
            hosts_off = vhosts.filter(machine__isnull=True, )
            context.update({'hosts_on': hosts_on, 'hosts_off': hosts_off, })

        form = HostForm2(instance=host)

    active = 'cmdb_host_%d_active' % host.asset_type if host.asset_type else 0
    context.update({'form': form, 'id': id, active: 'active'})

    return render(request, html, context)


def host_add(request):
    if not request.user.has_perm('cmdb.add_host'):
        raise PermissionDenied

    t = request.GET.get('t', '2')  # 资产类型ID
    active = 'cmdb_host_1_active' if t == '1' else 'cmdb_host_2_active'

    context = {active: 'active'}
    if request.method == 'POST':
        # import ipdb;ipdb.set_trace()
        newhost = QueryDict(mutable=True)
        newhost.update(request.POST)
        newhost.update({'asset_type': t})
        form = HostForm(newhost)
        if form.is_valid():
            form.save()
            ref_url = request.POST.get('ref_url', '/')
            return redirect(ref_url)
    else:
        form = HostForm()
        ref_url = request.META.get('HTTP_REFERER', '/')  # 来源URL,供POST成功后返回
        context.update({'ref_url': ref_url})

    context.update({'form': form})
    html = 'host_2.html'

    return render(request, html, context)


def host_del(request):
    if not request.user.has_perm('cmdb.delete_host'):
        raise PermissionDenied

    ret = {'status': True, 'error': None, }
    try:
        id = request.POST.get('nid', None)
        host = Host.objects.get(id=id)
        host.delete()
    except Exception as e:
        ret = {
            "static": False,
            "error": '删除请求错误,{}'.format(e)
        }
    return HttpResponse(json.dumps(ret))


def host_alldel(request):
    if not request.user.has_perm('cmdb.delete_host'):
        raise PermissionDenied

    ret = {'status': True, 'error': None, }
    try:
        ids = request.POST.getlist('id', None)
        Host.objects.extra(where=['id IN (%s)' % ','.join(ids)]).delete()
    except Exception as e:
        ret = {
            "static": False,
            "error": '删除请求错误,{}'.format(e)
        }
    return HttpResponse(json.dumps(ret))


class WebSSH(LoginRequiredMixin, PermissionRequiredMixin, View):
    # 网页终端
    permission_required = 'cmdb.ssh_host'

    def get(self, request):
        hostgroups = []
        hosts = Host.get_user_host(request.user)  # 过滤筛择用户权限内的主机
        for hostgroup in HostGroup.objects.all():
            hostgroup.user_hosts = [h for h in hosts if h.group == hostgroup]
            if hostgroup.user_hosts:
                hostgroups.append(hostgroup)

        cmdb_webssh_active = 'active'
        user = request.user
        return render_to_response('webssh.html', locals())

# # 修改默认的合法schemes列表，用于主机终端，跳转调用外部程序，比如xshell
# HttpResponseRedirect.allowed_schemes.append(conf.CliSSH['scheme'])


class CliSSH(LoginRequiredMixin, PermissionRequiredMixin, View):
    # 软件终端，比如xshell，客户端需安装/设置支持从网页跳转到xshell
    permission_required = 'cmdb.ssh_host'

    @staticmethod
    def pwd():
        # 生成ssh临时密码
        s = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
        pwd = ''
        while len(pwd) < 6:
            pwd = '%s%s' % (pwd, random.choice(s))
        return pwd

    def get(self, request, hostid):
        host = get_object_or_404(Host, id=hostid)
        user = request.user
        type = request.GET.get('type', 'ssh')
        if not host.chk_user_prem(user, type):
            print '非法操作？！用户<%s>没有主机操作权限:' % user.username, host
            raise PermissionDenied
        user, passwd = user.username, CliSSH.pwd()
        key = 'clissh_%s_%s' % (user, passwd)
        cache.set(key, hostid, timeout=conf.CliSSH['password_timeout'])  # 写入缓存

        cmdb = request.META['HTTP_HOST'].split(':')[0]
        port = conf.CliSSH['port']
        scheme = conf.CliSSH['scheme'][type]
        ssh_username = host.get_ssh_user()[0]
        return HttpResponse('{scheme}://{user}:{passwd}@{cmdb}:{port}\\" \\"-newtab\\" \\"{username}/{host}'.format(
                scheme=scheme,  # 自定义的网页调用外部软件(xshell)协议
                cmdb=cmdb,  # xshell连接主机(cmdb堡垒机代理)
                port=port,
                user=user,  # xshell连接主机的用户(cmdb堡垒机代理)
                passwd=passwd,
                host=host.ip,  # xshell标签显示连接的主机(后端SSH实际主机)
                username=ssh_username  # xshell标签显示连接的用户(后端SSH实际用户)
            ))


class CmdRun(LoginRequiredMixin, View):

    def get(self, request):
        ASSET_TYPES = (1, 2, 3)  # Linux主机
        SH_TYPE = request.GET.get('s', '1')
        if SH_TYPE != '1':
            SH_TYPE = '2'
            ASSET_TYPES = (4, )  # H3C交换机
            cmdb_cmdrun2_active = 'active'
        else:
            cmdb_cmdrun_active = 'active'

        html = 'cmdrun_%s.html' % SH_TYPE

        hostgroups = []
        hosts = Host.get_user_host(request.user)  # 过滤筛择用户权限内的主机
        for hostgroup in HostGroup.objects.all():
            hostgroup.user_hosts = [h for h in hosts if h.asset_type in ASSET_TYPES and h.group == hostgroup]
            if hostgroup.user_hosts:
                hostgroups.append(hostgroup)

        user = request.user
        shs = SH.objects.filter(sh=SH_TYPE)
        return render(request, html, locals())

    def post(self, request):
        # print request.POST, 1111
        # print request.body, 2222
        # import ipdb;ipdb.set_trace()
        post_data = request.POST
        if not post_data:
            # contentType: "application/json"
            post_data = json.loads(request.body)

        if 'key' in post_data:
            # 文本搜索
            if not request.user.has_perm('cmdb.grep_host'):
                return HttpResponse(u'当前登陆用户没有分配主机grep_host(搜索日志) 权限！')
            vstr = post_data.get('vstr', '')  # 忽略字符所在行
            key = post_data['key']
            file = post_data['file']  # 日志文件
            if not file.startswith('/'):
                # 相对路径，主目录为host.tomcat
                file = '{0.tomcat}/%s' % file
                print file, 88888
            lines = post_data.get('lines', '')  # 上下文行数
            case = post_data.get('case', 'off')  # 区分大小写
            case = ' -' if case == 'on' else '-i'
            num = post_data.get('num', '15')  # greg匹配次数，由于日志文件太大，所以不全匹配
            desc = post_data.get('desc', 'off')  # 倒序(由后往前)匹配

            if lines and lines.isdigit():
                lines = '-C%s' % lines
            else:
                lines = ''
            if not num.isdigit():
                return HttpResponse(u'次数必需为正整数')
            if desc == 'off':
                cat = 'cat'
                desc = ''
            else:
                cat = 'tac'
                desc = " | sed '1!G;h;$!d'"

            if vstr:
                print '---%s--' % vstr
                vstr = '| grep -av "%s"' % vstr

            cmd = '%s %s %s | grep %sam%s %s %s %s' % (cat, file, vstr, case, num, lines, key, desc)

            ctype = 1

        elif 'sh' in post_data:
            # 执行脚本
            if not request.user.has_perm('cmdb.run_sh_host'):
                return HttpResponse(u'当前登陆用户没有分配主机run_sh_host(执行常用脚本) 权限！')
            s = get_object_or_404(SH, id=post_data['sh'])
            cmd = s.cmd
            ctype = 2

        elif 'cmd' in post_data:
            # 执行自定义命令
            if not request.user.has_perm('cmdb.run_cmd_host'):
                return HttpResponse(u'当前登陆用户没有分配主机run_cmd_host(执行自定义命令) 权限！')
            cmd = post_data['cmd']
            ctype = 6

        inpage = request.GET.get('inpage', '0')
        hosts = post_data.get('hosts', '')
        host_ids = hosts.split(',')
        host_ids = [i for i in host_ids if i.isdigit()]
        # print host_ids, 89898

        hs = Host.objects.filter(id__in=host_ids)

        user_hosts = Host.get_user_host(request.user)  # 过滤筛择只保留用户权限内的主机
        hosts = hs & user_hosts

        if not hosts:
            return HttpResponse(u'Error: 未选择主机，或者选择的主机不存在/无权限！')

        cmd_msgs = runcmd(hosts, cmd, ctype, request.user)  # 执行

        return render(request, 'cmdrun_msg.html', locals())


def runcmd(hosts, cmd, ctype, user, thead_timeout=15, ssh_timeout=5, cmdlog=1, refresh=1):
    # 批量主机执行命令，不进行网站用户权限验证，应在此之前处理

    msgs = []  # 收集线程执行结果

    newcmd = None
    if cmdlog:
        # 添加日志，CMD执行结果
        newcmd = CMD.newcmd(hosts=hosts, cmd=cmd, ctype=ctype, user=user)
    elif ctype == 4:
        # APP文件目录检查，根据情况显示实时状态或上次状态
        tms = AppFiles.objects.filter(host__in=hosts)
        if len(tms) != len(hosts):
            # 添加日志，CMD执行结果
            newcmd = CMD.newcmd(hosts=hosts, cmd=cmd, ctype=ctype, user=user)

        if not refresh:
            # 不刷新，只显示上次执行的结果(若有)
            for tm in tms:
                # 提取上次执行的结果
                host = tm.host
                msgs.append((host.ip, host.id, tm.text))
            tm_hosts = [tm.host for tm in tms]
            hosts = [h for h in hosts if h not in tm_hosts]  # 只保留从未执行目录检查的主机

    ths = []  # 线程池
    for host in hosts:
        # 并发执行
        if ctype == 6 and host.asset_type == 4:
            # 华3交换机，自定义命令检查，以免执行不安全的命令
            if not (cmd.startswith('ping ') or cmd.startswith('display ')):
                msgs.append((host.ip, host.id, '你想干什么？！'))
                continue
        th = MyThread(func=host.ssh_cmd, args=(cmd, ssh_timeout))
        th.host = host

        th.setDaemon(True)
        ths.append(th)
        th.start()

    time.sleep(2)
    while ths:
        for th in ths:
            if thead_timeout == 0 or not th.is_alive():
                # 超时或线程结束
                result = th.result.replace('\x00', '') if th.result else u'线程运行超时, TimeOut:%ds' % thead_timeout
                msgs.append((th.host.ip, th.host.id, result))
                ths.remove(th)
                if cmdlog:
                    # 添加日志，CMD执行结果
                    CMD_Log.objects.create(cmd=newcmd, host=th.host, text=result)
                elif ctype == 4:
                    # APP文件目录检查
                    try:
                        tm = tms.get(host=th.host)
                        if newcmd:
                            tm.cmd = newcmd
                        tm.text = result
                        tm.save()
                    except:
                        AppFiles.objects.create(cmd=newcmd, host=th.host, text=result)

        time.sleep(1)
        thead_timeout -= 1
        print thead_timeout, 'sleep....'

    if newcmd:
        newcmd.end = True
        newcmd.save()
    return msgs, newcmd


class MyThread(threading.Thread):

    def __init__(self, func, args=()):
        super(MyThread, self).__init__()
        self.func = func
        self.args = args
        # self.host = args[1]
        self.result = ''

    def run(self):
        result = self.func(*self.args)
        # print type(result[0]), 77777
        # import ipdb;ipdb.set_trace(frame=None, context=3)
        try:
            self.result = '%s\n%s' % result
        except UnicodeDecodeError:
            self.result = str(result)

# class Group(LoginRequiredMixin,ListView):
#     template_name = "grouplist.html"
#     model = HostGroup
#     def get_context_data(self, **kwargs):
#         kwargs['cmdb_group_active'] = 'active'
#         return super(self.__class__, self).get_context_data(**kwargs)


@login_required(login_url="/login")
def group(request):
    # 主机分组

    cmdb_group_active = 'active'
    return render_to_response('host_2.html', locals())


from django.views.decorators.csrf import csrf_exempt


@csrf_exempt
def host_group_edit(request):
    # jstree 鼠标拖动调整主机分组
    if request.method == 'POST':
        # print 1111,request.POST,3333

        host_id = request.POST.get('id')
        group_id = request.POST.get('parent')
        print 'host_id:%s, group_id:%s' % (host_id, group_id)

        return HttpResponse(json.dumps(request.POST))

    return HttpResponse('1123')

import requests
import ssl
import urllib3
# openssl s_client -connect $a10_ip:443  -tls1
# A10的https接口使用的SSL协议(ssl.PROTOCOL_TLSv1)版本很老，
# 而python ssl 客户端为安全已禁止使用TLSv1，导致连接禁止
# print requests.packages.urllib3.util.ssl_.DEFAULT_CIPHERS, 44444444444
requests.packages.urllib3.util.ssl_.DEFAULT_CIPHERS = 'ALL'
# urllib3.util.ssl_.resolve_ssl_version


def resolve_ssl_version(candidate='TLSv1_2'):
    """
    like resolve_cert_reqs
    """
    if candidate is None:
        return ssl.PROTOCOL_TLSv1  # 使用TLSv1

    if isinstance(candidate, str):
        res = getattr(ssl, candidate, None)
        if res is None:
            res = getattr(ssl, 'PROTOCOL_' + candidate)
        return res

    return candidate
urllib3.connection.resolve_ssl_version = resolve_ssl_version  # 使用TLSv1
urllib3.disable_warnings()  # 不打印非安全HTTPS警告信息


class SshLogList(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = SSH_Log
    template_name = 'sshloglist.html'
    permission_required = 'cmdb.replay_ssh_log'
    raise_exception = True


class SshMonitor(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    model = SSH_Log
    template_name = 'sshmonitor.html'
    permission_required = 'cmdb.replay_ssh_log'
    raise_exception = True
