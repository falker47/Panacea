"""Turbo refresh ordering with real workers and inert UI/Windows boundaries."""
import threading
import time
import tkinter as tk
from collections import deque
from types import SimpleNamespace
from unittest.mock import Mock

import customtkinter as ctk
import pytest

from test_ui_controller import app_without_window


class Control:
    def __init__(self):
        self.settings = {'state': 'normal'}

    def configure(self, **settings):
        self.settings.update(settings)

    def select(self):
        pass

    def deselect(self):
        pass


def turbo_app():
    app = app_without_window()
    app._update_installing = False
    app._turbo_states = {'power': False}
    app._turbo_master = False
    app._turbo_saved = ()
    app._maintenance_controls = []
    app.operation_label = Control()
    app._show_toast = Mock()
    app.turbo_vars = {'power': Mock()}
    app.turbo_switches = {'power': Control()}
    app.master_switch = Control()
    app.btn_restore_turbo = Control()
    app.turbo_saved_label = Control()
    app.scheduled = deque()
    app.after = lambda delay, callback: app.scheduled.append(callback)
    return app


def drain_until(app, predicate, timeout=3):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.dispatcher.drain()
        # Run only callbacks present at the start, avoiding a self-retry spin.
        for _ in range(len(app.scheduled)):
            app.scheduled.popleft()()
        if predicate():
            return True
        time.sleep(0.001)
    return False


def test_stale_initial_read_cannot_replace_completed_turbo_mutation():
    app = turbo_app()
    machine = {'enabled': False}
    entered, release = threading.Event(), threading.Event()
    reads = []

    def read():
        before = machine['enabled']
        reads.append(before)
        if len(reads) == 1:
            entered.set()
            assert release.wait(3), 'Fixture initial read was not released'
        return {'power': before}, before

    app._read_turbo_states = read
    app.perf_mgr = SimpleNamespace(get_saved_settings=lambda: ('power',) if machine['enabled'] else ())
    app._load_turbo_states()
    try:
        assert entered.wait(3)
        def mutate():
            machine['enabled'] = True
            return True, 'enabled'
        assert app._request_operation('Turbo settings', mutate, on_done=app._load_turbo_states)
        assert drain_until(app, lambda: not app.workers.busy())
        # The mutation requests another refresh while the initial one still owns
        # turbo-state. Its older snapshot must be discarded and the request kept.
        release.set()
        assert drain_until(app, lambda: app._turbo_states.get('power') is True), (
            f"Live power={machine['enabled']}, displayed={app._turbo_states}, queries={reads}")
        assert app._turbo_master is True
        assert app._turbo_saved == ('power',)
    finally:
        release.set()
        app.workers.join(3)
        app.workers.close()


def test_switches_stay_disabled_until_post_mutation_refresh_is_applied():
    app = turbo_app()
    entered, release = threading.Event(), threading.Event()
    def read():
        entered.set()
        assert release.wait(3), 'Fixture post-mutation read was not released'
        return {'power': True}, True
    app._read_turbo_states = read
    app.perf_mgr = SimpleNamespace(get_saved_settings=lambda: ('power',))
    try:
        assert app._request_operation('Turbo settings', lambda: (True, 'enabled'),
                                      on_done=app._load_turbo_states)
        assert drain_until(app, entered.is_set)
        assert app.turbo_switches['power'].settings['state'] == 'disabled'
        assert app.master_switch.settings['state'] == 'disabled'
        assert app.btn_restore_turbo.settings['state'] == 'disabled'
        release.set()
        assert drain_until(app, lambda: app._turbo_states.get('power') is True)
        assert app.turbo_switches['power'].settings['state'] == 'normal'
        assert app.master_switch.settings['state'] == 'normal'
        assert app.btn_restore_turbo.settings['state'] == 'normal'
    finally:
        release.set()
        app.workers.join(3)
        app.workers.close()


def test_initial_refresh_deferred_by_unrelated_maintenance_is_retried():
    app = turbo_app()
    read_entered, read_release = threading.Event(), threading.Event()
    maintenance_entered, maintenance_release = threading.Event(), threading.Event()
    def read():
        read_entered.set()
        assert read_release.wait(3), 'Fixture state read was not released'
        return {'power': True}, True
    def maintain():
        maintenance_entered.set()
        assert maintenance_release.wait(3), 'Fixture maintenance was not released'
        return True, 'completed'
    app._read_turbo_states = read
    app.perf_mgr = SimpleNamespace(get_saved_settings=lambda: ('power',))
    app._load_turbo_states()
    try:
        assert read_entered.wait(3)
        # A cleanup/preview completion does not explicitly refresh Turbo.
        assert app._request_operation('Temporary file preview', maintain)
        assert maintenance_entered.wait(3)
        read_release.set()
        assert drain_until(app, lambda: not app.workers.busy('turbo-state'))
        maintenance_release.set()
        assert drain_until(app, lambda: not app.workers.busy() and app._turbo_states.get('power') is True)
        assert app._turbo_saved == ('power',)
    finally:
        read_release.set()
        maintenance_release.set()
        app.workers.join(3)
        app.workers.close()


@pytest.mark.parametrize('active', [True, False])
def test_master_snapshot_updates_disabled_switch_without_firing_action(active):
    app = turbo_app()
    interpreter = tk.Tcl()  # Variables only: no Tk window or native GUI created.
    app.master_var = tk.BooleanVar(master=interpreter, value=not active)
    # Use CTk's actual state and variable behavior; drawing/configuration are the
    # only replaced boundaries. select()/deselect() ignore a disabled control.
    switch = ctk.CTkSwitch.__new__(ctk.CTkSwitch)
    switch._state = tk.DISABLED
    switch._check_state = not active
    switch._variable = app.master_var
    switch._onvalue, switch._offvalue = True, False
    switch._variable_callback_blocked = False
    switch._command = Mock()
    switch._draw = lambda **kwargs: None
    switch.configure = lambda **kwargs: setattr(switch, '_state', kwargs.get('state', switch._state))
    trace = app.master_var.trace_add('write', switch._variable_callback)
    app.master_switch = switch
    try:
        app._apply_turbo_states(({'power': active}, active))
        assert switch.get() is active
        assert app.master_var.get() is active
        switch._command.assert_not_called()
    finally:
        app.master_var.trace_remove('write', trace)
        app.workers.close()
