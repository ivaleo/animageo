"""Manim animations for the style guide.

Render all four in one command:
    cd /path/to/animageo
    PYTHONPATH=. manim -ql --media_dir /tmp/animageo_media --disable_caching \\
        docs/guide/examples/anim_scenes.py \\
        AnimCirclePoint AnimMovingVertex AnimShowBuildup AnimUpdater

Then copy MP4s to assets:
    cp /tmp/animageo_media/videos/anim_scenes/480p15/*.mp4 \\
       docs/guide/assets/examples/
"""
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))

from manim import Mobject
from animageo.animageo import AnimaGeoScene

STYLE = str(HERE / 'guide_style.json')


def _setup(scene, w=854, h=480, scale=46):
    scene.style.export['ptUnit'] = scale
    scene.style.export['ptWidth'] = w
    scene.style.export['ptHeight'] = h
    scene.style.export['ptXZero'] = w / 2
    scene.style.export['ptYZero'] = h / 2


def _align_guide_rendering(scene):
    """Small renderer-only adjustments used by the animation examples."""
    return None


# ── 1. play_keyframes: точка по окружности ───────────────────────────

class AnimCirclePoint(AnimaGeoScene):
    """Точка P обходит окружность, центральный угол α следит за ней.

    Светло-серые радиусы OQ и OP показывают стороны угла;
    fill-сектор и stroke-дужка совпадают на всём пробеге α.

    Подписи обновляются **per-frame** (а не через keyframe_snapshots):
    P движется по дуге, и линейная интерполяция offset между двумя
    снапшотами давала бы смещение «в прямой», из-за чего в середине
    подпись P проскакивала бы на точке. Per-frame решатель (через
    ``autoPlaceLabels(dynamic=True)``) пересчитывает позиции каждые
    несколько кадров и гладко сглаживает EMA.

    Подпись O зафиксирована руками: O статична, так что и её подпись
    не должна «прыгать» под давлением решателя.
    """

    def construct(self):
        _setup(self)
        self.applyStyle(style=STYLE, export={"size": {"width": 854, "height": 480}})

        self.style_config.overlay.label_placement = {
            'enabled': True,
            'dynamic_angles': True,
            'distance_px': 6,
            'ema_alpha': 0.25,
            'anchor_flip_frames': 10,
            'solver_every_n_frames': 2,
        }

        self.putCode("""
O = Point(0, 0)
R = Point(3, 0)
c = Circle(O, R)
P = Point(c)
Q = Point(-3, 0)
rOQ = Segment(O, Q)
rOP = Segment(O, P)
s = Segment(Q, P)
alpha = Angle(Q, O, P)
""")
        # NB: set tparam via update_tparam + rebuild, иначе dependents
        # не инвалидируются и P остаётся в стартовой позиции (tparam=0).
        self.geo.update_tparam('P', np.pi / 6)
        self.geo.rebuild()

        _align_guide_rendering(self)

        # Радиусы-стороны угла — светло-серым.
        for n in ('rOQ', 'rOP'):
            el = self.element(n)
            el.style['stroke'] = '#b1b3b6'
            el.style['stroke_width_px'] = 0.8

        for n in ('O', 'Q', 'P'):
            self.element(n).style['label_visible'] = True
        self.element('alpha').style['label_visible'] = True
        self.element('alpha').style['label_text'] = r'$\alpha$'

        # O auto-placed dynamically — трекер расставит подпись сам,
        # уводя её от вращающихся OP/OQ.

        self.element('c').style['stroke'] = self.style.col
        self.element('s').style['stroke'] = self.style.col_accent
        self.element('s').style['stroke_width_px'] = 1.5
        self.element('alpha').style['fill'] = self.style.col_accent_light
        self.element('alpha').style['fill_opacity'] = 0.7
        self.element('alpha').style['arc_size_px'] = 22

        self.addAllGeometry(show=True)
        # dynamic=True — решатель работает per-frame, подписи гладко
        # подтягиваются к движущейся P.
        self.autoPlaceLabels(dynamic=True)
        self.updateAllGeometry()

        self.wait(0.3)

        # Отдельный ValueTracker для параметра P. Sentinel-updater обновляет
        # P.tparam, пересобирает геометрию и дёргает решатель подписей.
        from manim import ValueTracker, linear
        a_param = ValueTracker(np.pi / 6)
        self.add(a_param)

        scene = self

        def on_frame(mobj):
            scene.geo.update_tparam('P', a_param.get_value())
            updates = scene.geo.rebuild()
            scene.updateGeoElements(updates)
            if scene._label_tracker is not None:
                scene._apply_dynamic_labels()

        sentinel = Mobject()
        sentinel.add_updater(on_frame)
        self.add(sentinel)

        # Полный оборот CCW. Target чуть меньше 2π + start, чтобы не
        # упереться в knot `diff ≡ 0 mod 2π` (здесь не критично, т.к.
        # интерполируется скаляр, но оставим).
        target = 2 * np.pi + np.pi / 6 - 0.001
        self.play(a_param.animate.set_value(target), run_time=5,
                  rate_func=linear)

        sentinel.clear_updaters()
        self.remove(sentinel)
        self.remove(a_param)
        self.clearLabelTracker()
        self.wait(0.4)


# ── 2. play_keyframes: движущаяся вершина ────────────────────────────

class AnimMovingVertex(AnimaGeoScene):
    """Вершина C скользит по горизонтали; подписи плавно интерполируются.

    Важно: для `play_keyframes` нужен именно ``keyframe_snapshots=True``.
    ``autoPlaceLabels(dynamic=True)`` работает только для
    ``addUpdater``-сценариев — там решатель дёргается на каждом
    ``updateVar``, а ``play_keyframes`` его не использует.
    """

    def construct(self):
        _setup(self)
        self.applyStyle(style=STYLE, export={"size": {"width": 854, "height": 480}})

        self.style_config.overlay.label_placement = {
            'enabled': True,
            'keyframe_snapshots': True,
            'dynamic_angles': True,
            'canonicalize_anchor': True,
            'distance_px': 8,
            'interpolation': 'smooth',
        }

        self.putCode("""
A = Point(-3.5, -1.8)
B = Point(3.5, -1.8)
L1 = Point(-3.5, 2.0)
L2 = Point(3.5, 2.0)
rail = Line(L1, L2)
C = Point(rail)
p, a, b, c = Polygon(A, B, C)
alpha = Angle(B, A, C)
beta = Angle(A, B, C)
""")
        self.geo.update_tparam('C', 0.0)
        self.geo.rebuild()

        _align_guide_rendering(self)

        for n in ('A', 'B', 'C'):
            self.element(n).style['label_visible'] = True
        self.element('alpha').style['label_visible'] = True
        self.element('alpha').style['label_text'] = r'$\alpha$'
        self.element('beta').style['label_visible'] = True
        self.element('beta').style['label_text'] = r'$\beta$'

        for n in ('rail', 'L1', 'L2'):
            self.element(n).visible = False

        self.element('p').style['fill'] = self.style.col_light
        self.element('p').style['fill_opacity'] = 0.5

        self.addAllGeometry(show=True)
        self.autoPlaceLabels()
        self.updateAllGeometry()

        self.wait(0.3)
        self.play_keyframes({
            "keyframes": [
                {"t": 0.0, "values": {"C": {"tparam": 0.2}}},
                {"t": 2.0, "values": {"C": {"tparam": 0.8}}, "easing": "smooth"},
                {"t": 4.0, "values": {"C": {"tparam": 0.2}}, "easing": "smooth"},
            ]
        })
        self.wait(0.4)


# ── 3. Show/Hide: поэтапное появление ────────────────────────────────

class AnimShowBuildup(AnimaGeoScene):
    """Треугольник появляется поэтапно: точки → стороны → заливка → угол."""

    def construct(self):
        _setup(self)
        self.applyStyle(style=STYLE, export={"size": {"width": 854, "height": 480}})

        self.putCode("""
A = Point(-3.5, -1.8)
B = Point(3.5, -1.8)
C = Point(0.5, 2.5)
p, a, b, c = Polygon(A, B, C)
alpha = Angle(B, A, C)
""")
        _align_guide_rendering(self)

        for n in ('A', 'B', 'C'):
            self.element(n).style['label_visible'] = True
        self.element('alpha').style['label_visible'] = True
        self.element('alpha').style['label_text'] = r'$\alpha$'

        self.element('p').style['fill'] = self.style.col_light
        self.element('p').style['fill_opacity'] = 0.5
        self.element('alpha').style['fill'] = self.style.col_accent_light
        self.element('alpha').style['fill_opacity'] = 0.7

        # Шаг 1: полная сборка и авто-раскладка.
        self.addAllGeometry(show=True)
        self.autoPlaceLabels()
        self.updateAllGeometry()

        # Шаг 2: всё скрываем — позиции подписей запомнены.
        for el in self.geo.elements:
            el.visible = False
        for el in self.geo.elements:
            m = self.mobject(el.name)
            if m:
                self.remove(m)

        # Шаг 3: build-up по стадиям.
        self.wait(0.3)
        self.playShow(['A', 'B', 'C'], mode='Fade')
        self.wait(0.3)
        self.playShow(['a', 'b', 'c'], mode='Create', run_time=1.2)
        self.wait(0.3)
        self.playShow(['p'], mode='Fade')
        self.wait(0.3)
        self.playShow(['alpha'], mode='Create')
        self.wait(0.5)


# ── 4. addVar + addUpdater: ручная анимация параметра ────────────────

class AnimUpdater(AnimaGeoScene):
    """Точка P скользит по AB; высота PC и угол APC перестраиваются.

    Продолжения отрезка AB (слева и справа) нарисованы светло-серым.
    Дуга угла α залита акцентным цветом; при t=0.5 угол ровно 90° —
    держим паузу 1 секунду, чтобы акцентировать этот момент.

    Подписи статических точек (A, B, C) **зафиксированы вручную**, так
    как они не двигаются. Авто-решатель иначе дрейфовал бы из-за
    изменения obstacle-cloud (сегмент PC меняет своё направление каждый
    кадр, что сдвигает preferred_dir у A и B). Подпись P отрабатывает
    per-frame LabelTracker.
    """

    def construct(self):
        _setup(self)
        self.applyStyle(style=STYLE, export={"size": {"width": 854, "height": 480}})

        self.putCode("""
A_ext = Point(-5.5, 0)
B_ext = Point(5.5, 0)
A = Point(-3, 0)
B = Point(3, 0)
s_left = Segment(A_ext, A)
s = Segment(A, B)
s_right = Segment(B, B_ext)
P = Point(s)
C = Point(0, 2.5)
h = Segment(C, P)
alpha = Angle(A, P, C)
""")
        # Старт в A (tparam=0 на AB). update_tparam + rebuild — см. комментарий
        # в AnimCirclePoint: прямое elem.tparam = 0 не инвалидирует кэш.
        self.geo.update_tparam('P', 0.0)
        self.geo.rebuild()
        _align_guide_rendering(self)

        for n in ('A', 'B', 'C', 'P'):
            self.element(n).style['label_visible'] = True
        self.element('alpha').style['label_visible'] = True
        self.element('alpha').style['label_text'] = r'$\alpha$'

        # Статические A, B, C — фиксируем их подписи чтобы не
        # «плавали» из-за меняющегося облака препятствий.
        self.element('A').style.update({
            'label_offset_px': [-14, -12], 'label_anchor': 'MC',
            'label_placement_locked': True,
        })
        self.element('B').style.update({
            'label_offset_px': [14, -12], 'label_anchor': 'MC',
            'label_placement_locked': True,
        })
        self.element('C').style.update({
            'label_offset_px': [0, 16], 'label_anchor': 'MC',
            'label_placement_locked': True,
        })

        # Продолжения AB — светло-серые (палитра: aux)
        for n in ('s_left', 's_right'):
            el = self.element(n)
            el.style['stroke'] = '#b1b3b6'
            el.style['stroke_width_px'] = 0.8
        # Скрываем служебные точки-концы продолжений.
        for n in ('A_ext', 'B_ext'):
            self.element(n).visible = False

        # Высота PC — акцентный цвет.
        self.element('h').style['stroke'] = self.style.col_accent
        self.element('h').style['stroke_width_px'] = 1.5

        # Дуга угла — цветная заливка.
        self.element('alpha').style['fill'] = self.style.col_accent_light
        self.element('alpha').style['fill_opacity'] = 0.75

        # Включаем dynamic_angles, чтобы биссектриса α подписи
        # пересчитывалась каждый кадр.
        self.style_config.overlay.label_placement = {
            'enabled': True,
            'dynamic_angles': True,
            'distance_px': 6,
        }

        self.addAllGeometry(show=True)
        # dynamic=True устанавливает LabelTracker: для статических
        # подписей (locked) решатель их пропускает, для P (движется) —
        # EMA-сглаживание; для угла α — биссектриса per-frame.
        self.autoPlaceLabels(dynamic=True)
        self.updateAllGeometry()

        self.wait(0.3)

        # Переменная t ∈ [0, 1] управляет tparam точки P.
        t = self.addVar('t', 0.0)

        scene = self
        def update_p(mobj):
            scene.geo.update_tparam('P', t.get_value())
            updates = scene.geo.rebuild()
            scene.updateGeoElements(updates)
            # Вручную дёргаем решатель подписей: sentinel-паттерн не идёт
            # через updateVar, поэтому per-frame трекер нужно вызывать сами.
            if scene._label_tracker is not None:
                scene._apply_dynamic_labels()

        sentinel = Mobject()
        sentinel.add_updater(update_p)
        self.add(sentinel)

        # Едем к перпендикуляру (t=0.5 даёт угол ровно 90°).
        self.play(t.animate.set_value(0.5), run_time=1.8)
        # Пауза на прямом угле.
        self.wait(1.0)
        # Продолжаем к B.
        self.play(t.animate.set_value(1.0), run_time=1.5)
        # Назад в окрестность старта.
        self.play(t.animate.set_value(0.2), run_time=1.5)

        sentinel.clear_updaters()
        self.remove(sentinel)
        self.clearLabelTracker()
        self.wait(0.4)
