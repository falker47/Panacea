"""Five primary destinations with two sibling panels visible per group."""
from unittest.mock import Mock

from panacea_ui import PanaceaApp


def _navigation_app():
    app = PanaceaApp.__new__(PanaceaApp)
    pages = [page for _, _, _, group_pages in app.NAV_GROUPS for page in group_pages]
    app.frames = {page: Mock() for page in pages}
    app.group_frames = {root: Mock() for root, _, _, _ in app.NAV_GROUPS}
    app._setup_functions = {page: Mock() for page in pages}
    app._built_frames = set()
    app.nav_buttons = {root: Mock() for root, _, _, _ in app.NAV_GROUPS}
    app.icons = {}
    app.icons_active = {}
    return app


def test_five_primary_destinations_cover_every_view_once():
    groups = PanaceaApp.NAV_GROUPS
    assert len(groups) == 5
    assert [root for root, _, _, _ in groups] == [
        'Dashboard', 'Cleaning', 'Tools', 'Turbo', 'Resurrect',
    ]
    views = [page for _, _, _, pages in groups for page in pages]
    assert len(views) == len(set(views)) == 8
    assert set(views) == {
        'Dashboard', 'Cleaning', 'Apps', 'Tools', 'Disk', 'Turbo', 'Startup', 'Resurrect',
    }


def test_secondary_views_highlight_their_primary_section():
    app = _navigation_app()
    for page, root in [('Apps', 'Cleaning'), ('Disk', 'Tools'),
                       ('Startup', 'Turbo'), ('Resurrect', 'Resurrect')]:
        app.select_frame(page)
        assert app.active_frame == page
        assert app.active_group == root
        assert app.nav_buttons[root].configure.call_args.kwargs['fg_color'] == '#263a56'
    assert app._built_frames == {'Cleaning', 'Apps', 'Tools', 'Disk', 'Turbo', 'Startup', 'Resurrect'}


def test_navigating_between_sibling_views_preserves_both_visible_panels():
    app = _navigation_app()
    app.select_frame('Cleaning')
    app.select_frame('Apps')
    app.select_frame('Cleaning')
    assert app._setup_functions['Cleaning'].call_count == 1
    assert app._setup_functions['Apps'].call_count == 1
    assert app.active_group == 'Cleaning'
    assert app.group_frames['Cleaning'].grid.call_count == 1
    assert app._setup_functions['Turbo'].call_count == 0
    app.select_frame('Unknown')
    assert app.active_frame == 'Cleaning'


def test_pair_reflow_uses_actual_usable_panel_width_by_section():
    # Canvas width is measured after sidebar, outer padding and scrollbar.
    assert PanaceaApp._group_requires_stack('Cleaning', 610)
    assert not PanaceaApp._group_requires_stack('Cleaning', 625)
    assert PanaceaApp._group_requires_stack('Tools', 625)
    assert not PanaceaApp._group_requires_stack('Tools', 640)
    assert PanaceaApp._group_requires_stack('Turbo', 650)
    assert not PanaceaApp._group_requires_stack('Turbo', 670)


def test_guided_steps_use_two_rows_of_five_when_readable_with_responsive_fallbacks():
    assert PanaceaApp._step_layout_mode(360) == '1'
    assert PanaceaApp._step_layout_mode(540) == '2'
    assert PanaceaApp._step_layout_mode(729) == '3'
    assert PanaceaApp._step_layout_mode(960) == '3'
    assert PanaceaApp._step_layout_mode(1180) == '5'
    assert PanaceaApp._step_layout_mode(1400) == '5'


def test_reselecting_a_visible_group_skips_redundant_grid_and_navigation_redraw():
    app = _navigation_app()
    app.select_frame('Cleaning')
    redraw_count = app.group_frames['Cleaning'].grid.call_count
    app.nav_buttons['Cleaning'].configure.reset_mock()
    app.select_frame('Apps')  # The sibling was already visible.
    app.select_frame('Cleaning')
    assert app.group_frames['Cleaning'].grid.call_count == redraw_count
    app.nav_buttons['Cleaning'].configure.assert_not_called()
