import json
import math
from datetime import datetime,timezone,timedelta
from fastapi import FastAPI,Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

SEGMENT_DURATION = 9
PLAYLIST_LENGTH = 6

app = FastAPI()

# 静的ファイルの配信を追加
app.mount("/static", StaticFiles(directory="static"), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # すべてのオリジンを許可（開発用）
    allow_credentials=True,
    allow_methods=["*"],  # すべてのHTTPメソッドを許可
    allow_headers=["*"],  # すべてのHTTPヘッダーを許可
)

with open("schedule.json","r") as f:
    schedule = sorted(json.load(f),key=lambda x: x["start_time"])

def get_program_by_global_segment(global_segment_index):
    """
    global_segment_index : 調べたいグローバルセグメントのインデックス
    global_segment_indexがどの番組に属しているかを調べる関数
    """
    #番組の開始グローバルセグメント番号
    current_global_index = 0

    for program in schedule:
        #番組のセグメント数
        program_segments = math.ceil(program["duration_sec"] / SEGMENT_DURATION)
        
        if current_global_index <= global_segment_index < current_global_index + program_segments:
            program_segment_index = global_segment_index - current_global_index
            return program,program_segment_index
        
        current_global_index += program_segments

    return None,None

@app.get("/live/video.m3u8",response_class=Response)
def get_vod_playlist():
    #timezoneを日本時間に変更
    jst = timezone(timedelta(hours=9))
    now = datetime.now(jst)

    current_program = None
    program_start_time = None
    prev_program = None

    #現在時間に放送されている番組を特定
    for i,program in enumerate(schedule):
        start_time = datetime.fromisoformat(program["start_time"])
        end_time = start_time + timedelta(seconds=program["duration_sec"])
        if start_time <= now < end_time:
            current_program = program
            program_start_time = start_time
            if i > 0:
                prev_program = schedule[i-1]
            break
    
    #該当する番組が存在しない場合
    if not current_program:
        return Response(content="現在は放送されていません。",status_code=404)
    
    #番組スタートからの経過時間
    time_info_program = (now - program_start_time).total_seconds()

    #現在のセグメントのインデックス
    #例えば番組開始から15秒経過していた場合一つのセグメントあたり10秒なので，インデックスは1になる
    current_segment_index = int(time_info_program / SEGMENT_DURATION)

    #全体を通してのインデックスの取得
    total_segments_before = 0
    for program in schedule:
        if program == current_program:
            break
        total_segments_before += math.ceil(program["duration_sec"] / SEGMENT_DURATION)

    global_current_segment = total_segments_before + current_segment_index

    #m3u8の最初のセグメントが全体で何番目のセグメントかを識別するもの
    #PALYLIST_LENGTHは一つのm3u8ファイルにのるtsファイルの数
    #現在のインデックスが11だったら11-PLAYLIST_LENGTHがm3u8ファイルの最初のtsファイルになる
    start_global_index = max(0,global_current_segment - PLAYLIST_LENGTH + 1)

    #動的にm3u8ファイルを生成する
    m3u8_content = [
        "#EXTM3U",
        "#EXT-X-VERSION:3",
        f"#EXT-X-TARGETDURATION:{SEGMENT_DURATION}",
        f"#EXT-X-MEDIA-SEQUENCE:{start_global_index}",
        "#EXT-X-ALLOW-CACHE:YES"
    ]
    
    # print("current_segment_index:",current_segment_index)
    # print("start_index: ",start_index)
    last_program = None
    for global_index in range(start_global_index,global_current_segment + 1):
        #globalなsegmentのインデックスから番組内でのインデックスと番組名を取得
        segment_program,program_segment_index = get_program_by_global_segment(global_index)

        if not segment_program:
            continue
        
        #番組が切り替わったらタグをつける
        if last_program and last_program != segment_program:
            m3u8_content.append("#EXT-X-DISCONTINUITY")
        
        m3u8_content.append(f"#EXTINF:{SEGMENT_DURATION}.0,")
        segment_filename = segment_program["path_template"].format(str(program_segment_index).zfill(3))
        absolute_url = f"/{segment_filename}"
        m3u8_content.append(absolute_url)    

        last_program = segment_program   

    final_content = "\n".join(m3u8_content) + "\n"

    return Response(content=final_content,media_type="application/vnd.apple.mpegurl")