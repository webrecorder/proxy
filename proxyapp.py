from libmproxy import controller, proxy
from libmproxy.proxy.server import ProxyServer
from libmproxy.models import HTTPResponse

from netlib.http import Headers
from netlib.http.http1.assemble import assemble_request
from netlib.utils import parse_url

from pywb.warc.recordloader import ArcWarcRecordLoader

from werkzeug.contrib.iterio import IterIO

from six.moves.urllib.parse import quote

from io import BytesIO

import traceback


#==============================================================================
class DirectUpstreamController(controller.Master):
    def __init__(self, server, upstream_url):
        super(DirectUpstreamController, self).__init__(server)
        self.upstream_url = upstream_url
        self.loader = ArcWarcRecordLoader()

    def handle_request(self, flow):
        self._set_request_url(flow)
        flow.reply()

    def _set_request_url(self, flow, postreq=''):
        req_url = flow.request.scheme + '://' + flow.request.host + flow.request.path

        req_url = quote(req_url)

        full_url = self.upstream_url.format(postreq=postreq, url=req_url, closest='now')

        scheme, host, port, path = parse_url(full_url)

        flow.request.scheme = scheme
        flow.request.host = host
        flow.request.port = port
        flow.request.path = path

        flow.request.req_url = req_url

    def handle_responseheaders(self, flow):
        flow.response.stream = True
        flow.reply()
        return flow

    def handle_response(self, flow):
        an_iter = flow.live.read_response_body(flow.request, flow.response)
        stream = IterIO(an_iter)

        #buff = stream.read()
        #stream = BytesIO(buff)
        #stream.seek(0)

        #print('RESPOND', flow.request.req_url)

        try:
            self._set_response(stream, flow.response)
        except Exception as e:
            print(flow.request.req_url)
            print(type(e))
            #traceback.print_exc()

        flow.reply()

    def _set_response(self, stream, response):
        record = self.loader.parse_record_stream(stream)

        response.headers = Headers(record.status_headers.headers)

        protocol = record.status_headers.protocol
        status, reason = record.status_headers.statusline.split(' ', 1)

        response.status_code = int(status)
        response.reason = reason

        response.stream = StreamIO(record.stream)

    def run(self):
        try:
            return controller.Master.run(self)
        except KeyboardInterrupt:
            self.shutdown()


#==============================================================================
class PostUpstreamController(DirectUpstreamController):
    POSTREQ_PATH = '/postreq'

    def handle_request(self, flow):
        orig_req_data = assemble_request(flow.request)

        self._set_request_url(flow, self.POSTREQ_PATH)

        headers = Headers()
        headers['Content-Length'] = str(len(orig_req_data))
        headers['Connection'] = flow.request.headers['Connection']

        flow.request.method = 'POST'
        flow.request.headers = headers
        flow.request.content = orig_req_data

        #print(flow.client_conn.address)
        flow.reply()


#==============================================================================
class StreamIO(object):
    BUFF_SIZE = 8192

    def __init__(self, thereader=None):
        self.thereader = thereader

    def __call__(self, chunks):
        while True:
            buff = self.thereader.read(self.BUFF_SIZE)
            if not buff:
                break

            yield buff


#==============================================================================
if __name__ == "__main__":
    config = proxy.ProxyConfig(port=9080)
    server = ProxyServer(config)
    upstream_url = 'http://localhost:8080/live/resource{postreq}?url={url}&closest={closest}'
    m = PostUpstreamController(server, upstream_url)
    m.run()


