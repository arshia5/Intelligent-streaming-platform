# Intelligent Multi-Source Video Analytics & Streaming Platform

## 🛠️ Setup & Installation Instructions

This project integrates real-time multi-source video streaming, object detection using YOLOv5, analytics, and MQTT-based control. It relies on GStreamer for video pipelines and a custom Flask server.

### 1. Environment Setup

> Note: All steps are tested on macOS. Minor modifications might be needed for Linux or Windows.

#### 🔹 Install Python and Create Virtual Environment

```bash
# From your project folder
python3 -m venv gst_env
source gst_env/bin/activate
```

#### 🔹 Install Python Dependencies

```bash
pip install -r requirements.txt
```


#### 🔹 Install GStreamer and Plugins via Homebrew

```bash
brew install gstreamer gst-plugins-base gst-plugins-good gst-plugins-bad gst-plugins-ugly gst-libav
```

Ensure you have these binaries available:

```bash
gst-launch-1.0
```

#### 🔹 Install MQTT Broker (Mosquitto)

```bash
brew install mosquitto
brew services start mosquitto
```

> Mosquitto will now run on `localhost:1883` by default.

---




## 🧠 System Architecture & Data Flow

### Architecture Diagram

```
            ┌──────────────────────────────┐
            │        Web Interface         │
            └────────────┬─────────────────┘
                         │ HTTP
                     ┌───▼────┐
                     │ Flask  │
                     │ Server │
                     └──┬─────┘
     ┌──────────────────┼──────────────────┐
     │                  │                  │
 ┌───▼───┐         ┌────▼────┐        ┌────▼────┐
 │ Webcam│         │ IP Cam  │        │ MQTT Broker
 └──┬────┘         └────┬────┘        └────┬────┘
    │  GStreamer         │  GStreamer       │
    ▼                   ▼                  ▼
[YOLOv5 Detection]  [YOLOv5 Detection]     MQTT Metrics
    ▼                   ▼                  ▲
 [Heatmaps / Analytics Overlay]           │
    ▼                   ▼                  │
      MJPEG Streams served via Flask <────┘
```

### Flow Summary:

* `main.py` runs the Flask web server
* `stream_manager.py` sets up GStreamer video pipelines per source (webcam or IP camera)
* Frames are processed using a YOLOv5 model
* Detections and overlays (like heatmaps) are encoded as MJPEG streams
* MQTT messages control stream toggles and receive metrics feedback

---

## 🚀 Key Features

* Real-time multi-camera input
* Object detection with YOLOv5
* Heatmap overlay using background subtraction
* MQTT integration for remote control and analytics
* Resizable, modern web interface for stream viewing

---

## 🔌 Running the App

```bash
source gst_env/bin/activate
python main.py
```

* Web UI: [http://localhost:5001](http://localhost:5001)
* MJPEG Streams: `/video/webcam`, `/video/ipcam`
* API: `/stream/<src>/start`, `/stop`, `/detect_on`, `/heat_on`, etc.
* System Status: `/system/status`

---

## 📡 MQTT Command Usage

Use these MQTT commands to control the video sources. You can publish using `mosquitto_pub`:

```bash
# Start the webcam stream
mosquitto_pub -t "yolo/control/webcam/start" -m '{}'

# Start IP cam stream
mosquitto_pub -t "yolo/control/ipcam/start" -m '{}'

# Turn on detection
mosquitto_pub -t "yolo/control/webcam/detect_on" -m '{}'

# Turn off detection
mosquitto_pub -t "yolo/control/webcam/detect_off" -m '{}'

# Enable heatmap
mosquitto_pub -t "yolo/control/webcam/heat_on" -m '{}'

# Disable heatmap
mosquitto_pub -t "yolo/control/webcam/heat_off" -m '{}'

# Stop the stream
mosquitto_pub -t "yolo/control/webcam/stop" -m '{}'
```

You can also listen to feedback:

```bash
mosquitto_sub -t "yolo/events/webcam/metrics"
mosquitto_sub -t "yolo/events/webcam/control_ack"
```

---

## 📌 Notes

* YOLOv5 is loaded via Torch Hub. Adjust model size (s, m, l) in `stream_manager.py`
* GStreamer must be correctly configured for your camera hardware.
* IP cam stream must be accessible at `http://192.168.116.233:4747/video` (or edit in code).

---


