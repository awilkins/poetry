from typing import Set

import pytest

from poetry.inspection.info import PackageInfo
from poetry.inspection.info import PackageInfoError
from poetry.utils._compat import PY35
from poetry.utils._compat import CalledProcessError
from poetry.utils._compat import Path
from poetry.utils._compat import decode
from poetry.utils.env import EnvCommandError
from poetry.utils.env import VirtualEnv


FIXTURE_DIR_BASE = Path(__file__).parent.parent / "fixtures"
FIXTURE_DIR_INSPECTIONS = FIXTURE_DIR_BASE / "inspection"


@pytest.fixture(autouse=True)
def pep517_metadata_mock():
    pass


@pytest.fixture
def demo_sdist():  # type: () -> Path
    return FIXTURE_DIR_BASE / "distributions" / "demo-0.1.0.tar.gz"


@pytest.fixture
def demo_wheel():  # type: () -> Path
    return FIXTURE_DIR_BASE / "distributions" / "demo-0.1.0-py2.py3-none-any.whl"


@pytest.fixture
def source_dir(tmp_path):  # type: (Path) -> Path
    yield Path(tmp_path.as_posix())


@pytest.fixture
def demo_setup(source_dir):  # type: (Path) -> Path
    setup_py = source_dir / "setup.py"
    setup_py.write_text(
        decode(
            "from setuptools import setup; "
            'setup(name="demo", '
            'version="0.1.0", '
            'install_requires=["package"])'
        )
    )
    yield source_dir


@pytest.fixture
def demo_setup_cfg(source_dir):  # type: (Path) -> Path
    setup_cfg = source_dir / "setup.cfg"
    setup_cfg.write_text(
        decode(
            "\n".join(
                [
                    "[metadata]",
                    "name = demo",
                    "version = 0.1.0",
                    "[options]",
                    "install_requires = package",
                ]
            )
        )
    )
    yield source_dir


@pytest.fixture
def demo_setup_complex(source_dir):  # type: (Path) -> Path
    setup_py = source_dir / "setup.py"
    setup_py.write_text(
        decode(
            "from setuptools import setup; "
            'setup(name="demo", '
            'version="0.1.0", '
            'install_requires=[i for i in ["package"]])'
        )
    )
    yield source_dir


@pytest.fixture
def demo_setup_complex_pep517_legacy(demo_setup_complex):  # type: (Path) -> Path
    pyproject_toml = demo_setup_complex / "pyproject.toml"
    pyproject_toml.write_text(
        decode("[build-system]\n" 'requires = ["setuptools", "wheel"]')
    )
    yield demo_setup_complex


def demo_check_info(info, requires_dist=None):  # type: (PackageInfo, Set[str]) -> None
    assert info.name == "demo"
    assert info.version == "0.1.0"
    assert info.requires_dist

    requires_dist = requires_dist or {
        'cleo; extra == "foo"',
        "pendulum (>=1.4.4)",
        'tomlkit; extra == "bar"',
    }
    assert set(info.requires_dist) == requires_dist


def test_info_from_sdist(demo_sdist):
    info = PackageInfo.from_sdist(demo_sdist)
    demo_check_info(info)


def test_info_from_wheel(demo_wheel):
    info = PackageInfo.from_wheel(demo_wheel)
    demo_check_info(info)


def test_info_from_bdist(demo_wheel):
    info = PackageInfo.from_bdist(demo_wheel)
    demo_check_info(info)


def test_info_from_poetry_directory():
    info = PackageInfo.from_directory(FIXTURE_DIR_INSPECTIONS / "demo")
    demo_check_info(info)


def test_info_from_requires_txt():
    info = PackageInfo.from_metadata(
        FIXTURE_DIR_INSPECTIONS / "demo_only_requires_txt.egg-info"
    )
    demo_check_info(info)


@pytest.mark.skipif(not PY35, reason="Parsing of setup.py is skipped for Python < 3.5")
def test_info_from_setup_py(demo_setup):
    info = PackageInfo.from_setup_files(demo_setup)
    demo_check_info(info, requires_dist={"package"})


@pytest.mark.skipif(not PY35, reason="Parsing of setup.cfg is skipped for Python < 3.5")
def test_info_from_setup_cfg(demo_setup_cfg):
    info = PackageInfo.from_setup_files(demo_setup_cfg)
    demo_check_info(info, requires_dist={"package"})


def test_info_no_setup_pkg_info_no_deps():
    info = PackageInfo.from_directory(
        FIXTURE_DIR_INSPECTIONS / "demo_no_setup_pkg_info_no_deps"
    )
    assert info.name == "demo"
    assert info.version == "0.1.0"
    assert info.requires_dist is None


@pytest.mark.skipif(not PY35, reason="Parsing of setup.py is skipped for Python < 3.5")
def test_info_setup_simple(mocker, demo_setup):
    spy = mocker.spy(VirtualEnv, "run")
    info = PackageInfo.from_directory(demo_setup, allow_build=True)
    assert spy.call_count == 0
    demo_check_info(info, requires_dist={"package"})


@pytest.mark.skipif(
    PY35,
    reason="For projects with setup.py using Python < 3.5 fallback to pep517 build",
)
def test_info_setup_simple_py2(mocker, demo_setup):
    spy = mocker.spy(VirtualEnv, "run")
    info = PackageInfo.from_directory(demo_setup, allow_build=True)
    assert spy.call_count == 2
    demo_check_info(info, requires_dist={"package"})


@pytest.mark.skipif(not PY35, reason="Parsing of setup.cfg is skipped for Python < 3.5")
def test_info_setup_cfg(mocker, demo_setup_cfg):
    spy = mocker.spy(VirtualEnv, "run")
    info = PackageInfo.from_directory(demo_setup_cfg, allow_build=True)
    assert spy.call_count == 0
    demo_check_info(info, requires_dist={"package"})


def test_info_setup_complex(demo_setup_complex):
    info = PackageInfo.from_directory(demo_setup_complex, allow_build=True)
    demo_check_info(info, requires_dist={"package"})


def test_info_setup_complex_pep517_error(mocker, demo_setup_complex):
    mocker.patch(
        "poetry.utils.env.VirtualEnv.run",
        auto_spec=True,
        side_effect=EnvCommandError(CalledProcessError(1, "mock", output="mock")),
    )

    with pytest.raises(PackageInfoError):
        PackageInfo.from_directory(demo_setup_complex, allow_build=True)


def test_info_setup_complex_pep517_legacy(demo_setup_complex_pep517_legacy):
    info = PackageInfo.from_directory(
        demo_setup_complex_pep517_legacy, allow_build=True
    )
    demo_check_info(info, requires_dist={"package"})


@pytest.mark.skipif(not PY35, reason="Parsing of setup.py is skipped for Python < 3.5")
def test_info_setup_complex_disable_build(mocker, demo_setup_complex):
    spy = mocker.spy(VirtualEnv, "run")
    info = PackageInfo.from_directory(demo_setup_complex, allow_build=False)
    assert spy.call_count == 0
    assert info.name == "demo"
    assert info.version == "0.1.0"
    assert info.requires_dist is None