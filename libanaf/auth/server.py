import logging
import threading
from queue import Queue

from werkzeug.serving import make_server
from werkzeug.wrappers import Request, Response

logger = logging.getLogger(__name__)


class OAuthCallbackServer:
    def __init__(
        self,
        host: str = "localhost",
        port: int = 8000,
        use_ssl: bool = True,
        cert_file: str | None = None,
        key_file: str | None = None,
    ):
        """Initialize an auth callback server.

        Args:
            host: Hostname to bind to. Defaults to "localhost".
            port: Port number to bind to. Defaults to 8000.
            use_ssl: Whether to enable TLS/SSL. Defaults to True.
            cert_file: Path to the TLS certificate file when `use_ssl` is True.
            key_file: Path to the TLS private key file when `use_ssl` is True.

        Raises:
            RuntimeError: If `use_ssl` is True and either `cert_file` or `key_file` is not provided.
        """
        self.host = host
        self.port = port
        self.use_ssl = use_ssl

        if self.use_ssl and (cert_file is None or key_file is None):
            raise RuntimeError("When SSL is enabled, certificate file and key file are mandatory")

        self.cert_file = cert_file
        self.key_file = key_file

    def get_auth_response(self):
        """Block until ANAF redirects to the local callback and return the query parameters.

        Starts a lightweight Werkzeug HTTP server in a background thread,
        waits for a single request (the OAuth redirect), shuts the server
        down, and returns the query-string parameters from that request.

        Returns:
            ImmutableMultiDict: Query parameters from the ANAF redirect; contains
                ``"code"`` on success or ``"error"`` on denial.
        """
        q = Queue()

        @Request.application
        def code_request(request: Request):
            """Handle the redirect from ANAF with the authorization result."""
            logger.debug(request)
            logger.debug(f"request.headers = {request.headers}")
            logger.debug(f"request.args = {request.args}")

            q.put(request.args)

            if "error" in request.args:
                logger.error(f"Error received: {request.args['error']}")
                return Response(f"Error occured: {request.args['error']}", mimetype="text/plain")
            elif "code" in request.args:
                logger.debug(f"Auth code: {request.args['code']}")
                return Response(
                    f"Authorization code received: {request.args['code']}",
                    mimetype="text/plain",
                )

        logger.debug(f"Starting server on {self.host}:{self.port}, SSL={self.use_ssl}")
        if self.use_ssl:
            self.server = make_server(
                self.host,
                self.port,
                code_request,
                ssl_context=(self.cert_file, self.key_file),
            )
        else:
            self.server = make_server(self.host, self.port, code_request)

        t = threading.Thread(target=self.server.serve_forever)
        t.start()
        response = q.get(block=True)

        logger.debug("Shutting down the temporary web server ...")
        self.server.shutdown()
        t.join()

        return response
