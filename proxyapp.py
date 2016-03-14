from netlib.http import Headers
from netlib.http.http1.assemble import assemble_request
from netlib.utils import parse_url

from pywb.warc.recordloader import ArcWarcRecordLoader

from werkzeug.contrib.iterio import IterIO

from six.moves.urllib.parse import quote

from io import BytesIO

import re
import netlib.utils

netlib.utils._label_valid = re.compile(b"(?!-)[A-Z\d_-]{1,63}(?<!-)$", re.IGNORECASE)


#==============================================================================
class DirectUpstream(object):
    def __init__(self, upstream_url, default_coll):
        self.upstream_url = upstream_url
        self.loader = ArcWarcRecordLoader()
        self.default_coll = default_coll

    def request(self, flow):
        flow.request.req_url = None
        self._set_request_url(flow)

    def _set_request_url(self, flow, postreq=''):
        req_url = flow.request.scheme + '://' + flow.request.host + flow.request.path
        req_url = quote(req_url)

        full_url = self.upstream_url.format(coll=self.default_coll,
                                            postreq=postreq,
                                            url=req_url,
                                            closest='now')
        print(full_url)

        scheme, host, port, path = parse_url(full_url)

        flow.request.scheme = scheme
        flow.request.host = host
        flow.request.port = port
        flow.request.path = path

        flow.request.req_url = req_url

    def responseheaders(self, flow):
        flow.response.stream = True

    def response(self, flow):
        an_iter = flow.live.read_response_body(flow.request, flow.response)
        stream = IterIO(an_iter)

        try:
            self._set_response(stream, flow.response)
        except Exception as e:
            if hasattr(flow.request, 'req_url'):
                print(flow.request.req_url)
            print(type(e))
            #traceback.print_exc()


    def _set_response(self, stream, response):
        record = self.loader.parse_record_stream(stream)

        response.headers = Headers(record.status_headers.headers)

        protocol = record.status_headers.protocol
        status, reason = record.status_headers.statusline.split(' ', 1)

        response.status_code = int(status)
        response.reason = reason

        response.stream = StreamIO(record.stream)


#==============================================================================
class PostUpstream(DirectUpstream):
    POSTREQ_PATH = '/postreq'

    PASS_THROUGH = ['Connection']

    def request(self, flow):
        orig_req_data = assemble_request(flow.request)

        self._set_request_url(flow, self.POSTREQ_PATH)

        headers = Headers()
        headers['Content-Length'] = str(len(orig_req_data))

        for n in self.PASS_THROUGH:
            val = flow.request.headers.get(n)
            if val is not None:
                headers[n] = val

        flow.request.method = 'POST'
        flow.request.headers = headers
        flow.request.content = orig_req_data
        #print(flow.client_conn.address)


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
