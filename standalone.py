from libmproxy import controller, proxy
from libmproxy.proxy.server import ProxyServer

from proxyapp import PostUpstream

#==============================================================================
class PostUpstreamController(PostUpstream, controller.Master):
    def __init__(self, server, upstream_url):
        controller.Master.__init__(self, server)
        PostUpstream.__init__(self, upstream_url)

    def run(self):
        try:
            return super(PostUpstreamController, self).run()
        except KeyboardInterrupt:
            self.shutdown()

    def handle_request(self, flow):
        self.request(flow)
        flow.reply()

    def handle_responseheaders(self, flow):
        self.responseheaders(flow)
        flow.reply()

    def handle_response(self, flow):
        self.handle_response(flow)
        flow.reply()



#==============================================================================
if __name__ == "__main__":
    config = proxy.ProxyConfig(port=9080)
    server = ProxyServer(config)
    upstream_url = 'http://webrecplatform_webagg_1:8080/live/resource{postreq}?url={url}&closest={closest}'
 #   upstream_url = upstream_url.replace('webrecplatform_webagg_1', 'localhost')
    m = PostUpstreamController(server, upstream_url)
    m.run()


