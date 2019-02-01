# -*- coding: utf-8 -*-


"""
ASGI entrypoint file for default channel layer.

Points to the channel layer configured as "default" so you can point
ASGI applications at "databinding.asgi:channel_layer" as their channel layer.
"""

import os
from channels.asgi import get_channel_layer
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dj.settings")
channel_layer = get_channel_layer()

def channel_layer2():
    #使用函数channel_layer，而不是上面的channel_layer变量，函数体只有在调用时才加载执行。而若使用channel_layer，由于循环import时routing未加载完全导致channel_routing=[]
    return get_channel_layer()

# print 4,'dj.asgi'
# channel_layer = channel_layer2()
