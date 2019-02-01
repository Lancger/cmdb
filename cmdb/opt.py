# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import base64
from Crypto.Cipher import AES
import magic
import mimetypes


def get_AES(password, encode=0):
    # 密码加密解密，默认为解密
    # pycrypto==2.6.1

    KEY = '1234567890123456'
    BLOCK_SIZE = 16  # AES.block_size
    PADDING = chr(20)  # 'ý' #未满16*n时，补齐字符chr(253)

    pad = lambda s: s + (BLOCK_SIZE - len(s) % BLOCK_SIZE) * PADDING
    EncodeAES = lambda c, s: base64.b64encode(c.encrypt(pad(s)))
    DecodeAES = lambda c, e: c.decrypt(base64.b64decode(e)).rstrip(PADDING)
    cipher = AES.new(KEY)
    if encode:
        # 密码加密，用于内部保存
        # try:
        #     decoded = DecodeAES(cipher, password)
        # return  password #未修改密码直接提交，原字符已为密文，无需再次加密
        # except:
        #     pass
        return EncodeAES(cipher, password)  # 修改了密码，重新加密为密文
    else:
        # 密码解密，用于外部提取
        try:
            return DecodeAES(cipher, password)
        except:
            print 'Error: AES密码解密失败！！'
            return ''


def get_mime(file=None, buf=None):
    # 获取MIME类型
    mime = None
    if file:
        try:
            # 读取本地文件头来判断
            mime = magic.from_file(file, mime=True)
        except Exception as e:
            print str(e)
            # 通过文件后缀名来判断
            mime = mimetypes.guess_type(file)[0]
    elif buf:
        # 读取本地文件头来判断
        mime = magic.from_buffer(buf, mime=True)

    return mime if mime else 'application/empty'
