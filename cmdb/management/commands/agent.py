# coding=utf-8

# import traceback
# import time
# import json
from django.core.management.base import BaseCommand, CommandError

from cmdb.models import Host
from cmdb.zabbix import Zabbix, ZABBIX
from datetime import datetime

# m = 'sys'
# exec "import " +　m

# from django.utils import simplejson
####################################
import sys
reload(sys)
sys.setdefaultencoding('UTF-8')  # 原默认为sys.getdefaultencoding(): ascii
####################################

agent_sh = '''
source /etc/profile
curl -s http://10.2.21.34:8088/static/agent.py | python
'''


class Command(BaseCommand):
    # 用于外部脚本定时计划任务，每天收集更新各主机软硬件配置。
    help = u'收集主机软硬件配置'

    def add_arguments(self, parser):
        parser.add_argument('htype', nargs='?', default='app', type=str,
                            help=u'''
                            收集哪类主机:
                            all 所有主机;
                            app 所有含有APP的主机;
                            xx.xx.xx.xx 主机IP，多台逗号间隔;

                            ''')

    def handle(self, *args, **options):
        print "Start....."

        htype = options['htype']
        # print type, 111
        hosts = Host.objects.filter(status__in=(1, 2), asset_type__in=(1, 2))  # 使用/备用中的物理机/虚拟机
        if htype == 'all':
            pass
        elif htype == 'app':
            hosts = hosts.exclude(app__isnull=True)
        else:
            hosts = hosts.filter(ip__in=[ip for ip in htype.split(',')])

        for host in hosts:
            get_agent(host)

        # hosts = hosts.filter(ip__startswith='10.2')  # 暂时只有南山zabbix有主机配置信息
        # # print hosts
        # zabbix(hosts)


def get_agent(host):
    print '\n\n开始登陆收集软硬件配置', host.ip
    r, e = host.ssh_cmd(agent_sh.replace('\r', ''))
    print r
    if e:
        print e


def zabbix(hosts):
    # 更新主机软硬件配置信息
    pass
    z_1 = Zabbix(ZABBIX[0])  # 南山zabbix
    z_2 = Zabbix(ZABBIX[1])  # 观澜zabbix

    for host in hosts:
        ip = host.ip
        z = z_1 if ip.startswith('10.2') else z_2

        hostinfo = z.host(ip)
        print hostinfo
        try:
            hostinfo = hostinfo[0]['inventory']
        except:
            print 'zabbix中没有主机%s配置信息' % ip
            continue
        host.hostname = hostinfo['name']
        host.os = hostinfo['os_full']
        host.kernel = hostinfo['os_short']
        host.jdk_ver = hostinfo['software_app_a']
        host.tomcat_ver = hostinfo['software_app_b']
        host.agenttime = datetime.today()  # 配制更新日期
        host.save()
