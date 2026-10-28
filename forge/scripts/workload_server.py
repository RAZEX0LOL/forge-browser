# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. https://mozilla.org/MPL/2.0/
"""Deterministic local interactive workload; no third-party resources or user data."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

PAGE = b'''<!doctype html><html lang="ru"><meta charset="utf-8"><title>Forge workload</title>
<style>body{font:16px system-ui;max-width:1000px;margin:24px auto}li{display:flex;gap:12px;padding:4px;border-bottom:1px solid #ddd}canvas{border:1px solid}</style>
<h1>Local interactive workload</h1><label>Filter <input id="filter"></label><button id="update">Update</button>
<button id="frames">Frame lifecycle</button><output id="count"></output><ul id="items"></ul><canvas width="600" height="200"></canvas>
<script src="/workload.js"></script></html>'''
SCRIPT = b'''
const input=document.getElementById('filter'),items=document.getElementById('items');let rows=[];
function render(){const fragment=document.createDocumentFragment();for(const row of rows.filter(row=>row.name.includes(input.value))){
const li=document.createElement('li');li.textContent=row.name+' '+row.value;fragment.append(li);}items.replaceChildren(fragment);document.getElementById('count').textContent=items.children.length;}
input.addEventListener('input',render);
document.getElementById('update').onclick=async()=>{rows=await(await fetch('/api/items')).json();render();};
document.getElementById('frames').onclick=()=>{for(let i=0;i<40;i++){const frame=document.createElement('iframe');frame.srcdoc='<title>Frame fixture</title><p>detached</p>';document.body.append(frame);frame.remove();}};
window.workloadReady=(async()=>{rows=await(await fetch('/api/items')).json();render();localStorage.setItem('forge-fixture','persistent');return true;})();
window.runWorkload=async()=>{await workloadReady;const start=performance.now();for(let i=0;i<8;i++){input.value=String(i);render();void items.offsetHeight;}
input.value='';render();const c=document.querySelector('canvas').getContext('2d');for(let i=0;i<2000;i++){c.fillStyle='hsl('+i+',60%,50%)';c.fillRect(i%600,i%200,8,8);}
history.pushState({fixture:true},'', '#updated');return {elapsedMs:performance.now()-start,rows:items.children.length,persistent:localStorage.getItem('forge-fixture')==='persistent'};};
'''


class WorkloadServer:
    def __enter__(self):
        owner = self
        self.requests = {}
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                path = self.path.split('?',1)[0]
                owner.requests[path] = owner.requests.get(path,0)+1
                if path in ('/', '/index.html'):
                    body, kind = PAGE, 'text/html; charset=utf-8'
                elif path == '/workload.js':
                    body, kind = SCRIPT, 'text/javascript'
                elif path == '/api/items':
                    body = json.dumps([{'name':f'Item-{i:04}','value':i*i} for i in range(1000)]).encode()
                    kind = 'application/json'
                else:
                    self.send_error(404);return
                self.send_response(200)
                self.send_header('Content-Type',kind)
                self.send_header('Cache-Control','no-store')
                self.send_header('Content-Length',str(len(body)))
                self.end_headers();self.wfile.write(body)
            def log_message(self,*args):
                pass
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.thread=Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.url=f'http://127.0.0.1:{self.server.server_port}/'
        return self

    def __exit__(self,*args):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=5)
