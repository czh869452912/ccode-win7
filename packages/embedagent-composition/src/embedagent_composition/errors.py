class CompositionError(ValueError):
    def __init__(self, code, message):
        self.code = str(code)
        self.message = str(message)
        super().__init__("%s: %s" % (self.code, self.message))
