"""1.9.0a4: ``render(t=…, timeline=…)``, the report at time t and video
formats (plan L3 §5.3, §5.5); needs manim, ffmpeg for the video."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

pytest.importorskip('manim')
pytestmark = pytest.mark.manim

from animageo import native  # noqa: E402
from animageo.native.timeline_fixtures import paths_document, triangle_document  # noqa: E402

needs_ffmpeg = pytest.mark.skipif(shutil.which('ffmpeg') is None, reason='ffmpeg is not installed')

MOVE = {'version': 2, 'keyframes': [
    {'t': 0, 'values': {'A': [0, 0], 'Pc': {'tparam': 0.5}}},
    {'t': 1, 'values': {'A': [1, -1], 'Pc': {'tparam': 2.0, 'direction': 'ccw'}, 'Pq': {'tparam': 2.0}},
     'easing': 'linear'},
    {'t': 2, 'values': {'A': [1, -1]}},
]}


def test_svg_at_time_draws_the_visible_elements_at_their_values(tmp_path):
    doc = triangle_document()
    st = native.steps_timeline(doc)
    early = native.render(doc, fmt='svg', out=tmp_path / 'a.svg', t=1.5, timeline=st.keyframes)
    rep = early.report
    assert rep['t'] == 1.5 and rep['visible']['A'] is True and rep['visible']['m'] is False
    assert rep['elements']['A']['box'] is not None and rep['elements']['m']['box'] is None
    late = native.render(doc, fmt='svg', out=tmp_path / 'b.svg', t=st.duration, timeline=st.keyframes)
    assert all(late.report['visible'][e] for e in ('A', 'B', 'C', 'M', 'm', 't'))
    assert late.report['elements']['m']['box'] is not None
    moved = native.render(paths_document(), fmt='svg', out=tmp_path / 'c.svg', t=1.0, timeline=MOVE).report
    still = native.render(paths_document(), fmt='svg', out=tmp_path / 'd.svg',
                          inputs={'A': {'kind': 'point', 'value': [1, -1]}}).report
    assert moved['elements']['A']['box'] == still['elements']['A']['box']


def _frames(path, fps, n):
    out = path.with_suffix(f'.{n}.png')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(path), '-vf', f'select=eq(n\\,{n})',
                    '-vframes', '1', str(out)], check=True)
    return out


def _metrics(video_png, still_png):
    import numpy as np
    from PIL import Image
    a = np.asarray(Image.open(video_png).convert('RGB'), dtype=float)
    im = Image.open(still_png).convert('RGBA')
    bg = Image.new('RGBA', im.size, (255, 255, 255, 255))
    bg.alpha_composite(im)
    b = np.asarray(bg.convert('RGB').resize((a.shape[1], a.shape[0])), dtype=float)
    mse = ((a - b) ** 2).mean()
    psnr = 10 * np.log10(255 ** 2 / mse) if mse else float('inf')
    bad = float((np.abs(a - b).max(axis=2) > 16).mean())
    return psnr, bad


FRAMES = sorted((Path(__file__).resolve().parent / 'frames').glob('*.json'))


def test_twenty_frames():
    assert sum(len(json.loads(p.read_text(encoding='utf-8'))['frames']) for p in FRAMES) == 20


def test_png_frame_through_the_video_camera(tmp_path):
    """1.9.0a5: ``render(fmt="png", video=…)`` draws with the manim camera of
    the video at its pixel size; without ``video`` a PNG is cairosvg."""
    from PIL import Image
    doc = triangle_document()
    st = native.steps_timeline(doc)
    low = native.render(doc, fmt='png', out=tmp_path / 'low.png', t=st.duration, timeline=st.keyframes,
                        video={'quality': 'low'})
    assert Image.open(low.path).size == (400, 266)
    assert low.report['video'] == {'quality': 'low', 'width': 400, 'height': 266}
    assert low.report['t'] == st.duration and low.report['visible']['m'] is True
    plain = native.render(doc, fmt='png', out=tmp_path / 'plain.png', t=st.duration, timeline=st.keyframes)
    assert 'video' not in plain.report
    assert plain.report['elements'] == low.report['elements']
    with pytest.raises(ValueError):
        native.render(doc, fmt='png', video={'quality': 'huge'})


def _h264_floor(still_png, tmp_path):
    """Pixels off by more than 16/255 between a still and the same still
    through H.264 as manim encodes (libx264, crf 23, yuv420p): the error of
    the codec alone."""
    enc = tmp_path / (still_png.stem + '.h264.mp4')
    back = tmp_path / (still_png.stem + '.h264.png')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(still_png), '-c:v', 'libx264', '-crf', '23',
                    '-pix_fmt', 'yuv420p', str(enc)], check=True)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(enc), '-vframes', '1', str(back)], check=True)
    return _metrics(back, still_png)[1]


@pytest.mark.slow
@needs_ffmpeg
@pytest.mark.parametrize('path', FRAMES, ids=lambda p: p.stem)
def test_mp4_frame_matches_render_at_time(tmp_path, path):
    """``tests/native/frames/*.json`` (20 frames, plan L3 §5.5): the frame
    ``n`` of the MP4 against ``render(t=n/fps, fmt="png", video=…)`` — the
    still drawn by the camera of the video (1.9.0a5).

    Measured (1.9.0a5): PSNR 45.7 dB – ∞ on all 20 frames; 17 frames have
    ≤ 0.1 % of pixels off by more than 16/255, three (``paths`` 3 and 5,
    ``number`` 19) have 0.100–0.134 %, below the error of H.264 at manim's
    crf 23 on the same still (0.17–0.37 %): what is left is the codec, not
    the frame. Before (cairosvg of the SVG, 1.9.0a4): 29.6–46 dB, ≤ 1.23 %.
    Guarded: ≥ 40 dB; ≤ 0.1 % or not more than the codec alone; a frame is
    closer to ``render`` at its own ``t`` than at the other frames of the file.
    """
    case = json.loads(path.read_text(encoding='utf-8'))
    doc, timeline, fps = case['document'], case['timeline'], case['fps']
    quality = {'fps': fps, 'quality': case['quality']}
    video = native.render(doc, fmt='mp4', out=tmp_path / 'v.mp4', timeline=timeline, video=quality)
    assert video.report['video']['fps'] == fps
    stills = {n: Path(native.render(doc, fmt='png', out=tmp_path / f's{n}.png', t=n / fps, timeline=timeline,
                                    video=quality).path)
              for n in case['frames']}
    for n in case['frames']:
        frame = _frames(tmp_path / 'v.mp4', fps, n)
        psnr, bad = _metrics(frame, stills[n])
        assert psnr >= 40, (n, psnr, bad)
        assert bad <= 0.001 or bad <= _h264_floor(stills[n], tmp_path), (n, psnr, bad)
        for m, other in stills.items():
            if m != n:
                psnr_other, _bad = _metrics(frame, other)
                assert psnr >= psnr_other or abs(psnr - psnr_other) < 0.05, (n, m, psnr, psnr_other)


STYLED = {'version': 2, 'keyframes': [
    {'t': 0, 'values': {'A': [0, 0], '@camera': {'center': [0, 0], 'width': 14}}},
    {'t': 1, 'values': {'A': [1, -1], '@camera': {'center': [1, 0.5], 'width': 10}},
     'styles': {'m': {'stroke': '#ff0000', 'stroke_width_px': 6}}, 'easing': 'linear'},
    {'t': 2, 'values': {'A': [1, -1]}, 'styles': {'t': {'fill': '#00aa00', 'fill_opacity': 0.5}}},
]}


def test_styles_and_camera_at_time(tmp_path):
    """1.9.0a5: ``render(t)`` applies ``styles`` and ``@camera`` of the
    timeline as the playback leaves them (held after their keyframe)."""
    from animageo.native.rendering import timeline_extras
    doc = triangle_document()
    extras = timeline_extras(doc, STYLED)
    assert [sorted(kf) for kf in extras['keyframes']] == [['t', 'values'], ['easing', 'styles', 't', 'values'],
                                                         ['styles', 't']]
    assert timeline_extras(doc, MOVE) is None
    plain = native.render(doc, fmt='svg', out=tmp_path / 'plain.svg', t=1.5, timeline=MOVE).path
    styled = native.render(doc, fmt='svg', out=tmp_path / 'styled.svg', t=1.5, timeline=STYLED).path
    text = Path(styled).read_text(encoding='utf-8').lower()
    assert 'rgb(100%, 0%, 0%)' in text or '#ff0000' in text or 'rgb(255,0,0)' in text
    assert Path(plain).read_text(encoding='utf-8') != Path(styled).read_text(encoding='utf-8')


@pytest.mark.slow
@needs_ffmpeg
def test_mp4_frame_with_styles_and_camera(tmp_path):
    """The MP4 of a timeline with ``styles`` and ``@camera`` against
    ``render(t, fmt="png", video=…)``. Measured (1.9.0a5): 38.5–53 dB, the
    rest is H.264 on red-on-green edges (≤ the codec alone on the same
    still); without the styles and the camera of the earlier keyframe the
    frame at t = 1.5 was 18 dB."""
    doc = triangle_document()
    quality = {'fps': 10, 'quality': 'medium'}
    native.render(doc, fmt='mp4', out=tmp_path / 'v.mp4', timeline=STYLED, video=quality)
    for n in (0, 5, 10, 15, 19):
        frame = _frames(tmp_path / 'v.mp4', 10, n)
        still = Path(native.render(doc, fmt='png', out=tmp_path / f's{n}.png', t=n / 10, timeline=STYLED,
                                   video=quality).path)
        psnr, bad = _metrics(frame, still)
        assert psnr >= 36, (n, psnr, bad)
        assert bad <= 0.001 or bad <= _h264_floor(still, tmp_path), (n, psnr, bad)


@pytest.mark.slow
@needs_ffmpeg
def test_gif_of_a_steps_timeline(tmp_path):
    doc = triangle_document()
    st = native.steps_timeline(doc, lag=0.1, duration=0.2, pause=0.1)
    result = native.render(doc, fmt='gif', out=tmp_path / 'steps.gif', timeline=st.keyframes,
                           video={'fps': 5, 'quality': 'low'})
    assert result.fmt == 'gif' and (tmp_path / 'steps.gif').stat().st_size > 0
    assert result.report['video']['width'] == 400
