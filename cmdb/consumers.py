# -*- coding: utf-8 -*-


from channels.generic.websockets import WebsocketConsumer
from channels import Group
try:
    import simplejson as json
except ImportError:
    import json
from django.utils.encoding import smart_unicode
from django.core.exceptions import ObjectDoesNotExist
from django.db import connection, OperationalError

from django.conf import settings
from django.utils import timezone
import os
import time
import traceback
import re
import logging

from cmdb.models import Host, SSH_Log, docker
# from sudoterminal import ShellHandler

# print 2,'webssh.consumers'
from interactive import TTY, docker_tty
from cmdb.models import DockerHost

####################################
# 程序中有print u'汉字'时，需定义程序环境编码为UTF-8，否则需直接用print '汉字'，不能用u''
import sys
reload(sys)
sys.setdefaultencoding('UTF-8')  # 原默认为sys.getdefaultencoding(): ascii
####################################

logger = logging.getLogger('Get_CMD')
lv = logging.DEBUG  # DEBUG INFO WARNING ERROR CRITICAL
logger.setLevel(lv)
ch = logging.StreamHandler()  # 到控制台
ch.setLevel(lv)
logger.addHandler(ch)


class Websocket(WebsocketConsumer):
    http_user = True  # 自动从HTTP获取用户(免重新登陆)
    http_user_and_session = True
    channel_session = True
    channel_session_user = True

    def connect(self, message):
        self.message.reply_channel.send({"accept": True})
        # import ipdb;ipdb.set_trace()

    def disconnect(self, message=None):
        # import ipdb; ipdb.set_trace()
        self.message.reply_channel.send({"accept": False})
        redis = self.message.channel_layer._connection_list[0]
        redis.lpush(self.message.reply_channel.name, '\x04')

    def receive(self, text=None, bytes=None, **kwargs):
        # 从前端WebSocket收取数据
        try:
            if text:
                # print text, 9999999
                redis = self.message.channel_layer._connection_list[0]
                data = json.loads(text)
                if data[0] == 'hostid':
                    hostid = data[1]
                    try:
                        data = Host.objects.get(id=hostid)
                        user = self.message.user
                        if not data.chk_user_prem(user, 'ssh'):
                            print '用户<%s>没有主机终端权限:' % user.username, data
                            self.message.reply_channel.send({"text": json.dumps(['stdout', u'\033[1;3;31m非法操作！当前用户无主机终端权限。\033[0m\r\n'])}, immediately=True)
                            self.message.reply_channel.send({"accept": False})
                            return

                    except ObjectDoesNotExist:
                        self.message.reply_channel.send({"text": json.dumps(['stdout', '\033[1;3;31mConnect to server! Server ip doesn\'t exist!\033[0m\r\n'])}, immediately=True)
                        self.message.reply_channel.send({"accept": False})
                        return

                    username, password = data.get_ssh_user()
                    tty = TTY(self.message.reply_channel)
                    # print self, tty, 898989
                    tty.connect(data.ip, data.port, username, password, timeout=3)

                    channel = self.message.reply_channel.name
                    sshlog = SSH_Log.objects.create(host=data, user=user, channel=channel)  # 用于在线监视
                    times, stdins, stdouts = tty.shell()  # 用于录像回放，阻塞式
                    self.disconnect()
                    end_msg = u'\r\n连接结束...\r\n'
                    print end_msg, channel
                    self.message.reply_channel.send({'text': json.dumps(['stdout', end_msg])}, immediately=True)
                    stdouts.append([0.1, end_msg])
                    savelog(sshlog, times, stdouts, stdins)

                elif data[0] in ['stdin']:  # ,'stdout'
                    # 前端输入转发给redis队列左入，后端将从redis队列右取（redis模拟先进先出--消息队列）
                    print data, '###########'
                    # import ipdb; ipdb.set_trace()
                    redis.lpush(self.message.reply_channel.name, data[1])

                elif data[0] == 'close':
                    self.disconnect()
                else:
                    self.message.reply_channel.send({"text": json.dumps(['stdout', '\033[1;3;31mUnknow command found!\033[0m\r\n'])}, immediately=True)
            elif bytes:
                print 'bytes:', bytes
                redis = self.message.channel_layer._connection_list[0]
                redis.lpush(self.message.reply_channel.name, json.loads(bytes)[1])
        except Exception:
            print traceback.print_exc()


# class CheckSftp(WebsocketConsumer):
#     # 用于网页sftp关闭后，自动断开代理的后端sftp连接

#     def connect(self, message):
#         # print channel, 223
#         self.message.reply_channel.send({"accept": True})

#     def receive(self, text=None, bytes=None, **kwargs):
#         # 从前端WebSocket收取数据
#         try:
#             if text:
#                 data = json.loads(text)
#                 if data[0] == 'hostid':
#                     self.message.channel_layer.hostid = data[1]
#                     # 使用self.message.channel_layer传递参数
#                     # ws被动断开后调用的disconnect()实例，是重新实例化生成的CheckSftp()
#                     # 和当前所在实例self不一致，但self.message.channel_layer为同一个实例
#                     while 1:
#                         time.sleep(2)
#                 elif data[0] == 'close':
#                     # 主动关闭
#                     self.disconnect(self.message)
#         except Exception:
#             print traceback.print_exc()

#     def disconnect(self, message):
#         self.message.reply_channel.send({"accept": False})
#         from elfinder import multiple_elf
#         if hasattr(self.message.channel_layer, 'hostid'):
#             elfinder = multiple_elf.get(self.message.channel_layer.hostid)
#             if elfinder:
#                 print 'close elfinder.....'
#                 elfinder.close()
#                 multiple_elf.pop(self.message.channel_layer.hostid)
#         self.close()


class SshMonitor(WebsocketConsumer):
    # 终端监视
    http_user = True
    http_user_and_session = True
    channel_session = True
    channel_session_user = True

    def connect(self, message, channel):
        channel = channel.replace('!', '-')  # Group(channel)要求只能字母数字、连接符
        # print channel, 223
        self.message.reply_channel.send({"accept": True})
        Group(channel).add(self.message.reply_channel.name)

    def disconnect(self, message, channel):
        channel = channel.replace('!', '-')
        Group(channel).discard(self.message.reply_channel.name)
        self.message.reply_channel.send({"accept": False})
        self.close()

    def receive(self, text=None, bytes=None, **kwargs):
        pass


def savelog(sshlog, times, stdouts, stdins):

    # 终端日志设置结束时间、命令记录
    cmds = get_cmds(stdins)  # 命令记录
    sshlog.end_time = timezone.now()
    sshlog.cmds = str(cmds)
    n = 3
    while n:
        n -= 1
        try:
            try:
                sshlog.save()
            except Exception as e:
                print e
                time.sleep(5)
                connection.close()
                print '---connection.close()---'
        except Exception as e:
            print e

    # 记录终端回放日志文件
    attrs = {
        "version": 1,
        "width": 90,
        "height": 32,
        "duration": times,
        "command": os.environ.get('SHELL', None),
        'title': None,
        "env": {
            "TERM": os.environ.get('TERM'),
            "SHELL": os.environ.get('SHELL', 'sh')
        },
        'stdout': list(map(lambda frame: [frame[0], frame[1]], stdouts))
    }
    logfile = os.path.join(settings.MEDIA_ROOT, settings.SSH_REPLAY, sshlog.log)
    print logfile
    logfile_dir = os.path.dirname(logfile)
    if not os.path.exists(logfile_dir):
        # 目录不存在时创建
        os.makedirs(logfile_dir)
    with open(logfile, "w+") as f:
        f.write(json.dumps(attrs, ensure_ascii=True, indent=2))

    # print '-----------------------------'
    # print stdouts
    # print '-----------------------------'


def get_cmds(stdins=[]):
    # 解析输入输出按键信息，生成用户执行的命令
    # return ''
    # texts = []
    # for stdin in stdins:
    #     text = stdin[1]
    #     if text.startswith('^C\r\n'):
    #         text = '^C'
    #     elif text.startswith('\r\n') or (u'\u001b]0;' in text and u'\u0007' in text):
    #         # u'\u001b]0;' u'\u0007'， 命令输入所在行，开头的类似[root@dev ~]#
    #         text = '\r\n'
    #     # elif len(text) > 888:
    #     #     continue

    #     texts.append(text)

    # 开始将texts按元素'\r\n'、'^C'间隔，进行分割成多个子列表
    cmds = []
    cmd = []
    for stdin in stdins:
        cmd.append(stdin)
        if stdin == '\r\n':
            # 结尾，分隔命令
            cmds.append(cmd)
            cmd = []
        elif stdin == '^C':
            # ctrl+c取消的命令
            cmd = []
        else:
            if stdin.startswith(u'\r\u001b[C\u001b[C\u001b[C\u001b[C'):
                # 上下方向键，终端输出为\r“回车”+右移显示原有[root@dev ~]# ，然后+新命令(或短命令+光标清行)
                # 这种情况下，如果新命令和之前老命令开头有部分相同，将导致新命令开头部分缺失
                new_cmd = stdin[1:].replace(u'\x1b[K', '')
                while new_cmd.startswith(u'\x1b[C'):
                    new_cmd = new_cmd[3:]
                new_cmd = replace_xP(new_cmd.replace(u'\u001b[1@', ''))  # 去除上下键产生的 u'\u001b[数字P'、u'\u001b[1@'
                if new_cmd.endswith(u'\x1b[C'):
                    # 当前命令和前一个命令，后面部分相同，终端输出时直接在原有基础上处理显示
                    # cmd[-2]: "vi /data/shell/hf_cup_ftp.sh"
                    # cmd[-1]: "cat /data/shell/hf_cup_ftp.sh"
                    # "\r\u001b[C\u001b[C\u001b[C\u001b[C\u001b[C\u001b[C\u001b[C\u001b[C\u001b[C\u001b[C\u001b[C\u001b[C\u001b[C\u001b[C\u001b[C\u001b[C\u001b[C\u001b[C\u001b[1@cat\u001b[C\u001b[C\u001b[C\u001b[C\u001b[C\u001b[C\u001b[C\u001b[C\u001b[C\u001b[C\u001b[C\u001b[C\u001b[C\u001b[C\u001b[C\u001b[C\u001b[C\u001b[C\u001b[C\u001b[C\u001b[C\u001b[C\u001b[C\u001b[C\u001b[C\u001b[C"
                    new_cmd = new_cmd[:-3]
                    n = 1  # 后面部分相同字符长度
                    while new_cmd.endswith(u'\x1b[C'):
                        new_cmd = new_cmd[:-3]
                        n += 1  # 每去除一个尾部右移，相同字符位数+1
                    new_cmd = '%s%s' % (new_cmd, cmd[-2][-n:])  # cat + 后面26位相同字符“ /data/shell/hf_cup_ftp.sh”
                cmd = [new_cmd]
            elif stdin.endswith(u'\u001b[C\u001b[C\u001b[C\u001b[C') and u'\r\u001b[C\u001b[C\u001b[C\u001b[C' in stdin:
                # 左右、home、end光标偏移输入
                # u"v /data/shell/hf_cup_ftp.sh\r\u001b[C\u001b[C\u001b[C\u001b[C\u001b[C\u001b[C\u001b[C\u001b[C\u001b[C\u001b[C\u001b[C\u001b[C\u001b[C\u001b[C\u001b[C\u001b[C\u001b[C\u001b[C\u001b[C"
                cmd[-1] = stdin[0]  # 更新stdin
            elif stdin.endswith(u'\x1b[K') or stdin.startswith(u'\b'):
                # u'\b\b\b\b\b\b\b\bll\u001b[K'
                # u'\b\b\b\b\u001b[2Pll'
                # ！cmd = [u'crontab -l', u'\x08e', '\r\n'] 向上键历史命令，当前面有部分内容相同时
                new_cmd = stdin.lstrip(u'\b').replace(u'\x1b[K', '')
                new_cmd = replace_xP(new_cmd)  # 去除上下键产生的 u'\u001b[数字P'
                cmd = [new_cmd]
            else:
                while stdin.startswith(u'\x1b[C') and stdin.endswith(u'\b'):
                    # 在快速按键输入并同时狂按左移键时，终端输出有延时，
                    # 会输出右移+字符+“\b左移”，左右抵消后结果仍一致
                    stdin = stdin[3:-1]
                cmd[-1] = stdin  # 更新stdin

    logger.info('cmds: %s 0000' % cmds)

    # import ipdb;ipdb.set_trace()
    cmds_1 = []
    for cmd in cmds:
        # 处理 退格、删除，上下、左右方向键+输入 产生的"\u001b[1@按键字符"，(命令字符串空格左边的输入)
        if cmd == ['\r\n']:
            continue
        cmd_1 = ''  # cmd列表按键转为字符输入
        enum = enumerate(cmd)
        i = 0  # 光标位置
        for (index, key) in enum:
            # index列表索引， key 按键输入，一般为单个字符，因实时websocket人工输入慢而计算机快
            logger.debug('%s %s %s' % (i, index, [key]))
            # i += 1
            if key == u'\x1b[D':
                # 左
                i -= 1  # 光标位置左移一位
            elif key == u'\x1b[C':
                # 右
                i += 1  # 光标位置右移一位
            elif key == u'\x1b[F':
                # End
                i = len(cmd_1)
            elif key == u'\x1b[H':
                # Home
                i = 0
            elif key == u'\x7f':
                # 退格
                cmd_1 = '%s%s' % (cmd_1[:i - 1], cmd_1[i:])  # 删除光标前一个按键字符
                i -= 1
            elif key == u'\x1b[3~':
                # 删除
                cmd_1 = '%s%s' % (cmd_1[:i], cmd_1[i + 1:])  # 删除光标所在位一个按键字符
            elif key.startswith(u'\u001b[1@'):
                # 光标有偏移时，在字符串空格左边，按键输入
                stdin_key = key.replace(u'\u001b[1@', '')
                cmd_1 = '%s%s%s' % (cmd_1[:i], stdin_key, cmd_1[i:])
                i += len(stdin_key)  # 按键字符输入后，光标自动右移一位
            elif key.endswith('\b'):
                # 上下方向键
                # 或光标有偏移时，在字符串最后一个空格分隔的右边，按键输入
                # key: 输入字符+光标后面的字符+\b数个
                stdin_key = del_str(key)
                cmd_1 = '%s%s%s' % (cmd_1[:i], stdin_key, cmd_1[i:])
                i += len(stdin_key)  # 按键字符输入后，光标自动右移一位
            elif key == u'\r\n':
                # 回车执行命令，忽略光标偏移，放到命令末尾
                cmd_1 = '%s%s' % (cmd_1, key)
            else:
                #  正常按键字符输入
                cmd_1 = '%s%s%s' % (cmd_1[:i], key, cmd_1[i:])
                i += len(key)
            # logger.debug('cmd_1: %s ************' % cmd_1)
        cmds_1.append(cmd_1)

    logger.info('cmds_1: %s 1111' % cmds_1)
    return '\r\n'.join(cmds_1)


def replace_xP(s):
    p = '(\x1b\[\d+P)'
    new_s = re.sub(re.compile(p, re.S), '', s)  # 去除上下键产生的 u'\u001b[数字P'
    return new_s


def del_str(s):
    # u'd65\x08\x08f65\x08\x08'
    # 上下键、左右键后光标偏移输入
    cs = [c for c in s]
    indexs = [i for (i, j) in enumerate(cs) if j == '\b']  # 存储退格符所在索引位置
    del_indexs = indexs[:]  # 将要删除的元素(含退格本身)所在列表位置
    # print 'indexs', indexs
    for index in indexs:
        del_index = index - 1
        while (del_index in del_indexs):
            # 若元素已被之前退格删，删除前移一位元素。
            del_index -= 1
        del_indexs.append(del_index)
    print 'del_indexs', del_indexs
    cs2 = [j for (i, j) in enumerate(cs) if i not in del_indexs]
    key = ''.join(cs2).strip()
    if not key and s[0] == ' ':
        # 用户输入的就是空格
        key = ' '
    return key

    """
    cs_1 = []  # 去除界面信息、(tab、向下键空)
    # import ipdb;ipdb.set_trace()
    for cmd in cmds:
        # if cmd[-1] == '\r\n':
        add = 1  # 是否将cmd收集到cs_1中
        for i in cmd:
                # print i, len(i), 555
            if len(i) > 222:
                    # 命令长度不会很长
                add = 0
                break
            elif len(i) > 20:
                for u in [
                    # 命令行窗口
                    u'\u001b[0m',
                    u'\u001b[01',
                    # vi窗口
                    u'\u001b[m',
                    # u'\u001b[?',
                    u'\u001bP+',
                ]:
                    if u in i:
                            # 命令不含\u001b[0m这类终端界面表格字符
                        add = 0
                        break
            elif i.startswith(u'\u001b['):
                if not (i.startswith(u'\u001b[C') or i.startswith(u'\u001b[1@')):
                    # 除右方向键符及输入，人工输入不会以它开头，包括退格、tab、方向键。
                    add = 0
                    break
        if add:
            cs_1.append(cmd)
    logger.info('cs_1: %s 1111' % cs_1)

    cs_2 = []  # 处理tab键等空效果字符\x07，tab导致了回车分割，重新拼接成一个命令
    for cmd in cs_1:
        try:
            last_cmd = cs_2[-1]  # 上一个cmd
            if last_cmd[-2] == u'\u0007' or cmd[0] == u'\u0007':
                # 上一个cmd 最后按键是tab等空效果字符或当前命令第一个为tab，二个命令合成一个
                last_cmd.pop(-2)  # '\x07'
                last_cmd.pop(-1)  # '\r\n'
                if cmd[-1] != '^C':
                    last_cmd.extend(cmd)
                else:
                    # 当前命令以ctrl+C结尾，放弃，并将和当前命令为同一条的上条不全命令删除
                    cs_2.pop(-1)
            else:
                raise IndexError
        except IndexError:
            if cmd[-1] != '^C':
                cs_2.append(cmd)
        except Exception:
            print traceback.print_exc()
    logger.info('cs_2: %s 2222' % cs_2)

    cs_3 = []  # 处理方向键退格键等
    for cmd in cs_2:
        c_3 = []
        for i in cmd:
            # 上下左右方向键、Home、End
            if i.strip('\b') == '':
                # 去除左方向键效果，因退格键为“\b光标符”，无输入字符
                continue
            elif i.strip('\u001b[C') == '':
                # 去除右方向键效果
                continue
            elif i.startswith(u'\u001b[C' * 4) and i.endswith(u'\u001b[K'):
                # 上下方向键产生的字符变化，一般为很长字符变化为短字符，
                # 删除很长字符时终端输出不是用大量\b\b光标去删。而是回车从头开始，右移光标[root@dev ~]#末
                c_3 = [i.replace(u'\u001b[C', '')]  # 将之前历史元素清空，复位
                continue
            else:
                c_3.append(i)

        c_3_2 = ''  # 收录列表字符按键
        for i in c_3:
            # 左右移动光标，并且有输入
            pass
            if i.endswith('\b'):
                # 右移光标，然后输入
                # i: 输入字符+光标后面的字符+\b数个
                s = i.rstrip('\b')
                # stdin_str = s[len(i) - len(s):]  # 输入，一般为单个字符，因实时websocket人工输入慢而计算机快
                right_str = s[len(s) - len(i):]  # 光标后面的字符串，长度和\b数len(i)-len(s)一致
                if c_3_2.endswith(right_str):
                    c_3_2 = '%s%s' % (c_3_2[:len(right_str)], s)  # 光标左字符串+输入单字符+光标右字符串
                    continue
                else:
                    print '???????????????????????????????????'
                    print '未知异常，c_3_2: %s, right_str: %s' % (c_3_2, right_str)
                    print '???????????????????????????????????'
            c_3_2 = '%s%s' % (c_3_2, i)

        cmd = [i for i in c_3_2.replace(u'\x08\x1b[K', '\b').strip() if i != u'\u0007']  # 使元素全为单字符，去掉退格光标指示符、tab产生的响铃字符，便于退格键处理
        # print cmd, 44444444
        indexs = [i for (i, j) in enumerate(cmd) if j == '\b']  # 存储退格键所在索引位置
        del_indexs = indexs[:]  # 将要删除的元素(含退格键本身)所在列表位置
        # print 'indexs', indexs
        for index in indexs:
            del_index = index - 1
            while (del_index in del_indexs):
                # 若元素已被之前退格删，删除前移一位元素。
                del_index -= 1
            del_indexs.append(del_index)
        print 'del_indexs', del_indexs
        c_3 = [j for (i, j) in enumerate(cmd) if i not in del_indexs]
        cmd = ''.join(c_3).strip()
        if cmd:
            cs_3.append(''.join(c_3))
    logger.info('cs_3: %s 3333' % cs_3)

    # 2.stdins，带回车的粘贴输入
    if stdins:
        logger.info('stdins: %s 4444' % stdins)
    cs_3.extend(stdins)
    p = "(\x1b\[[0-9]*[;0-9]*[;0-9]*[mHABCDJsuLMP])"  # 终端控制字符
    cmds = re.sub(re.compile(p, re.S), '', '\r\n'.join(cs_3))
    logger.info('cmds: %s 5555' % cmds)
    return cmds
    """


class DockerWebsocket(WebsocketConsumer):
    """
    用于容器终端 - Websocket
    实际上，所有Docker终端连接操作全是通过Docker服务端HTTP API完成，
    当前WebSocket只是做为中介，将docker客户端、服务端HTTP交互信息展示给前端
    """
    http_user = True  # 自动从HTTP获取用户(免重新登陆)
    http_user_and_session = True
    channel_session = True
    channel_session_user = True

    def connect(self, message):
        self.message.reply_channel.send({"accept": True})
        # import ipdb;ipdb.set_trace()
        # permission auth

    def disconnect(self, message=None):
        # import ipdb; ipdb.set_trace()
        self.message.reply_channel.send({"accept": False})
        redis = self.message.channel_layer._connection_list[0]
        redis.lpush(self.message.reply_channel.name, '\x04')
        print 'disconnect..................'

    def receive(self, text=None, bytes=None, **kwargs):
        # 从前端WebSocket收取数据
        try:
            if text:
                # print text, 9999999
                redis = self.message.channel_layer._connection_list[0]
                data = json.loads(text)
                if data[0] == 'hostid':
                    user = self.message.user
                    # import ipdb; ipdb.set_trace()
                    if not user.has_perm('cmdb.containers_manage'):
                        print '用户<%s>没有容器管理权限' % user.username
                        self.message.reply_channel.send({"text": json.dumps(['stdout', u'\033[1;3;31m非法操作！当前用户无容器管理权限。\033[0m\r\n'])}, immediately=True)
                        self.message.reply_channel.send({"accept": False})
                        return

                    cli = DockerHost.objects.get(id=data[1]).client
                    """
                    container = cli.containers.get(data[2])
                    tty = container.exec_run('/bin/bash', stdin=True, socket=True, tty=True)
                    若要自定义终端宽高，需重写官方container.exec_run函数
                    docker官方底层API支持定义终端宽高，
                    1. client.api.exec_create，生成resp['Id']
                    2. client.api.exec_start
                    3. time.sleep
                    4. client.api.exec_resize(resp['Id'], 高, 宽)
                    container.exec_run函数只执行上面二步，但返回的对像，已不含resp连接信息

                    终端参数说明
                    1. socket，必需为True，保持socket连接，类似websocket终端连接. 客户端为网站服务器，服务端为远程宿主机。
                    2. stdin，必需为True，开启输入交互，每次按键都可发给服务端或者回车后将命令发给服务端，上下键历史命令、tab补全功能，需实时将stdin按键发送给容器HTTP服务端。
                    3. tty，建议为True，开启伪终端后，Docker HTTP API stdout输出信息会带终端版面布局、着色等，否则输出不带终端布局字符.
                    """
                    # 开始建立终端连接，tty=True，终端为伪终端，所有终端通讯实质为HTTP API，服务端HTTP返回的信息带终端版面、着色等终端字符。
                    tty_ok = 0
                    shs = ['/bin/bash', '/bin/sh']  # 终端入口命令，如果容器上没有，将HTTP404
                    for sh in shs:
                        try:
                            resp = cli.api.exec_create(
                                container=data[2], cmd=sh, stdout=True, stderr=True, stdin=True, tty=True,
                                privileged=False, user='', environment=None
                            )
                        except docker.errors.APIError as e:
                            error = '\033[1;3;31mdocker exec执行出错,\r\n%s\033[0m\r\n' % str(e)
                            self.message.reply_channel.send({"text": json.dumps(['stdout', error])}, immediately=True)
                            self.message.reply_channel.send({"accept": False})
                            return
                        tty = cli.api.exec_start(
                            resp['Id'], detach=False, tty=True, stream=False, socket=True
                        )
                        time.sleep(1)
                        try:
                            cli.api.exec_resize(resp['Id'], 32, 106)  # 调整终端输出窗口大小
                            tty_ok = 1
                            break
                        except docker.errors.NotFound:
                            continue

                    if tty_ok:
                        docker_tty(tty, self.message.reply_channel, redis)
                    else:
                        error = '\033[1;3;31m生成终端需依赖%s其中之一，请确认当前容器是否含有这些文件\033[0m\r\n' % ' '.join(shs)
                        self.message.reply_channel.send({"text": json.dumps(['stdout', error])}, immediately=True)
                        self.message.reply_channel.send({"accept": False})
                    return

                elif data[0] in ['stdin']:  # ,'stdout'
                    # 前端输入转发给redis队列左入，后端将从redis队列右取（redis模拟先进先出--消息队列）
                    print data, '###########'
                    # import ipdb; ipdb.set_trace()
                    redis.lpush(self.message.reply_channel.name, data[1])

                elif data[0] == 'close':
                    self.disconnect()
                else:
                    self.message.reply_channel.send({"text": json.dumps(['stdout', '\033[1;3;31mUnknow command found!\033[0m\r\n'])}, immediately=True)
            elif bytes:
                print 'bytes:', bytes
                redis = self.message.channel_layer._connection_list[0]
                redis.lpush(self.message.reply_channel.name, json.loads(bytes)[1])

        except Exception:
            print traceback.print_exc()
