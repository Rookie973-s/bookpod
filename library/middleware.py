class SeoHeadersMiddleware:
    """Keep JSON API responses and the admin out of search results (pages themselves stay indexable)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith("/api/"):
            response["X-Robots-Tag"] = "noindex"
        elif request.path.startswith("/admin/"):
            response["X-Robots-Tag"] = "noindex, nofollow"
        return response
