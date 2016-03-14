FROM mitmproxy/releases:0.16

WORKDIR /code/

ADD requirements.txt /code/requirements.txt
RUN pip install -r requirements.txt

ADD proxyapp.py /code/proxyapp.py
ADD run.py /code/run.py

CMD mitmdump -p 9080 --client-certs /certs/ --no-http2 -s "/code/run.py $WEBAGG live"

