from proxyapp import PostUpstream

handler = None

def start(context, argv):
    if len(argv) < 3:
        raise ValueError('Usage: <upstream> <default_coll>')

    url = argv[1] + '/{coll}/resource{postreq}?url={url}&closest={closest}'

    print(url)

    global handler
    handler = PostUpstream(url, argv[2])

def request(conext, flow):
    handler.request(flow)

def responseheaders(context, flow):
    handler.responseheaders(flow)

def response(context, flow):
    handler.response(flow)

