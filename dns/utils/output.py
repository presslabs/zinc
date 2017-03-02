class Output:
    def __init__(self):
        self.destination = None
        self.output = self.to_none

    def use_stdout(self):
        self.output = self.to_stdout

    def use_none(self):
        self.output = self.to_none

    def to_stdout(self, msg, *a, **kwa):
        print(msg.format(*a, **kwa))

    def to_none(self, *a, **kwa):
        pass

    def __call__(self, *a, **kwa):
        self.output(*a, **kwa)

output = Output()
