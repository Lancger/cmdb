#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright (C) 2003-2007  Robey Pointer <robeypointer@gmail.com>
#
# This file is part of paramiko.
#
# Paramiko is free software; you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# Paramiko is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Paramiko; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA.

import threading
# import sys
# import traceback
import socket
import paramiko
import selectors2 as selectors

from django.core.cache import cache
from cmdb.models import Host
from cmdb.conf import CliSSH

import sys
reload(sys)
sys.setdefaultencoding('UTF-8')

# ssh_client ===>>          proxy_ssh             ==>> ssh_server
# ssh_client ===>> (proxy_server -> proxy_client) ==>> ssh_server


def transport_keepalive(transport):
    # 对后端transport每隔x秒发送空数据以保持连接
    send_keepalive = CliSSH.get('send_keepalive', 0)
    transport.set_keepalive(send_keepalive)


class ServerInterface(paramiko.ServerInterface):
    # proxy_ssh = (proxy_server + proxy_client)

    def __init__(self):
        self.event = threading.Event()
        self.tty_args = ['?', 80, 40]  # 终端参数(终端, 长, 宽)
        self.ssh_args = None  # ssh连接参数
        self.type = None

    def conn_ssh(self):
        # proxy_client ==>> ssh_server

        proxy_client = paramiko.SSHClient()
        proxy_client.load_system_host_keys()
        proxy_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        print("*** Connecting SSH (%s@%s) ...." % (self.ssh_args[2], self.ssh_args[0]))
        proxy_client.connect(*self.ssh_args)

        self.chan_ser = proxy_client.invoke_shell(*self.tty_args)
        print("*** Connecting SSH ok")

    def bridge(self):
        # 桥接 客户终端 和 代理服务终端 交互
        transport_keepalive(self.chan_ser.transport)
        sel = selectors.DefaultSelector()  # Linux epol
        sel.register(self.chan_cli, selectors.EVENT_READ)
        sel.register(self.chan_ser, selectors.EVENT_READ)

        while self.chan_ser and self.chan_cli and not (self.chan_ser.closed or self.chan_cli.closed):
            events = sel.select(timeout=60)
            # import ipdb; ipdb.set_trace()
            for key, n in events:
                if key.fileobj == self.chan_ser:
                    try:
                        x = self.chan_ser.recv(1024)
                        if len(x) == 0:
                            self.chan_cli.send("\r\n服务端已断开连接....\r\n")
                            return
                        self.chan_cli.send(x)
                    except socket.timeout:
                        pass
                if key.fileobj == self.chan_cli:
                    try:
                        x = self.chan_cli.recv(1024)
                        if len(x) == 0:
                            print("\r\n客户端断开了连接....\r\n")
                            return
                        self.chan_ser.send(x)
                    except socket.timeout:
                        pass
                    except socket.error:
                        break

    def close(self):
        # 关闭ssh终端
        self.chan_ser.transport.close()
        try:
            self.chan_cli.transport.close()
        except:
            pass
        # import ipdb; ipdb.set_trace()
        print('SSH ({0[2]}@{0[0]}) end..................'.format(self.ssh_args))

    def set_ssh_args(self, hostid):
        # 准备proxy_client ==>> ssh_server连接参数，用于后续SSH、SFTP
        host = Host.objects.get(id=hostid)
        username, password = host.get_ssh_user()  # ssh_server的SSH用户/密码
        ip = host.ip
        port = host.port or 22
        self.ssh_args = (ip, port, username, password)

    def check_channel_request(self, kind, chanid):
        if kind == "session":
            return paramiko.OPEN_SUCCEEDED
        return paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

    def check_auth_password(self, username, password):
        # 验证密码
        key = 'clissh_%s_%s' % (username, password)
        hostid = cache.get(key)
        if hostid:
            # ssh_client ===>> proxy_server 验证通过
            if not self.ssh_args:
                self.set_ssh_args(hostid)
            # self.conn_ssh(hostid)
            return paramiko.AUTH_SUCCESSFUL
        return paramiko.AUTH_FAILED

    def check_auth_gssapi_with_mic(
        self, username, gss_authenticated=paramiko.AUTH_FAILED, cc_file=None
    ):
        """
        .. note::
            We are just checking in `AuthHandler` that the given user is a
            valid krb5 principal! We don't check if the krb5 principal is
            allowed to log in on the server, because there is no way to do that
            in python. So if you develop your own SSH server with paramiko for
            a certain platform like Linux, you should call ``krb5_kuserok()`` in
            your local kerberos library to make sure that the krb5_principal
            has an account on the server and is allowed to log in as a user.

        .. seealso::
            `krb5_kuserok() man page
            <http://www.unix.com/man-page/all/3/krb5_kuserok/>`_
        """
        if gss_authenticated == paramiko.AUTH_SUCCESSFUL:
            return paramiko.AUTH_SUCCESSFUL
        return paramiko.AUTH_FAILED

    def check_auth_gssapi_keyex(
        self, username, gss_authenticated=paramiko.AUTH_FAILED, cc_file=None
    ):
        if gss_authenticated == paramiko.AUTH_SUCCESSFUL:
            return paramiko.AUTH_SUCCESSFUL
        return paramiko.AUTH_FAILED

    def enable_auth_gssapi(self):
        return True

    def get_allowed_auths(self, username):
        return "gssapi-keyex,gssapi-with-mic,password,publickey"

    def check_channel_shell_request(self, channel):
        self.event.set()
        return True

    def check_channel_pty_request(
        self, channel, term, width, height, pixelwidth, pixelheight, modes
    ):
        self.tty_args = [term, width, height]
        # print (self.tty_args, 7777777777777)
        self.type = 'pty'
        return True

    def check_channel_window_change_request(self, channel, width, height,
                                            pixelwidth, pixelheight):
        # print channel, width, height, pixelwidth, pixelheight, 88888888
        self.chan_ser.resize_pty(width=width, height=height)
        return True

    def check_channel_subsystem_request(self, channel, name):
        # SFTP子系统
        # print (channel, name, 'subsystem')

        self.type = 'subsystem'
        self.event.set()
        return super(ServerInterface, self).check_channel_subsystem_request(channel, name)

    def check_channel_direct_tcpip_request(self, chan_id, origin, destination):
        # SSH隧道
        self.type = 'direct-tcpip'
        self.event.set()
        return 0
