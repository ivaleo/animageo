import pytest

from animageo.export_layout import compute_export_layout
from animageo.export_layout import compute_reference_export_layout
from animageo.export_layout import normalize_content_options


SOURCE = {
    'ptUnit': 50,
    'ptWidth': 300,
    'ptHeight': 150,
    'ptXZero': 150,
    'ptYZero': 75,
}


def test_contain_scales_source_view_into_export_canvas():
    layout = compute_export_layout(SOURCE, export_size=[1200, 600])

    assert layout.ptWidth == 1200
    assert layout.ptHeight == 600
    assert layout.contentScale == pytest.approx(4)
    assert layout.ptUnit == pytest.approx(200)
    assert layout.ptUnit_style == pytest.approx(50)
    assert layout.ptXZero == pytest.approx(600)
    assert layout.ptYZero == pytest.approx(300)


def test_height_fit_centers_horizontally():
    layout = compute_export_layout(
        SOURCE,
        export_size=[1200, 900],
        fit='height',
    )

    assert layout.contentScale == pytest.approx(6)
    assert layout.contentOffsetX == pytest.approx(-300)
    assert layout.contentOffsetY == pytest.approx(0)
    assert layout.ptXZero == pytest.approx(600)


def test_none_fit_uses_anchor_without_scaling():
    layout = compute_export_layout(
        SOURCE,
        export_size=[1200, 600],
        fit='none',
        anchor='top_left',
        offset=[10, 20],
    )

    assert layout.contentScale == pytest.approx(1)
    assert layout.contentOffsetX == pytest.approx(10)
    assert layout.contentOffsetY == pytest.approx(20)
    assert layout.ptUnit == pytest.approx(50)
    assert layout.ptXZero == pytest.approx(160)
    assert layout.ptYZero == pytest.approx(95)


def test_manual_fit_requires_scale():
    with pytest.raises(ValueError, match='manual_scale'):
        compute_export_layout(SOURCE, export_size=[1200, 600], fit='manual')


def test_rendered_bounds_source_rect_is_accepted_after_caller_measures_bounds():
    layout = compute_export_layout(
        {**SOURCE, 'ptWidth': 100, 'ptHeight': 50, 'ptXZero': 25, 'ptYZero': 30},
        export_size=[400, 200],
        source_rect='rendered_bounds',
    )

    assert layout.contentScale == pytest.approx(4)
    assert layout.ptXZero == pytest.approx(100)
    assert layout.ptYZero == pytest.approx(120)
    assert layout.source_rect == 'rendered_bounds'


def test_unknown_source_rect_is_rejected():
    with pytest.raises(ValueError, match='source_rect'):
        compute_export_layout(SOURCE, export_size=[1200, 600], source_rect='explicit')


def test_reference_size_overrides_source_dimensions_only():
    layout = compute_export_layout(
        SOURCE,
        export_size=[1000, 500],
        reference_size=[250, 125],
    )

    assert layout.referenceWidth == pytest.approx(250)
    assert layout.referenceHeight == pytest.approx(125)
    assert layout.contentScale == pytest.approx(4)
    assert layout.ptUnit_style == pytest.approx(50)


def test_reference_export_layout_separates_geometry_and_export_scale():
    layout = compute_reference_export_layout(
        {**SOURCE, 'ptWidth': 1200, 'ptHeight': 300, 'ptXZero': 600, 'ptYZero': 150},
        reference_size=[500, 500],
        export_size=[1000, 1000],
        content={'fit': 'contain'},
        export={'fit': 'contain'},
    )

    assert layout.referenceWidth == pytest.approx(500)
    assert layout.referenceHeight == pytest.approx(500)
    assert layout.geometryScale == pytest.approx(500 / 1200)
    assert layout.exportScale == pytest.approx(2)
    assert layout.contentScale == pytest.approx(2)
    assert layout.ptUnit_style == pytest.approx(50 * 500 / 1200)
    assert layout.ptUnit == pytest.approx(layout.ptUnit_style * 2)


def test_content_infinite_policy_defaults_to_ignore():
    content = normalize_content_options({'source': 'rendered_bounds'})

    assert content['infinite_policy'] == 'ignore'


def test_content_infinite_policy_accepts_clip_opt_in():
    content = normalize_content_options({
        'source': 'rendered_bounds',
        'infinite_policy': 'clip',
    })

    assert content['infinite_policy'] == 'clip'


def test_content_infinite_policy_rejects_unknown_value():
    with pytest.raises(ValueError, match='content.infinite_policy'):
        normalize_content_options({'infinite_policy': 'extend'})
