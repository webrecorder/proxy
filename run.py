from proxyapp import PostUpstream
from argparse import ArgumentParser

from upstreamresolver import FixedUrlResolver, RedisIPCacheResolver
import sys

handler = None

def start():
    global handler

    argv = sys.argv

    parser = ArgumentParser()
    parser.add_argument('--host')
    parser.add_argument('--no-rw', dest='is_rw', action='store_false', default=True)
    parser.add_argument('--magic-fwd', help='Forward magic host to target host')
    parser.add_argument('--fixed', help='Single Url Resolver')
    parser.add_argument('--redis', help='Redis IP Cache Resolver')

    r = parser.parse_args(argv[1:])

    host = r.host
    if r.fixed:
        resolver = FixedUrlResolver(host, r.fixed)

    elif r.redis:
        resolver = RedisIPCacheResolver(host, r.redis)

    handler = PostUpstream(resolver, is_rw=r.is_rw, magic_fwd=r.magic_fwd)

def serverconnect(server_conn):
    handler.serverconnect(server_conn)

def request(flow):
    handler.request(flow)

def responseheaders(flow):
    handler.responseheaders(flow)

def response(flow):
    handler.response(flow)

def error(flow):
    handler.error(flow)

