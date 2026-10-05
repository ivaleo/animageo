"""1.9.0a4: ``render(t=…, timeline=…)``, the report at time t and video
formats (plan L3 §5.3, §5.5); needs manim, ffmpeg for the video."""
import shutil
import subprocess

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


@pytest.mark.slow
@needs_ffmpeg
def test_mp4_frame_matches_render_at_time(tmp_path):
    """The frame of the MP4 at ``n/fps`` against ``render(t=n/fps, fmt="png")``.

    Measured (1.9.0a4): PSNR ≈ 32 dB, ≈ 1.1 % of pixels off by more than
    16/255 at every ``t`` — moving or still — so the gap is the rasteriser
    (cairosvg of the SVG against the manim camera and the h264 codec), not
    the geometry; the metric of the plan (≥ 40 dB, ≤ 0.1 %) is not met yet
    (remainder of stage 4). Guarded here: the frame at ``t`` is much closer
    to ``render(t)`` than to ``render`` at another ``t``.
    """
    doc = paths_document()
    fps = 10
    video = native.render(doc, fmt='mp4', out=tmp_path / 'v.mp4', timeline=MOVE,
                          video={'fps': fps, 'quality': 'medium'})
    assert video.report['video'] == {'fps': fps, 'quality': 'medium', 'width': 800, 'height': 534,
                                     'duration': 2.0}
    assert video.report['t'] == 2.0
    stills = {}
    for n in (0, 5, 10):
        stills[n] = native.render(doc, fmt='png', out=tmp_path / f's{n}.png', t=n / fps, timeline=MOVE).path
    for n in (0, 5, 10):
        frame = _frames(tmp_path / 'v.mp4', fps, n)
        psnr, bad = _metrics(frame, stills[n])
        assert psnr >= 30 and bad <= 0.02, (n, psnr, bad)
        other = stills[10 if n != 10 else 0]
        psnr_other, _bad = _metrics(frame, other)
        assert psnr >= psnr_other + 3, (n, psnr, psnr_other)


@pytest.mark.slow
@needs_ffmpeg
def test_gif_of_a_steps_timeline(tmp_path):
    doc = triangle_document()
    st = native.steps_timeline(doc, lag=0.1, duration=0.2, pause=0.1)
    result = native.render(doc, fmt='gif', out=tmp_path / 'steps.gif', timeline=st.keyframes,
                           video={'fps': 5, 'quality': 'low'})
    assert result.fmt == 'gif' and (tmp_path / 'steps.gif').stat().st_size > 0
    assert result.report['video']['width'] == 400
