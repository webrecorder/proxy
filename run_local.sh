webagg-server --live -p 8080 &
mitmdump -p 8081 --no-upstream-cert --no-http2 -s "./run.py --host http://localhost:8080 --magic-fwd http://webrecorder.io/ --fixed /live/resource{postreq}?url={url}&closest=now"
pkill -P $$
