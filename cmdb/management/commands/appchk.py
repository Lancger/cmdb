# coding=utf-8

# import traceback
import time
# import json
from django.core.management.base import BaseCommand, CommandError

from smtplib import SMTPRecipientsRefused

from django import template
from django.conf import settings
from django.core.mail import EmailMessage
from cmdb.models import App, Mail_Log, cache
from cmdb.app import tomcat_md5
from cmdb.conf import AppChk
from django.contrib.auth.models import User
# m = 'sys'
# exec "import " +　m

# from django.utils import simplejson
####################################
import sys
reload(sys)
sys.setdefaultencoding('UTF-8')  # 原默认为sys.getdefaultencoding(): ascii
####################################


class Command(BaseCommand):

    help = u'检查所有APP各主机的tomcat目录文件MD5，生成差异数据并发邮件。由于系统资源占用大，请在凌晨各主机空闲时执行'

    def add_arguments(self, parser):
        parser.add_argument('app_ids', nargs='?', default='all', type=str, help=u'APP ID，默认为所有')

    def handle(self, *args, **options):
        print "App_tomcat_md5_check Start....."
        try:
            request_user = User.objects.get(username=AppChk['request_user'])
        except Exception as e:
            print '获取用户出错', AppChk['request_user'], e
            exit()

        app_ids = options['app_ids']
        apps = App.objects.filter(state=1)
        if app_ids != 'all':
            apps = apps.filter(id__in=app_ids.split(','))

        for app in apps:
            # 虽然tomcat_md5可多app进行处理(基于网页request短时响应要求)，
            # 而当前脚本计划任务无需及时返回最终结果，所以一个个app进行处理，减少短时系统资源占用压力。
            msg = tomcat_md5([app], request_user, refresh=1, thead_timeout=60, ssh_timeout=10)
            cache.set('app_%d' % app.id, msg, timeout=3600*20)
            time.sleep(30)

        mail(app_ids, apps)


def mail(app_ids, apps):
    # 邮件通知
    r_mails = AppChk['mails']
    today = time.strftime('%Y-%m-%d', time.localtime(time.time()))
    title = 'APP文件较验-(%s) %s' % (app_ids, today)
    context = get_context(apps)
    # print '############################## context ##############################'
    # print context
    # print '############################## context ##############################'
    # exit()
    newmail = EmailMessage(
        title,  # 邮件标题
        context,  # html正文
        settings.EMAIL_HOST_USER,  # 发送人，注意SPF
        r_mails,  # 收件人
    )
    newmail.content_subtype = "html"  # text/html

    mails = ','.join(r_mails)
    mail_log = {'name': title, 'mails': mails, }
    try:
        print '发送邮件.....'
        newmail.send()
        print '邮件发送成功'
        mail_log.update({'ok': True})
    except SMTPRecipientsRefused, date:
        errmsg = str(date).split('(')[1][0:-2]
        print '邮件发送失败，邮箱：%s，出错原因：%s' % (mails, errmsg)
        mail_log.update({'ok': False, 'text': errmsg, })
    except Exception as e:
        print '邮件发送失败，邮箱：%s，出错原因：%s' % (mails, str(e))
        mail_log.update({'ok': False, 'text': str(e), })

    Mail_Log(**mail_log).save()


html = '''
{% load filt %}
<div id="{{ app.id }}" >
    <h4><a href="http://10.2.21.34/cmdb/appchk/{{ app.id }}" target="_blank">{{ app.name }}</a> 文件较验 <a href="#top">返回顶端</a> </h4>
    {{ error }}
    {% if result %}
    <table border="1" cellpadding="0" cellspacing="0">
        <thead name="app_thead">
            <tr>
                <th width="30%">文件路径</th>
                {% for app_host in result.0.1 %}
                <th>
                    <a href="http://10.2.21.34/admin/cmdb/appfiles/{{ app_host.ip|appfiles:'id'  }}" target="_blank">{{ app_host.ip  }}</a><br/>
                    {% if app_host.jdk_ver %}jdk: {{ app_host.jdk_ver }}<br/>{% endif %}
                    {% if app_host.tomcat_ver %}tomcat: {{ app_host.tomcat_ver }}<br/>
                    md5: {{ app_host.ip|appfiles:'changetime' }}<br/>{% endif %}
                </th>
                {% endfor %}
            </tr>
        </thead>
        <tbody name="app_files">
            {% for file, md5_list in result.0.2.items %}
            <tr>
                <td>{{ file }}</td>
                {% for md5 in md5_list %}
                <td>{{ md5|safe }}&nbsp;</td>
                {% endfor %}
            {% empty %}
                <td>无差异</td>
                <td colspan="{{ result.0.1|length }}">各主机tomcat目录文件完全一致</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
    {% endif %}
</div>
'''


def get_context(apps):
    # 生成邮件正文
    indexs = []  # 索引，app列
    for app in apps:
        index = '<a href="#%d">%s</a><br/>' % (app.id, app.name)
        indexs.append(index)
        # print index
    contexts = []  # 正文内容，app列
    for app in apps:
        msg = cache.get('app_%d' % app.id)
        # print msg, 333
        msg['app'] = app
        # error = msg.get('error', '')  # str
        # result = msg.get('result', [])  # [[str(app), app_hosts, app_files],]
        req = template.Template(html).render(template.Context(msg, autoescape=False))
        contexts.append(req)
        # print req

    return '%s\r\n\r\n\r\n%s' % ('\r\n'.join(indexs), '\r\n'.join(contexts))
