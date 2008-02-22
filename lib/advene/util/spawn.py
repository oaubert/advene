#
# This file is part of Advene.
#
# Advene is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Advene is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Advene; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
"""Process Launcher module.
"""

import os
import signal
import threading

class ProcessLauncher:
    """Process launcher class.

    @ivar program_name: the program name
    @ivar program_path: the program path (directory)
    @ivar pid: the process pid
    @type pid: int
    @ivar args: the program parameters
    @type args: list of strings
    @ivar thread: the launcher thread
    @type thread: threading.Thread
    """
    def __init__ (self, name, args=None, path=None):
        """Create a new ProcessLauncher for a specific program.

        @param name: the program name
        @type name: string
        @param path: the program path (directory)
        @type path: string
        @param args: program parameters
        @type args: list of strings
        """
        self.program_name = name
        if args is None:
            args=[]
        if path is None:
            self.program_path = self.get_absolute_path (name)
        else:
            self.program_path = os.path.join (path, name)
        self.pid = None
        self.args = args
        self.thread = None

    def get_absolute_path (self, program):
        """Return the absolute path for the program.

        Note: this method should be portable.

        @param program: the program name
        @type program: string
        @return: the absolute path
        @rtype: string
        """
        for dir in os.environ['PATH'].split(os.pathsep):
            absolute = os.path.join (dir, self.program_name)
            if os.access (absolute, os.X_OK):
                return absolute
        raise Exception("No %s in path" % program)

    def _start_program (self):
        """Private method used to launch the program."""
        args = (self.program_name, )+ tuple([str(i) for i in self.args])
        # FIXME: we should close all existing sockets
        #print "Launching %s with %s" % (self.program_path, args)
        self.pid = os.spawnv (os.P_NOWAIT, self.program_path, tuple(args))
        try:
            signal.signal(signal.SIGCHLD, self.sigchld)
        except ValueError:
            # FIXME: we should investigate this rather than ignore it.
            pass
        #os.waitpid (self.pid, 0)
        #print "After waitpid"
        return True

    def sigchld(self, sig, stack_frame):
        (pid, status)=os.wait()
        print "Caught child %d" % pid
        return True

    def start (self, args=None):
        """Start the application.

        @param args: parameters (overriding default ones)
        @type args: list of strings
        """
        if self.thread is not None and self.thread.isAlive():
            return True
        if args is not None:
            self.args=args
        #self.thread = threading.Thread (target=self._start_program)
        #self.thread.start ()
        self._start_program()
        return True

    def stop (self):
        """Abruptly terminate the program.

        This should be used as a last way. Use the CORBA exit() method instead.
        """
        os.kill (self.pid, signal.SIGKILL)

    def is_running (self):
        """Return a boolean stating whether the process is alive of not.

        @return: True if the process is alive.
        """
        if self.thread is None:
            return False
        else:
            return self.thread.isAlive()

if __name__ == '__main__':
    args = ('10', )
    l = ProcessLauncher ('sleep', args=args)
    print "l = Launcher(%s)" % l.program_name
