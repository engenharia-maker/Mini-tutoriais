"""Baixa, de uma Release PRIVADA, o MP4 e/ou SRT usando gh autenticado via GITHUB_TOKEN."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--tag', required=True)
    p.add_argument('--dir', default='entrada')
    p.add_argument('--modo', choices=('transcrever', 'final'), required=True)
    args = p.parse_args()
    repo = os.getenv('GITHUB_REPOSITORY', '')
    if not repo or not os.getenv('GH_TOKEN'):
        raise SystemExit('GITHUB_REPOSITORY e GH_TOKEN são necessários. Execute pelo GitHub Actions.')
    out = Path(args.dir)
    out.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(['gh', 'release', 'view', args.tag, '-R', repo, '--json', 'assets'], check=True,
                       text=True, capture_output=True)
    assets = json.loads(r.stdout)['assets']
    names = [a['name'] for a in assets]
    videos = [s for s in names if s.lower().endswith(('.mp4','.mov','.m4v','.webm'))]
    if len(videos) != 1:
        raise SystemExit(f'A Release {args.tag!r} deve ter exatamente 1 vídeo MP4/MOV/M4V/WEBM. Encontrados: {videos}')
    target = [('video', videos[0], 'original' + Path(videos[0]).suffix.lower())]
    if args.modo == 'final':
        if 'legendas_revisadas.srt' not in names:
            raise SystemExit('Adicione à mesma Release o arquivo com nome EXATO legendas_revisadas.srt.')
        target.append(('srt', 'legendas_revisadas.srt', 'legendas_revisadas.srt'))
    for _, filename, dest in target:
        with tempfile.TemporaryDirectory() as td:
            subprocess.run(['gh', 'release', 'download', args.tag, '-R', repo, '--pattern', filename,
                            '--dir', td], check=True)
            src = Path(td) / filename
            if not src.is_file():
                raise SystemExit(f'Arquivo não encontrado na Release: {filename}')
            shutil.copyfile(src, out / dest)
    print('Arquivos obtidos com acesso privado:', [t[2] for t in target])


if __name__ == '__main__':
    main()
