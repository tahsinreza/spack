# Copyright 2013-2023 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)
import os
import shutil
import sys

import pytest

import llnl.util.filesystem as fs

import spack.environment as ev
import spack.spec
from spack.main import SpackCommand

develop = SpackCommand("develop")
env = SpackCommand("env")

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="does not run on windows")


@pytest.mark.usefixtures("mutable_mock_env_path", "mock_packages", "mock_fetch", "config")
class TestDevelop(object):
    def check_develop(self, env, spec, path=None):
        path = path or spec.name

        # check in memory representation
        assert spec.name in env.dev_specs
        dev_specs_entry = env.dev_specs[spec.name]
        assert dev_specs_entry["path"] == path
        assert dev_specs_entry["spec"] == str(spec)

        # check yaml representation
        yaml = env.manifest[ev.TOP_LEVEL_KEY]
        assert spec.name in yaml["develop"]
        yaml_entry = yaml["develop"][spec.name]
        assert yaml_entry["spec"] == str(spec)
        if path == spec.name:
            # default paths aren't written out
            assert "path" not in yaml_entry
        else:
            assert yaml_entry["path"] == path

    def test_develop_no_path_no_clone(self):
        env("create", "test")
        with ev.read("test") as e:
            # develop checks that the path exists
            fs.mkdirp(os.path.join(e.path, "mpich"))
            develop("--no-clone", "mpich@1.0")
            self.check_develop(e, spack.spec.Spec("mpich@=1.0"))

    def test_develop_no_clone(self, tmpdir):
        env("create", "test")
        with ev.read("test") as e:
            develop("--no-clone", "-p", str(tmpdir), "mpich@1.0")
            self.check_develop(e, spack.spec.Spec("mpich@=1.0"), str(tmpdir))

    def test_develop(self):
        env("create", "test")
        with ev.read("test") as e:
            develop("mpich@1.0")
            self.check_develop(e, spack.spec.Spec("mpich@=1.0"))

    def test_develop_no_args(self):
        env("create", "test")
        with ev.read("test") as e:
            # develop and remove it
            develop("mpich@1.0")
            shutil.rmtree(os.path.join(e.path, "mpich"))

            # test develop with no args
            develop()
            self.check_develop(e, spack.spec.Spec("mpich@=1.0"))

    def test_develop_twice(self):
        env("create", "test")
        with ev.read("test") as e:
            develop("mpich@1.0")
            self.check_develop(e, spack.spec.Spec("mpich@=1.0"))

            develop("mpich@1.0")
            # disk representation isn't updated unless we write
            # second develop command doesn't change it, so we don't write
            # but we check disk representation
            e.write()
            self.check_develop(e, spack.spec.Spec("mpich@=1.0"))
            assert len(e.dev_specs) == 1

    def test_develop_update_path(self, tmpdir):
        env("create", "test")
        with ev.read("test") as e:
            develop("mpich@1.0")
            develop("-p", str(tmpdir), "mpich@1.0")
            self.check_develop(e, spack.spec.Spec("mpich@=1.0"), str(tmpdir))
            assert len(e.dev_specs) == 1

    def test_develop_update_spec(self):
        env("create", "test")
        with ev.read("test") as e:
            develop("mpich@1.0")
            develop("mpich@2.0")
            self.check_develop(e, spack.spec.Spec("mpich@=2.0"))
            assert len(e.dev_specs) == 1

    def test_develop_canonicalize_path(self, monkeypatch, config):
        env("create", "test")
        with ev.read("test") as e:
            path = "../$user"
            abspath = spack.util.path.canonicalize_path(path, e.path)

            def check_path(stage, dest):
                assert dest == abspath

            monkeypatch.setattr(spack.stage.Stage, "steal_source", check_path)

            develop("-p", path, "mpich@1.0")
            self.check_develop(e, spack.spec.Spec("mpich@=1.0"), path)

            # Check modifications actually worked
            assert spack.spec.Spec("mpich@1.0").concretized().satisfies("dev_path=%s" % abspath)

    def test_develop_canonicalize_path_no_args(self, monkeypatch, config):
        env("create", "test")
        with ev.read("test") as e:
            path = "$user"
            abspath = spack.util.path.canonicalize_path(path, e.path)

            def check_path(stage, dest):
                assert dest == abspath

            monkeypatch.setattr(spack.stage.Stage, "steal_source", check_path)

            # Defensive check to ensure canonicalization failures don't pollute FS
            assert abspath.startswith(e.path)

            # Create path to allow develop to modify env
            fs.mkdirp(abspath)
            develop("--no-clone", "-p", path, "mpich@1.0")

            # Remove path to ensure develop with no args runs staging code
            os.rmdir(abspath)

            develop()
            self.check_develop(e, spack.spec.Spec("mpich@=1.0"), path)

            # Check modifications actually worked
            assert spack.spec.Spec("mpich@1.0").concretized().satisfies("dev_path=%s" % abspath)
