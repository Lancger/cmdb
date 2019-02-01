# coding=utf-8
from django import template
register = template.Library()


@register.simple_tag(takes_context=True)
def menu_prem(context, *args, **kwargs):
    # 判断用户是否有model的权限，用于网页左边栏动态显示菜单
    pass
    user = context['user']

    prem = {
        'view_host': user.has_perm('cmdb.view_host'),

        'view_user': user.has_perm('auth.view_user'),
        'view_group': user.has_perm('auth.view_group'),


        'ssh_host': user.has_perm('cmdb.ssh_host'),  # 终端
        'webssh_log': user.has_perm('cmdb.replay_ssh_log'),  # 终端日志
        'deploy_host': user.has_perm('cmdb.deploy_host'),  # APP部署
        'grep_host': user.has_perm('cmdb.grep_host'),  # grep日志
        'run_sh_host': user.has_perm('cmdb.run_sh_host'),  # 常用脚本
        'run_cmd_host': user.has_perm('cmdb.run_cmd_host'),  # 自定义命令
        'other_do_host': user.has_perm('cmdb.other_do_host'),  # 其它操作



        'view_admin': user.is_staff,
        'view_sshuser': user.has_perm('cmdb.view_sshuser'),


        'view_docker': user.has_perm('cmdb.view_docker'),  # Docker管理（主菜单）
        'images_manage': user.has_perm('cmdb.images_manage'),  # 镜像管理
        'containers_manage': user.has_perm('cmdb.containers_manage'),  # 容器管理
        'net_manage': user.has_perm('cmdb.net_manage'),  # 容器网络
        'view_dockercompose': user.has_perm('cmdb.view_dockercompose'),  # 容器编排

    }
    if user.is_superuser:
        prem['view_oss'] = True

    # print prem
    return prem
