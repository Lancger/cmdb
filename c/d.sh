#!/bin/bash


f=`basename $0` #当前文件名d
p="$( cd "$( dirname "$0"  )" && pwd  )" #脚本目录c路径

base=`dirname "$p"` #sdj路径

cd $base #sdj


run() {
    #用于生产环境启动停止django网站进程
    arg1=$1
    # echo $arg1
    ifs=$IFS; IFS="\n"; 
    proc="$(ps -ef | grep -Ei '(c/d runworker|daphne|runserver 0.0.0.0:'$port'|c/d cert|proxy_sshd|python -u manage.py)' | grep -v 'grep')"
    # echo $proc

    if [ "$arg1" == "stop" ];then
        if [ -z "$2" ];then
            echo "Stopping....."
            echo -e $proc | grep -Ei '('$port'|[[:space:]]cert|[[:space:]]proxy_sshd)' | awk '{print $2}' | xargs kill -9 2>/dev/null
        else
            echo "结束端口 <$2> 进程..."
            netstat -tnlp|grep :$2|awk '{print $7}' |awk -F '/' '{print $1}' | xargs kill -9 2>/dev/null
            #${s%/*}
        fi
    elif [ "$arg1" == "start" ];then
        pid=`echo -e $proc | grep $port | awk '{print $2}'`
        if [ -z "$pid" ];then
            nohup $p/$f runworker --only-channels=${web_channel_route}* >& worker.log --threads 16 &
            nohup $p/$f runworker --only-channels=${web_channel_route}websocket.* >& websocket.log --threads 16 &
            nohup $p/$f runworker --only-channels=${web_channel_route}http.* --threads 16 >& http.log &
            nohup $p/$f proxy_sshd >& sshd.log &
            nohup $p/$f cert 4 >& cert.log &
            nohup python -u /usr/bin/daphne -t 150 -b 0.0.0.0 -p $port --ws-protocol "graphql-ws" --proxy-headers sdj.asgi:channel_layer >& daphne.log &
            echo "Starting....."
            sleep 1
            ps aux | grep -Ei '(c/d runworker|daphne|runserver 0.0.0.0:'$port'|c/d cert|python -u manage.py)' | grep -v 'grep'
        else
            echo -e $proc
            echo "已有相关进程运行中，忽略处理"
        fi

    elif [ "$arg1" == "state" ];then
        if [ -z "$proc" ];then
            echo "No running.."
        else
            echo -e $proc
        fi

    fi
    IFS=$ifs
}





port=8088 #默认端口

multiple_web=1
# 使一台机器支持运行多个django网站
# channels只考虑分布式或一台主机仅支持一个django
# 为支持同一主机运行多个网站，不同端口的runworker进行区分隔离，以免混用。
# daphne -t 150 -b 0.0.0.0 -p $port .... #port = sys.argv[6]
# 需修改官方channels routing.py和generic/websockets.py

if [ "$multiple_web" -ne 0 ];then
    web_channel_route=${port}.
fi


arg1=$1
arg2=$2


if ([ "$arg1" -gt 0 ] 2>/dev/null && [ -z "$arg2" ]) ;then 
    arg2='0.0.0.0:'${arg1}
    arg1='runserver'
    # $p/$f proxy_sshd >& sshd.log &

elif [ "$arg1" == "ssh" ];then
    arg1='proxy_sshd'

elif [ "$arg1" == "m1" ];then
    arg1='makemigrations'
elif [ "$arg1" == "m2" ];then
	arg1='migrate'
    if [ "$arg2" == "gs" ];then
        arg2='--database gslb'
    fi

elif [ "$arg1" == "u" ];then
    arg1='createsuperuser'

elif [ "$arg1" == "h" ];then
    arg1='help'
elif [ "$arg1" == "s" ];then
    arg1='shell'
    python manage.py shell
    exit



elif [ -z "$arg1" ];then
    arg1='runserver'
    arg2='0.0.0.0:'$port
#elif [ -z "$arg2" ];then
#    arg2='0.0.0.0:'${arg1}
#    arg1='runserver'

elif [ "$arg1" == "stop" ];then
    run $arg1 $2
    exit
elif [ "$arg1" == "start" ];then
    run $arg1
    exit
elif [ "$arg1" == "state" ];then
    run $arg1
    exit
elif [ "$arg1" == "restart" ];then
    run "stop"
    sleep 1
    run "start"
    exit


fi











#echo $arg1
#echo $arg2


python -u manage.py $arg1 $arg2 $3 $4


#c/daphne -b 0.0.0.0 -p $port --ws-protocol "graphql-ws" --proxy-headers sdj.asgi:channel_layer





