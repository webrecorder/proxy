import redis


class FixedUrlResolver(object):
    def __init__(self, host, upstream_url):
        self.upstream_url = host + upstream_url
        print(self.upstream_url)

    def __call__(self, url, headers, address, postreq):
        full_url = self.upstream_url.format(url=url,
                                            postreq=postreq)

        return full_url, None


class RedisIPCacheResolver(object):
    def __init__(self, host, redis_url):
        self.host = host
        self.redis_url = redis_url
        self.redis = redis.StrictRedis.from_url(redis_url, decode_responses=True)

    def __call__(self, url, headers, address, postreq):
        ip = address.host
        browser_data = self.redis.hgetall('ip:' + ip)

        full_url = browser_data.get('upstream_url', '').format(url=url, postreq=postreq)
        if browser_data:
            browser_data['proxy_ip'] = ip

        return full_url, browser_data


