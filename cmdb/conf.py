# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import pickle
from django.core.cache import cache


Agent_Key = 'DW$@75d^k9'  # 资产脚本执行收集客户端自身信息后，POST到CMDB服务端时的KEY，用于和主机名一起加密生成较验KEY


App_Download_URL = 'http://10.2.21.35/app/conf/app.sh'


# ES节点所有索引状态在redis中缓存时长
RedisTimeOut = 600


CertMails = [
    # 证书过期，默认发送下列地址
    # 'xieyufeng@sdjgroup.com.cn',
]

CertWXs = [
    # 证书过期，默认发送下列微信用户ID
    # 'omM2vv9Auv3iFMvam0Z6MIJh9TZ0',
]


WeiXin_URL = 'http://10.2.13.15:8080/online-weixin-fe/template/sendWxOpTemplate'


ZABBIX = [
    {
        'url': 'http://10.2.21.35',
        'user': 'Admin',
        'pwd': 'wZypWs0exyMpVUSfjiMIBA==',  # AES密文
    },
    {
        'url': 'http://10.7.21.11',
        'user': 'Admin',
        'pwd': 'wZypWs0exyMpVUSfjiMIBA==',  # AES密文
    }

]


A10_CONF = {
    'ALLOWED_HOSTS': [
        # 允许客户端脚本通过cmdb操作A10
        '*',  # 不限IP
        '127.0.0.1',
        '10.2.16.11',  # bankfront 银联前置
        '10.2.16.12',  # bankfront 银联前置
        '10.7.16.12',  # bankfront 银联前置
        '10.7.16.13',  # bankfront 银联前置
        '192.168.80.238',  # test
    ],
    'CMDB_USER': 'xieyufeng',  # 进行A10操作时使用的用户

}

AppChk = {
    # 每天进行APP各主机tomcat目录文件检查对比
    'mails': [
        # 结果发送给下列地址
        'huxiaolin@sdjgroup.com.cn',
        # 'xieyufeng@sdjgroup.com.cn',
    ],
    'request_user': 'xieyufeng',  # 网站用户，用于记录日志，表示哪个用户进行的当前操作

}

DOCKER_CERT_PATH = '/etc/docker'  # docker客户端(cmdb本机)TSL证书目录，默认在cmdb运行用户的~/.docker/目录
# 三个TSL证书文件名，必需为默认的cert.pem、ca.pem、key.pem，如果不默认，需在cmdb程序中指定
import os
if not os.path.isdir(DOCKER_CERT_PATH):
    DOCKER_CERT_PATH = None

YmlDir = '/data/app/yml/'  # yml文件根目录
ImgDir = '/data/app/img/'  # 镜像包文件根目录


# 阿里云OSS文件管理

OSS = {
    'Server': 'oss-cn-shenzhen.aliyuncs.com',
    'AccessKeyID': 'LTAIYnrubX7nDWsK',
    'AccessKeySecret': 'v1TdWZ+PZpO7RVebWZcz/EVQjwdPS+J+BkShZy/d1ZU=',  # AES密文
    'BucketName': 'sdjapp',
}

CliSSH = {
    # 资产系统 -- SSH代理服务端，参数配置
    'host': '0.0.0.0',  # SSH监听地址
    'port': 2222,  # SSH监听端口
    'password_timeout': 900,  # 临时密码有效期(秒)
    # 'scheme': {'ssh': 'xshell', 'sftp': 'xftp'},
    'scheme': {
        'ssh': 'ssh',  # 设置ssh的scheme
        'sftp': 'sftp',  # 设置sftp的scheme
        # Xshell.exe  ssh://user:password@192.168.80.238:2222 -newtab 标识名
        # 从网页调用外部程序，自定义的协议名，直接调用xshell时它的值必需为"ssh"，xftp为"sftp"
        # scheme如改为其它名，需通过bat脚本或自行开发客户端调用xshell或securtCRT。注册表[HKEY_CLASSES_ROOT\<scheme>]
    },
    'send_keepalive': 60,  # 每隔x秒发送空数据以保持连接，0则不发送
}
