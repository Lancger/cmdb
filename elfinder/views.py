# coding=utf-8
import json
import copy

from django.http import HttpResponse, Http404
from django.utils.decorators import method_decorator
from django.views.generic.base import View
from django.views.decorators.csrf import csrf_exempt
from exceptions import ElfinderErrorMessages
from elfinder.connector import ElfinderConnector
from elfinder.conf import settings as ls
# from django.shortcuts import render_to_response
from django.shortcuts import get_object_or_404
from cmdb.models import Host, cache

import re
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.contrib.auth.mixins import LoginRequiredMixin

from elfinder.sftpstoragedriver.sftpstorage import SFTPStorage
from django.http import StreamingHttpResponse
import time

import sys
reload(sys)
sys.setdefaultencoding("utf-8")

# views.ElfinderConnectorView  ==> connector.ElfinderConnector ==> utils.volumes.instantiate_driver
# ==> volumes.storage.ElfinderVolumeStorage ==> sftpstoragedriver.sftpstorage.SFTPStorage


class Elfinders:

    def __init__(self):
        # self.opts = opts
        self.elfinder_sftps = {}
        self.sftp_timeout = 600  # sftp连接过期时间(秒)

    def get_elfinder(self, hostid):
        cache.expire('elfinder_%s' % hostid, timeout=self.sftp_timeout)  # 有操作，延长过期时间
        # print 'expire', self.sftp_timeout, '============================='
        return self.elfinder_sftps.get(hostid)

    def set_elfinder(self, hostid, optinon_sets):
        if hostid not in self.elfinder_sftps:
            self.elfinder_sftps[hostid] = ElfinderConnector(optinon_sets)
            cache.set('elfinder_%s' % hostid, 1, timeout=self.sftp_timeout)
        return self.elfinder_sftps[hostid]

    def chk_close_sftp(self):
        while 1:
            time.sleep(10)
            for hostid, elfinder in self.elfinder_sftps.items():
                if not cache.get('elfinder_%s' % hostid):
                    # import ipdb; ipdb.set_trace()
                    self.elfinder_sftps.pop(hostid).close()

    def run_close_sftp(self):
        import threading
        t = threading.Thread(target=self.chk_close_sftp)
        t.daemon = True
        t.start()

global elfinders  # 多线程共享变量
elfinders = Elfinders()
elfinders.run_close_sftp()


class ElfinderConnectorView(PermissionRequiredMixin, LoginRequiredMixin, View):
    """
    Default elfinder backend view
    streamhttpresponse
    """
    permission_required = 'cmdb.sftp_host'
    raise_exception = True
    elfinder = None

    def render_to_response(self, context, **kwargs):
        """
        It returns a json-encoded response, unless it was otherwise requested
        by the command operation
        """
        # import ipdb;import ipdb; ipdb.set_trace()
        # print context, 8989898
        kwargs = {}
        additional_headers = {}
        # create response headers
        if 'header' in context:
            for key in context['header']:
                if key == 'Content-Type':
                    kwargs['content_type'] = context['header'][key]
                elif key.lower() == 'status':
                    kwargs['status'] = context['header'][key]
                else:
                    additional_headers[key] = context['header'][key]
            del context['header']

        # return json if not header
        if 'content_type' not in kwargs:
            kwargs['content_type'] = 'application/json'

        if 'pointer' in context:  # return file
            if 'text/plain' not in kwargs.get('content_type') and 'storage' in context['volume']._options and isinstance(context['volume']._options['storage'], SFTPStorage):
                # stream sftp file download
                def file_iterator(file_name, chunk_size=32768):
                    while True:
                        c = file_name.read(chunk_size)
                        if c:
                            yield c
                        else:
                            context['volume'].close(context['pointer'], context['info']['hash'])
                            # fix sftp open transfer not close session bug
                            if 'storage' in context['volume']._options and isinstance(context['volume']._options['storage'], SFTPStorage):
                                context['volume']._options['storage'].sftp.close()
                            break
                the_file_name = additional_headers["Content-Location"]
                response = StreamingHttpResponse(file_iterator(context['pointer']))  # 读取流文件
                response['Content-Type'] = 'application/octet-stream'
                response['Content-Disposition'] = 'attachment;filename="{0}"'.format(the_file_name)
                return response
            else:
                context['pointer'].seek(0)
                kwargs['content'] = context['pointer'].read()  # 读取文件
                context['volume'].close(context['pointer'], context['info']['hash'])
        elif 'raw' in context and context['raw'] and 'error' in context and context['error']:  # raw error, return only the error list
            kwargs['content'] = context['error']
        elif kwargs['content_type'] == 'application/json':  # return json
            kwargs['content'] = json.dumps(context)
        else:  # return context as is!
            kwargs['content'] = context

        response = HttpResponse(**kwargs)
        for key, value in additional_headers.items():
            response[key] = value

        return response

    @staticmethod
    def handler_chunk(src, args):
        """
        handler chunk parameter
        """
        if "chunk" in src:
            args['chunk_name'] = re.findall(r'(.*?).\d+_\d+.part$', src['chunk'])[0]
            first_chunk_flag = re.findall(r'.*?.(\d+)_\d+.part$', src['chunk'])[0]
            if int(first_chunk_flag) == 0:
                args['is_first_chunk'] = True
            else:
                args['is_first_chunk'] = False
        else:
            args['chunk_name'] = False
            args['is_first_chunk'] = False

    def output(self, cmd, src):
        """
        Collect command arguments, operate and return self.render_to_response()
        """
        args = {}
        cmd_args = self.elfinder.commandArgsList(cmd)
        for name in cmd_args:
            if name == 'request':
                args['request'] = self.request
            elif name == 'FILES':
                args['FILES'] = self.request.FILES
            elif name == 'targets':
                args[name] = src.getlist('targets[]')
            else:
                arg = name
                if name.endswith('_'):
                    name = name[:-1]
                if name in src:
                    try:
                        args[arg] = src.get(name).strip()
                    except:
                        args[arg] = src.get(name)
        if cmd == 'mkdir':
            args['name'] = src.getlist('dirs[]') if 'dirs[]' in src else src.getlist('name')
        elif cmd == "upload":
            if 'upload_path[]' in src:
                dir_path = src.getlist('upload_path[]')
                if len(list(set(dir_path))) == 1 and dir_path[0] == args['target']:
                    args['upload_path'] = False
                    self.handler_chunk(src, args)
                else:
                    args['upload_path'] = dir_path
                    self.handler_chunk(src, args)
            else:
                args['upload_path'] = False
                self.handler_chunk(src, args)
        elif cmd == "size":
            args['targets'] = src.getlist('targets[0]')
        args['debug'] = src['debug'] if 'debug' in src else False
        # print args, 99999999
        res = self.elfinder.execute(cmd, **args)
        # res = elfinders.sftp(self.elfinder, cmd, args)

        return self.render_to_response(res)

    def get_command(self, src):
        """
        Get requested command
        """
        try:
            return src['cmd']
        except KeyError:
            return 'open'

    def get_optionset(self, **kwargs):
        # print kwargs, 99999999999999
        set_ = ls.ELFINDER_CONNECTOR_OPTION_SETS[kwargs['optionset']]
        if kwargs['host_id'] != 'default':
            for root in set_['roots']:
                root['startPath'] = kwargs['host_id']
        temp_dict = copy.deepcopy(set_)
        u_id_dict = {'debug': temp_dict['debug'], 'roots': temp_dict['roots']}
        return u_id_dict

    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        if not kwargs['optionset'] in ls.ELFINDER_CONNECTOR_OPTION_SETS:
            raise Http404
        # print kwargs, 7777777888888888
        return super(ElfinderConnectorView, self).dispatch(*args, **kwargs)

    def get_elfinder(self, request, *args, **kwargs):
        # 生成self.elfinder
        hid = kwargs['host_id']
        self.elfinder = elfinders.get_elfinder(hid)

        if self.elfinder:
            return
        else:
            # u_id = str(uuid.uuid4())
            # kwargs['u_id'] = u_id
            optinon_sets = self.get_optionset(**kwargs)
            if kwargs['optionset'] == 'sftp':
                host = get_object_or_404(Host, id=kwargs['host_id'])
                ip = host.ip
                username, password = host.get_ssh_user()
                optinon_sets['roots'][0]['alias'] = '{0}-{1}'.format(host.hostname, ip)
                key_label = "%s::%s" % (ip, username)

                optinon_sets['roots'][0]['storageKwArgs'] = {'host': ip,
                                                                   # 'ftp_readonly': 1,
                                                                   'params': {'port': host.port,
                                                                              'username': username,
                                                                              'password': password,
                                                                              'timeout': 10},
                                                                   'root_path': '/', 'interactive': False,
                                                                   'key_label': key_label}
                # import ipdb;ipdb.set_trace()
                optinon_sets['roots'][0]['ftp_readonly'] = request.user.userprofile.ftp_readonly
                self.elfinder = elfinders.set_elfinder(hid, optinon_sets)
            else:
                raise

    def get(self, request, *args, **kwargs):
        """
        used in get method calls
        """
        self.get_elfinder(request, *args, **kwargs)
        return self.output(self.get_command(request.GET), request.GET)

    def post(self, request, *args, **kwargs):
        """
        called in post method calls.
        It only allows for the 'upload' command
        """
        self.get_elfinder(request, *args, **kwargs)
        cmd = self.get_command(request.POST)

        if cmd not in ['upload']:
            self.render_to_response({'error': self.elfinder.error(ElfinderErrorMessages.ERROR_UPLOAD, ElfinderErrorMessages.ERROR_UPLOAD_TOTAL_SIZE)})
        return self.output(cmd, request.POST)

