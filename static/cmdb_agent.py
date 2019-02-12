#!/usr/bin/env python
# coding=utf-8

import os
from subprocess import Popen, PIPE
import re
import platform
import socket
import time
import json
import hashlib
import threading
from datetime import datetime
from collections import OrderedDict
import urllib
import urllib2


Agent_Key = 'DW$@75d^k9'

Tomcat_Path = '/data/app/tomcat'
CMDB_URL = {
    0: '自定义URL',
    1: 'http://127.0.0.1:8088',
    8: 'http://192.168.80.238:8088',
}

CMDB_URL_PATH = '/api/cmdb/host/'

GET_GROUP_URL_PATH = '/api/cmdb/group/'

# os.system('yum -y install epel-release')
# os.system('yum -y install pip')


# try:
#     import psutil
# except ImportError as msg:
#     print(msg)
#     print("----------------------------------------------")
#     print("begining install psutil module, please waiting")
#     p = Popen('pip install psutil==5.2.2', stdout=PIPE, shell=True)
#     stdout, stderr = p.communicate()
#     print stdout
#     import psutil


# try:
#     import requests
# except ImportError as msg:
#     print msg
#     print("------------------------------------------------")
#     print("begining install requests module, please waiting")
#     p = Popen('pip install requests==2.17.3', stdout=PIPE, shell=True)
#     stdout, stderr = p.communicate()
#     print stdout
#     import requests

def runcmd(cmd):
    p = Popen(cmd, shell=True, stdout=PIPE)
    stdout, stderr = p.communicate()
    return stdout, stderr


def get_host_ip(hostname):
    # 通过主机名对应IP
    try:
        # print u'通过主机名解析对应IP...'
        return socket.gethostbyname(hostname)
    except socket.gaierror:
        hostip = '0.0.0.0'
        ips = get_other_ip()
        if len(ips) == 0:
            print u'Error: 当前主机未设置任何IP，单机？！'
        elif len(ips) == 1:
            hostip = ips[0]
        elif len(ips) > 1:
            print u'Error: 获取主机名IP失败，且主机含有多个IP无法确定哪个为管理IP，IP默认使用0.0.0.0，请在hosts中设置主机名解析对应的管理IP'
        return hostip


def get_other_ip(hostip='0.0.0.0'):
    # ifconfig, ip addr，去除主机对应IP
    p = Popen('/sbin/ifconfig -a |grep "inet " |grep -v 127.0.0', shell=True, stdout=PIPE)
    stdout, stderr = p.communicate()
    ips = []
    for lineip in stdout.split('\n'):
        ls = lineip.split()
        if len(ls) > 1:
            ip = ls[1].strip('addr:')  # centos6带addr:
            ips.append(ip)

    if hostip in ips:
        ips.remove(hostip)
    elif hostip != '0.0.0.0':
        print('Waring: 管理IP {0} 不在IP列表中 {1}'.format(hostip, ips))

    return ips


def get_ports():
    # 获取TCP和UDP监听端口
    p = Popen("/bin/netstat -tunlp | awk '{print $4}' | grep :", shell=True, stdout=PIPE)
    stdout, stderr = p.communicate()
    return stdout


# def get_group(host_url, hostip):

#     url = host_url + GET_GROUP_URL_PATH
# print url,88888
#     groups = {}

#     try:
#         r = urllib2.Request(url)
#         page = urllib2.urlopen(r)
#         text = page.read()
#         code = page.code

#         if text:
#             groups=json.loads(text, encoding='utf-8')
#             print groups
#         else:
#             print("Http status code: {0}".format(code))
#     except StandardError as msg:
#         print msg

#     group_id = 0
#     if groups:
#         if hostip.startswith('10.2.4.'):
#             group_id = groups.get('Core')
#         elif hostip.startswith('10.2.12.'):
#             group_id = groups.get('DMZ')
#         elif hostip.startswith('10.2.16.'):
#             group_id = groups.get('DMZPTR')
#         elif hostip.startswith('10.2.0.'):
#             group_id = groups.get('DB')
#         elif hostip.startswith('10.2.21.'):
#             group_id = groups.get('Manager')
#         elif hostip.startswith('10.2.20.'):
#             group_id = groups.get('KVM')
# else:
# group_id = 1

#     return group_id


def get_dmi():
    p = Popen('/usr/sbin/dmidecode', stdout=PIPE, shell=True)
    stdout, stderr = p.communicate()
    return stdout


def parser_dmi(dmidata):
    pd = {}
    line_in = False
    for line in dmidata.split('\n'):
        if line.startswith('System Information'):
            line_in = True
            continue
        if line.startswith('\t') and line_in:
            k, v = [i.strip() for i in line.split(':')]
            pd[k] = v
        else:
            line_in = False
    return pd


def get_mem_total():
    cmd = "grep MemTotal /proc/meminfo"
    p = Popen(cmd, stdout=PIPE, shell=True)
    data = p.communicate()[0]
    mem_total = data.split()[1]
    memtotal = int(round(int(mem_total) / 1024.0 / 1024.0, 0))
    return memtotal


def get_cpu_model():
    cmd = "cat /proc/cpuinfo"
    p = Popen(cmd, stdout=PIPE, stderr=PIPE, shell=True)
    stdout, stderr = p.communicate()
    return stdout
    # cat /proc/cpuinfo | grep name | cut -f2 -d: | uniq -c


def get_cpu_cores():
    # cpu_cores = {"logical": psutil.cpu_count(), "physical": psutil.cpu_count(logical=False)}

    p = Popen('cat /proc/cpuinfo| grep "physical id"| sort| uniq| wc -l', stdout=PIPE, shell=True)
    physical = p.communicate()[0].strip()

    p = Popen('cat /proc/cpuinfo| grep "processor"| wc -l', stdout=PIPE, shell=True)
    logical = p.communicate()[0].strip()

    cpu_cores = {"logical": logical, "physical": physical}
    return cpu_cores


def parser_cpu(stdout):
    groups = [i for i in stdout.split('\n\n')]
    group = groups[-2]
    cpu_list = [i for i in group.split('\n')]
    cpu_info = {}
    for x in cpu_list:
        k, v = [i.strip() for i in x.split(':')]
        cpu_info[k] = v
    return cpu_info


def get_disk_info():
    ret = OrderedDict()
    pcmd = Popen('/sbin/fdisk -l |grep "Disk /dev/sd"', shell=True, stdout=PIPE)
    stdout, stderr = pcmd.communicate()
    disk_dev = re.compile(r'Disk\s/dev/sd[a-z]{1}')
    disk_name = re.compile(r'/dev/sd[a-z]{1}')
    lines = stdout.split('\n')
    lines.reverse()
    for i in lines:
        disk = re.match(disk_dev, i)
        if disk:
            dlist = i.split(', ')
            dk = re.search(disk_name, dlist[0]).group()  # /dev/sda
            sz = re.search(re.compile(r'\d+'), dlist[1]).group()  # 32212254720
            p = str(int(sz) / 1024 / 1024 / 1024) + 'G'
            ret[dk] = p
    # import pdb;pdb.set_trace()
    # print ret,999, json.dumps(ret)
    return json.dumps(ret)


def get_disk_info2():
    #cat /proc/partitions
    ret = OrderedDict()
    pcmd = Popen("/bin/dmesg |grep  'GiB)'|awk '{print $(NF-7) $(NF-1)}'", shell=True, stdout=PIPE)
    stdout, stderr = pcmd.communicate()
    lines = stdout.split('\n')
    for i in lines:
        if len(i) < 10:
            continue
        dk = i[1:4]
        sz = i[8:] + i[5:7]
        ret[dk] = sz
    print ret
    return json.dumps(ret)


def get_sign(hostname):
    # 生成验证字符
    key = '%s_%s' % (hostname, Agent_Key)
    sign = hashlib.md5(key).hexdigest()
    return sign


def get_tomcat_info(tomcat_path=Tomcat_Path):
    # 获取JDK和Tomcat版本信息

    tomcat_info = {}

    sh_file = os.path.join(tomcat_path, 'bin/version.sh')
    if not os.path.exists(sh_file):
        print 'Tomcat不在默认目录/data/app/tomcat，尝试获取其目录....'
        stdout, stderr = runcmd('ps -ef|grep java|grep Dcatalina.base')

        CATALINA_BASE = re.compile(r'-Dcatalina.base=\S+')
        try:
            tomcat_path = re.search(CATALINA_BASE, stdout).group()[16:]
            print '检测到Tomcat目录：', tomcat_path
            tomcat_info['tomcat_path'] = tomcat_path
            sh_file = os.path.join(tomcat_path, 'bin/version.sh')
        except:
            print 'Waring: Tomcat没有运行或其它原因，无法获取Tomcat目录，Tomcat版本忽略'
            return {'JVM Version': get_jdk()}

    stdout, stderr = runcmd('source /etc/profile && sh %s |grep -E "number|Version"' % sh_file)

    if not stdout:
        print 'Error: Tomcat、JDK版本获取失败！请尝试执行 %s ，查看信息是否正常' % sh_file

    lines = stdout.split('\n')
    for i in lines:
        try:
            i = i.split(':')
            tomcat_info[i[0]] = i[1].strip()
        except:
            continue

    return tomcat_info


def get_jdk():
    # 未使用tomcat的主机，获取JDK版本
    stdout, stderr = runcmd('source /etc/profile && java -version 2>&1 | awk \'NR==1{gsub(/"/,"");print $3}\'')
    if not stdout.startswith('1.'):
        print '获取JDK版本失败'
        return ''
    return stdout.strip()


def post_data(host_url, data):
    url = host_url + CMDB_URL_PATH
    print 'POST URL:', url
    try:
        r = urllib2.Request(url, data, {"Content-Type": "application/json; charset=utf-8"})
        page = urllib2.urlopen(r)
        text = page.read()
        code = page.code

        if text:
            print text
        else:
            print("Server return http status code: {0}".format(code))
    except StandardError as msg:
        print msg
    return True


def asset_info(host_url):
    data_info = dict()
    data_info['memory'] = '%dG' % get_mem_total()
    disk_info = get_disk_info()
    if disk_info == '{}':
        print 'Waring: 当前系统用户无权限从fdisk -l命令获取磁盘信息，尝试使用dmesg命令...'
        disk_info = get_disk_info2()
    data_info['disk'] = disk_info
    cpuinfo = parser_cpu(get_cpu_model())
    cpucore = get_cpu_cores()
    data_info['cpu_num'] = '%s, %s' % (cpucore['physical'], cpucore['logical'])
    data_info['cpu_model'] = cpuinfo['model name']

    dmi_info = parser_dmi(get_dmi())
    data_info['sn'] = dmi_info.get('Serial Number', '?')  # 机器序列号
    data_info['vendor'] = dmi_info.get('Manufacturer', '?')  # 制造商
    if data_info['sn'] == '?':
        print 'Waring: 当前系统用户无权限从dmidecode获取信息，序列号和制造商信息将忽略'
    # data_info['product'] = parser_dmi(get_dmi())['Version']
    data_info['os'] = platform.linux_distribution()[0] + " " + platform.linux_distribution()[1]  # + " " + platform.machine()
    hostname = platform.node()
    data_info['hostname'] = hostname
    data_info['ip'] = get_host_ip(hostname)
    data_info['other_ip'] = ', '.join(get_other_ip(data_info.get('ip')))
    data_info['ports'] = get_ports()
    # group_id = get_group(host_url, data_info['ip'])
    # if group_id:
    #     data_info['group_id'] = group_id
    data_info['sign'] = get_sign(hostname)
    # data_info['text'] = '客户端Agent脚本于 %19s 更新' % datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    tomcat_info = get_tomcat_info()
    data_info['tomcat_ver'] = tomcat_info.get('Server number', '')
    data_info['jdk_ver'] = tomcat_info.get('JVM Version', '')
    data_info['kernel'] = tomcat_info.get('OS Version', '')
    if tomcat_info.has_key('tomcat_path'):
        data_info['tomcat'] = tomcat_info['tomcat_path']

    # import pdb;pdb.set_trace()
    # return data_info
    return json.dumps(data_info)


def asset_info_post(url_id=3, host_url=''):
    osenv = os.environ["LANG"]
    os.environ["LANG"] = "us_EN.UTF8"

    if not host_url:
        try:
            host_url = CMDB_URL[url_id]
        except:
            host_url = CMDB_URL[1]

    print '开始获取本机资产信息:'
    info = asset_info(host_url)
    print info
    print '----------------------------------------------------------'

    post_data(host_url, info)
    os.environ["LANG"] = osenv
    return True


def run_threaded(job_func):
    job_thread = threading.Thread(target=job_func)
    job_thread.start()


if __name__ == "__main__":
    import sys

    url_id = 3
    host_url = ''

    try:
        url_id = sys.argv[1]
        if url_id == '0':
            host_url = sys.argv[2].rstrip('/')
    except:
        pass

    asset_info_post(int(url_id), host_url)
