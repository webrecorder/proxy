from proxyapp import PostUpstream
from argparse import ArgumentParser

from upstreamresolver import FixedUrlResolver, RedisIPCacheResolver

handler = None

def start(context, argv):
    global handler

    parser = ArgumentParser()
    parser.add_argument('--host')
    parser.add_argument('--fixed', help='Single Url Resolver')
    parser.add_argument('--redis', help='Redis IP Cache Resolver')

    r = parser.parse_args(argv[1:])

    host = r.host
    if r.fixed:
        resolver = FixedUrlResolver(host, r.fixed)

    elif r.redis:
        resolver = RedisIPCacheResolver(host, r.redis)

    handler = PostUpstream(resolver)

def request(conext, flow):
    handler.request(flow)

def responseheaders(context, flow):
    handler.responseheaders(flow)

def response(context, flow):
    handler.response(flow)

