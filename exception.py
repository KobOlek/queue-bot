class DatabaseException(Exception):
    """ Common base class for all non-exit exceptions. """
    def __init__(self, message="Database Error: bad query"):
        self.message = message
        super().__init__(self.message)