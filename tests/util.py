#!/usr/bin/env python
# encoding: utf-8
#
# Copyright © 2014 deanishe@deanishe.net
#
# MIT Licence. See http://opensource.org/licenses/MIT
#
# Created on 2014-08-17
#

"""
Stuff used be multiple tests
"""

from __future__ import print_function, unicode_literals, absolute_import

from cStringIO import StringIO
import sys
import os
import shutil
import subprocess

import workflow
import workflow.workflow
from workflow._env import WorkflowEnvironment

INFO_PLIST_TEST = os.path.join(os.path.abspath(os.path.dirname(__file__)),
                               'data', 'info.plist.test')

INFO_PLIST_PATH = os.path.join(os.path.abspath(os.getcwdu()),
                               'info.plist')

VERSION_PATH = os.path.join(os.path.abspath(os.getcwdu()),
                            'version')

# info.plist settings
# These are the same as in data/info.plist.test
BUNDLE_ID = 'net.deanishe.alfred-workflow'
WORKFLOW_NAME = 'Alfred-Workflow Test'
DATADIR = os.path.expanduser('~/Library/Application Support/Alfred 2/'
                             'Workflow Data/{0}'.format(BUNDLE_ID))
CACHEDIR = os.path.expanduser('~/Library/Caches/com.runningwithcrayons.'
                              'Alfred-2/Workflow Data/{0}'.format(BUNDLE_ID))

# Variables that would be in os.environ if running within Alfred
ALFRED_ENVVARS = {
    b'alfred_preferences':
    os.path.expanduser('~/Dropbox/Alfred/Alfred.alfredpreferences'),
    b'alfred_preferences_localhash':
    b'adbd4f66bc3ae8493832af61a41ee609b20d8705',
    b'alfred_theme': b'alfred.theme.yosemite',
    b'alfred_theme_background': b'rgba(255,255,255,0.98)',
    b'alfred_theme_subtext': b'3',
    b'alfred_version': b'2.4',
    b'alfred_version_build': b'277',
    b'alfred_workflow_bundleid': str(BUNDLE_ID),
    b'alfred_workflow_cache': str(CACHEDIR),
    b'alfred_workflow_data': str(DATADIR),
    b'alfred_workflow_name': b'Alfred-Workflow Test',
    b'alfred_workflow_uid':
    b'user.workflow.B0AC54EC-601C-479A-9428-01F9FD732959',
}


class WorkflowEnv(object):
    """Simulates a valid workflow environment.

    Can be used as a context manager. Individual setup/teardown
    sections can be called manually via the ``set_up_*`` and
    ``tear_down_*`` methods.

    - Creates ``version`` file in CWD (optional)
    - Links  ``data/info.plist.test`` to ``info.plist`` in CWD (default)
    - Overrides ``sys.argv`` (optional)
    - Overrides and registers ``sys.exit`` (default)
    - Overrides and captures ``subprocess.call`` (default)
    - Captures stderr output (optional)
    - Adds Alfred env vars to ``os.environ`` (default)
    - Adds custom vars to ``os.environ`` (optional)
    - Deletes all workflow data (cache, data directories) (default)

    :param version: Version number to set in ``version`` file
    :type version: string
    :param info_plist: Create ``info.plist`` in CWD
    :type info_plist: boolean
    :param argv: Optional ``sys.argv`` replacement
    :type argv: list
    :param exit: Override and capture calls to :func:`sys.exit`
    :type exit: boolean
    :param call: Override and capture calls to :func:`subprocess.call`
    :type call: boolean
    :param stderr: Capture STDERR output
    :type stderr: boolean
    :param env_default: Add default Alfred vars to :data:`os.environ`
    :type env_default: boolean
    :param env: Variables to add to :data:`os.environ`
    :type env: dict
    :param wfreset: Delete workflow data and cache directories
    :type wfreset: boolean

    """

    def __init__(self, version=None, info_plist=True,
                 argv=None, exit=True, call=True, stderr=False,
                 env_default=True, env=None, wfreset=True):

        self.version = version
        self.info_plist = info_plist
        self.ip_path = os.path.join(INFO_PLIST_PATH)
        self.ip_backup = os.path.join(os.getcwdu(),
                                      'info.plist.{0}'.format(os.getpid()))

        self.v_path = os.path.join(os.getcwdu(), 'version')
        self.v_backup = os.path.join(os.getcwdu(),
                                     'version.{0}'.format(os.getpid()))

        # if version and os.path.exists(self.v_path):
        #     raise IOError('Path already exists : {0}'.format(self.v_path))

        # if info_plist and os.path.exists(self.ip_path):
        #     raise IOError('Path already exists : {0}'.format(self.ip_path))

        self.argv = argv
        self.override_exit = exit
        self.exit_called = False
        self.exit_status = None
        self.override_call = call
        self.override_stderr = stderr
        self.env_default = env_default
        self.env = env
        self.wfreset = wfreset
        self.argv_orig = None
        self.call_orig = None
        self.exit_orig = None
        self.stderr_orig = None
        self.env_orig = None
        self.cmd = ()
        self.args = []
        self.kwargs = {}
        self.stderr = ''

    def __enter__(self):
        self.set_up()
        return self

    def __exit__(self, *args):
        self.tear_down()

    def set_up_osenv(self):
        """Set up environmental variables

        Add :data:`ALFRED_ENVVARS` and/or :attr:`env` to
        :data:`os.environ` where it will be picked up by
        :class:`~workflow._env.WorkflowEnvironment`

        """

        # Set up environmental variables
        # Clean up to start with
        for k in ALFRED_ENVVARS:
            if k in os.environ:
                del os.environ[k]
        d = {}
        if self.env_default:
            d.update(ALFRED_ENVVARS)
        if self.env:
            d.update(self.env)
        if d:
            for k, v in d.items():
                os.environ[k] = v

    def tear_down_osenv(self):
        """Remove any added environmental variables"""
        for k in ALFRED_ENVVARS:
            if k in os.environ:
                del os.environ[k]
        if self.env:
            for k in self.env:
                if k in os.environ:
                    del os.environ[k]

    def set_up_files(self):
        """Create ``info.plist`` and ``version`` files in CWD"""
        # Move existing files
        if os.path.exists(self.ip_path):
            os.rename(self.ip_path, self.ip_backup)
        if os.path.exists(self.v_path):
            os.rename(self.v_path, self.v_backup)

        if self.version is not None:
            # assert not os.path.exists(self.v_path)
            with open(self.v_path, 'wb') as fp:
                fp.write(str(self.version))

        if self.info_plist:
            # assert not os.path.exists(self.ip_path)
            if not os.path.exists(self.ip_path):
                os.symlink(INFO_PLIST_TEST, self.ip_path)

    def tear_down_files(self):
        """Remove ``info.plist`` and ``version`` files from CWD"""
        # Remove temporary files
        if self.info_plist:
            os.unlink(self.ip_path)
        if self.version:
            os.unlink(self.v_path)

        # Restore backups
        if os.path.exists(self.v_backup):
            os.rename(self.v_backup, self.v_path)
        if os.path.exists(self.ip_backup):
            os.rename(self.ip_backup, self.ip_path)

    def set_up_env(self):
        """Override :mod:`~workflow.env`

        Replace :mod:`~workflow.env` with pristine
        :class:`~workflow._env.WorkflowEnvironment`.

        """

        # workflow.env module
        self.env_orig = workflow.env
        workflow.env = WorkflowEnvironment()
        workflow.workflow.env = workflow.env

    def tear_down_env(self):
        """Restore :mod:`~workflow.env`"""
        # Restore workflow.env module
        if self.env_orig is not None:
            workflow.env = self.env_orig
            workflow.workflow.env = self.env_orig

    def set_up_libs(self):
        """Monkey-patch other libraries

        - :data:`sys.argv`
        - :attr:`sys.stderr`
        - :func:`sys.exit`
        - :func:`subprocess.call`

        """

        # Monkey-patch other libraries
        if self.override_call:
            self.call_orig = subprocess.call
            subprocess.call = self._call

        if self.override_exit:
            self.exit_orig = sys.exit
            sys.exit = self._exit

        if self.argv:
            self.argv_orig = sys.argv[:]
            sys.argv = self.argv[:]

        if self.override_stderr:
            self.stderr_orig = sys.stderr
            sys.stderr = StringIO()

    def tear_down_libs(self):
        """Revert monkey-patches"""
        # Restore other modules
        if self.call_orig:
            subprocess.call = self.call_orig

        if self.exit_orig:
            sys.exit = self.exit_orig

        if self.argv_orig:
            sys.argv = self.argv_orig[:]

        if self.stderr_orig:
            self.stderr = sys.stderr.getvalue()
            sys.stderr.close()
            sys.stderr = self.stderr_orig

    def tear_down_reset(self):
        """Delete workflow cache and data directories"""
        # Delete all workflow data and caches
        for dirpath in (DATADIR, CACHEDIR):
            if os.path.exists(dirpath):
                shutil.rmtree(dirpath)

    def set_up(self):
        """Call all other set_up_* methods"""
        self.set_up_osenv()
        self.set_up_files()
        self.set_up_env()
        # Other python libs
        self.set_up_libs()

    def tear_down(self):
        """Call all other tear_down_* methods"""
        # Restore os.environ
        self.tear_down_osenv()
        # Delete files
        self.tear_down_files()
        self.tear_down_env()
        self.tear_down_libs()

        # Delete data, cache and settings
        if self.wfreset:
            self.tear_down_reset()

    def _exit(self, status=0):
        """Temporary replacement for :func:`sys.exit`"""
        self.exit_called = True
        self.exit_status = status
        return

    def _call(self, cmd, *args, **kwargs):
        """Temporary replacement for :func:`subprocess.call`"""
        self.cmd = cmd
        self.args = args
        self.kwargs = kwargs


class WorkflowMock(object):
    """Context manager that overrides funcs and variables for testing

    c = WorkflowMock()
    with c:
        subprocess.call([arg1, arg2])
    c.cmd -> (arg1, arg2)

    """

    def __init__(self, argv=None, exit=True, call=True, stderr=False):
        """Context manager that overrides funcs and variables for testing

        :param argv: list of arguments to replace ``sys.argv`` with
        :type argv: list
        :param exit: Override ``sys.exit`` with noop?
        :param call: Override :func:`subprocess.call` and capture its
            arguments in :attr:`cmd`, :attr:`args` and :attr:`kwargs`?

        """

        self.argv = argv
        self.override_exit = exit
        self.override_call = call
        self.override_stderr = stderr
        self.argv_orig = None
        self.call_orig = None
        self.exit_orig = None
        self.stderr_orig = None
        self.cmd = ()
        self.args = []
        self.kwargs = {}
        self.stderr = ''

    def _exit(self, status=0):
        return

    def _call(self, cmd, *args, **kwargs):
        self.cmd = cmd
        self.args = args
        self.kwargs = kwargs

    def __enter__(self):
        if self.override_call:
            self.call_orig = subprocess.call
            subprocess.call = self._call

        if self.override_exit:
            self.exit_orig = sys.exit
            sys.exit = self._exit

        if self.argv:
            self.argv_orig = sys.argv[:]
            sys.argv = self.argv[:]

        if self.override_stderr:
            self.stderr_orig = sys.stderr
            sys.stderr = StringIO()

    def __exit__(self, *args):
        if self.call_orig:
            subprocess.call = self.call_orig

        if self.exit_orig:
            sys.exit = self.exit_orig

        if self.argv_orig:
            sys.argv = self.argv_orig[:]

        if self.stderr_orig:
            self.stderr = sys.stderr.getvalue()
            sys.stderr.close()
            sys.stderr = self.stderr_orig

# class VersionFile(object):
#     """Context manager to create and delete `version` file"""

#     def __init__(self, version, path=None):

#         self.version = version
#         self.path = path or VERSION_PATH

#     def __enter__(self):
#         with open(self.path, 'wb') as fp:
#             fp.write(self.version)
#         print('version {0} in {1}'.format(self.version, self.path),
#               file=sys.stderr)

#     def __exit__(self, *args):
#         if os.path.exists(self.path):
#             os.unlink(self.path)


# class InfoPlist(object):
#     """Context manager to create and delete `info.plist` out of the way"""

#     def __init__(self, path=None, dest_path=None, present=True):

#         self.path = path or INFO_PLIST_TEST
#         self.dest_path = dest_path or INFO_PLIST_PATH
#         # Whether or not Info.plist should be created or deleted
#         self.present = present

#     def __enter__(self):
#         if self.present:
#             create_info_plist(self.path, self.dest_path)
#         else:
#             delete_info_plist(self.dest_path)

#     def __exit__(self, *args):
#         if self.present:
#             delete_info_plist(self.dest_path)


def create_info_plist(source=INFO_PLIST_TEST, dest=INFO_PLIST_PATH):
    if os.path.exists(source) and not os.path.exists(dest):
        os.symlink(source, dest)


def delete_info_plist(path=INFO_PLIST_PATH):
    if os.path.exists(path) and os.path.islink(path):
        os.unlink(path)