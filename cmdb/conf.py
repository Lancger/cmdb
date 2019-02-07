# -*- coding: utf-8 -*-
from __future__ import unicode_literals


# ES节点所有索引状态在redis中缓存时长
RedisTimeOut = 600


DOCKER_CERT_PATH = '/etc/docker'  # docker客户端(cmdb本机)TSL证书目录，默认在cmdb运行用户的~/.docker/目录
# 三个TSL证书文件名，必需为默认的cert.pem、ca.pem、key.pem，如果不默认，需在cmdb程序中指定
import os
if not os.path.isdir(DOCKER_CERT_PATH) or not os.path.exists(os.path.join(DOCKER_CERT_PATH, 'cert.pem')):
    DOCKER_CERT_PATH = None

YmlDir = '/kf/yml/'  # yml文件根目录
ImgDir = '/kf/img/'  # 镜像包文件根目录


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
