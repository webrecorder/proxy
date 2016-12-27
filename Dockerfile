FROM webrecorder/pywb

WORKDIR /code/

USER root
RUN pip install 'mitmproxy>=1.0.1'

USER archivist


ADD *.py /code/
ADD banner.html /code/banner.html
ADD error.html /code/error.html
ADD home.html /code/home.html

CMD mitmdump -p 8080 --no-upstream-cert --no-http2 -s "/code/run.py --host $WEBAGG --magic-fwd $NGINX --fixed /live/resource{postreq}?url={url}&closest=now"

