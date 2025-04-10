""" An extension to the Thread class which allows a thread to return
a value which can be captured by the join() call.
Start a thread with th=ThreadWithReturn(target=func, args=(a,b,))
th.start() and capture the return code with rc=th.join().
See the example in the test function.
"""

from threading import Thread
import time


# =====================================================================
# Allow a thread to return a value. Use like this:
# thr = ThreadWithReturn(target=my_func, args=(None,))
# thr.start()
# rc = thr.join()
class ThreadWithReturn(Thread):
    """ A Thread class which returns a value.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._return = None

    def run(self):
        """ Starts the thread running """
        target = getattr(self, '_target')
        if target is not None:
            self._return = target(
                *getattr(self, '_args'),
                **getattr(self, '_kwargs')
            )

    def join(self, *args, **kwargs):
        """ Waits for the thread to terminate then returns its returned value """
        super().join(*args, **kwargs)
        return self._return


# =====================================================================

def thread1(delay):
    """ A simple thread which sleeps then returns its delay """
    print('thread sleeping for %d' % delay)
    time.sleep(delay)
    return delay

def test_ThreadWithReturn():
    """ Test ThreadWithReturn """
    thr1 = ThreadWithReturn(target = thread1, args=(2,))
    thr2 = ThreadWithReturn(target = thread1, args=(3,))
    thr1.start()
    thr2.start()
    rc1 = thr1.join()
    rc2 = thr2.join()
    assert(rc1 == 2)
    assert(rc2 == 3)

# =====================================================================
