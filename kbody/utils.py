# coding=utf-8
"""
Some utility functions.
"""

from __future__ import print_function, absolute_import

from os import getpid
from sys import platform
from subprocess import Popen, PIPE
from sys import version_info

__author__ = 'Xin Chen'
__email__ = 'Bismarrck@me.com'


def get_xargs(pid=None):
  """
  Return the build and execute command lines from standard input for a process. 
  This is a wrapper of the linux command `xargs -0 <`. maxOS and Win 
  are not supported.
  
  Args:
    pid: an `int` as the target process. 
  
  Returns:
    exe_args: a `str` as the execute command line for process `pid` or None.

  """
  if platform != "linux":
    return None

  if not pid:
    pid = getpid()

  p = Popen("xargs -0 < /proc/{}/cmdline".format(pid), stdout=PIPE, stderr=PIPE,
            shell=True)
  try:
    (stdout, stderr) = p.communicate()
  except Exception:
    return None
  if len(stderr) > 0:
    return None
  elif version_info > (3, 0):
    return bytes(stdout).decode("utf-8")
  else:
    return stdout
