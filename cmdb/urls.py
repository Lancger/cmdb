# coding=utf-8
#

from django.conf.urls import url

from host import *  # host, a10, 终端

from views import *  # es, user, oss

from dk import *

urlpatterns = [

    url(r'^host/add', host_add, name="host_add"),
    url(r'^host/del', host_del, name="host_del"),
    url(r'^host/alldel', host_alldel, name="host_alldel"),
    url(r'^host/(?P<id>\d+)/$', host_edit, name="host_edit"),
    # url(r'^group',  Group.as_view(), name="group"),
    url(r'^host_group', host_group_edit, name="host_group_edit"),
    url(r'^host', host, name="host"),
    # url(r'^(host)',  asset, name="host"),


    url(r'^clissh/(?P<hostid>\d+)', CliSSH.as_view(), name="clissh"),  # 生成临时账号密码供跳转xshell访问
    url(r'^webssh', WebSSH.as_view(), name="webssh"),
    url(r'^cmdrun', CmdRun.as_view(), name="cmdrun"),
    # url(r'^sshreplay/(?P<pk>\d+)/', SshReplay.as_view(), name='ssh_replay'),
    url(r'^sshlog', SshLogList.as_view(), name='sshlog'),
    url(r'^sshmonitor/(?P<channel>.*)', SshMonitor.as_view(), name='sshmonitor'),


    url(r'^es/(?P<pk>\d+)/indices/$', ESIndices.as_view(), name="es_indices"),
    url(r'^es/(?P<pk>\d+)/(?P<do>\w+)/(?P<index>\S+)/$', do_indices, name="do_indices"),
    url(r'^es/(?P<pk>\d+)/$', ESView.as_view(), name="es"),
    url(r'^es', ESList.as_view(), name="eslist"),


    url(r'^usergroup/(?P<pk>\d+)/$', UserGroupEdit.as_view(), name="usergroup_edit"),
    url(r'^user/(?P<pk>\d+)/$', UserEdit.as_view(), name="user_edit"),
    url(r'^user', UserList.as_view(), name="user"),


    url(r'^docker/info/(?P<pk>\d+)/', info, name="dockerinfo"),
    url(r'^docker/image/(?P<pk>\d+)/do/', image_do, name="docker_image_do"),
    url(r'^docker/image/(?P<pk>\d+)/rm/', image_rm, name="docker_image_rm"),
    url(r'^docker/image/(?P<pk>\d+)/', image, name="docker_image"),
    url(r'^docker/image/', image, name="docker_image"),

    url(r'^docker/container/(?P<pk>\d+)/do/', container_do, name="docker_container_do"),
    url(r'^docker/container/(?P<pk>\d+)/rm/', container_rm, name="docker_container_rm"),
    url(r'^docker/container/(?P<pk>\d+)/add/', container_add, name="docker_container_add"),
    url(r'^docker/container/(?P<pk>\d+)/', container, name="docker_container"),
    url(r'^docker/container/', container, name="docker_container"),

    url(r'^docker/net/(?P<pk>\d+)/do/', net_do, name="docker_net_do"),
    url(r'^docker/net/(?P<pk>\d+)/rm/', net_rm, name="docker_net_rm"),
    url(r'^docker/net/(?P<pk>\d+)/add/', net_add, name="docker_net_add"),
    url(r'^docker/net/(?P<pk>\d+)/', net, name="docker_net"),
    url(r'^docker/net/', net, name="docker_net"),

    url(r'^docker/host/', DockerHostList.as_view(), name="docker_host_list"),

    url(r'^docker/yml/(?P<pk>\d+)/$', DockerYmlEdit.as_view(), name="docker_yml_edit"),
    url(r'^docker/yml/add', DockerYmlAdd.as_view(), name="docker_yml_add"),
    url(r'^docker/yml/', DockerYmlList.as_view(), name="docker_yml_list"),
    url(r'^docker/compose/(?P<ids>.*)/del/', docker_compose_del, name="docker_compose_del"),
    url(r'^docker/compose/(?P<pk>\d+)/do/', DockerComposeDo.as_view(), name="docker_compose_do"),
    url(r'^docker/compose/(?P<pk>\d+)/$', DockerComposeEdit.as_view(), name="docker_compose_edit"),
    url(r'^docker/compose/add', DockerComposeAdd.as_view(), name="docker_compose_add"),
    url(r'^docker/compose/', DockerComposeList.as_view(), name="docker_compose_list"),


    url(r'^docker/imagefile/(?P<ids>.*)/del/', docker_imagefile_del, name="docker_imagefile_del"),
    url(r'^docker/imagefile/(?P<ids>.*)/load/(?P<hostid>\d+)', DockerImageFileLoad.as_view(), name="docker_imagefile_load"),
    url(r'^docker/imagefile/upload/$', DockerComposeUpload.as_view(), name="docker_imagefile_upload"),
    url(r'^docker/imagefile/$', DockerImageFileList.as_view(), name="docker_imagefile_list"),
    url(r'^docker/webssh', DockerWebSSH.as_view(), name="docker_webssh"),

]
