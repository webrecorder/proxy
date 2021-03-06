from mitmproxy.net.http import Headers
from mitmproxy.net.http.http1.assemble import assemble_request
from mitmproxy.net.http.url import parse, hostport

from warcio.recordloader import ArcWarcRecordLoader
from warcio.timeutils import http_date_to_timestamp
from warcio.statusandheaders import StatusAndHeaders

from pywb.cdx.cdxobject import CDXObject
from pywb.utils.canonicalize import canonicalize

from pywb.urlrewrite.rewriterapp import Rewriter
from pywb.rewrite.wburl import WbUrl
from pywb.rewrite.url_rewriter import UrlRewriter, SchemeOnlyUrlRewriter

from pywb.urlrewrite.templateview import JinjaEnv, HeadInsertView, BaseInsertView
from pywb.webagg.utils import chunk_encode_iter, buffer_iter

from werkzeug.contrib.iterio import IterIO

from six.moves.urllib.parse import quote, quote_plus

from io import BytesIO

import re
import mitmproxy.net.check
from mitmproxy.http import HTTPResponse

mitmproxy.net.check._label_valid = re.compile(b"(?!-)[A-Z\d_-]{1,63}(?<!-)$", re.IGNORECASE)


H_REFRESH_PATH = '/_homepage'
H_REDIR_PATH = '/_home_redir'


#==============================================================================
class DirectUpstream(object):
    def __init__(self, upstream_url_resolver,
                 proxy_magic='pywb.proxy',
                 magic_fwd='http://localhost/',
                 assets_path=None,
                 is_rw=True):

        self.upstream_url_resolver = upstream_url_resolver
        self.loader = ArcWarcRecordLoader()

        self.proxy_magic = proxy_magic
        self.fwd_scheme, self.fwd_host, self.fwd_port, self.fwd_path = parse(magic_fwd)

        self.fwd_scheme = self.fwd_scheme.decode('latin-1')
        self.fwd_host = self.fwd_host.decode('latin-1')
        self.fwd_path = self.fwd_path.decode('latin-1')

        self.jinja_env = JinjaEnv(assets_path=assets_path)
        self.head_insert_view = HeadInsertView(self.jinja_env, 'head_insert.html', 'banner.html')
        self.error_view = BaseInsertView(self.jinja_env, 'error.html')
        self.home_redir_view = BaseInsertView(self.jinja_env, 'home.html')

        if is_rw:
            self.content_rewriter = Rewriter(is_framed_replay=False)
        else:
            self.content_rewriter = None

    def request(self, flow):
        self._set_request_url(flow)

    def _set_request_url(self, flow, postreq=''):
        host = flow.request.headers.get('host')
        if not host:
            host = flow.request.host

        homepage_redirect = None

        if (host == self.proxy_magic and
            (flow.request.path in (H_REFRESH_PATH, H_REDIR_PATH))):
            homepage_redirect = flow.request.path

        elif host == self.proxy_magic:
            flow.request.host = self.fwd_host
            flow.request.scheme = self.fwd_scheme
            flow.request.port = self.fwd_port
            flow.request.headers['X-Proxy-For'] = str(flow.client_conn.address.host)
            return False

        if host:
            host = flow.request.scheme + '://' + host
        else:
            host = hostport(flow.request.scheme, flow.request.host, flow.request.port)

        req_url = host + flow.request.path

        flow.request.req_url = req_url
        flow.request.req_scheme = flow.request.scheme

        result = self.upstream_url_resolver(url=quote_plus(req_url),
                                            headers=flow.request.headers,
                                            address=flow.client_conn.address,
                                            postreq=postreq)

        full_url, extra_data = result

        if homepage_redirect:
            url = extra_data.get('url')
            if url:
                if homepage_redirect == H_REFRESH_PATH:
                    self.homepage_refresh(flow, url)
                elif homepage_redirect == H_REDIR_PATH:
                    self.homepage_redir(flow, url)

                return False

        scheme, host, port, path = parse(full_url)

        flow.request.scheme = scheme
        flow.request.host = host
        flow.request.port = port
        flow.request.path = path

        flow.extra_data = extra_data
        return True

    def responseheaders(self, flow):
        if flow.request.host == self.fwd_host:
            return

        if hasattr(flow, 'direct_response'):
            return

        if flow.response.status_code == 200:
            flow.response.stream = True

    def response(self, flow):
        if flow.request.host == self.fwd_host:
            return

        if hasattr(flow, 'direct_response'):
            return

        if flow.response.status_code != 200:
            url = flow.request.req_url
            err_status = 400
            err_msg = 'Proxy Error'
            if flow.response.status_code == 404:
                err_status = 404
                err_msg = 'Not Found'

            self.send_error(flow, url, err_status, err_msg)
            return

        an_iter = flow.live.read_response_body(flow.request, flow.response)
        stream = IterIO(an_iter)

        try:
            self._set_response(flow, stream)
        except Exception as e:
            if hasattr(flow.request, 'req_url'):
                print(flow.request.req_url)
            print(type(e), e)
            import traceback
            traceback.print_exc()

    def homepage_redir(self, flow, redir_url):
        flow.request.host = self.fwd_host
        flow.response = HTTPResponse.make(303, b'', {'Location': redir_url})
        return True

    def homepage_refresh(self, flow, url):
        flow.direct_response = True
        environ = {}
        environ['webrec.template_params'] = {'url': url}
        resp_data = self.home_redir_view.render_to_string(environ).encode('utf-8')
        flow.response = HTTPResponse.make(200, resp_data, {'Content-Type': 'text/html; charset=utf-8'})
        return True

    def send_error(self, flow, url, status, reason):
        template_params = {}
        if hasattr(flow, 'extra_data') and flow.extra_data:
            template_params = flow.extra_data

        template_params['url'] = url

        template_params['cdx'] = {'url': url}
        template_params['proxy_magic'] = self.proxy_magic

        host_prefix = flow.request.req_scheme + '://' + self.proxy_magic
        template_params['wbrequest'] = {'host_prefix': host_prefix}

        environ = {'pywb_proxy_magic': self.proxy_magic,
                   'webrec.template_params': template_params}

        msg = self.error_view.render_to_string(environ).encode('utf-8')

        flow.response.content = msg
        flow.response.status_code = status
        flow.response.reason = reason
        flow.response.headers = Headers()
        flow.response.headers['Content-Type'] = 'text/html; charset=utf-8'
        flow.response.headers['Content-Length'] = str(len(msg))

    def process_record(self, record, flow):
        headers = flow.response.headers
        url = flow.request.req_url
        scheme = flow.request.req_scheme

        if not self.content_rewriter:
            return record.http_headers, StreamIO(record.raw_stream)

        cookie_rewriter = None

        template_params = flow.extra_data

        environ = {'pywb_proxy_magic': self.proxy_magic,
                   'webrec.template_params': template_params}

        wb_url = WbUrl(url)
        wb_prefix = ''
        host_prefix = flow.request.req_scheme + '://' + self.proxy_magic
        urlrewriter = SchemeOnlyUrlRewriter(wb_url, '')

        if flow.request.headers.get('X-Requested-With', '').lower() == 'xmlhttprequest':
            urlrewriter.rewrite_opts['is_ajax'] = True

        head_insert_func = (self.head_insert_view.
                                create_insert_func(wb_url,
                                                   wb_prefix,
                                                   host_prefix,
                                                   url,
                                                   environ,
                                                   False))

        urlkey = canonicalize(wb_url.url)

        cdx = CDXObject()
        cdx['urlkey'] = urlkey
        cdx['timestamp'] = http_date_to_timestamp(headers.get('Memento-Datetime'))
        cdx['url'] = wb_url.url
        if headers.get('Webagg-Source-Coll') == 'live':
            cdx['is_live'] = 'true'

        result = self.content_rewriter.rewrite_content(urlrewriter,
                                               record.http_headers,
                                               record.raw_stream,
                                               head_insert_func,
                                               urlkey,
                                               cdx,
                                               cookie_rewriter,
                                               environ)

        status_headers, gen, is_rw = result

        status_headers.remove_header('Content-Security-Policy')

        # check for content-length
        res = status_headers.get_header('content-length')
        try:
            if int(res) > 0:
                return status_headers, IterIdent(gen)
        except:
            pass

        # need to either chunk or buffer to get content-length
        if flow.request.http_version == 'HTTP/1.1':
            status_headers.remove_header('content-length')
            status_headers.headers.append(('Transfer-Encoding', 'chunked'))
            #gen = chunk_encode_iter(gen)
        else:
            gen = buffer_iter(status_headers, gen)

        return status_headers, IterIdent(gen)

    def _set_response(self, flow, stream):
        record = self.loader.parse_record_stream(stream)

        status_headers, gen = self.process_record(record, flow)

        if status_headers:
            headers_bytes = [(n.encode('iso-8859-1'), v.encode('iso-8859-1')) for n, v in status_headers.headers]

            flow.response.headers = Headers(headers_bytes)

        protocol = status_headers.protocol
        status, reason = status_headers.statusline.split(' ', 1)

        flow.response.status_code = int(status)
        flow.response.reason = reason

        flow.response.stream = gen

    def serverconnect(self, server_conn):
        return

    def error(self, flow):
        if hasattr(flow.request, 'req_url'):
            url = flow.request.req_url
        else:
            url = ''

        print('ERROR', url)


#==============================================================================
class PostUpstream(DirectUpstream):
    POSTREQ_PATH = '/postreq'

    PASS_THROUGH = ['Connection', 'X-Requested-With']

    def request(self, flow):
        orig_req_data = assemble_request(flow.request)

        if not self._set_request_url(flow, self.POSTREQ_PATH):
            return

        headers = Headers()
        headers['Content-Length'] = str(len(orig_req_data))

        for n in self.PASS_THROUGH:
            val = flow.request.headers.get(n)
            if val is not None:
                headers[n] = val

        flow.request.method = 'POST'
        flow.request.headers = headers
        flow.request.content = orig_req_data


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
class IterIdent(object):
    def __init__(self, gen):
        self.gen = gen

    def __call__(self, _):
        for val in self.gen:
            yield val


