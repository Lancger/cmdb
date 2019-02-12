# -*- coding: utf-8 -*-

from socket import timeout
from ssl import SSLError
import sys
from paramiko.py3compat import u
from django.utils.encoding import smart_unicode

try:
    import termios
    import tty
    has_termios = True
except ImportError:
    has_termios = False
    raise Exception('This project does\'t support windows system!')
try:
    import simplejson as json
except ImportError:
    import json

import paramiko
# import threading
import time
import re

reload(sys)
sys.setdefaultencoding('UTF-8')


class CustomeFloatEncoder(json.JSONEncoder):

    def encode(self, obj):
        if isinstance(obj, float):
            return format(obj, '.6f')
        return json.JSONEncoder.encode(self, obj)


class TTY():
    # SSH终端，便于处理输入输出信息生成执行的历史命令
    ssh = paramiko.SSHClient()

    def __init__(self, ws_channel):
        self.redis = ws_channel.channel_layer._connection_list[0]
        self.ws_channel = ws_channel  # 前端WebSocket
        self.stdin = ''  # 收集用户端按键输入
        self.stdins = ['', ]  # 收集用户端按键输入
        # self.stdin_time = time.time()  # 记录用户最后一次按键时的时间
        # self.stdin_timeout = 2  # 超时秒数，多久前用户最后一次按键算为超时

    def connect(self, ip, port, username, password, timeout=3):
        # 连接ssh
        # import ipdb;ipdb.set_trace()
        ssh = self.ssh
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            ssh.connect(ip, port, username, password, timeout=timeout)
        except timeout:
            self.ws_channel.send({"text": json.dumps(['stdout', '\033[1;3;31mConnect to server time out\033[0m\r\n'])}, immediately=True)
            self.ws_channel.send({"accept": False})

        except Exception as e:
            self.ws_channel.send(
                {"text": json.dumps(['stdout', '\033[1;3;31mError: %s (HOST: %s, SSH_User: %s)\033[0m\r\n' % (e, ip, username)])}, immediately=True)
            self.ws_channel.send({"accept": False})
        self.chan = ssh.invoke_shell(term='xterm', width=90, height=32,)
        self.trans = ssh._transport
        # print self.ssh._transport, 333333333333333

    def close(self):
        # import ipdb; ipdb.set_trace()
        # print self.ssh._transport, 8888888888
        if self.trans:
            self.trans.close()  # 关闭ssh
            self.trans = None
        # self.ssh.close()  # paramiko.SSHClient.connect连接多个SSH时，所有的ssh._transport为最后连接那个ssh的_transport，无法区分
        self.ws_channel.send({"text": json.dumps(['disconnect', ''])})  # 关闭websocket
        del self

    def shell(self):
        if has_termios:
            # sh=threading.Thread(target=posix_shell, args=(chan,ws_channel))
            # sh.setDaemon(True)
            # sh.start()
            times, stdouts = self.posix_shell(self.chan, self.ws_channel, self.redis)
            self.close()
            return times, self.stdins[1:], stdouts
        else:
            sys.exit(1)

    def send(self, stdin):
        # import ipdb;ipdb.set_trace()
        self.stdin = stdin
        try:
            self.chan.send(stdin)
        except Exception as e:
            self.ws_channel.send(
                {"text": json.dumps(['stdout', '\033[1;3;31mError: %s \033[0m\r\n' % e])}, immediately=True)

    def posix_shell(self, chan, ws_channel, redis):
        """
        chan: 后端paramiko所连接的主机SSH终端，当前函数中只收不发
        ws_channel：前端WebSocket，当前函数中只发不收
        后端chan ==> 前端ws_channel
        """
        stdouts = []  # 录像记录
        begin_time = time.time()
        last_write_time = {'last_activity_time': begin_time}

        try:
            chan.settimeout(0.0)
            while not chan.closed:
                # import ipdb; ipdb.set_trace()
                data = redis.rpop(ws_channel.name)
                if data:
                    # print type(data), 44444444444
                    if data == '\x04':
                        print 'websocket断开...'
                        break
                    else:
                        chan.send(data)
                # 循环监视ssh终端输出，实时发给websocket客户端显示
                if not chan.recv_ready():
                    time.sleep(0.005)  # 分析审计输入命令时，需快过人工按键频率 0.02
                    continue
                try:
                    # print 'stdin:', self.stdin, '!!!!!!!!!!'
                    # import ipdb;ipdb.set_trace()
                    x = chan.recv(4096)  # 收取ssh-tty打印信息，带着色
                    while ord(x[-1]) > 127:
                        # utf8字符为3位，有时截取时结尾刚好碰到utf8字符，导致汉字被分割成二部分
                        try:
                            x += chan.recv(1)
                        except:
                            break
                    # sys.stdout.write(x)
                    # sys.stdout.flush()
                    x = smart_unicode(x)
                    print 'stdout:', [x], 888
                    # import ipdb;ipdb.set_trace()
                    # print 111,len(x),222,'<%s>'% x[-1]
                    if len(x) == 0:
                        ws_channel.send({'text': json.dumps(['disconnect', smart_unicode('\r\n*** EOF\r\n')])}, immediately=True)
                        break
                    now = time.time()
                    delay = round(now - last_write_time['last_activity_time'], 6)
                    last_write_time['last_activity_time'] = now
                    # print[delay, x], 999
                    stdouts.append([delay, x])

                    if self.stdin:
                        # 收集输入按键，用于审计生成命令
                        self.set_stdins(stdin=self.stdin, stdout=x)
                        print self.stdins, '-----------------'
                        self.stdin = ''
                    elif len(x) < 3 and x.strip(u'\x07') != '':
                        # 按键过快，输出慢的情景
                        self.stdins.append(x)

                    ws_channel.send({'text': json.dumps(['stdout', x])}, immediately=True)  # 发送信息到WebSock终端显示
                    # print json.dumps(['stdout',smart_unicode(x)]),555

                    # 发送到监视
                    ws_channel.channel_layer.channel_layer.send_group(ws_channel.name.replace('!', '-'), {'text': json.dumps(['stdout', x])})
                except timeout:
                    pass
                except UnicodeDecodeError, e:
                    # import ipdb;ipdb.set_trace()
                    print e
                    # if e.reason == 'invalid start byte':
                    #     ws_channel.send({'text': json.dumps(['stdout', '\r\nwebssh不支持当前操作'], )}, immediately=True)
                    #     continue
                    lines = x.splitlines()
                    for line in lines:
                        # recv(1024字节)，除乱码字符所在行外，将其它行正常显示
                        if line:
                            try:
                                ws_channel.send({'text': json.dumps(['stdout', '%s\r\n' % smart_unicode(line)])}, immediately=True)
                            except UnicodeDecodeError, e:
                                ws_channel.send({'text': json.dumps(['stdout', 'Error: utf-8编码失败！！！\r\n%s\r\n' % smart_unicode(e)], )}, immediately=True)

                except Exception, e:
                    print 111, e, 3333
                    ws_channel.send({'text': json.dumps(['stdout', 'Error: 连接意外中断.' + smart_unicode(e)], )}, immediately=True)
                    break
        # except:
        #     import ipdb; ipdb.set_trace()
        finally:
            times = round(time.time() - begin_time, 6)  # 录像总时长
            # print '#######################################################'
            # print self.stdins
            # print '#######################################################'
            return (times, stdouts)

    def set_stdins(self, stdin, stdout):
        """
        根据输入输出，生成命令输入按键字符列表，用于审计
        1.处理输出stdout，虽然界面stdout中包含了所有信息，但复制粘贴一大片带回车的命令时，
          由于输出无延时，输入输出信息同时出现，合成一大片，解析处理复杂，所以忽略，需结合stdin
        2.处理前端输入stdin，由于table键补全、上下方向键历史命令，都无法获知，只有stdout中才有，
          在第三方软件界面，比如vi top等，stdin混杂了很多无需统计的按键输入，处理复杂。
        将输入输入的信息合成到self.stdins
        """

        # import ipdb;ipdb.set_trace()
        if stdin == u'\x1b[2;2R\x1b[>0;276;0c' or u'\x1bP' in stdin or u'\x1b\\' in stdin:
            # 进入vi窗口，前端websocket会自动输入一些终端版面数据
            return
        elif stdin == stdout:
            # 除了控制命令，正常情况下输入命令按键与终端显示输出一样
            self.stdins.append(stdin)
        elif stdin == '\r':
            if stdout.startswith('\r\n'):
                self.stdins.append('\r\n')
            else:
                # 非命令行界面的回车
                self.stdins.append('^C')
        elif '\r' in stdin:
            # 复制粘贴多行，根据输出判断是否直接加入或vi等第三方界面的粘贴
            # 假如粘贴的命令中带tab，无法探测自动补全
            l = stdin.split('\r')
            if l[0]:
                # 第一个命令，stdout开头应当有
                if not stdout.startswith('%s\r' % l[0]):
                    return
            else:
                # 回车
                if not stdout.startswith('\r'):
                    return
            self.stdins.append(stdin.replace('\r', '\r\n').replace('\t', '<Tab键>'))  # 直接加入
            self.stdins.append('\r\n')  # 分隔、结尾退出

        elif stdin == u'\x03':
            if stdout.startswith('^C'):
                self.stdins.append('^C')
        elif stdout.strip(u'\u0007') == '':
            # 输出空效果字符(主板㖓鸣器)
            return
        else:
            if u'\u001b[' in stdout:
                txt = stdout
                for c in [
                    u'\u001b[K',  # 光标
                    u'\u001b[C',  # 右键字符
                    u'\u001b[1@',  # 左右移动光标后，空格分隔的左边输入字符
                ]:
                    txt = txt.replace(c, '')
                p = '(\x1b\[\d+P)'
                txt = re.sub(re.compile(p, re.S), '', txt)  # 上下左右键产生的 u'\u001b[数字P'
                if u'\u001b[' in txt:
                    # 除去退格键、方向键产生的\u001b[字符外，仍有其它非人工输入导致出现在终端界面字符
                    # 非命令输入，不收集。比如vi编辑、top等界面
                    return

            if stdin in (u'\x1b', '\t'):
                # tab esc处理
                if '\r\n' in stdout or stdout == u'\x07':
                    # 用户按tab，终端显示多行内容，需选择补全，不收集
                    return
                stdout = stdout.strip(u'\x07')  # 有些终端补全的字符前带㖓鸣字符

            if stdin in (
                u'\x1b[C',  # 右
                u'\x1b[D',  # 左
                u'\x1b[H',  # Home
                u'\x1b[F',  # End
                u'\x7f',  # 退格
                u'\x1b[3~',  # Delete
            ):
                self.stdins.append(stdin)
                return
            elif '\r\n' in stdout:
                return
            # if stdin not in (
            #     u'\x1b[A',  # 上
            #     u'\x1b[B',  # 下
            #     u'\x7f',  # 退格，输出效果和上下按键一样，合并处理

            #     u'\t',  # tab
            #     u'\x1b',  # Esc

            #     # u'\x1a',  # ctrl+z
            #     # u'\x18',  # ctrl+x
            #     # u'\x1b[2~',  # Insert
            #     # u'\x1b[5~',  # 上页
            #     # u'\x1b[6~',  # 下页
            # ):
            #     if stdout == u'\x1b[1@%s' % stdin:
            #         # 左右方向键后，按键输入，append(stdout)
            #         pass
            #     else:
            #         # 非控制键，按键输入与输出不同，不收集
            #         return
            self.stdins.append(stdout)
            # import ipdb;ipdb.set_trace()


def docker_tty(chan, ws_channel, redis):
    """
    chan: 后端Docker HTTP 伪终端，当前函数中只收不发
    ws_channel：前端WebSocket，当前函数中只发不收
    redis队列 ==> 后端chan ==> 前端ws_channel
    Docker Server HTTP API 终端不支持汉字
    """

    # import ipdb; ipdb.set_trace()
    chan.settimeout(0.1)
    while 1:
        data = redis.rpop(ws_channel.name)
        if data:
            # print type(data), 44444444444
            # import ipdb; ipdb.set_trace()
            if data == '\x04':
                print 'websocket断开...'
                break
            else:
                chan.send(data)
        # 循环监视ssh终端输出，实时发给websocket客户端显示
        try:
            # print 'stdin:', self.stdin, '!!!!!!!!!!'
            # import ipdb;ipdb.set_trace()
            x = chan.recv(4096)  # 收取ssh-tty打印信息，带着色
            try:
                while ord(x[-1]) > 127:
                    # utf8字符为3位，有时截取时结尾刚好碰到utf8字符，导致汉字被分割成二部分
                    try:
                        x += chan.recv(1)
                    except:
                        break
            except IndexError:
                break
            # sys.stdout.write(x)
            # sys.stdout.flush()
            x = smart_unicode(x)
            print 'stdout:', [x], 888
            # import ipdb;ipdb.set_trace()
            # print 111,len(x),222,'<%s>'% x[-1]
            if len(x) == 0:
                ws_channel.send({'text': json.dumps(['disconnect', smart_unicode('\r\n*** EOF\r\n')])}, immediately=True)
                break

            ws_channel.send({'text': json.dumps(['stdout', x])}, immediately=True)  # 发送信息到WebSock终端显示
            # print json.dumps(['stdout',smart_unicode(x)]),555

        except (timeout, SSLError):
            # 非加密docker API, socket.timeout
            # TLS加密的2375, ssl.SSLError
            # time.sleep(0.1)
            pass
        except UnicodeDecodeError, e:
            # import ipdb;ipdb.set_trace()
            print e
            lines = x.splitlines()
            for line in lines:
                # recv(1024字节)，除乱码字符所在行外，将其它行正常显示
                if line:
                    try:
                        ws_channel.send({'text': json.dumps(['stdout', '%s\r\n' % smart_unicode(line)])}, immediately=True)
                    except UnicodeDecodeError, e:
                        ws_channel.send({'text': json.dumps(['stdout', 'Error: utf-8编码失败！！！'], )}, immediately=True)

        except Exception, e:
            # raise
            print 111, e, 3333
            ws_channel.send({'text': json.dumps(['stdout', 'Error: 连接意外中断.' + smart_unicode(e)], )}, immediately=True)
            break
