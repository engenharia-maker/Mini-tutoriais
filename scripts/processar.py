"""HNL: Whisper -> SRT revisável -> MP4 horizontal com capa, legendas e encerramento."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import subprocess
import tempfile
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
LOGO = ROOT / 'assets' / 'logo_hnl.png'
MAX_SECONDS = 181  # tolerância pequena para metadados


def run(args, cwd=None):
    print('+', ' '.join(map(str, args)), flush=True)
    subprocess.run([str(x) for x in args], check=True, cwd=cwd)


def probe(video):
    import json
    info = json.loads(subprocess.check_output([
        'ffprobe', '-v', 'error', '-show_entries', 'format=duration:stream=codec_type',
        '-of', 'json', str(video)
    ], text=True))
    duration = float(info.get('format', {}).get('duration', 0))
    if duration <= 0 or duration > MAX_SECONDS:
        raise ValueError(f'O vídeo deve ter até 3 minutos (duração identificada: {duration:.1f}s).')
    return duration, any(x.get('codec_type') == 'audio' for x in info.get('streams', []))


def fmt_srt(t):
    millis = max(0, int(round(float(t) * 1000)))
    hrs, rem = divmod(millis, 3_600_000)
    mins, rem = divmod(rem, 60_000)
    secs, ms = divmod(rem, 1000)
    return f'{hrs:02d}:{mins:02d}:{secs:02d},{ms:03d}'


def transcrever(video, out, modelo):
    probe(video)
    from faster_whisper import WhisperModel
    print(f'Transcrevendo com faster-whisper {modelo} (CPU/int8)...', flush=True)
    model = WhisperModel(modelo, device='cpu', compute_type='int8', cpu_threads=4)
    segments, info = model.transcribe(str(video), language='pt', beam_size=5,
                                       vad_filter=True, condition_on_previous_text=False)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with out.open('w', encoding='utf-8') as f:
        for seg in segments:
            phrase = ' '.join(seg.text.split())
            if not phrase or seg.end <= seg.start:
                continue
            count += 1
            f.write(f'{count}\n{fmt_srt(seg.start)} --> {fmt_srt(seg.end)}\n{phrase}\n\n')
    print(f'{count} legendas geradas: {out}', flush=True)
    if not count:
        print('Aviso: não foi detectada fala; o SRT ficará vazio.', flush=True)


def parse_srt(path):
    text = Path(path).read_text(encoding='utf-8-sig').replace('\r\n', '\n').replace('\r', '\n')
    pat = re.compile(r'(?:(?:^|\n)\s*\d+\s*\n)?(?P<start>\d\d:\d\d:\d\d[,\.]\d{1,3})\s*-->\s*(?P<end>\d\d:\d\d:\d\d[,\.]\d{1,3})(?:[^\n]*)\n(?P<content>.*?)(?=\n\s*\n|\Z)', re.S)
    cues = []
    for m in pat.finditer(text):
        def num(s):
            h, mi, sec = s.replace(',', '.').split(':')
            return float(h)*3600 + float(mi)*60 + float(sec)
        start, end = num(m.group('start')), num(m.group('end'))
        content = m.group('content').strip()
        if end > start and content:
            cues.append((start, end, content))
    if not cues:
        raise ValueError('O arquivo SRT não tem legendas válidas. Revise ou exporte pelo editor HTML.')
    return sorted(cues, key=lambda x:x[0])


def ass_time(seconds):
    cs = int(round(seconds * 100))
    hr, r = divmod(cs, 360000)
    mi, r = divmod(r, 6000)
    ss, c = divmod(r, 100)
    return f'{hr}:{mi:02d}:{ss:02d}.{c:02d}'


def make_ass(cues, dst, width=1920, height=1080):
    scale = width / 1920
    def esc(s):
        # Escape all ASS dialogue format controls from external SRT text.
        s = s.replace('\\', ' ').replace('{', '(').replace('}', ')')
        return r'\N'.join(' '.join(line.split()) for line in s.splitlines() if line.strip())
    style = ','.join([
        'Subtitle','DejaVu Sans', str(max(24, round(55*scale))),
        '&H00FFFFFF','&H00FFFFFF','&H00000000','&H99001B12',
        '0','0','0','0','100','100','0','0','3',
        str(max(5,round(10*scale))),'0','2',str(round(120*scale)),str(round(120*scale)),str(round(88*scale)),'1'
    ])
    head = f'''[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: {style}

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
    body = ''.join(f'Dialogue: 0,{ass_time(st)},{ass_time(en)},Subtitle,,0,0,0,,{esc(s)}\n' for st,en,s in cues)
    Path(dst).write_text(head + body, encoding='utf-8')


def font(sz, bold=True):
    paths = ['/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
             '/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf',
             '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']
    for p in paths:
        if os.path.isfile(p):
            return ImageFont.truetype(p, sz)
    return ImageFont.load_default()


def wrap(draw, text, max_width, fnt, max_lines=3):
    words = text.split()
    lines, cur = [], ''
    for word in words:
        cand = f'{cur} {word}'.strip()
        if draw.textbbox((0,0), cand, font=fnt)[2] <= max_width:
            cur = cand
        else:
            if cur: lines.append(cur)
            cur = word
    if cur: lines.append(cur)
    return lines[:max_lines]


def make_cards(equipamento, tema, dirname, width, height):
    dirname = Path(dirname)
    W,H = width,height
    ratio = W/1920
    img = Image.new('RGB', (W,H), '#FBFEFC')
    d = ImageDraw.Draw(img)
    green = '#087D4B'
    deep = '#075039'
    light = '#E5F5EB'
    d.ellipse((-int(.28*W),int(.48*H),int(.35*W),int(1.35*H)), fill='#DCEFCB')
    d.ellipse((-int(.22*W),int(.55*H),int(.22*W),int(1.2*H)), fill=green)
    d.ellipse((int(.73*W),-int(.48*H),int(1.25*W),int(.42*H)), fill=light)
    x, y = int(124*ratio), int(85*ratio)
    with Image.open(LOGO) as logo:
        logo = logo.convert('RGBA')
        logo.thumbnail((int(195*ratio), int(130*ratio)))
        img.paste(logo,(x,y),logo)
    d = ImageDraw.Draw(img)
    f18 = font(max(13,int(27*ratio)))
    f28 = font(max(19,int(36*ratio)))
    f45 = font(max(26,int(67*ratio)))
    fsmall = font(max(12,int(22*ratio)), False)
    d.text((x+int(230*ratio),y+int(30*ratio)), 'HOSPITAL NAPOLEÃO LAUREANO', fill=deep, font=f28)
    d.text((x+int(230*ratio),y+int(79*ratio)), 'ENGENHARIA CLÍNICA', fill=green, font=f18)
    bx, by = x+int(70*ratio), int(.42*H)
    d.rounded_rectangle((bx,by,bx+int(294*ratio),by+int(64*ratio)), radius=int(28*ratio), fill=deep)
    d.text((bx+int(22*ratio),by+int(15*ratio)), 'MINITUTORIAL', fill='white', font=f18)
    title = equipamento.strip()[:100] or 'Equipamento'
    selected_size = int(78*ratio)
    for size in range(selected_size, int(33*ratio), -max(1,int(3*ratio))):
        ft = font(size)
        lines=wrap(d,title,int(W*.75),ft,2)
        if len(lines)<2 or ' '.join(lines)==title:
            break
    for line in lines:
        d.text((bx,by+int(106*ratio)),line,fill=deep,font=ft)
        by+=int(size*1.15)
    topic_lines=wrap(d,tema.strip()[:170],int(W*.71),f28,2)
    ty=by+int(128*ratio)
    for line in topic_lines:
        d.text((bx,ty),line,fill='#4D886B',font=f28)
        ty+=int(48*ratio)
    d.line((x,int(H*.89),int(W*.94),int(H*.89)), fill='#AED3BC',width=max(2,int(2*ratio)))
    d.text((x,int(H*.91)), 'CONTEÚDO INSTITUCIONAL  •  ORIENTAÇÃO TÉCNICA', fill='#517967',font=fsmall)
    img.save(dirname/'capa.png')
    out = Image.new('RGB',(W,H),'#FBFEFC')
    od=ImageDraw.Draw(out)
    od.ellipse((-int(.4*W),int(.4*H),int(.24*W),int(1.3*H)),fill='#D9F0DD')
    od.ellipse((int(.78*W),-int(.55*H),int(1.25*W),int(.37*H)),fill='#DDF0D7')
    with Image.open(LOGO) as logo:
        logo=logo.convert('RGBA');logo.thumbnail((int(230*ratio),int(140*ratio)))
        out.paste(logo,(int(W/2-logo.width/2),int(140*ratio)),logo)
    od=ImageDraw.Draw(out)
    msg='Obrigado por assistir!'
    fbig=font(int(85*ratio))
    bbox=od.textbbox((0,0),msg,font=fbig)
    od.text(((W-(bbox[2]-bbox[0]))/2,int(H*.48)),msg,fill=deep,font=fbig)
    msg2='Engenharia Clínica • Hospital Napoleão Laureano'
    w2=od.textbbox((0,0),msg2,font=f28)[2]
    od.text(((W-w2)/2,int(H*.63)),msg2,fill=green,font=f28)
    out.save(dirname/'encerramento.png')
    watermark = Image.new('RGBA',(int(250*ratio),int(134*ratio)),(0,0,0,0))
    wd = ImageDraw.Draw(watermark)
    wd.rounded_rectangle((0,0,watermark.width-1,watermark.height-1),radius=int(20*ratio),fill=(255,255,255,219))
    with Image.open(LOGO) as l:
        l=l.convert('RGBA');l.thumbnail((int(180*ratio),int(116*ratio)))
        watermark.alpha_composite(l,((watermark.width-l.width)//2,(watermark.height-l.height)//2))
    watermark.save(dirname/'marca.png')


def render(video, srt, equipamento, tema, saida, width=1920, height=1080, fps=30):
    duration, has_audio = probe(video)
    cues = parse_srt(srt)
    saida = Path(saida).resolve()
    saida.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='hnl_') as td:
        work=Path(td)
        make_cards(equipamento, tema, work, width, height)
        make_ass(cues, work/'legendas.ass', width, height)
        for input_png, output in [('capa.png','capa.mp4'),('encerramento.png','encerramento.mp4')]:
            run(['ffmpeg','-hide_banner','-loglevel','error','-y',
                 '-loop','1','-framerate',str(fps),'-t','2','-i',input_png,
                 '-f','lavfi','-t','2','-i','anullsrc=channel_layout=stereo:sample_rate=48000',
                 '-c:v','libx264','-preset','veryfast','-crf','20','-pix_fmt','yuv420p',
                 '-r',str(fps),'-c:a','aac','-b:a','128k','-ar','48000','-ac','2',
                 '-shortest',output],cwd=work)
        source = Path(video).resolve()
        vidfilter = f'[0:v]scale={width}:{height}:force_original_aspect_ratio=decrease,' + \
                    f'pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,fps={fps},' + \
                    'ass=legendas.ass[base];[1:v]format=rgba[logo];' + \
                    f'[base][logo]overlay=W-w-{int(30*width/1920)}:{int(26*width/1920)}:format=auto,' + \
                    'format=yuv420p[v]'
        cmd=['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(source),'-i','marca.png']
        if not has_audio:
            cmd += ['-f','lavfi','-i','anullsrc=channel_layout=stereo:sample_rate=48000']
        cmd += ['-filter_complex',vidfilter,'-map','[v]','-map','0:a:0' if has_audio else '2:a:0',
                '-t',str(duration),'-r',str(fps),'-c:v','libx264','-preset','veryfast','-crf','20',
                '-pix_fmt','yuv420p','-c:a','aac','-b:a','128k','-ar','48000','-ac','2',
                '-movflags','+faststart','video.mp4']
        run(cmd,cwd=work)
        (work/'lista.txt').write_text("file 'capa.mp4'\nfile 'video.mp4'\nfile 'encerramento.mp4'\n",encoding='utf-8')
        run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i','lista.txt',
             '-c','copy','-movflags','+faststart',str(saida)],cwd=work)
    print(f'MP4 criado: {saida} ({saida.stat().st_size/1e6:.1f} MB)',flush=True)


def main():
    p=argparse.ArgumentParser(description='HNL: transcrição Whisper e vídeo institucional')
    sub=p.add_subparsers(dest='cmd',required=True)
    p1=sub.add_parser('transcrever')
    p1.add_argument('--video',required=True)
    p1.add_argument('--saida',required=True)
    p1.add_argument('--modelo',choices=['large-v3-turbo','medium','small'],default='large-v3-turbo')
    p2=sub.add_parser('renderizar')
    p2.add_argument('--video',required=True)
    p2.add_argument('--srt',required=True)
    p2.add_argument('--equipamento',required=True)
    p2.add_argument('--tema',required=True)
    p2.add_argument('--saida',required=True)
    p2.add_argument('--largura',type=int,default=1920)
    p2.add_argument('--altura',type=int,default=1080)
    p2.add_argument('--fps',type=int,default=30)
    a=p.parse_args()
    video=Path(a.video).resolve()
    if not video.exists():raise SystemExit(f'Vídeo não encontrado: {video}')
    if a.cmd=='transcrever':transcrever(video,a.saida,a.modelo)
    else:render(video,a.srt,a.equipamento,a.tema,a.saida,a.largura,a.altura,a.fps)

if __name__=='__main__':main()
