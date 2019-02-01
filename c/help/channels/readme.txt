
asgiref-1.1.2
channels-1.1.8
daphne-1.4.2

# 使一台机器支持运行多个django网站
# channels只考虑大型网站分布式或一台主机仅支持一个django
# 为支持同一主机运行多个网站，不同端口的runworker进行区分隔离，以免混用。
# daphne -t 150 -b 0.0.0.0 -p $port .... #port = sys.argv[6]
# 因channels进程是在网站py程序初始化之前启动，所以不能在网站程序中重写,
# 需修改官方channels routing.py和generic/websockets.py
