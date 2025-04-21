# server.py
import asyncio
import json
from aiohttp import web
from aiortc import RTCPeerConnection, VideoStreamTrack, RTCSessionDescription
from aiortc.contrib.media import MediaBlackhole, MediaPlayer
import cv2
import av

pcs = set()

class CameraStream(VideoStreamTrack):
    """
    RTSPストリームをWebRTCで送信するトラック
    """
    def __init__(self, rtsp_url):
        super().__init__()
        print("CameraStream init")
        self.video = cv2.VideoCapture(rtsp_url)
        if not self.video.isOpened():
            raise RuntimeError(f"RTSPストリームを開けません: {rtsp_url}")
        # フレームレートを設定
        self.video.set(cv2.CAP_PROP_FPS, 30)
        # トラックの方向を明示的に設定
        self._direction = "sendonly"
        # トラックのIDを設定
        self._id = "video"
        # トラックの種類を設定
        self.kind = "video"

    @property
    def direction(self):
        return self._direction

    @direction.setter
    def direction(self, value):
        self._direction = value

    @property
    def id(self):
        return self._id

    @id.setter
    def id(self, value):
        self._id = value

    @property
    def kind(self):
        return self._kind

    @kind.setter
    def kind(self, value):
        self._kind = value

    async def recv(self):
        pts, time_base = await self.next_timestamp()
        
        # フレームを読み込む
        ret, frame = self.video.read()
        if not ret:
            # 再接続を試みる
            self.video.release()
            self.video = cv2.VideoCapture(rtsp_url)
            ret, frame = self.video.read()
            if not ret:
                raise RuntimeError("RTSPストリームの読み込みエラー")

        # フレームをRGBに変換
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # フレームをAVFrameに変換
        av_frame = av.VideoFrame.from_ndarray(frame, format="rgb24")
        av_frame.pts = pts
        av_frame.time_base = time_base
        
        return av_frame

def create_player(rtsp_url):
    # RTSPストリームの設定を改善
    options = {
        "rtsp_transport": "tcp",  # TCPを使用して安定性を向上
        "stimeout": "5000000",    # タイムアウトを5秒に設定
        "buffer_size": "1024000", # バッファサイズを増加
        "fflags": "nobuffer",     # バッファリングを無効化
        "flags": "low_delay",     # 低遅延モードを有効化
    }
    print(f"Creating MediaPlayer with URL: {rtsp_url}")
    player = MediaPlayer(rtsp_url, options=options)
    print(f"MediaPlayer created, video track: {player.video}")
    return player.video

async def offer(request):
    request_json = await request.json()
    offer = RTCSessionDescription(sdp=request_json["sdp"], type=request_json["type"])

    pc = RTCPeerConnection()
    pcs.add(pc)

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        print("Connection state:", pc.connectionState)
        if pc.connectionState == "failed":
            await pc.close()
            pcs.discard(pc)

    # RTSP URLを指定
    # rtsp_url = "rtsp://KodaiKomatsu:Kodai1998@10.0.0.60/stream1"
    rtsp_url = "mov_hts-samp009.mp4"
    # video_track = CameraStream(rtsp_url)
    video_track = create_player(rtsp_url)
    
    pc.addTrack(video_track)

    print("Set Remote offer")
    await pc.setRemoteDescription(offer)
    
    # アンサーを生成
    answer = await pc.createAnswer()
    print("Set Local answer")
    
    # ローカルディスクリプションを設定
    await pc.setLocalDescription(answer)
    
    return web.Response(
        content_type="application/json",
        text=json.dumps({"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}),
    )

app = web.Application()
app.router.add_post("/offer", offer)
app.router.add_static("/", path="static")

web.run_app(app, port=8080)