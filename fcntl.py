# Windows compatibility stub for Unix fcntl module.
# pytest-homeassistant-custom-component imports homeassistant.runner which
# uses fcntl only for process-level file locking — not needed during tests.
LOCK_EX = 2
LOCK_NB = 4
LOCK_SH = 1
LOCK_UN = 8


def flock(fd, operation):  # noqa: ARG001
    return 0


def fcntl(fd, cmd, arg=0):  # noqa: ARG001
    return 0


def ioctl(fd, request, arg=0, mutate_flag=True):  # noqa: ARG001
    return 0
