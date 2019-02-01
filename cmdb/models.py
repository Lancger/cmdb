# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models
# from django.utils.timezone import now, localdate
from datetime import datetime, timedelta

from django.core.cache import cache
from django import template
from django.contrib.auth.models import User, Group
import traceback
import paramiko
import docker
import os
import sys
import cStringIO
import urlparse
import uuid
from .conf import YmlDir, ImgDir, DOCKER_CERT_PATH
from compose.cli.main import dispatch as docker_compose
import tarfile
import json
from .opt import get_AES

# from conf import YmlDir

# from django.db.models.options import Options
# old_contribute_to_class = Options.contribute_to_class


# def new_contribute_to_class(instance, cls, name):
#     # 设置verbose_name_plural为verbose_name
#     old_contribute_to_class(instance, cls, name)
#     instance.verbose_name_plural = instance.verbose_name
# models.options.Options.contribute_to_class = new_contribute_to_class


class HostGroup(models.Model):
    name = models.CharField(u"组名/区域", max_length=30, unique=True)
    ip = models.CharField(u"IP匹配", help_text='IP开头字符，比如Core组IP为10.2.4.开头。用于客户端脚本添加新主机时自动设置组，不支持通配符', max_length=20, default='', blank=True)
    desc = models.CharField(u"描述", max_length=100, null=True, blank=True)

    class Meta:
        ordering = ['name']
        verbose_name = '主机分组'

    def __unicode__(self):
        return self.name

    @staticmethod
    def get_group(ip):
        # 客户端脚本自动添加主机时，自动设置主机所属组(安全区域)

        groups = HostGroup.objects.exclude(ip='').order_by('-ip')
        group_id = 0
        for group in groups:
            if ip.startswith(group.ip):
                group_id = group.id
                break
        return group_id


class SshUser(models.Model):
    # 各服务器SSH登陆用户
    name = models.CharField(u"名称", max_length=50, default='', help_text='标识名称，当不同服务器使用相同的SSH账号名，但密码不同时，此项名称可进行区分。')
    username = models.CharField(u"SSH账号", max_length=50, default='', )
    password = models.CharField(u"密码", max_length=50, default='', null=True, blank=True, help_text='若不想修改原密码，不用设置此项')
    changetime = models.DateTimeField('最后修改', auto_now=True, blank=True, null=True)
    text = models.TextField(u"备注信息", default='', null=True, blank=True)

    class Meta:
        ordering = ['name']
        verbose_name = '主机SSH用户'
        unique_together = [('name', 'username'), ]

    def __unicode__(self):
        return '%s - %s' % (self.name, self.username)

    def save(self, *args, **kwargs):

        if self.password:
            password_aes = get_AES(password=self.password, encode=1)  # AES加密
            self.password = password_aes
        elif self.id:
            del self.password  # 防止不修改密码时，提交的空密码覆盖原有数据
        # import ipdb;ipdb.set_trace()
        super(self.__class__, self).save(*args, **kwargs)  # Call the "real" save() method.


class Host(models.Model):
    # 虚拟机、物理机 等设备
    ASSET_STATUS = (
        (1, u"在用"),
        (2, u"备用"),
        (3, u"故障"),
        (4, u"下线"),
        (6, u"其它"),
    )

    ASSET_TYPE = (
        (1, u"物理机"),
        (2, u"虚拟机"),
        (3, u"容器"),
        (4, u"H3C交换机"),
        (6, u"其它")
    )

    name = models.CharField(max_length=100, verbose_name=u"标识名称", default='', help_text='用于人工辨别，自动脚本默认设置为主机名，可改为其它便于人员识别的名称')
    hostname = models.CharField(max_length=50, verbose_name=u"主机名/计算机名", unique=True, help_text='关键字段，请谨慎修改')  # 服务器数据以计算机名为锚，以验证身份不重复添加数据
    ip = models.GenericIPAddressField(u"管理IP", max_length=15, help_text='若有多个IP且主机名无指定解析则默认为0.0.0.0，请在客户端/etc/hosts中设置其主机名对应IP解析')
    port = models.IntegerField(verbose_name='ssh端口', null=True, blank=True, default=22)
    other_ip = models.CharField(u"其它IP", max_length=100, null=True, blank=True)
    group = models.ForeignKey(HostGroup, verbose_name=u"组/安全区域", default=1, on_delete=models.SET_NULL, null=True, blank=True)
    # asset_no = models.CharField(u"资产编号", max_length=50, null=True, blank=True)
    # domain = models.CharField(u"安全区域", max_length=20, null=True, blank=True)
    status = models.SmallIntegerField(u"设备状态", choices=ASSET_STATUS, default=1, null=True, blank=True)
    asset_type = models.SmallIntegerField(u"设备类型", choices=ASSET_TYPE, default=1, null=True, blank=True)
    # 注意，django 1.11对postgresql 8.*低版本支持不好，ForeignKey字段有修改就会SQL报错 array_agg(attname ORDER BY rnum)
    machine = models.ForeignKey('self', verbose_name=u"所属物理机", limit_choices_to={'asset_type': 1},
                                on_delete=models.SET_NULL, null=True, blank=True, help_text='设备类型为虚拟机/容器时，设置所在物理机')
    os = models.CharField(u"操作系统", max_length=100, default='', null=True, blank=True)
    # vendor = models.CharField(u"设备厂商", max_length=50, null=True, blank=True)
    cpu_model = models.CharField(u"CPU型号", max_length=100, default='', null=True, blank=True)
    cpu_num = models.CharField(u"CPU数量", max_length=100, default='', null=True, blank=True, help_text='物理核个数, 逻辑核个数，(intel高端CPU带超线程技术)')
    memory = models.CharField(u"内存大小", max_length=30, default='', null=True, blank=True)
    disk = models.CharField(u"硬盘信息", max_length=255, default='', null=True, blank=True)
    vendor = models.CharField(u"供应商", max_length=150, default='', null=True, blank=True)
    sn = models.CharField(u"主机序列号", max_length=150, default='', null=True, blank=True)
    ports = models.TextField(u"监听端口", default='', null=True, blank=True, help_text='主机上处于监听状态的TCP和UDP端口')

    createtime = models.DateTimeField('创建时间',
                                      auto_now_add=True,
                                      # default=now,
                                      blank=True, null=True)
    changetime = models.DateTimeField('修改时间', auto_now=True, blank=True, null=True)
    agenttime = models.DateTimeField('配置更新', blank=True, null=True, help_text='最近一次主机客户端自动脚本运行更新软硬件信息的时间')

    usergroup = models.ManyToManyField(Group, verbose_name='网站用户组', blank=True, help_text='网站哪些用户组能对当前主机进行操作')
    user = models.ManyToManyField(User, verbose_name='网站用户权限', blank=True,
                                  # through='Host_User',  # 行级别的权限控制，人工录入时麻烦，比较困难实现快速批量设置主机清单
                                  help_text='网站哪些用户能对当前主机进行操作，超级用户直接有操作权限')
    ssh_user = models.ForeignKey(SshUser, verbose_name='SSH终端用户', on_delete=models.SET_NULL, null=True, blank=True, help_text='当前主机的SSH用户，用于ssh连接执行命令或终端WEB SSH')

    buydate = models.DateField('购买日期', default=datetime.today, blank=True, null=True)
    position = models.CharField(u"所处位置", max_length=250, default='', null=True, blank=True)
    sernumb = models.CharField(u"服务编号", max_length=150, default='', null=True, blank=True)
    sercode = models.CharField(u"服务代码", max_length=150, default='', null=True, blank=True)
    admin = models.ForeignKey(User, verbose_name='管理人', related_name='user_set2', null=True, blank=True, help_text='负责人直接有(当前主机/名下主机)操作权限')

    tomcat = models.CharField(max_length=100, verbose_name=u"Tomcat目录", default='/data/app/tomcat')
    tomcat_ver = models.CharField(max_length=50, verbose_name=u"Tomcat版本", default='', blank=True)
    jdk_ver = models.CharField(max_length=50, verbose_name=u"JDK版本", default='', blank=True)
    kernel = models.CharField(max_length=60, verbose_name=u"系统内核版本", default='', blank=True)

    # idc = models.ForeignKey(Idc, verbose_name=u"所在机房", on_delete=models.SET_NULL, null=True, blank=True)
    # position = models.CharField(u"所在位置", max_length=100, null=True, blank=True)
    # info = models.CharField(u"应用信息", max_length=200, default='', null=True, blank=True)
    text = models.TextField(u"备注信息", default='', null=True, blank=True)

    class Meta:
        permissions = (
            # 实现表级别的权限控制
            ("deploy_host", "Can deploy host"),    # APP部署
            ("ssh_host", "Can ssh host"),          # 终端登陆
            ("sftp_host", "Can sftp host"),        # 文件管理
            ("grep_host", "Can grep host"),        # 执行日志搜索
            ("run_sh_host", "Can run_sh host"),    # 执行常用命令
            ("run_cmd_host", "Can run_cmd host"),   # 执行自定义命令
            ("other_do_host", "Can other_do host"),  # 执行其它操作，如ES节点索引
        )
        ordering = ['group', 'ip']
        verbose_name = '主机'

    def __unicode__(self):
        return '%s - %s' % (self.name, self.ip)

    @staticmethod
    def newhost(kwargs):
        # 添加/修改host数据
        hostname = kwargs['hostname']
        host = Host.objects.filter(hostname=hostname)
        try:
            if host:
                host = host[0]
                # print '已有记录',hostname,'更新主机信息'
                kwargs.pop('hostname')
                text = kwargs.get('text', '')
                if text:
                    kwargs['text'] = '%s\r\n%s' % (host.text, text)  # 备注信息只在原基础信息上追加
                for k, v in kwargs.items():
                    setattr(host, k, v)
                host.agenttime = datetime.today()
                host.save()
            else:
                # 添加新主机
                hostname, ip = kwargs.get('hostname', ''), kwargs.get('ip', '')
                kwargs['name'] = kwargs.get('name', '%s' % (hostname, ))  # 当标识名未提供，则填入计算机名。
                kwargs['asset_type'] = kwargs.get('asset_type', 2)  # 默认为虚拟机类型
                kwargs['agenttime'] = datetime.today()  # 配制更新日期

                group_id = kwargs.get('group_id', HostGroup.get_group(ip))

                if group_id:
                    kwargs['group_id'] = group_id

                Host(**kwargs).save()
            return 1
        except:
            print(traceback.format_exc())
            return 0

    def get_ssh_user(self):
        # 获取某台主机SSH用户/密码

        ssh_user = self.ssh_user
        if not ssh_user:
            ssh_users = SshUser.objects.filter(username='app')  # 下面取id最小的app用户
            if ssh_users:
                ssh_user = ssh_users[0]
            else:
                print 'Error: SshUser数据表为空，新安装CMDB？'
                return '', ''
        username = ssh_user.username
        password = get_AES(password=ssh_user.password, encode=0)
        return username, password

    @staticmethod
    def get_user_host(user):
        # 获取用户有操作权限的所有主机

        hosts = Host.objects.all()
        if user.is_superuser:
            return hosts

        hosts1 = hosts.filter(user=user)  # 已设置用户为操作用户
        hosts2 = hosts.filter(admin=user)
        hosts3 = hosts.filter(machine__in=hosts2)  # 负责人有物理机名下虚拟机权限
        # print hosts2.union(hosts3),7777

        hosts4 = hosts.filter(usergroup__in=user.groups.all())  # 已设置用户所属组有操作权限
        # hosts4 = []
        return hosts1 | hosts2 | hosts3 | hosts4

    def chk_user_prem(self, user, perm=''):
        # 验证用户操作权限，表级别权限和行级别权限
        # import ipdb;ipdb.set_trace()
        if user.is_superuser:
            return 1  # 超级管理员直接有权限
        elif not user.has_perm('cmdb.%s_host' % perm):
            # 验证表级别权限
            return 0  # 未设置用户相对应的主机权限，超级管理员无需设置而直接有权限
        elif user in self.user.all() or self.admin == user:
            return 1  # 主机有设置用户为网站操作用户/负责人
        elif self.machine and self.machine.admin == user:
            return 1  # 所属物理机负责人有操作权限

        usergroups = self.usergroup.all()
        for usergroup in usergroups:
            if user in usergroup.user_set.all():
                return 1  # 主机设置的网站用户组包含user
        return 0

    def ssh_cmd(self, cmd, ssh_timeout=10):
        # 登陆服务器执行cmd，返回('正常信息', '错误信息')
        # import ipdb;import ipdb; ipdb.set_trace()
        try:
            cmd = cmd.format(self)  # 有些为变量，比如Tomcat目录
        except:
            pass
        print cmd, 888
        ip = self.ip
        port = getattr(self, 'port', 22)
        ssh_user, ssh_pwd = self.get_ssh_user()

        if not ssh_pwd:
            return ('', 'Error: SSH User %s 异常' % ssh_user)

        s = paramiko.SSHClient()
        s.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            s.connect(ip, port, ssh_user, ssh_pwd, timeout=ssh_timeout)
        except Exception as e:
            return ('', 'SSH connect error: %s' % e)

        stdin, stdout, stderr = s.exec_command(cmd)
        # stdin.write("Y")
        # msg = stdout.read().decode('utf-8'), stderr.read().decode('utf-8')
        if self.asset_type == 4:
            # H3C交换机，显示More之后内容
            stdin.write('                                                                          q')
            out = stdout.read()
            out = out.replace('  ---- More ----\x1b[16D                \x1b[16D', '')  # import pyte
        else:
            out = stdout.read()
        err = stderr.read()
        s.close()
        return out, err

    def get_ha_a10(self):
        # 获取主机的A10组

        balances = self.balance_set.all()
        a10s = set()
        for balance in balances:
            a10s = a10s | set(balance.a10.filter(state=1))
        if not a10s:
            if self.ip.startswith('10.2.4.'):
                ha = 2
            elif self.ip.startswith('10.2.12.'):
                ha = 1
            elif self.ip.startswith('10.2.14.'):
                ha = 2
            elif self.ip.startswith('10.2.16.'):
                ha = 3
            else:
                # ha = 1
                return a10s

            a10s = A10.objects.filter(ha=ha, state=1)
        a10s = [a10 for a10 in a10s]
        a10s.sort(cmp=None, key=lambda i: i.name, reverse=False)
        return a10s


# class Host_User(models.Model):
# 主机用户权限多对多中间表，实现行级别的权限控制

#     host = models.ForeignKey(Host, verbose_name=u"主机",)
#     user = models.ForeignKey(User, verbose_name=u"网站用户",)

#     deploy = models.BooleanField(verbose_name='APP部署', default=False)
#     webssh = models.BooleanField(verbose_name='连接终端', default=False)
#     sh = models.BooleanField(verbose_name='常用脚本', default=False)
#     cmd = models.BooleanField(verbose_name='自定义命令', default=False)
#     grep = models.BooleanField(verbose_name='日志搜索', default=True)
#     other = models.BooleanField(verbose_name='其它操作', default=True, help_text='比如主机ES节点索引打开/关闭等')

#     class Meta:
#         unique_together = [('host', 'user'), ]
#         verbose_name = '用户操作权限'


class ES(models.Model):

    """
    Elasticsearch 节点
    """

    name = models.CharField(max_length=50, verbose_name=u"标识名称", default='')
    host = models.ForeignKey(Host, verbose_name=u"所在主机")
    port = models.IntegerField(verbose_name='ES端口', default=9200)
    cluster = models.CharField(max_length=50, verbose_name=u"集群名称", default='', blank=True, null=True)
    node = models.CharField(max_length=50, verbose_name=u"节点名称", default='', blank=True, null=True)
    text = models.TextField('备注', default='', blank=True, null=True)
    createtime = models.DateTimeField('创建时间', auto_now_add=True, blank=True, null=True)
    changetime = models.DateTimeField('修改时间', auto_now=True, blank=True, null=True)

    class Meta:
        ordering = ['host']
        verbose_name = 'ES节点'
        unique_together = [('host', 'port'), ]

    def __unicode__(self):
        return '{} ({}:{})'.format(self.name, self.host.ip, self.port)


class SH(models.Model):
    # 常用脚本

    SH_TYPE = (
        (1, u"默认"),
        (2, u"H3C交换机"),
        (3, u"APP配置"),
    )

    name = models.CharField(max_length=100, verbose_name=u"标识名", default='')
    fname = models.CharField(max_length=100, verbose_name=u"文件名", default='', help_text='使脚本能通过URL形式来调用，http://10.2.21.34:8088/api/sh/文件名，并且通过后缀名区分py、sh脚本')
    sh = models.SmallIntegerField(u"脚本类型", choices=SH_TYPE, default=1, null=True, blank=True)
    # server = models.SmallIntegerField(u"主机类型", choices=SERVER_TYPE, default=1, null=True, blank=True)
    cmd = models.TextField(u"脚本内容", blank=True, null=True)
    text = models.TextField(u"备注", blank=True, null=True)

    createtime = models.DateTimeField('创建时间', auto_now_add=True, blank=True, null=True)

    class Meta:
        verbose_name = '常用命令/脚本'
        ordering = ['sh', 'fname']
        unique_together = [('sh', 'fname'), ]

    def __unicode__(self):
        return self.name

    def save(self, *args, **kwargs):
        #  windows、苹果换行改为Uinx
        try:
            self.cmd = self.cmd.replace('\r\n', '\n').replace('\r', '\n')
        except:
            print self.name, 'SH脚本替换换行失败，忽略!!!!!!!!'
            pass
        return super(self.__class__, self).save(*args, **kwargs)


class CMD(models.Model):
    # 命令项执行记录
    CMD_TYPE = (
        (1, u"GREP日志"),
        (2, u"常用脚本"),
        (4, u"APP配置较验"),
        (6, u"自定义命令"),
    )

    cmd = models.TextField(u"命令内容")
    ctype = models.SmallIntegerField(u"命令类型", choices=CMD_TYPE, default=1, null=True, blank=True)
    host = models.ManyToManyField(Host, verbose_name='执行主机', blank=True)
    text = models.TextField(u"备注", blank=True, null=True)

    createtime = models.DateTimeField('创建时间', auto_now_add=True, blank=True, null=True)
    user = models.ForeignKey(User, verbose_name='操作人', null=True, blank=True, )
    end = models.BooleanField(verbose_name='任务完成', default=False)

    class Meta:
        verbose_name = 'CMD记录'

    def __unicode__(self):
        return self.cmd

    @staticmethod
    def newcmd(hosts, **kwargs):
        if not hosts:
            return
        cmd = CMD(**kwargs)
        cmd.save()
        cmd.host.set(hosts)
        return cmd


# default_cmd_name = u'自定义命令'
class CMD_Log(models.Model):
    # 命令执行结果

    cmd = models.ForeignKey(CMD, verbose_name=u"命令")
    host = models.ForeignKey(Host, verbose_name='主机')
    createtime = models.DateTimeField('创建时间', auto_now_add=True, blank=True, null=True)
    text = models.TextField(u"返回信息", default='', null=True, blank=True)

    class Meta:
        verbose_name = 'CMD结果'

    def __unicode__(self):
        return '%s (%s)' % (self.cmd, self.host)


# from django.contrib.auth.models import AbstractUser
# class UserProfile(AbstractUser):
from django.contrib.auth.models import User
from django_otp.plugins.otp_totp.models import TOTPDevice


class UserProfile(models.Model):
    '''
    扩展用户表，增加字段
    '''
    user = models.OneToOneField(User)
    ftp_readonly = models.BooleanField(verbose_name='SFTP只读', default=False, help_text='SFTP文件管理时只读')
    weixin = models.CharField(max_length=100, verbose_name='微信ID', default='', blank=True, null=True, help_text="需要时，用于接收由公司公众号发给当前用户的微信告警信息")
    otp = models.BooleanField(verbose_name='OTP验证', default=False, help_text='当前用户登陆时，是否需进行T-otp验证')
    show_otp = models.BooleanField(verbose_name='显示otp二维码', default=True, help_text='新用户首次登陆，或者手机丢失了otp信息，需重新扫码用于生成otp验证，验证成功后不再提供显示')
    yx = models.SmallIntegerField(u"有效期", default=365, help_text="用户有效期天数，过期后自动停用")
    usertime = models.DateTimeField('上次过期', default=datetime.now, help_text="用于计算/保存用户过期日期")
    pwdtime = models.DateTimeField('上次修改密码', default=datetime.now, help_text="用于计算密码过期日期")
    expired = models.SmallIntegerField(u"密码过期", default=90, help_text="密码过期天数，过期后登陆需修改密码")

    class Meta:
        verbose_name = '用户扩展信息'
        verbose_name = verbose_name

    def __unicode__(self):
        return self.user.username

    def chk_yx(self):
        # 用户有效期检查，若过期则自动禁用用户
        user = self.user
        today = datetime.today().date()
        date = self.usertime.date()
        overday = date + timedelta(days=self.yx)
        # import ipdb;ipdb.set_trace()
        if today > overday:
            user.is_active = False
            user.save()
            self.usertime = datetime.today()
            self.save()
            return 1
        else:
            return 0

    def chk_expired(self):
        # 密码过期检查，若过期则每次登陆跳转到修改密码页面
        today = datetime.today().date()
        date = self.pwdtime.date()
        overday = date + timedelta(days=self.expired)
        if today > overday:
            return 1
        else:
            return 0

    @staticmethod
    def new(user):
        p = UserProfile(user=user)
        p.save()
        totpdevice = user.totpdevice_set.filter(confirmed=1)
        if not totpdevice:
            # 创建t-otp device，使user支持t-otp验证
            t = TOTPDevice(name='自动创建', user=user)
            t.save()

        return p


class DockerHost(models.Model):
    # 容器宿主机、物理机，必需已开启监听端口(swarm)，用于cmdb连接远程API
    # CMDB不使用swarm、docker service功能，因网络只能为overlay无法自定义配置

    name = models.CharField(max_length=100, verbose_name=u"标识名称")
    """
    host = models.CharField(verbose_name='宿主机', max_length=50, default='.docker.sdj',
        help_text='Docker容器宿主机、物理机域名，比如xxx.docker.sdj，<br/>\
        为简化配置处理，统一使用泛域名*.docker.sdj SSL证书<br/>')
    """
    ip = models.GenericIPAddressField(u"宿主机IP", max_length=15, unique=True)
    port = models.IntegerField(verbose_name='Docker端口', default=2375)
    tls = models.BooleanField(verbose_name='TLS', default=True, help_text='Docker-API不会进行安全验证，任意接入的客户端都能进行所有操作<br/>为安全需配置TLS，客户端使用证书访问API接口')
    # ver = models.CharField(max_length=20, verbose_name=u"Docker版本", help_text='Docker服务端版本', null=True, blank=True)
    text = models.TextField(u"备注信息", default='', blank=True)

    class Meta:
        verbose_name = '容器宿主机'
        permissions = (
            # 实现表级别的权限控制
            ("images_manage", "镜像管理"),      # 镜像管理
            ("containers_manage", "容器管理"),  # 容器管理
            ("net_manage", "容器管理"),  # 网络管理
        )

    def __unicode__(self):
        return '%s (%s)' % (self.name, self.ip)

    # def ip2host(self):
    #     # 将IP转换为虚拟构造的域名，用于泛域名*.docker.sdj SSL证书验证
    #     return '%s.docker.sdj' % self.ip.replace('.', '_')

    @property
    def client(self):
        tls = 1 if self.tls else ''  # docker.utils.utils.kwargs_from_env
        try:
            cli = docker.from_env(
                timeout=30,
                assert_hostname=False,
                environment={
                    'DOCKER_HOST': 'tcp://%s:%d' % (self.ip, self.port),
                    'DOCKER_CERT_PATH': DOCKER_CERT_PATH,
                    'DOCKER_TLS_VERIFY': tls
                }
            )
        except docker.errors.TLSParameterError as e:
            # 默认三个证书文件在django进程用户主目录下的.docker中
            # ~/.docker/ca.pem
            # ~/.docker/cert.pem
            # ~/.docker/key.pem
            print e
            error = 'SSL证书不存在？证书目录: %s，TSL验证: %s' % (DOCKER_CERT_PATH, tls)
            return error

        cli.dockerhost = self
        return cli


class DockerYmlGroup(models.Model):
    name = models.CharField(u"类名", max_length=30, unique=True)
    path = models.CharField(max_length=100, verbose_name=u"yml目录", unique=True)
    desc = models.CharField(u"描述", max_length=100, blank=True)

    class Meta:
        ordering = ['name']
        verbose_name = '容器YML分组'

    def __unicode__(self):
        return '%s (%s)' % (self.name, self.path)


class DockerYml(models.Model):
    name = models.CharField(max_length=100, verbose_name=u"标识名称")
    group = models.ForeignKey(DockerYmlGroup, verbose_name=u"容器YML分组",)
    file = models.CharField(max_length=100, verbose_name=u"yml文件名")
    # docker = models.ManyToManyField(Docker, verbose_name='容器宿主机', blank=True)
    text = models.TextField(u"备注", default='', blank=True)
    state = models.BooleanField(verbose_name='启用', default=True)

    class Meta:
        ordering = ['name']
        verbose_name = '容器YML'
        unique_together = [('group', 'file'), ]

    def __unicode__(self):
        return '%s / %s' % (self.group.path, self.file)

    def get_ymlfile(self):
        # 获取yml完整路径
        # 必需返回字符串，不能为unicode。
        # docker-compose有BUG或者命令行下字符不可能为unicode，它判断yml文件参数，不是str(单文件)就是列表(多文件)
        return str(os.path.join(YmlDir, self.group.path, self.file))


class DockerCompose(models.Model):
    """
    通过dockercompose.yml文件创建的容器编排
    """
    name = models.CharField(max_length=100, verbose_name=u"标识名称")
    yml = models.ForeignKey(DockerYml, verbose_name=u"容器YML", limit_choices_to={'state': True})
    dockerhost = models.ForeignKey(DockerHost, verbose_name=u"容器宿主机",)
    scale = models.CharField(max_length=100, verbose_name=u"数量参数", default='', blank=True,
                             help_text='scale参数，默认每个服务只启动1个容器，多个时比如设置web=2,worker=3\
                             <br/>需启动多个容器的服务，不能配置IP、容器名等唯一项，以免冲突')
    createtime = models.DateTimeField('创建时间', auto_now_add=True, blank=True, null=True)
    changetime = models.DateTimeField('修改时间', auto_now=True, blank=True, null=True)
    # state = models.BooleanField(verbose_name='启用', default=True, editable=False)
    text = models.CharField('备注', max_length=300, default='', blank=True)

    class Meta:
        ordering = ['name']
        verbose_name = '容器编排'
        unique_together = [('yml', 'dockerhost'), ]

    def __unicode__(self):
        return self.name

    def get_compose_cmd(self):
        """
        获取docker-compose客户端，用于执行命令，up、start、stop等
        c = DockerCompose.objects.get(id=2)
        cc = c.get_compose_cmd()
        cc.command('up', '-d')
        cc.command('up', '-d', '--scale', 'ng=3')
        cc.command('top')
        """
        class DockerComposeCommand():
            # 执行docker-compose命令

            def __init__(self, dockercompose):
                dockerhost = dockercompose.dockerhost
                self.cmd_args = ['docker-compose']
                self.cmd_args.extend(['-H', 'tcp://%s:%d' % (dockerhost.ip, dockerhost.port)])
                if dockerhost.tls:
                    # import ipdb; ipdb.set_trace()
                    if DOCKER_CERT_PATH:
                        os.environ.setdefault('DOCKER_CERT_PATH', DOCKER_CERT_PATH)
                    else:
                        os.environ.setdefault('DOCKER_CERT_PATH', os.path.join(os.path.expanduser('~'), '.docker'))
                    # 指定客户端(cmdb本机)证书路径环境变量，若不指定，需手工增加证书参数
                    # --tlscacert=/root/.docker/ca.pem --tlscert=/root/.docker/cert.pem --tlskey=/root/.docker/key.pem
                    # '--tlscacert', '/root/.docker/ca.pem', '--tlscert', '/root/.docker/cert.pem', '--tlskey', '/root/.docker/key.pem'
                    self.cmd_args.extend([
                        '--tlsverify',  # tls检查
                        '--skip-hostname-check',  # 忽略域名检查
                    ])
                else:
                    if 'DOCKER_CERT_PATH' in os.environ:
                        """
                        清除环境变量DOCKER_CERT_PATH，以免在加密/非加密HTTP连接切换时，导致HTTP的宿主机使用HTTPS
                        因官方docker-compose是单机服务端命令，设计时不会考虑多宿主机HTTP/HTTPS并存
                        compose.cli.docker_client.tls_config_from_options
                        cert_path = environment.get('DOCKER_CERT_PATH')
                        """
                        os.environ.pop('DOCKER_CERT_PATH')
                self.cmd_args.append('--no-ansi')  # 去掉终端格式字符
                self.cmd_args.extend(['-f', dockercompose.yml.get_ymlfile()])
                # print self.cmd_args, 8888888888

            def command(self, cmd, *args):
                # cmd: up、start、stop等
                if cmd not in (
                    'up',
                    'start',
                    'stop',
                    'pause',
                    'restart',
                    'top',
                    'ps',
                    'logs',
                    'down',
                ):
                    return '为了安全，默认只开放部分命令操作权限'
                cmd_args = list(self.cmd_args)
                cmd_args.append(cmd)
                cmd_args.extend(args)

                sys.argv = [str(i.strip()) for i in cmd_args if i.strip()]
                # print sys.argv, 777777777

                strio = cStringIO.StringIO()
                sys.stderr = sys.stdout = strio  # 输出重定向到内存变量，用于显示到网页
                try:
                    docker_compose()()  # 执行docker-compose命令，参数为sys.argv[1:]
                except Exception as e:
                    print '执行docker-compose出错:\r\n', e
                    raise
                sys.stderr = sys.__stderr__  # 还原输出到控制台
                sys.stdout = sys.__stdout__  # 还原输出到控制台
                msg = strio.getvalue()
                # print '###################'
                # print msg
                # print '###################'

                return msg

        try:
            return self.compose_cmd
        except:
            self.compose_cmd = DockerComposeCommand(self)
            return self.compose_cmd

    def compose_up(self):
        # DockerCompose表单保存后，可能需更新容器编排
        compose_cmd = self.get_compose_cmd()
        args = []
        scale = self.scale.strip().replace('，', ',')
        if scale:
            for i in scale.split(','):
                if i.strip():
                    args.extend(['--scale', i])

        compose_cmd.command('up', '-d', '--force-recreate', *args)


class DockerImageFile(models.Model):
    # 备份/保存的镜像包文件
    name = models.CharField(max_length=100, verbose_name=u"镜像名")
    ver = models.CharField(max_length=100, verbose_name=u"版本", null=True, blank=True)
    dockerhost = models.ForeignKey(DockerHost, verbose_name=u"来源/宿主机", blank=True, null=True, on_delete=models.SET_NULL)
    file = models.CharField(max_length=100, verbose_name=u"文件名", unique=True)
    size = models.BigIntegerField(verbose_name=u"文件大小", default=0)
    createtime = models.DateTimeField('创建时间', auto_now_add=True, blank=True, null=True)
    upload = models.BooleanField(verbose_name='手工上传', default=False)
    text = models.TextField(u"备注", default='', blank=True)

    class Meta:
        ordering = ['name']
        verbose_name = '容器镜像包'
        unique_together = [('name', 'ver', 'dockerhost'), ]

    def __unicode__(self):
        return '%s:%s' % (self.name, self.ver)

    def delobj(self):
        # 删除条目，并删除镜像包
        file = os.path.join(ImgDir, self.file)
        if os.path.exists(file):
            os.remove(file)
        self.delete()

    @staticmethod
    def save_file(upload_file):
        """
        手工上传的镜像包，解析处理后保存，返回处理结果
        """
        # import ipdb; ipdb.set_trace()
        filetype = os.path.splitext(upload_file.name)[1].lstrip('.')  # 文件扩展名
        # 开始解析镜像包文件是否合法
        try:
            tf = tarfile.open(fileobj=upload_file.file, mode='r:%s' % filetype)
        except tarfile.ReadError, e:
            return '未知格式的镜像包，%s' % str(e)
        except Exception as e:
            return '解析镜像包出错，%s' % str(e)

        try:
            manifest = tf.getmember('manifest.json')
        except KeyError:
            return '镜像包中没有manifest.json文件，这是一个容器镜像包？'
        except Exception as e:
            return '无法获取镜像包文件manifest.json，%s' % str(e)

        manifest_file = tarfile.ExFileObject(tf, manifest)  # 从包中获取manifest.json文件
        txt = manifest_file.read()  # manifest.json文件内容
        print txt, 333
        try:
            image_name = json.loads(txt)[0]['RepoTags'][0]  # busybox:latest
        except Exception as e:
            return '镜像包文件manifest.json内容解析提取镜像(名称:版本)出错，请联系反映BUG. \r\n%s出错信息:%s' % (txt, str(e))

        name, ver = image_name.split(':')
        file = '%s(%s).upload.tar' % (name.replace('/', '#'), ver)
        size = upload_file.size

        filepath = os.path.join(ImgDir, file)
        if os.path.exists(filepath):
            if DockerImageFile.objects.filter(file=file):
                return '之前已曾上传相同(名称:版本)的镜像包，为安全已取消覆盖保存，请先删除之前上传的镜像包{}后再重新上传'.format(file)
        try:
            f = open(filepath, 'w')
            for chunk in upload_file.chunks():
                # print len(chunk)
                f.write(chunk)
            f.close()

            obj = DockerImageFile(name=name, ver=ver, file=file, size=size, upload=True)
            obj.save()
        except Exception as e:
            return '文件保存失败：%s' % str(e)
        return '上传成功.'

    @staticmethod
    def save_obj(image):
        """
        从宿主机下载保存镜像，相当于docker save命令，
        DOCKER远程API，通过官方函数image.save()下载的镜像包，不含镜像名版本标签"RepoTags":null
        self.client.api.get_image(self.id)
        API: GET https://ip:2375/v1.30/images/镜像ID/get，"RepoTags":null
        self.client.api.get_image(self.tags[0])
        API: GET https://ip:2375/v1.30/images/镜像名/get，"RepoTags":["busybox:latest"] 单个镜像
        API: GET https://ip:2375/v1.30/images/get?names=镜像名1&names=镜像名2，可多个镜像
        """
        def get_image(api, image_name):
            """
            docker client.api.get_image重写
            官方函数api._url特意不对/进行转义，且API网址为images/镜像名/get，
            需进行/转义或改API网址为images/get?names=镜像名
            """
            # image_name = image_name.replace('/', '%2f')
            # url手工转义 / --> %2F后，在api._url中会对%进行转义，导致/字符由%2f变成%252f
            url = api._url("/images/get?names={0}", image_name)
            # print url, 9999999999
            # url = url.replace('%25', '%')  # %取消转义
            res = api._get(url, stream=True)
            api._raise_for_status(res)
            return res.raw

        name, ver = image.tags[0].split(':')
        dockerhost = image.client.dockerhost
        img = DockerImageFile.objects.filter(name=name, ver=ver, dockerhost=dockerhost)
        if img:
            return '已有相同的镜像包，当前版本的镜像可能之前曾有过保存操作，为安全忽略此次处理。\r\n若要重新保存，请先删除已有的镜像包后再试。'
        file = '%s(%s).%d.tar' % (name.replace('/', '#'), ver, dockerhost.id)
        # print datetime.today().strftime("%Y-%m-%d %H:%M:%S"), 1
        try:
            # data = image.save()  # "RepoTags":null
            image_name = '%s:%s' % (name, ver)
            # data = image.client.api.get_image(image_name)  # "RepoTags":["busybox:latest"]
            data = get_image(image.client.api, image_name)
            # import ipdb; ipdb.set_trace()
            try:
                # docker.__version__ == '2.7.0'
                data = data.stream()
            except:
                # docker.__version__ == '3.3.0'
                # 正式版机器中的docker版本高，data直接为stream
                pass
            f = open(os.path.join(ImgDir, file), 'w')
            for chunk in data:
                # print len(chunk)
                f.write(chunk)
            f.close()
            size = os.path.getsize(os.path.join(ImgDir, file))
            obj = DockerImageFile(name=name, ver=ver, dockerhost=dockerhost, file=file, size=size)
            obj.save()
            return '镜像保存/备份成功！可在<镜像包>中查看'
        except Exception as e:
            # raise
            return '镜像保存/备份出错:\r\n%s' % str(e)

    def load_obj(self, cli):
        # 将资产系统中的镜像包复制/还原到宿主机docker镜像，相当于docker load命令
        try:
            with open(os.path.join(ImgDir, self.file), 'rb') as f:
                old_timeout, cli.api.timeout = cli.api.timeout, 300
                cli.images.load(f)
                cli.api.timeout = old_timeout
            return '镜像复制/还原成功！'
        except Exception as e:
            raise
            return '镜像复制/还原出错:\r\n%s' % str(e)


class SshUserCheck(models.Model):
    # 记录检查主机SSH登陆用户密码更新是否正确
    host = models.ForeignKey(Host, verbose_name=u"主机",)
    password = models.CharField(max_length=100, verbose_name=u"使用密码")
    error = models.CharField(verbose_name='失败原因', max_length=400, default='', blank=True, null=True)
    createtime = models.DateTimeField('创建时间', auto_now_add=True, blank=True, null=True)

    class Meta:
        ordering = ['host__ip']
        verbose_name = '主机SSH密码失败日志'

    def __unicode__(self):
        return '%s - %s' % (self.host, self.host.ssh_user)

    # def save(self, *args, **kwargs):
    #     print args, kwargs, 777
    #     return super(self.__class__, self).save(*args, **kwargs)


def get_logname():
    # 生成不重复的回放录像文件名
    return '%s.%s.json' % (datetime.now().strftime("%Y.%m.%d.%H.%M.%S"), uuid.uuid4().hex[:6])


class SSH_Log(models.Model):
    # 终端操作回放录像
    host = models.ForeignKey(Host, verbose_name=u'主机',)
    user = models.ForeignKey(User, verbose_name='用户')
    channel = models.CharField(max_length=100, verbose_name='channel', default='', blank=False, editable=False)
    log = models.CharField(max_length=100, verbose_name='文件名', unique=True,
                           default=get_logname, editable=False, blank=False)
    cmds = models.TextField(u"命令记录", null=True, blank=True, help_text='用户终端操作所执行的命令记录')
    start_time = models.DateTimeField(auto_now_add=True, verbose_name='开始时间')
    end_time = models.DateTimeField(verbose_name='结束时间', blank=True, null=True)

    def __unicode__(self):
        return '%s' % self.host

    class Meta:
        permissions = (
            ("replay_ssh_log", "播放终端操作"),
            # ("monitor_ssh_log", "监控SSH操作"),
        )
        ordering = ['-start_time', ]
        verbose_name = '终端操作记录'
