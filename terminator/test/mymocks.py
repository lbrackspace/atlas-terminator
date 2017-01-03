import json

class MockResponse(object):
    def __init__(self, obj, status_code):
        self.text = json.dumps(obj)
        self.status_code = status_code

    def __str__(self):
        return "{text=%s, status_code%d}" % (self.text, self.status_code)

    def __repr__(self):
        return self.__str__()
