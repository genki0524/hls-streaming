import subprocess

video_name = "embot-copy.mp4"

CMD = ["ffmpeg","-i",video_name,"-c:v","copy","-c:a","copy","-f","hls",
       "-hls_time","9","-hls_playlist_type","vod","-hls_segment_filename","static/stream/embot/video%3d.ts","static/stream/embot/video.m3u8"]

subprocess.run(CMD)