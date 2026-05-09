# Windows stub for Unix resource module.
# homeassistant.util.resource uses this only for fd limit tuning on Linux.
RLIMIT_NOFILE = 7
RLIM_INFINITY = -1


class struct_rlimit:
    def __init__(self, cur=0, max=0):
        self.rlim_cur = cur
        self.rlim_max = max


def getrlimit(resource):  # noqa: ARG001
    return struct_rlimit(1024, 65536)


def setrlimit(resource, limits):  # noqa: ARG001
    pass
