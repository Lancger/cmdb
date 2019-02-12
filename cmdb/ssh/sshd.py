# coding=utf-8
import os
import socket
import threading

import paramiko
from sftpinterface import SFTPInterface
from sshinterface import ServerInterface
import sys
# vi /usr/lib/python2.7/site-packages/sitecustomize.py
reload(sys)
sys.setdefaultencoding('UTF-8')

cons = 100  # SSHD 连接数


class SSHServer:

    def __init__(self, host, port):
        self.listen_host = host
        self.listen_port = port

    @property
    def host_key(self):
        host_key_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ssh_proxy_rsa.key')
        if not os.path.isfile(host_key_path):
            pass
        return paramiko.RSAKey(filename=host_key_path)

    def run(self):
        host = self.listen_host
        port = self.listen_port
        print('Starting ssh server at {}:{}'.format(host, port))
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
        sock.bind((host, port))
        sock.listen(cons)

        while 1:
            # import ipdb; ipdb.set_trace()
            client, addr = sock.accept()  # 阻塞等待客户端连接
            t = threading.Thread(target=self.handle_connection, args=(client, addr))
            t.daemon = True
            t.start()

    def handle_connection(self, sock, addr):
        transport = paramiko.Transport(sock, gss_kex=False)

        transport.load_server_moduli()

        transport.add_server_key(self.host_key)
        transport.set_subsystem_handler(
            'sftp', paramiko.SFTPServer, SFTPInterface
        )
        print('client socket:', addr)
        proxy_ssh = ServerInterface()

        # import ipdb; ipdb.set_trace()
        transport.start_server(server=proxy_ssh)  # SSH时输密码 或 SFTP时调用子系统开启SFTP
        # print('start Transport.start_server')

        while transport.is_active():
            chan_cli = transport.accept()
            proxy_ssh.chan_cli = chan_cli
            proxy_ssh.event.wait(5)  # 等待
            if not chan_cli:
                continue

            if not proxy_ssh.event.is_set():
                sock.close()
                return
            else:
                proxy_ssh.event.clear()

            t = threading.Thread(target=self.dispatch, args=(proxy_ssh,))
            t.daemon = True
            t.start()

    @staticmethod
    def dispatch(proxy_ssh):
        supported = {'pty', 'x11', 'forward-agent'}
        chan_type = proxy_ssh.type
        # import ipdb; ipdb.set_trace()
        if chan_type in supported:
            # SSH
            proxy_ssh.conn_ssh()  # 连接后端SSH
            proxy_ssh.bridge()  # 阻塞
            proxy_ssh.close()
        elif chan_type == 'subsystem':
            # SFTP
            pass
        else:
            msg = "Request type `{}` not support now".format(chan_type)
            proxy_ssh.chan_cli.send(msg)
