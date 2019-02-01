# coding=utf-8
from django import forms
# from django.forms import ModelForm
from cmdb.models import Host, SshUser, DockerYml, DockerCompose
from django.forms.widgets import CheckboxSelectMultiple

# from django.contrib.auth.models import User, Group


class HostForm(forms.ModelForm):
    # 前端主机添加页面

    class Meta:
        model = Host
        fields = '__all__'
        # exclude = ("asset_type",)

        widgets = {
            'user': CheckboxSelectMultiple,
            'usergroup': CheckboxSelectMultiple,
        }

        # error_messages = {
        #     'model':{
        #         'max_length': ('太短了'),
        #     }
        # }

        # help_texts = {
        #     'user': u'哪些登陆用户能对当前主机进行操作，超级用户直接有操作权限'
        # }

    # model_field = Meta.model._meta.get_field('user')
    # user = forms.ModelMultipleChoiceField(widget=CheckboxSelectMultiple, queryset=User.objects.filter(is_superuser=False), label=model_field.verbose_name, required=False, help_text=model_field.help_text)


class HostForm2(HostForm):
    # 前端主机编辑页面去除 主机类型 字段

    class Meta(HostForm.Meta):
        exclude = ('asset_type', )


class SshUserForm(forms.ModelForm):
    # password = forms.CharFie()ld(label=u"密码", widget=forms.PasswordInput, required=False)

    class Meta:
        model = SshUser
        fields = '__all__'
        # exclude = ("id",)

        widgets = {
            'password': forms.PasswordInput(),
        }

        labels = {

        }

        help_texts = {
        }
        error_messages = {

        }


class ContainerAddForm(forms.Form):
    name = forms.CharField(label=u'名称', max_length=100, min_length=2, required=True)
    image = forms.CharField(label=u'镜像', max_length=200, required=True)
    network = forms.CharField(label=u'网络', max_length=100, required=True)
    ip = forms.GenericIPAddressField(label=u'IP', required=False)
    ports = forms.CharField(label=u'端口', required=False)
    volumes = forms.CharField(label=u'挂载', required=False)
    command = forms.CharField(label=u'命令', required=False)
    start = forms.CharField(label=u'启动', required=False)
    tty = forms.CharField(label=u'伪终端', required=False)
    stdin = forms.CharField(label=u'输入交互', required=False)

    def clean_volumes(self):
        # 宿目录:容器目录:ro,宿目录:容器目录,容器目录
        volumes = self.cleaned_data.get('volumes', '')
        vs = [volume.strip() for volume in volumes.split(',') if volume.strip()]
        for v in vs:
            # 检查挂载目录设置是是否正确
            paths = v.split(':')
            if len(paths) > 1:
                path = paths[1]
            else:
                path = paths[0]
            if not path.startswith('/'):
                raise forms.ValidationError("容器目录(%s)必需为绝对路径" % path)
        return volumes


class NetAddForm(forms.Form):
    # 添加容器网络
    name = forms.CharField(label=u'名称', max_length=200, min_length=2, required=True)
    driver = forms.CharField(label=u'网络类型', max_length=100, required=True)
    interface = forms.CharField(label=u'接口', max_length=100, required=True)
    ip = forms.GenericIPAddressField(label=u'接口IP', required=False, protocol='IPv4')
    subnet = forms.CharField(label=u'容器网段', required=True)
    gateway = forms.GenericIPAddressField(label=u'容器网关', required=True, protocol='IPv4')

    def clean(self):
        # 检查网段
        subnet = self.cleaned_data.get('subnet', '')
        gateway = self.cleaned_data.get('gateway', '')
        import IPy
        try:
            if gateway in IPy.IP(subnet):
                error = ''
            else:
                error = '网关不属于所填的网段中'
        except:
            error = '网段填写错误'
            # import ipdb; ipdb.set_trace()
        if error:
            raise forms.ValidationError(error)


class DockerYmlForm(forms.ModelForm):

    class Meta:
        model = DockerYml
        fields = '__all__'


class DockerComposeForm(forms.ModelForm):

    class Meta:
        model = DockerCompose
        fields = '__all__'
