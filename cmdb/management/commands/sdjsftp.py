# coding=utf-8

# import traceback
# import time
# import json
from django.core.management.base import BaseCommand

# from cmdb.models import Host

from datetime import datetime, timedelta
import os
import stat
import sys

from paramiko import Transport, SFTPClient

reload(sys)
sys.setdefaultencoding('utf-8')

# 源sftp对账文件服务器
servers = [

    {
        'ip': '10.2.16.10',
        'username': 'sdjftp',
        'password': 'Sdjabc123!',
        'base': '/data/ftp/sdj2ylstp',
        'dirs': [
            '48930000',
            '49985910',
            '48935840',
            '48939220',
        ],
    },

]


tmppath = '/tmp/sdjsftp'  # 本地临时目录
zip_pwd = 'SDJ@sftp-zip'  # zip打包并设置解压密码

# 目录sftp服务器
ip = '10.8.0.60'
user = 'app'
password = 'apps1234'
basedir = '/data/sftp'

days = 3  # 保留最近*天数据


def get_dates(days=3):
    # 获取最近几天目录
    today = datetime.today()
    dates = []
    for n in range(days):
        date = today - timedelta(days=n)
        dates.append(date.strftime("%Y%m%d"))
    return dates


def down():
    # 源SFTP服务器目录 ===》 本地临时目录
    yestoday = datetime.today() - timedelta(days=1)
    local_dir = tmppath
    if not os.path.exists(local_dir):
        os.makedirs(local_dir)
    for server in servers:
        ip = server['ip']
        port = 22
        username = server['username']
        password = server['password']
        remote_dir = server['base']

        ftp = Sftp(ip=ip, port=port, username=username, password=password, remote_dir=remote_dir, local_dir=local_dir)
        ftp.connect()
        if ftp.sftp:
            # import ipdb; ipdb.set_trace()
            # exit()
            for dir in server['dirs']:
                subdir = os.path.join(dir, yestoday.strftime("%Y%m%d"))
                ftp.downloads(subdir)

            ftp.close()


def zip():
    # 本地临时目录压缩
    yestoday = datetime.today() - timedelta(days=1)
    date = yestoday.strftime("%Y%m%d")
    for server in servers:
        for dir in server['dirs']:
            path = os.path.join(tmppath, dir)
            zipfile = os.path.join(path, '%s.zip' % date)
            if os.path.exists(zipfile):
                print '压缩包已存在，不重复打包', zipfile
                # os.remove(zipfile)
            else:
                # datepath = os.path.join(path, date)
                os.chdir(path)
                os.system('/usr/bin/zip -P {0} {1}.zip {1}/* && rm -rf {1}'.format(zip_pwd, date))


def up():
    # 本地临时目录 ===》 目标SFTP服务器目录
    ftp = Sftp(ip=ip, port=22, username=user, password=password, remote_dir=basedir, local_dir=tmppath)
    ftp.connect()
    if ftp.sftp:
        ftp.uploads()

        # # 删除旧日期目录
        # for server in servers:
        #     for dir in server['dirs']:
        #         datedirs = []
        #         ls = ftp.sftp.listdir_attr(os.path.join(basedir, dir))
        #         for l in ls:
        #             if stat.S_ISDIR(l.st_mode):
        #                 # 目录
        #                 if len(l.filename) == 8:
        #                     datedirs.append(l.filename)

        #         if len(datedirs) > days:
        #             datedirs.sort()
        #             rmdirs = datedirs[:-days]
        #             for rmdir in rmdirs:
        #                 path = os.path.join(basedir, dir, rmdir)
        #                 print '删除旧日期目录:', path
        #                 ftp.rmdir(path)

        # 已将日期目录改为上传压缩包
        for server in servers:
            for dir in server['dirs']:
                datezips = []
                ls = ftp.sftp.listdir(os.path.join(basedir, dir))
                for l in ls:
                    # import ipdb; ipdb.set_trace()
                    if os.path.splitext(l)[1] == '.zip':
                        datezips.append(l)

                if len(datezips) > days:
                    datezips.sort()
                    rmzips = datezips[:-days]
                    for zipfile in rmzips:
                        print '删除旧压缩包:', zipfile
                        zipfile = os.path.join(basedir, dir, zipfile)
                        ftp.sftp.remove(zipfile)

        ftp.close()


class Command(BaseCommand):
    help = u'对账文件同步'

    def add_arguments(self, parser):
        parser.add_argument('rm', nargs='?', default=0, type=int,
                            help=u'''
                            是否清空本地临时目录（重新下载），默认为否
                            ''')

    def handle(self, *args, **options):
        # import ipdb; ipdb.set_trace()
        rm = options['rm']
        if rm:
            os.system('rm -rf %s/*' % tmppath)
        down()
        zip()
        up()


class Sftp(object):

    def __init__(self, ip='127.0.0.1', port=22, username='root', password='.', remote_dir='', local_dir=''):
        self.sftp = None
        self.ip = ip
        self.port = port
        self.username = username
        self.password = password
        self.remote_dir = remote_dir
        self.local_dir = local_dir

    def connect(self):
        # 连接FTP
        if self.sftp:
            print u'已有连接', self.ip
        try:
            transport = Transport((self.ip, self.port))
            transport.use_compression()
            transport.connect(username=self.username, password=self.password)
            self.sftp = SFTPClient.from_transport(transport)
            print u'连接成功 ', self.ip, self.port
        except Exception as e:
            print u'连接失败：', str(e), self.port

    def close(self):
        # 关闭FTP
        if self.sftp:
            self.sftp.close()
            print '### 断开 sftp server:', self.ip, self.port
            self.sftp = None

    def mkldir(self, path):
        # 创建本地目录，用于下载
        if not os.path.exists(path):
            os.makedirs(path)

    def mkrdir(self, rpath):
        # 创建远程目录，用于上传
        try:
            self.sftp.stat(rpath)
        except:
            # 目录不存在
            self.sftp.mkdir(rpath)

    def download(self, remote_file, local_file):
        if os.path.exists(local_file):
            # print '文件已存在，删除：', local_file
            # os.remove(local_file)
            print '本地文件已存在，跳过下载：', local_file
            return
        self.sftp.get(remote_file, local_file)

    def downloads(self, subdir=''):
        # 递归获取remote_dir所有文件的列表、下载
        all_files = list()
        rpath_dir = os.path.join(self.remote_dir, subdir)
        lpath_dir = os.path.join(self.local_dir, subdir)
        if not os.path.exists(lpath_dir):
            os.makedirs(lpath_dir)
        print rpath_dir, 222

        # 获取当前指定目录下的所有目录及文件，包含属性值
        try:
            files = self.sftp.listdir_attr(rpath_dir)
        except IOError as e:
            print e
            return all_files
        for x in files:
            filename = os.path.join(subdir, x.filename)
            if stat.S_ISDIR(x.st_mode):
                # 如果是目录，则递归处理该目录，这里用到了stat库中的S_ISDIR方法，与linux中的宏的名字完全一致
                print '发现子目录:', filename
                self.mkldir(os.path.join(self.local_dir, filename))
                all_files.extend(self.downloads(filename))
            else:
                all_files.append(filename)
                r_file = os.path.join(self.remote_dir, filename)
                l_file = os.path.join(self.local_dir, filename)
                print filename, '==>>', l_file
                self.download(r_file, l_file)  # 下载
        return all_files

    def upload(self, local_file, remote_file):
        try:
            self.sftp.stat(remote_file)
            print '远程文件已存在，跳过上传：', remote_file
        except:
            self.sftp.put(local_file, remote_file)

    def uploads(self):
        local_path = self.local_dir
        remote_dir = self.remote_dir
        for parent, paths, files in os.walk(local_path):
            for path in paths:
                # 创建目录结构
                # print parent, path
                rpath = os.path.join(parent, path).replace(local_path, remote_dir)
                print '创建目录', rpath
                self.mkrdir(rpath)
            for f in files:
                # print parent, paths, f
                file = os.path.join(parent, f)
                rfile = file.replace(local_path, remote_dir)
                print file, '==>>', rfile
                self.upload(file, rfile)

    def rmdir(self, path):
        # 删除目录及其中所有文件
        pass
        ls = self.sftp.listdir_attr(path)
        for l in ls:
            file = os.path.join(path, l.filename)
            if stat.S_ISDIR(l.st_mode):
                # 如果是目录，则递归处理该目录，这里用到了stat库中的S_ISDIR方法，与linux中的宏的名字完全一致
                print '删除子目录:', file
                self.rmdir(os.path.join(path, file))
            else:
                print '删除文件:', file
                self.sftp.remove(file)
        self.sftp.rmdir(path)
