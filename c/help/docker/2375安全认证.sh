

#docker 2375端口默认不进行客户端安全验证，远程客户端连入2375后都可管理docker，不安全。
#服务端配置TSL证书后，只允许证书一致的客户端才能访问。



cd ~/.docker

#1.CA
openssl genrsa -out ca-key.pem 4096
openssl req -x509 -sha256 -batch -subj '/CN=sdj' -new -days 9999 -key ca-key.pem -out ca.pem



#2.用CA生成证书
openssl genrsa -out key.pem 4096
openssl req -subj '/CN=Docker' -sha256 -new -key key.pem -out csr.pem

#只允许*.docker.sdj域名
echo subjectAltName = DNS:*.docker.sdj,IP:127.0.0.1 > allow.list
openssl x509 -req -days 365 -sha256 -in csr.pem -CA ca.pem -CAkey ca-key.pem -CAcreateserial -out cert.pem -extfile allow.list

#3.
rm -rf allow.list ca.srl ca-key.pem csr.pem
chmod 400 *.pem




#服务端

vi /usr/lib/systemd/system/docker.service

docker daemon -H=0.0.0.0:2375    --tlsverify --tlscacert=/root/.docker/ca.pem --tlscert=/root/.docker/cert.pem --tlskey=/root/.docker/key.pem

或
vi /etc/docker/daemon.json
{
    "hosts": ["tcp://0.0.0.0:2375", "unix://var/run/docker.sock"],
    "tls": true,
    "tlscacert": "/etc/docker/ca.pem",
    "tlscert": "/etc/docker/cert.pem",
    "tlskey": "/etc/docker/key.pem"
}


systemctl restart docker


#客户端

docker -H=tcp://127.0.0.1:2375 --tlsverify --tlscacert=/root/.docker/ca.pem --tlscert=/root/.docker/cert.pem --tlskey=/root/.docker/key.pem info


#证书在客户端默认目录~/.docker、默认文件名时可不提供
docker -H=tcp://1.docker.sdj:2375 --tlsverify info

或
export DOCKER_HOST=tcp://1.docker.sdj:2375 DOCKER_TLS_VERIFY=1
echo $DOCKER_HOST
docker info
