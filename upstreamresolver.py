import redis


class FixedUrlResolver(object):
    def __init__(self, host, upstream_url):
        self.upstream_url = host + upstream_url
        print(self.upstream_url)

    def __call__(self, url, headers, address, postreq):
        full_url = self.upstream_url.format(url=url,
                                            postreq=postreq)

        return full_url


class RedisIPCacheResolver(object):
    def __init__(self, host, redis_url):
        self.host = host
        self.redis_url = redis_url
        self.redis = redis.StrictRedis.from_url(redis_url)

    def __call__(self, url, headers, address, postreq):
        ip = address.host
        upstream_url = self.redis.hget('ip:' + ip, 'upstream_url')

        full_url = upstream_url.format(url=url, postreq=postreq)

        return full_url


