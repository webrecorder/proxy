FROM mitmproxy/releases:0.16

WORKDIR /code/

ADD requirements.txt /code/requirements.txt
RUN pip install -r requirements.txt

ADD *.py /code/

CMD mitmdump -p 8080 --client-certs /certs/ --no-http2 -s "/code/run.py --host $WEBAGG --fixed /live/resource{postreq}?url={url}&closest=now"

