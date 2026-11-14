import orjson
from ninja.parser import Parser
from ninja.renderers import BaseRenderer


class OrjsonParser(Parser):
    def parse_body(self, request):
        return orjson.loads(request.body)


class OrjsonRenderer(BaseRenderer):
    media_type = "application/json"

    def render(self, request, data, *, response_status):
        return orjson.dumps(data, option=orjson.OPT_NON_STR_KEYS)
