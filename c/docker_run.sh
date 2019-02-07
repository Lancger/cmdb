#!/bin/bash

port=8088
cd /kf/dj

# 启动REDIS
nohup redis-server /etc/redis.conf >& redis.log &
sleep 2s

# 启动Django网站
# c/d start
echo "Starting....."
# 启动SSH代理（堡垒机）
nohup python -u manage.py proxy_sshd >& sshd.log &
# 启动后端负载 http + websocket
nohup python -u manage.py runworker --only-channels=* >& worker.log --threads 16 &
# 启动前端监听 0.0.0.0:8088
python -u /usr/bin/daphne -t 150 -b 0.0.0.0 -p $port --ws-protocol "graphql-ws" --proxy-headers dj.asgi:channel_layer

