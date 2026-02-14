# TODO:
# This file contains tests for the OAuth2 authorization code flow, simulating a client
# interacting with the authorization server.
#
# The tests will cover the following scenarios:
#
# 1. A client initiates the authorization flow by making a request to /oauth/authorize
# with valid parameters, and receives an authorization code.
#
# 2. The client then exchanges the authorization code for an access token by making a
# POST request to /oauth/token with the correct parameters, and receives an access token
# in response.
#
# 3. The tests will also cover error cases, such as missing or invalid parameters,
# expired or already-used authorization codes, and invalid client credentials.
#
# Note: Since we are not running a real client server, we will simulate the client's
# behavior by making direct requests to the FastAPI app using the TestClient. We will
# not be testing real browser redirects, but we will ensure that the correct responses
# are returned at each step of the flow.
#
# The typical flow we want to test is:
# •	redirects the user to /oauth/authorize
# •	receives code on its redirect URI
# •	POSTs to /oauth/token
#
# These tests act as the OAuth client by:
# 	1.	Calling GET /oauth/authorize with query params
# 	2.	Observing the 302 redirect and extracting code from the Location header
# 	3.	Calling POST /oauth/token with the code + code_verifier
# 	4.	Asserting token issuance / failures
# TODO: Future - test real browser redirects end-to-end, explore client server
# testing options (e.g. Selenium, Playwright) if needed.
