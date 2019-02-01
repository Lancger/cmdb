# coding=utf-8

import traceback
import time
import json
from django.core.management.base import BaseCommand, CommandError
from cmdb.models import Cert

from django.db import connection, OperationalError
from datetime import datetime, timedelta
from django.core.mail import EmailMessage
from smtplib import SMTPRecipientsRefused
from django.conf import settings

from cmdb.conf import CertMails, CertWXs, WeiXin_URL
from cmdb.models import Mail_Log
import urllib2
# m = 'sys'
# exec "import " +　m

# from django.utils import simplejson
####################################
import sys
reload(sys)
sys.setdefaultencoding('UTF-8')  # 原默认为sys.getdefaultencoding(): ascii
####################################


def get_cert():
    # 获取快过期的证书
    now = datetime.now()
    print '\r\n\r\n%s Start..' % str(now)
    certlist = []
    certs = Cert.objects.exclude(send=1)
    for cert in certs:
        exp_time = cert.exp_date
        note_time = exp_time - timedelta(days=cert.days)  # 预过期时间
        if now > exp_time:
            # 已过期
            state = 3
        elif now > note_time:
            # 将过期
            state = 2
            certlist.append(cert)
        else:
            state = 1
        if state != cert.state:
            print '更新过期状态', cert
            cert.state = state
            cert.save(update_fields=['state'])

    return certlist


def mail(cert, user):
    # 证书过期邮件通知
    r_mails = set(CertMails)
    um = [u.email for u in user]
    r_mails = r_mails | set(um)

    title = '证书将要过期 - (%s)' % cert.name
    context = '证书(%s)过期日期为%s, 提前通知天数: %d' % (cert.name, cert.exp_date, cert.days)
    newmail = EmailMessage(
        title,  # 邮件标题
        context,  # html正文
        settings.EMAIL_HOST_USER,  # 发送人，注意SPF
        r_mails,  # 收件人
    )
    # newmail.content_subtype = "html"

    mails = ','.join(r_mails)
    mail_log = {'name': title, 'mails': mails, }
    try:
        newmail.send()
        print '邮件通知成功'
        mail_log.update({'ok': True})
        # cert.mail = True
        # cert.mail_date = datetime.now()
        # cert.save()
    except SMTPRecipientsRefused, date:
        errmsg = str(date).split('(')[1][0:-2]
        print '邮件发送失败，邮箱：%s，出错原因：%s' % (mails, errmsg)
        mail_log.update({'ok': False, 'text': errmsg, })
    except Exception as e:
        print '邮件发送失败，邮箱：%s，出错原因：%s' % (mails, str(e))
        mail_log.update({'ok': False, 'text': str(e), })

    Mail_Log(**mail_log).save()


def wx(cert, user):
    # 证书过期微信通知
    r_wxs = set(CertWXs)
    # um = [u.userprofile.weixin for u in user]
    um = []
    for u in user:
        try:
            wx = u.userprofile.weixin
        except:
            continue
        um.append(wx)

    r_wxs = r_wxs | set(um)

    data = {
        "first": '证书将过期',
        "occurtime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
        "content": '证书(%s)过期日期为%s, 提前通知天数: %d。' % (cert.name, cert.exp_date, cert.days),
        "remark": '本消息由CMDB微信提醒触发',
        "openIdList": list(r_wxs),  # 微信用户ID，用户已关注公司警报通知的公众号
    }
    data = json.dumps(data, ensure_ascii=False).encode('utf-8')
    # print data
    request = urllib2.Request(WeiXin_URL, data, headers={"Content-Type": "application/json"})
    try:
        response = urllib2.urlopen(request).read()
        # print response
        if 'success' in response:
            print '微信通知成功'
            # cert.wx = True
            # cert.wx_date = datetime.now()
            # cert.save()
        else:
            print '微信通知失败，服务端返回信息', response
    except Exception as e:
        print u'发送微信通知出错', str(e)


class Command(BaseCommand):

    help = u'用于检查证书是否到了过期预通知时间，到了通知时间则进行邮件/微信通知'

    def add_arguments(self, parser):
        parser.add_argument('hours', nargs='?', default=4, type=int, help=u'重新检测执行的间隔小时数')

    def handle(self, *args, **options):
        print "Cert_check Start....."

        hours = options['hours']

        while 1:
            try:
                print 11
                certlist = get_cert()
                # break
                for cert in certlist:
                    user = cert.send_user.all()
                    if user:
                        print cert, '发送邮件通知'
                        mail(cert, user)
                        print cert, '发送微信通知'
                        wx(cert, user)
                        cert.send = True
                        cert.send_date = datetime.now()
                        cert.save()
                    else:
                        print '证书 %s 未设置通知用户，无法进行通知。' % cert.name

            except:
                print traceback.format_exc()
                try:
                    connection.close()
                    print '---connection.close()---'
                except:
                    print traceback.format_exc()
                    pass
                print str(datetime.now())
                import sys
                print sys.exc_info()
                # import pdb;pdb.set_trace()
                time.sleep(30)
                continue
            finally:
                print '%s End...' % datetime.now()
                print '每%s小时检查一次' % hours
                time.sleep(3600 * hours)

        print 'Error: Cert_check exit!!!!!!!!!!'
