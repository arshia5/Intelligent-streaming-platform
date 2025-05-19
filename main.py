# ─────────────────────────────────────────────────────────────
# main.py (Entry point)
# ─────────────────────────────────────────────────────────────
from flask import Flask, render_template, Response, jsonify, request
from mqtt_handler import setup_mqtt
from stream_manager import start_stream, stop_stream, flags_stream, flags_detect, flags_heatmap, params, analytics, make_mjpeg_stream, initialize_shared_state

app = Flask(__name__, template_folder='templates')

setup_mqtt()
initialize_shared_state()

@app.route('/')
def index():
    return render_template('index2.html')

@app.route('/stream/<src>/start', methods=['POST'])
def api_start(src):
    data = request.get_json(silent=True) or {}
    ok   = start_stream(src,
                        data.get('resolution', params[src]['resolution']),
                        data.get('fps',        params[src]['fps']),
                        data.get('bitrate',    params[src]['bitrate']))
    return jsonify(source=src, status=('running' if ok else 'error'))

@app.route('/stream/<src>/stop', methods=['POST'])
def api_stop(src):
    stop_stream(src)
    return jsonify(source=src, status='stopped')

@app.route('/stream/<src>/detect_on',  methods=['POST'])
def api_detect_on(src):
    flags_detect[src] = True
    return jsonify(src=src, detect='on')

@app.route('/stream/<src>/detect_off', methods=['POST'])
def api_detect_off(src):
    flags_detect[src] = False
    return jsonify(src=src, detect='off')

@app.route('/stream/<src>/heat_on',  methods=['POST'])
def api_heat_on(src):
    flags_heatmap[src] = True
    return jsonify(src=src, heat='on')

@app.route('/stream/<src>/heat_off', methods=['POST'])
def api_heat_off(src):
    flags_heatmap[src] = False
    return jsonify(src=src, heat='off')

@app.route('/system/status')
def system_status():
    from stream_manager import lock
    with lock:
        status = {
            s: {
                'stream':  'running' if flags_stream[s] else 'stopped',
                'detect':  'on'      if flags_detect[s] else 'off',
                'heatmap': 'on'      if flags_heatmap[s] else 'off',
                **params[s]
            } for s in ('webcam','ipcam')
        }
        metrics = {}
        for s in ('webcam','ipcam'):
            ts    = analytics[s]['times']
            fps_a = len(ts) / (ts[-1] - ts[0]) if len(ts) >= 2 else 0.0
            cnts  = analytics[s]['counts']
            confs = analytics[s]['confs']
            metrics[s] = {
                'actual_fps':    round(fps_a,1),
                'avg_det_count': round(sum(cnts)/len(cnts),2) if cnts else 0.0,
                'avg_det_conf':  round(sum(confs)/len(confs),2) if confs else 0.0
            }
    return jsonify(status=status, metrics=metrics)

@app.route('/video/<src>')
def video(src):
    if src not in flags_stream:
        return "Not found", 404
    return Response(make_mjpeg_stream(src),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, threaded=True)
