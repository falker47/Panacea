"""Freeze the interfaces consumed by already shipped installations, including mutation controls."""

import ast
from configparser import ConfigParser
from pathlib import Path
import shlex

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ("Panacea.exe", "Panacea.exe.sha256", "PanaceaSetup.exe", "PanaceaSetup.exe.sha256")
FLAGS = ("--panacea-update-helper", "--panacea-update-ready", "--smoke-test", "--smoke-backend-imports")


def read(path):
    return (ROOT / path).read_text(encoding="utf-8-sig")


def calls(tree, name):
    return [node for node in ast.walk(tree) if isinstance(node, ast.Call) and ast.unparse(node.func) == name]


def names_and_order(source):
    release = yaml.safe_load(source)
    assets = []
    for step in release["jobs"]["draft"]["steps"]:
        for line in step.get("run", "").replace("\\\n", " ").splitlines():
            words = shlex.split(line)
            if words[:3] in (["gh", "release", "create"], ["gh", "release", "upload"]):
                assets.extend(Path(w).name for w in words if w.endswith((".exe", ".sha256")))
    assert sorted(assets) == sorted(ASSETS), "release asset names"
    assert assets[0] == "Panacea.exe", "legacy first executable"


def repo(source):
    assignments = [node.value for node in ast.parse(source).body if isinstance(node, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == "GITHUB_REPO" for t in node.targets)]
    assert len(assignments) == 1 and ast.literal_eval(assignments[0]) == "falker47/Panacea", "repository identity"


def cli(source, flag):
    options = [node for node in ast.walk(ast.parse(source)) if isinstance(node, ast.Call)
               and isinstance(node.func, ast.Attribute) and node.func.attr == "add_argument"
               and node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value == flag]
    assert len(options) == 1, flag
    keywords = {k.arg: k.value for k in options[0].keywords}
    if flag.startswith("--smoke"):
        assert ast.literal_eval(keywords["action"]) == "store_true", flag
    else:
        assert "nargs" not in keywords and "action" not in keywords, flag


def marker(source):
    function, = [f for f in ast.parse(source).body if isinstance(f, ast.FunctionDef) and f.name == "readiness_path"]
    ns = {"Path": Path}
    exec(compile(ast.Module(body=[function], type_ignores=[]), "<readiness contract>", "exec"), ns)
    target = Path("example/Panacea.exe")
    assert ns["readiness_path"](target) == target.parent / "Panacea.exe.update-ready.json", "readiness marker"


def mutex(source):
    guard, = [f for f in ast.parse(source).body if isinstance(f, ast.FunctionDef) and f.name == "_transaction_guard"]
    identity = "hashlib.sha256(os.path.normcase(os.path.abspath(target)).encode('utf-8')).hexdigest()"
    digest_names = {ast.unparse(t) for node in ast.walk(guard) if isinstance(node, ast.Assign)
                    and ast.unparse(node.value) == identity for t in node.targets}
    operands = [c.args[2] for c in calls(guard, "create") if len(c.args) == 3]
    assert any(isinstance(e, ast.BinOp) and isinstance(e.op, ast.Add) and isinstance(e.left, ast.Constant)
               and e.left.value == "Global\\PanaceaUpdater." and ast.unparse(e.right) in digest_names
               for e in operands), "global normalized-path mutex"


def onefile(source):
    tree = ast.parse(source)
    assert not calls(tree, "COLLECT"), "one-file bundle"
    exes = calls(tree, "EXE")
    assert len(exes) == 1, "one-file EXE"
    exe = exes[0]
    options = {kw.arg: ast.literal_eval(kw.value) for kw in exe.keywords if kw.arg in ("name", "exclude_binaries")}
    assert options["name"] == "Panacea", "one-file EXE name"
    args = {ast.unparse(arg) for arg in exe.args}
    assert not options.get("exclude_binaries") and {"a.datas", "a.binaries"} <= args, "one-file payload"


def inno(source):
    config = ConfigParser(interpolation=None, strict=True)
    setup = "[Setup]" + source.split("[Setup]", 1)[1].split("\n[", 1)[0]
    config.read_string(setup)
    assert config["Setup"]["AppId"] == "{{B6C0FB10-27BC-4E6F-9078-40F9E8B49B2D}", "Inno AppId"
    assert config["Setup"]["DefaultDirName"] == r"{autopf}\Panacea", "Program Files directory"


def qml_ready(source):
    main, = [f for f in ast.parse(source).body if isinstance(f, ast.FunctionDef) and f.name == "main"]
    loads = calls(main, "engine.load")
    assert len(loads) == 1, "QML load"
    load = loads[0]
    roots = [node for node in ast.walk(main) if isinstance(node, ast.If)
             and ast.unparse(node.test) == "not engine.rootObjects()"
             and any(isinstance(s, ast.Return) for s in node.body)]
    ack, = calls(main, "acknowledge_ready")
    callbacks = {f.name for f in ast.walk(main) if isinstance(f, ast.FunctionDef) and f is not main
                 and ack in ast.walk(f)}
    schedules = [c for c in calls(main, "QTimer.singleShot") if len(c.args) == 2
                 and ast.unparse(c.args[1]) in callbacks]
    assert roots and len(schedules) == 1 and load.lineno < roots[0].lineno < schedules[0].lineno, "post-QML readiness"
    assert ack.lineno > roots[0].lineno, "post-QML acknowledgment"
    assert ast.unparse(ack.args[1]) == "args.panacea_update_ready", "readiness token"


# Each test first checks the actual file, then changes just the relevant input in memory.
CASES = [
    ("version.py", repo, "falker47/Panacea", "falker47/panacea", "repository identity"),
    ("modules/update_install.py", marker, ".update-ready.json", ".ready", "readiness marker"),
    ("modules/update_install.py", mutex, r"Global\\PanaceaUpdater.", r"Local\\PanaceaUpdater.", "mutex"),
    ("modules/update_install.py", mutex, "os.path.normcase(os.path.abspath(target))", "str(target)", "mutex"),
    ("Panacea.spec", onefile, "name='Panacea'", "name='Portable'", "EXE name"),
    ("Panacea.spec", onefile, "a.binaries,", "", "one-file payload"),
    ("Panacea.spec", onefile, "exe = EXE(", "COLLECT(pyz)\nexe = EXE(", "one-file bundle"),
    ("packaging/Panacea.iss", inno, "B6C0FB10", "B6C0FB11", "AppId"),
    ("packaging/Panacea.iss", inno, r"{autopf}\Panacea", r"{tmp}\Panacea", "directory"),
    ("qt_app/main.py", qml_ready, "engine.load(QUrl.fromLocalFile(str(source)))",
     "pass\n    # delayed engine load", "QML load"),
    ("qt_app/main.py", qml_ready, "if not engine.rootObjects():", "if False:", "post-QML"),

]


@pytest.mark.parametrize(("path", "guard", "before", "after", "reason"), CASES)
def test_frozen_interface_and_mutation(path, guard, before, after, reason):
    source = read(path)
    guard(source)
    assert before in source
    with pytest.raises(AssertionError, match=reason):
        guard(source.replace(before, after))


@pytest.mark.parametrize("asset", ASSETS)
def test_each_published_name_and_mutation(asset):
    source = read(".github/workflows/release.yml")
    names_and_order(source)
    with pytest.raises(AssertionError, match="release asset names"):
        names_and_order(source.replace("assets/" + asset + " ", "assets/Changed.exe ")
                        .replace("assets/" + asset + "\n", "assets/Changed.exe\n"))


def test_legacy_first_executable_and_mutation():
    source = read(".github/workflows/release.yml")
    names_and_order(source)
    swapped = source.replace("assets/Panacea.exe ", "assets/placeholder ")
    swapped = swapped.replace("assets/PanaceaSetup.exe ", "assets/Panacea.exe ")
    with pytest.raises(AssertionError, match="legacy first executable"):
        names_and_order(swapped.replace("assets/placeholder ", "assets/PanaceaSetup.exe "))


@pytest.mark.parametrize("path", ["main.py", "qt_app/main.py"])
@pytest.mark.parametrize("flag", FLAGS)
def test_cli_flags_and_mutation(path, flag):
    source = read(path)
    if path == "main.py" and flag == "--smoke-backend-imports" and flag not in source:
        pytest.xfail("Legacy Tk main.py has no backend-import smoke option. The packaged Qt entry point implements it.")
    cli(source, flag)
    with pytest.raises(AssertionError, match=flag):
        cli(source.replace(flag, "--removed-option"), flag)


def test_early_readiness_timer_is_detected():
    source = read("qt_app/main.py")
    qml_ready(source)
    tree = ast.parse(source)
    method, = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "main"]
    load, = calls(method, "engine.load")
    ack, = calls(method, "acknowledge_ready")
    callback, = [node for node in ast.walk(method) if isinstance(node, ast.FunctionDef)
                 and node is not method and ack in ast.walk(node)]
    timer, = [node for node in calls(method, "QTimer.singleShot")
              if ast.unparse(node.args[-1]) == callback.name]
    # Move the schedule before loading while retaining the real load and failure path.
    lines = source.splitlines()
    lines[timer.lineno - 1] = " " * timer.col_offset + "pass"
    lines.insert(load.lineno - 1, " " * load.col_offset + ast.unparse(timer))
    with pytest.raises(AssertionError, match="post-QML"):
        qml_ready("\n".join(lines))
