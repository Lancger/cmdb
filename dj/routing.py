# -*- coding: utf-8 -*-

from channels import route_class  # , route

from cmdb.consumers import Websocket, SshMonitor, DockerWebsocket

# The channel routing defines what channels get handled by what consumers,
# including optional matching on message attributes. In this example, we route
# all WebSocket connections to the class-based BindingConsumer (the consumer
# class itself specifies what channels it wants to consume)


# channel_routing.extend([
#     route_class(webterminal,path = r'^/ws'),
#     # route_class(CommandExecute,path= r'^/execute'),
# ])


channel_routing = [
    route_class(Websocket, path=r'^/webssh'),
    route_class(SshMonitor, path=r'^/monitor/(?P<channel>.*)'),
    route_class(DockerWebsocket, path=r'^/docker/webssh'),
    # route_class(CommandExecute,path= r'^/execute')
]
