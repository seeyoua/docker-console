import os
import json
from docker import APIClient
import tornado.ioloop
import tornado.httpserver
import tornado.web
import tornado.tcpclient
from tornado.web import RequestHandler
from tornado.gen import coroutine
from tornado.options import define, options
from tornado.websocket import WebSocketHandler
import tornado.httpclient

host = '192.168.210.38'
port = 2375
container = 'a2f7aa0b819d'
define('port', default=8000, type=int)


class IndexHandler(RequestHandler):
    def get(self):
        return self.render('index.html')


class DockerConsole(WebSocketHandler):

    @coroutine
    def open(self):
        print('websocket opended')
        http_client = tornado.httpclient.AsyncHTTPClient()
        res = yield http_client.fetch(
            'http://{host}:{port}/containers/{container}/exec'.format(host=host, port=port, container=container),
            method='POST',
            headers={
                'Content-Type': 'application/json',
            },
            body=json.dumps({
                'AttachStdin': True,
                'AttachStdout': True,
                'AttachStderr': True,
                'DetachKeys': 'ctrl-p,ctrl-q',
                'Tty': True,
                'Cmd': [
                    '/bin/bash'
                ]
            })
        )
        data = res.body
        exec_id = json.loads(data)['Id']
        print(exec_id)
        tcp_client = tornado.tcpclient.TCPClient()
        docker_socket = yield tcp_client.connect(host, port)
        data = json.dumps({
            'Detach': False,
            'Tty': True
        })
        yield docker_socket.write(bytes('POST /exec/{}/start HTTP/1.1\r\n'.format(exec_id), encoding='utf-8'))
        yield docker_socket.write(bytes('Host: 192.168.210.28:2375\r\n', encoding='utf-8'))
        yield docker_socket.write(bytes('Connection: Upgrade\r\n', encoding='utf-8'))
        yield docker_socket.write(bytes('Content-Type: application/json\r\n', encoding='utf-8'))
        yield docker_socket.write(bytes('Upgrade: tcp\r\n', encoding='utf-8'))
        yield docker_socket.write(bytes('Content-Length: {}\r\n'.format(len(data)), encoding='utf-8'))
        yield docker_socket.write(bytes("\r\n", encoding='utf-8'))
        yield docker_socket.write(bytes(data, encoding='utf-8'))
        res = yield docker_socket.read_until(bytes('\r\n\r\n', encoding='utf-8'))
        self.socket = docker_socket

        @tornado.gen.coroutine
        def test():
            while True:
                print(1234)
                try:
                    data = yield docker_socket.read_bytes(1024, partial=True)
                    self.write_message(data)
                except tornado.iostream.StreamClosedError:
                    self.close()
                    break
        test()

    @tornado.gen.coroutine
    def on_message(self, message):
        try:
            print(message)
            yield self.socket.write(message.encode('utf-8'))
        except tornado.iostream.StreamClosedError:
            self.write_message('Terminal has disconnected.')
            self.close()

    def on_close(self):
        try:
            # 这里可能有暗坑，比如进入 vim 后，页面被关闭（WebSocket 关闭）
            # 如果发送 exit 到容器里的话，是没法退出的
            self.socket.write('\nexit\n')  # exit bash when ws close
            self.socket.close()
        except tornado.iostream.StreamClosedError:
            pass
        print("close")

    def check_origin(self, origin):
        return True


if __name__ == '__main__':
    tornado.options.parse_command_line()
    app = tornado.web.Application(
        [
            (r'/', IndexHandler),
            (r'/console', DockerConsole),
        ],
        static_path=os.path.join(os.path.dirname(__file__), "static"),
        template_path=os.path.join(os.path.dirname(__file__), "templates"),
        autoreload=True
    )
    http_server = tornado.httpserver.HTTPServer(app)
    http_server.listen(options.port)
    tornado.ioloop.IOLoop.current().start()




