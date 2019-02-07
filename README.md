# cmdb
项目本来是叫webssh，去年那时只从CMDB中提取webssh功能，这次加了些功能后就干脆叫cmdb算了。

* 特色:

        基于django、python2.7开发。
        1. webssh终端，该有功能基本都有，websocker基于django的channels模块，和http在同一监听端口，减少模块依赖安装
        2. websftp文件操作，基于elfinder
        3. SSH堡垒机，支持从网页跳转到Xshell，需文件操作时可以从Xshell启动Xftp进行
        4. docker管理，支持跨宿主机管理容器，支持创建二层容器网络（二层桥接和macvlan，相当使容器网卡和所属宿主机网卡接在同一交换机上，而不跨路由/NAT），
        前提需对宿主机网卡进行设置，详情帮助见 根目录\c\help\docker\docker二层网络.txt

* 环境：

        centos6/7
        python2.7

* 搭建：

        一. 容器部署方式（推荐）
        拉取镜像，docker pull py2010/cmdb
        启动容器，docker run -p 8088:8088 py2010/cmdb
        二、如果不使用容器布署，准备centos6或7（估计unbuntu也行，没实际布署测试过），python2.7安装requirements.txt中的模块，安装redis或使用内存做为websocket跨进程通信
        
        容器或centos系统布署好了后， 访问网页，http://ip:8088，用户名/密码：admin/admin@2019
